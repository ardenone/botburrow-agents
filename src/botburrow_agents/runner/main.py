"""Runner service main module.

The runner:
1. Claims work from work queue (BRPOP for efficient waiting)
2. Loads agent config from R2 (with cache support)
3. Executes agent activations in sandbox
4. Reports results and metrics
5. Integrates with circuit breaker for failing agents
"""

from __future__ import annotations

import asyncio
import os
import signal
import time
from typing import Any

import click
import structlog

from botburrow_agents.clients.hub import HubClient
from botburrow_agents.clients.r2 import R2Client
from botburrow_agents.clients.redis import RedisClient
from botburrow_agents.config import ActivationMode, Settings, get_settings
from botburrow_agents.coordinator.assigner import Assigner
from botburrow_agents.coordinator.scheduler import Scheduler
from botburrow_agents.coordinator.work_queue import ConfigCache, WorkItem, WorkQueue
from botburrow_agents.executors import get_executor
from botburrow_agents.models import (
    ActivationResult,
    AgentConfig,
    Assignment,
    TaskType,
)
from botburrow_agents.observability import (
    MetricsServer,
    record_activation_complete,
    record_activation_start,
    record_tokens,
    set_runner_heartbeat,
    set_runner_info,
)
from botburrow_agents.runner.context import ContextBuilder
from botburrow_agents.runner.loop import AgentLoop
from botburrow_agents.runner.metrics import BudgetChecker, MetricsReporter
from botburrow_agents.runner.sandbox import Sandbox

logger = structlog.get_logger(__name__)


class Runner:
    """Agent runner service.

    Responsibilities:
    - Claim work from Redis work queue (BRPOP for efficient blocking)
    - Load agent configurations from R2 (with caching)
    - Execute agent activations in sandboxed environment
    - Report results and metrics to Hub
    - Integrate with circuit breaker for repeated failures
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.hub = HubClient(self.settings)
        self.r2 = R2Client(self.settings)
        self.redis = RedisClient(self.settings)

        # Scheduler and assigner for backward compatibility
        self.scheduler = Scheduler(self.hub, self.redis, self.settings)
        self.assigner = Assigner(self.hub, self.redis, self.settings)

        # Scalability components
        self.work_queue: WorkQueue | None = None
        self.config_cache: ConfigCache | None = None

        self.metrics = MetricsReporter(self.hub, self.settings)
        self.budget_checker = BudgetChecker(self.hub, self.settings)
        self.context_builder = ContextBuilder(self.hub, self.r2)

        # Runner identity
        self.runner_id = self.settings.runner_id or os.environ.get(
            "HOSTNAME", f"runner-{os.getpid()}"
        )

        # Observability
        self.metrics_server = MetricsServer(port=9091)  # Different port from coordinator

        self._running = False
        self._shutdown_event = asyncio.Event()
        self._current_activation: str | None = None
        self._current_work: WorkItem | None = None

    async def start(self) -> None:
        """Start the runner service."""
        logger.info(
            "runner_starting",
            runner_id=self.runner_id,
            mode=self.settings.runner_mode.value,
        )

        # Connect to Redis
        await self.redis.connect()

        # Initialize scalability components
        self.work_queue = WorkQueue(self.redis, self.settings)
        self.config_cache = ConfigCache(self.redis)

        # Start metrics server and set runner info
        await self.metrics_server.start()
        set_runner_info(self.runner_id, self.settings.runner_mode.value)

        self._running = True

        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_shutdown)

        # Start background tasks
        tasks = [
            asyncio.create_task(self._work_loop()),
            asyncio.create_task(self._heartbeat_loop()),
        ]

        logger.info("runner_started", runner_id=self.runner_id)

        # Wait for shutdown
        await self._shutdown_event.wait()

        # Cancel tasks
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        # Cleanup
        await self.metrics.flush()
        await self.metrics_server.stop()
        await self.hub.close()
        await self.redis.close()

        logger.info("runner_stopped", runner_id=self.runner_id)

    def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        logger.info("runner_shutdown_requested", runner_id=self.runner_id)
        self._running = False
        self._shutdown_event.set()

    async def _work_loop(self) -> None:
        """Main work loop using WorkQueue.

        Uses BRPOP for efficient blocking wait, priority-based work claiming,
        and integrated circuit breaker for failing agents.
        """
        while self._running:
            try:
                # Claim work from queue (blocks up to 30 seconds)
                if self.work_queue:
                    work = await self.work_queue.claim(
                        runner_id=self.runner_id,
                        timeout=30,
                    )
                else:
                    work = None

                if work:
                    self._current_work = work
                    logger.info(
                        "work_claimed",
                        agent_id=work.agent_id,
                        task_type=work.task_type.value,
                        priority=work.priority,
                    )

                    # Convert WorkItem to Assignment for backward compatibility
                    assignment = Assignment(
                        agent_id=work.agent_id,
                        agent_name=work.agent_name,
                        task_type=work.task_type,
                        inbox_count=work.inbox_count,
                    )

                    # Execute activation
                    result = await self._activate_agent(assignment)

                    # Mark work complete with success/failure for circuit breaker
                    if self.work_queue:
                        await self.work_queue.complete(work, success=result.success)

                    # Release lock and report result
                    await self.assigner.release(
                        assignment.agent_id,
                        self.runner_id,
                        result,
                    )

                    # Flush metrics
                    await self.metrics.flush()
                    self._current_work = None

                # If no work from queue, try fallback to scheduler (backward compat)
                elif not self.work_queue:
                    fallback_assignment = await self.scheduler.get_next_assignment(
                        self.settings.runner_mode
                    )
                    if fallback_assignment:
                        if await self.assigner.try_claim(fallback_assignment, self.runner_id):
                            result = await self._activate_agent(fallback_assignment)
                            await self.assigner.release(
                                fallback_assignment.agent_id,
                                self.runner_id,
                                result,
                            )
                            await self.metrics.flush()
                    else:
                        await asyncio.sleep(5)

            except Exception as e:
                logger.error("work_loop_error", error=str(e))
                # Mark current work as failed if we have it
                if self._current_work and self.work_queue:
                    await self.work_queue.complete(self._current_work, success=False)
                    self._current_work = None
                await asyncio.sleep(10)

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats."""
        while self._running:
            try:
                status = "busy" if self._current_activation else "idle"
                await self.assigner.heartbeat(self.runner_id, status)
                # Update Prometheus heartbeat metric
                set_runner_heartbeat(self.runner_id)
            except Exception as e:
                logger.warning("heartbeat_error", error=str(e))

            await asyncio.sleep(10)

    async def _load_agent_config(self, agent_id: str) -> AgentConfig:
        """Load agent config with caching.

        Args:
            agent_id: Agent ID to load

        Returns:
            AgentConfig from cache or R2
        """
        # Try cache first
        if self.config_cache:
            cached = await self.config_cache.get(agent_id)
            if cached:
                logger.debug("agent_config_cache_hit", agent_id=agent_id)
                return AgentConfig(**cached)

        # Load from R2
        agent = await self.r2.load_agent_config(agent_id)

        # Cache for next time
        if self.config_cache:
            await self.config_cache.set(agent_id, agent.model_dump())

        logger.debug("agent_config_loaded", agent_id=agent_id)
        return agent

    async def _activate_agent(self, assignment: Assignment) -> ActivationResult:
        """Execute a single agent activation.

        Args:
            assignment: Work assignment with agent and task info

        Returns:
            ActivationResult with success/failure and metrics
        """
        start_time = time.time()
        self._current_activation = assignment.agent_id

        # Record activation start for Prometheus
        record_activation_start(self.runner_id)

        logger.info(
            "activation_starting",
            agent_id=assignment.agent_id,
            agent_name=assignment.agent_name,
            task_type=assignment.task_type.value,
        )

        try:
            # 1. Check budget
            can_proceed, reason = await self.budget_checker.check_budget(
                assignment.agent_id
            )
            if not can_proceed:
                duration = time.time() - start_time
                # Record failed activation
                record_activation_complete(
                    agent_id=assignment.agent_id,
                    task_type=assignment.task_type.value,
                    success=False,
                    duration_seconds=duration,
                    runner_id=self.runner_id,
                )
                return ActivationResult(
                    agent_id=assignment.agent_id,
                    agent_name=assignment.agent_name,
                    success=False,
                    error=reason,
                    duration_seconds=duration,
                )

            # 2. Load agent config (with caching)
            agent = await self._load_agent_config(assignment.agent_id)

            # 3. Start sandbox
            sandbox = Sandbox(agent, self.settings)
            await sandbox.start()

            try:
                # 4. Execute based on task type
                if assignment.task_type == TaskType.INBOX:
                    result = await self._process_inbox(agent, sandbox)
                else:
                    result = await self._run_exploration(agent, sandbox)

                duration = time.time() - start_time

                # 5. Record metrics (Hub)
                self.metrics.record_usage(
                    agent_id=agent.name,
                    model=agent.brain.model,
                    tokens_input=result.get("tokens_input", 0),
                    tokens_output=result.get("tokens_output", 0),
                    duration_seconds=duration,
                )

                # Record Prometheus metrics
                record_activation_complete(
                    agent_id=assignment.agent_id,
                    task_type=assignment.task_type.value,
                    success=True,
                    duration_seconds=duration,
                    runner_id=self.runner_id,
                )
                record_tokens(
                    agent_id=assignment.agent_id,
                    model=agent.brain.model,
                    tokens_input=result.get("tokens_input", 0),
                    tokens_output=result.get("tokens_output", 0),
                )

                return ActivationResult(
                    agent_id=assignment.agent_id,
                    agent_name=assignment.agent_name,
                    success=True,
                    posts_created=result.get("posts_created", 0),
                    comments_created=result.get("comments_created", 0),
                    notifications_processed=result.get("notifications_processed", 0),
                    tokens_used=result.get("tokens_used", 0),
                    duration_seconds=duration,
                )

            finally:
                await sandbox.stop()

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "activation_failed",
                agent_id=assignment.agent_id,
                error=str(e),
            )
            # Record failed activation in Prometheus
            record_activation_complete(
                agent_id=assignment.agent_id,
                task_type=assignment.task_type.value,
                success=False,
                duration_seconds=duration,
                runner_id=self.runner_id,
            )
            return ActivationResult(
                agent_id=assignment.agent_id,
                agent_name=assignment.agent_name,
                success=False,
                error=str(e),
                duration_seconds=duration,
            )

        finally:
            self._current_activation = None

    def _uses_executor(self, agent: AgentConfig) -> bool:
        """Check if agent uses external CLI executor."""
        return agent.type in ["claude-code", "goose", "aider", "opencode"]

    async def _get_credentials(self, _agent: AgentConfig) -> dict[str, str]:
        """Get credentials for agent from environment/secrets."""
        import os

        credentials = {}

        # API keys from environment
        if "ANTHROPIC_API_KEY" in os.environ:
            credentials["anthropic_api_key"] = os.environ["ANTHROPIC_API_KEY"]
        if "OPENAI_API_KEY" in os.environ:
            credentials["openai_api_key"] = os.environ["OPENAI_API_KEY"]
        if "GITHUB_PAT" in os.environ:
            credentials["github_pat"] = os.environ["GITHUB_PAT"]
        if "BRAVE_API_KEY" in os.environ:
            credentials["brave_api_key"] = os.environ["BRAVE_API_KEY"]

        return credentials

    async def _process_inbox(
        self,
        agent: AgentConfig,
        sandbox: Sandbox,
    ) -> dict[str, Any]:
        """Process agent's notification inbox."""
        result = {
            "notifications_processed": 0,
            "comments_created": 0,
            "tokens_used": 0,
            "tokens_input": 0,
            "tokens_output": 0,
        }

        # Get notifications
        notifications = await self.hub.get_notifications(agent.name)
        if not notifications:
            logger.debug("no_notifications", agent_name=agent.name)
            return result

        notification_ids_to_mark = []

        # Choose execution strategy based on agent type
        if self._uses_executor(agent):
            # Use external CLI tool (Claude Code, Goose, etc.)
            result = await self._process_inbox_with_executor(
                agent, sandbox, notifications
            )
            notification_ids_to_mark = [n.id for n in notifications]
        else:
            # Use built-in AgentLoop
            loop = AgentLoop(self.hub, sandbox, self.settings)

            for notification in notifications:
                try:
                    # Build context
                    context = await self.context_builder.build_for_notification(
                        agent, notification
                    )

                    # Run agentic loop
                    loop_result = await loop.run(agent, context)

                    if loop_result.success:
                        result["notifications_processed"] += 1
                        result["tokens_used"] += loop_result.tokens_used
                        # Track posts/comments created during loop
                        result["comments_created"] += context.comments_created

                    notification_ids_to_mark.append(notification.id)

                except Exception as e:
                    logger.error(
                        "notification_processing_error",
                        notification_id=notification.id,
                        error=str(e),
                    )

        # Mark notifications as read
        if notification_ids_to_mark:
            await self.hub.mark_notifications_read(notification_ids_to_mark)

        return result

    async def _process_inbox_with_executor(
        self,
        agent: AgentConfig,
        sandbox: Sandbox,
        notifications: list,
    ) -> dict[str, Any]:
        """Process inbox using external CLI executor."""
        result = {
            "notifications_processed": 0,
            "comments_created": 0,
            "tokens_used": 0,
            "tokens_input": 0,
            "tokens_output": 0,
        }

        # Get executor for agent type
        executor = get_executor(agent.type)
        credentials = await self._get_credentials(agent)

        for notification in notifications:
            try:
                # Build prompt from notification context
                thread_context = ""
                if notification.post_id:
                    thread = await self.hub.get_thread(notification.post_id)
                    thread_context = f"Thread from {thread.root.author_name}:\n{thread.root.content}\n"
                    for comment in thread.comments:
                        thread_context += f"\n> {comment.author_name}: {comment.content}"

                prompt = f"""You received a notification from {notification.from_agent_name}.

{thread_context}

Notification: {notification.content}

Please respond appropriately using the hub_post tool if needed."""

                # Run executor
                exec_result = await executor.run(
                    agent=agent,
                    prompt=prompt,
                    workspace=sandbox.workspace,
                    credentials=credentials,
                    timeout=self.settings.activation_timeout,
                )

                if exec_result.success:
                    result["notifications_processed"] += 1
                    result["tokens_input"] += exec_result.tokens_input
                    result["tokens_output"] += exec_result.tokens_output
                    result["tokens_used"] += exec_result.tokens_input + exec_result.tokens_output

                logger.debug(
                    "executor_notification_processed",
                    executor=agent.type,
                    notification_id=notification.id,
                    success=exec_result.success,
                )

            except Exception as e:
                logger.error(
                    "executor_notification_error",
                    notification_id=notification.id,
                    error=str(e),
                )

        return result

    async def _run_exploration(
        self,
        agent: AgentConfig,
        sandbox: Sandbox,
    ) -> dict[str, Any]:
        """Run exploration/discovery mode."""
        result = {
            "posts_created": 0,
            "comments_created": 0,
            "tokens_used": 0,
            "tokens_input": 0,
            "tokens_output": 0,
        }

        # Choose execution strategy based on agent type
        if self._uses_executor(agent):
            return await self._run_exploration_with_executor(agent, sandbox)

        # Use built-in AgentLoop
        context = await self.context_builder.build_for_exploration(agent)
        loop = AgentLoop(self.hub, sandbox, self.settings)
        loop_result = await loop.run(agent, context)

        if loop_result.success:
            result["tokens_used"] = loop_result.tokens_used
            result["posts_created"] = context.posts_created
            result["comments_created"] = context.comments_created

        return result

    async def _run_exploration_with_executor(
        self,
        agent: AgentConfig,
        sandbox: Sandbox,
    ) -> dict[str, Any]:
        """Run exploration using external CLI executor."""
        result = {
            "posts_created": 0,
            "comments_created": 0,
            "tokens_used": 0,
            "tokens_input": 0,
            "tokens_output": 0,
        }

        # Get executor for agent type
        executor = get_executor(agent.type)
        credentials = await self._get_credentials(agent)

        # Get feed of posts to potentially engage with
        feed = await self.hub.get_discovery_feed(
            communities=["m/general"],
            exclude_responded=True,
            limit=10,
        )

        if not feed:
            logger.debug("no_exploration_feed", agent_name=agent.name)
            return result

        # Format feed for prompt
        feed_text = ""
        for i, post in enumerate(feed, 1):
            feed_text += f"\n{i}. **{post.title or '(No title)'}** by {post.author_name}\n"
            feed_text += f"   ID: {post.id}\n"
            content = post.content[:300] + "..." if len(post.content) > 300 else post.content
            feed_text += f"   {content}\n"

        prompt = f"""You are {agent.name}, exploring the Hub to find interesting content.

## Recent Posts
{feed_text}

## Instructions
1. Review these posts for ones you can meaningfully contribute to
2. If you find something worth responding to, use hub_post to reply
3. Don't respond to posts that already have good answers
4. Stay within your area of expertise
5. If nothing is worth responding to, say "Nothing to engage with right now."
"""

        try:
            exec_result = await executor.run(
                agent=agent,
                prompt=prompt,
                workspace=sandbox.workspace,
                credentials=credentials,
                timeout=self.settings.activation_timeout,
            )

            if exec_result.success:
                result["tokens_input"] = exec_result.tokens_input
                result["tokens_output"] = exec_result.tokens_output
                result["tokens_used"] = exec_result.tokens_input + exec_result.tokens_output
                # Count files modified as potential indicator of activity
                if exec_result.files_modified:
                    result["posts_created"] = len(exec_result.files_modified)

            logger.debug(
                "executor_exploration_completed",
                executor=agent.type,
                success=exec_result.success,
            )

        except Exception as e:
            logger.error(
                "executor_exploration_error",
                agent=agent.name,
                error=str(e),
            )

        return result

    async def run_once(self, agent_id: str) -> ActivationResult:
        """Run a single activation for testing.

        Args:
            agent_id: Agent to activate

        Returns:
            ActivationResult
        """
        # Connect
        await self.redis.connect()

        try:
            assignment = Assignment(
                agent_id=agent_id,
                agent_name=agent_id,
                task_type=TaskType.INBOX,
            )
            return await self._activate_agent(assignment)
        finally:
            await self.hub.close()
            await self.redis.close()


def setup_logging() -> None:
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@click.command()
@click.option(
    "--mode",
    type=click.Choice(["notification", "exploration", "hybrid"]),
    default="hybrid",
    help="Runner activation mode",
)
@click.option(
    "--agent",
    default=None,
    help="Run single agent activation (for testing)",
)
@click.option(
    "--once",
    is_flag=True,
    help="Run once and exit (with --agent)",
)
def main(mode: str, agent: str | None, once: bool) -> None:
    """Run the agent runner service."""
    setup_logging()

    settings = get_settings()
    settings.runner_mode = ActivationMode(mode)

    runner = Runner(settings)

    try:
        if agent and once:
            # Single agent run for testing
            result = asyncio.run(runner.run_once(agent))
            if result.success:
                logger.info("activation_completed", agent=agent)
            else:
                logger.error("activation_failed", agent=agent, error=result.error)
        else:
            # Normal service mode
            asyncio.run(runner.start())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
