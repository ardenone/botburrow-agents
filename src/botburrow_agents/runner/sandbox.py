"""Sandbox container management for agent execution.

Provides isolated execution environment for:
- Filesystem operations (Read, Write, Edit)
- Shell commands (Bash)
- MCP server calls

Supports two modes:
- LocalSandbox: Direct execution (MVP, for development)
- DockerSandbox: Containerized execution (production)
"""

from __future__ import annotations

import asyncio
import glob
import json
import os
import re
import shutil
import tempfile
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import structlog

from botburrow_agents.config import Settings, get_settings
from botburrow_agents.models import AgentConfig, ToolResult

logger = structlog.get_logger(__name__)


class BaseSandbox(ABC):
    """Abstract base class for sandbox implementations."""

    def __init__(
        self,
        agent: AgentConfig,
        settings: Settings | None = None,
    ) -> None:
        self.agent = agent
        self.settings = settings or get_settings()
        self._workspace: Path | None = None

    @abstractmethod
    async def start(self) -> None:
        """Initialize sandbox environment."""
        pass

    @abstractmethod
    async def stop(self) -> None:
        """Clean up sandbox environment."""
        pass

    @property
    @abstractmethod
    def workspace(self) -> Path:
        """Get workspace directory."""
        pass

    @abstractmethod
    async def execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> ToolResult:
        """Execute a core tool."""
        pass

    @abstractmethod
    async def execute_mcp_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> ToolResult:
        """Execute an MCP server tool."""
        pass


class LocalSandbox(BaseSandbox):
    """Local sandbox for development/MVP mode.

    Runs tools directly in the runner process with basic isolation.
    Use DockerSandbox for production workloads.
    """

    def __init__(
        self,
        agent: AgentConfig,
        settings: Settings | None = None,
    ) -> None:
        super().__init__(agent, settings)
        self._mcp_processes: dict[str, Any] = {}

    async def start(self) -> None:
        """Initialize sandbox environment."""
        # Create workspace directory
        self._workspace = Path(tempfile.mkdtemp(prefix=f"agent-{self.agent.name}-"))
        logger.info("sandbox_started", workspace=str(self._workspace))

    async def stop(self) -> None:
        """Clean up sandbox environment."""
        # Stop MCP processes
        for name, process in self._mcp_processes.items():
            try:
                process.terminate()
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except Exception as e:
                logger.warning("mcp_stop_error", server=name, error=str(e))

        # Remove workspace
        if self._workspace and self._workspace.exists():
            try:
                shutil.rmtree(self._workspace)
                logger.info("sandbox_stopped", workspace=str(self._workspace))
            except Exception as e:
                logger.warning("workspace_cleanup_error", error=str(e))

    @property
    def workspace(self) -> Path:
        """Get workspace directory."""
        if self._workspace is None:
            raise RuntimeError("Sandbox not started")
        return self._workspace

    async def execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> ToolResult:
        """Execute a core tool.

        Args:
            tool_name: Name of the tool (Read, Write, Edit, Bash, Glob, Grep)
            args: Tool arguments

        Returns:
            ToolResult with output or error
        """
        handlers = {
            "Read": self._read,
            "Write": self._write,
            "Edit": self._edit,
            "Bash": self._bash,
            "Glob": self._glob,
            "Grep": self._grep,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return ToolResult(error=f"Unknown tool: {tool_name}")

        try:
            return await handler(args)
        except Exception as e:
            logger.error("tool_error", tool=tool_name, error=str(e))
            return ToolResult(error=str(e))

    async def execute_mcp_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> ToolResult:
        """Execute an MCP server tool.

        For MVP, we simulate MCP calls.
        Future: Actual MCP protocol over stdio/http.
        """
        # Parse tool name: mcp_github_create_pr -> github, create_pr
        parts = tool_name.split("_", 2)
        if len(parts) < 3:
            return ToolResult(error=f"Invalid MCP tool name: {tool_name}")

        server_name = parts[1]
        method_name = "_".join(parts[2:])

        logger.debug("mcp_call", server=server_name, method=method_name)

        # For MVP, return placeholder
        return ToolResult(output=f"MCP call to {server_name}.{method_name} with args: {args}")

    async def _read(self, args: dict[str, Any]) -> ToolResult:
        """Read file contents."""
        file_path = args.get("file_path", "")

        # Resolve path relative to workspace
        full_path = self._resolve_path(file_path)

        if not full_path.exists():
            return ToolResult(error=f"File not found: {file_path}")

        if not full_path.is_file():
            return ToolResult(error=f"Not a file: {file_path}")

        try:
            content = full_path.read_text()
            return ToolResult(output=content)
        except Exception as e:
            return ToolResult(error=f"Failed to read file: {e}")

    async def _write(self, args: dict[str, Any]) -> ToolResult:
        """Write content to file."""
        file_path = args.get("file_path", "")
        content = args.get("content", "")

        full_path = self._resolve_path(file_path)

        try:
            # Create parent directories
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content)
            return ToolResult(output=f"File written: {file_path}")
        except Exception as e:
            return ToolResult(error=f"Failed to write file: {e}")

    async def _edit(self, args: dict[str, Any]) -> ToolResult:
        """Edit file by replacing text."""
        file_path = args.get("file_path", "")
        old_text = args.get("old_text", "")
        new_text = args.get("new_text", "")

        full_path = self._resolve_path(file_path)

        if not full_path.exists():
            return ToolResult(error=f"File not found: {file_path}")

        try:
            content = full_path.read_text()
            if old_text not in content:
                return ToolResult(error=f"Text not found in file: {old_text[:50]}...")

            new_content = content.replace(old_text, new_text, 1)
            full_path.write_text(new_content)
            return ToolResult(output=f"File edited: {file_path}")
        except Exception as e:
            return ToolResult(error=f"Failed to edit file: {e}")

    async def _bash(self, args: dict[str, Any]) -> ToolResult:
        """Execute bash command."""
        command = args.get("command", "")

        # Security: check for blocked commands
        if self._is_blocked_command(command):
            return ToolResult(
                error=f"Command blocked by policy: {command}",
                blocked=True,
            )

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
                env=self._get_safe_env(),
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60.0,
            )

            output = stdout.decode()
            error = stderr.decode()

            if process.returncode != 0:
                return ToolResult(
                    output=output,
                    error=error or f"Command failed with code {process.returncode}",
                    exit_code=process.returncode,
                )

            return ToolResult(output=output, exit_code=0)

        except TimeoutError:
            return ToolResult(error="Command timed out after 60 seconds")
        except Exception as e:
            return ToolResult(error=f"Command execution failed: {e}")

    async def _glob(self, args: dict[str, Any]) -> ToolResult:
        """Find files matching glob pattern."""
        pattern = args.get("pattern", "")

        try:
            # Run glob relative to workspace
            full_pattern = str(self.workspace / pattern)
            matches = glob.glob(full_pattern, recursive=True)

            # Convert to relative paths
            relative_matches = []
            for match in matches:
                rel_path = os.path.relpath(match, self.workspace)
                relative_matches.append(rel_path)

            if not relative_matches:
                return ToolResult(output="No files found matching pattern.")

            return ToolResult(output="\n".join(sorted(relative_matches)))
        except Exception as e:
            return ToolResult(error=f"Glob failed: {e}")

    async def _grep(self, args: dict[str, Any]) -> ToolResult:
        """Search for text in files."""
        import shlex

        pattern = args.get("pattern", "")
        path = args.get("path", ".")

        try:
            full_path = self._resolve_path(path)

            # Use grep command for efficiency, with proper escaping to prevent injection
            # shlex.quote ensures special characters in pattern are escaped
            safe_pattern = shlex.quote(pattern)
            safe_path = shlex.quote(str(full_path))
            cmd = f"grep -rn {safe_pattern} {safe_path}"

            process = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.workspace),
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=30.0,
            )

            output = stdout.decode()
            if not output:
                return ToolResult(output="No matches found.")

            return ToolResult(output=output)

        except TimeoutError:
            return ToolResult(error="Search timed out")
        except Exception as e:
            return ToolResult(error=f"Search failed: {e}")

    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to workspace, preventing escape."""
        # Remove leading slashes to make relative
        path = path.lstrip("/")

        # Resolve and check it's within workspace
        full_path = (self.workspace / path).resolve()

        if not str(full_path).startswith(str(self.workspace)):
            raise ValueError(f"Path escapes workspace: {path}")

        return full_path

    def _is_blocked_command(self, command: str) -> bool:
        """Check if command is blocked by security policy."""
        blocked_patterns = [
            r"rm\s+-rf\s+/",
            r"rm\s+-rf\s+~",
            r"sudo\s+",
            r"chmod\s+777",
            r"curl.*\|\s*sh",
            r"curl.*\|\s*bash",
            r"wget.*\|\s*sh",
            r"wget.*\|\s*bash",
            r"eval\s*\(",
            r">\s*/etc/",
            r">\s*/var/",
        ]

        return any(re.search(pattern, command, re.IGNORECASE) for pattern in blocked_patterns)

    def _get_safe_env(self) -> dict[str, str]:
        """Get safe environment variables for subprocess."""
        # Start with minimal environment
        safe_env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": str(self.workspace),
            "TERM": "xterm-256color",
        }

        # Add allowed env vars from agent config
        for key in ["LANG", "LC_ALL"]:
            if key in os.environ:
                safe_env[key] = os.environ[key]

        return safe_env


class DockerSandbox(BaseSandbox):
    """Docker-based sandbox for production workloads.

    Runs tools inside an isolated Docker container with:
    - Resource limits (CPU, memory)
    - Network isolation
    - Read-only root filesystem (except workspace)
    - Non-root user execution
    """

    def __init__(
        self,
        agent: AgentConfig,
        settings: Settings | None = None,
        credentials: dict[str, str] | None = None,
    ) -> None:
        super().__init__(agent, settings)
        self._container_id: str | None = None
        self._container_name: str | None = None
        self._host_workspace: Path | None = None
        self._credentials = credentials or {}
        self._started = False

    async def start(self) -> None:
        """Start Docker container for sandbox."""
        if self._started:
            return

        # Create host workspace directory
        self._host_workspace = Path(tempfile.mkdtemp(prefix=f"sandbox-{self.agent.name}-"))
        self._workspace = Path("/workspace")

        # Generate unique container name
        self._container_name = f"sandbox-{self.agent.name}-{uuid.uuid4().hex[:8]}"

        # Build docker run command
        cmd = self._build_docker_run_command()

        logger.info(
            "starting_docker_sandbox",
            container=self._container_name,
            image=self.settings.sandbox_image,
            workspace=str(self._host_workspace),
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60.0,
            )

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                raise RuntimeError(f"Failed to start container: {error_msg}")

            self._container_id = stdout.decode().strip()
            self._started = True

            logger.info(
                "docker_sandbox_started",
                container_id=self._container_id[:12],
                container_name=self._container_name,
            )

        except TimeoutError as e:
            raise RuntimeError("Container start timed out") from e

    async def stop(self) -> None:
        """Stop and remove Docker container."""
        if not self._started or not self._container_id:
            return

        logger.info("stopping_docker_sandbox", container_id=self._container_id[:12])

        # Stop container with timeout
        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                "stop",
                "-t",
                "10",
                self._container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.communicate(), timeout=15.0)
        except Exception as e:
            logger.warning("container_stop_error", error=str(e))

        # Remove container
        try:
            process = await asyncio.create_subprocess_exec(
                "docker",
                "rm",
                "-f",
                self._container_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(process.communicate(), timeout=10.0)
        except Exception as e:
            logger.warning("container_remove_error", error=str(e))

        # Clean up host workspace
        if self._host_workspace and self._host_workspace.exists():
            try:
                shutil.rmtree(self._host_workspace)
            except Exception as e:
                logger.warning("workspace_cleanup_error", error=str(e))

        self._started = False
        self._container_id = None

        logger.info("docker_sandbox_stopped")

    @property
    def workspace(self) -> Path:
        """Get workspace directory (container path)."""
        if self._workspace is None:
            raise RuntimeError("Sandbox not started")
        return self._workspace

    @property
    def host_workspace(self) -> Path:
        """Get host workspace directory for volume mounting."""
        if self._host_workspace is None:
            raise RuntimeError("Sandbox not started")
        return self._host_workspace

    def _build_docker_run_command(self) -> list[str]:
        """Build docker run command with security options."""
        cmd = [
            "docker",
            "run",
            "--detach",
            "--name",
            self._container_name or "",
            # Resource limits
            "--memory",
            self.settings.sandbox_memory,
            "--cpus",
            self.settings.sandbox_cpu,
            # Security options
            "--security-opt",
            "no-new-privileges:true",
            "--cap-drop",
            "ALL",
            "--cap-add",
            "CHOWN",
            "--cap-add",
            "SETUID",
            "--cap-add",
            "SETGID",
            # Network: isolate by default, can be overridden per agent
            "--network",
            "none" if not self.agent.network.enabled else "bridge",
            # Workspace volume
            "-v",
            f"{self._host_workspace}:/workspace:rw",
            # Read-only root filesystem (workspace is writable)
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=256m",
            # Working directory
            "-w",
            "/workspace",
            # User (run as non-root)
            "--user",
            "agent",
        ]

        # Add environment variables for credentials
        for key, value in self._credentials.items():
            cmd.extend(["-e", f"{key}={value}"])

        # Add standard env vars
        cmd.extend(
            [
                "-e",
                "HOME=/workspace",
                "-e",
                "TERM=xterm-256color",
                "-e",
                "PYTHONUNBUFFERED=1",
            ]
        )

        # Image
        cmd.append(self.settings.sandbox_image)

        # Keep container running
        cmd.extend(["sleep", "infinity"])

        return cmd

    async def execute_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> ToolResult:
        """Execute a tool inside the Docker container."""
        if not self._started or not self._container_id:
            return ToolResult(error="Sandbox not started")

        handlers = {
            "Read": self._docker_read,
            "Write": self._docker_write,
            "Edit": self._docker_edit,
            "Bash": self._docker_bash,
            "Glob": self._docker_glob,
            "Grep": self._docker_grep,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return ToolResult(error=f"Unknown tool: {tool_name}")

        try:
            return await handler(args)
        except Exception as e:
            logger.error("docker_tool_error", tool=tool_name, error=str(e))
            return ToolResult(error=str(e))

    async def execute_mcp_tool(
        self,
        tool_name: str,
        args: dict[str, Any],
    ) -> ToolResult:
        """Execute an MCP server tool inside the container."""
        # Parse tool name: mcp_github_create_pr -> github, create_pr
        parts = tool_name.split("_", 2)
        if len(parts) < 3:
            return ToolResult(error=f"Invalid MCP tool name: {tool_name}")

        server_name = parts[1]
        method_name = "_".join(parts[2:])

        # Build MCP call command
        # This assumes MCP servers are installed in the container
        mcp_cmd = self._build_mcp_command(server_name, method_name, args)

        return await self._docker_exec(mcp_cmd, timeout=self.settings.mcp_timeout)

    def _build_mcp_command(self, server: str, method: str, args: dict[str, Any]) -> str:
        """Build command to invoke MCP server tool."""
        # Encode args as JSON for the MCP call
        args_json = json.dumps(args)
        # Use npx to run MCP server tools
        return f"npx @modelcontextprotocol/{server}-server call {method} '{args_json}'"

    async def _docker_exec(
        self,
        command: str,
        timeout: float = 60.0,
        workdir: str | None = None,
    ) -> ToolResult:
        """Execute command inside Docker container."""
        exec_cmd = [
            "docker",
            "exec",
            "-w",
            workdir or "/workspace",
        ]

        # Run command via bash
        exec_cmd.extend(
            [
                self._container_id or "",
                "/bin/bash",
                "-c",
                command,
            ]
        )

        try:
            process = await asyncio.create_subprocess_exec(
                *exec_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            output = stdout.decode()
            error = stderr.decode()

            if process.returncode != 0:
                return ToolResult(
                    output=output,
                    error=error or f"Command failed with code {process.returncode}",
                    exit_code=process.returncode or 1,
                )

            return ToolResult(output=output, exit_code=0)

        except TimeoutError:
            return ToolResult(error=f"Command timed out after {timeout} seconds")
        except Exception as e:
            return ToolResult(error=f"Execution failed: {e}")

    async def _docker_read(self, args: dict[str, Any]) -> ToolResult:
        """Read file from container."""
        file_path = args.get("file_path", "")
        # Sanitize path
        safe_path = self._sanitize_path(file_path)
        return await self._docker_exec(f"cat '{safe_path}'")

    async def _docker_write(self, args: dict[str, Any]) -> ToolResult:
        """Write file in container."""
        file_path = args.get("file_path", "")
        content = args.get("content", "")

        safe_path = self._sanitize_path(file_path)

        # Create parent directories and write file
        # Using base64 to safely handle content with special characters
        import base64

        encoded = base64.b64encode(content.encode()).decode()

        cmd = f"mkdir -p $(dirname '{safe_path}') && echo '{encoded}' | base64 -d > '{safe_path}'"
        result = await self._docker_exec(cmd)

        if result.error:
            return result

        return ToolResult(output=f"File written: {file_path}")

    async def _docker_edit(self, args: dict[str, Any]) -> ToolResult:
        """Edit file in container."""
        file_path = args.get("file_path", "")
        old_text = args.get("old_text", "")
        new_text = args.get("new_text", "")

        safe_path = self._sanitize_path(file_path)

        # Read current content
        read_result = await self._docker_exec(f"cat '{safe_path}'")
        if read_result.error:
            return ToolResult(error=f"File not found: {file_path}")

        content = read_result.output
        if old_text not in content:
            return ToolResult(error=f"Text not found in file: {old_text[:50]}...")

        # Replace and write back
        new_content = content.replace(old_text, new_text, 1)
        write_result = await self._docker_write(
            {
                "file_path": file_path,
                "content": new_content,
            }
        )

        if write_result.error:
            return write_result

        return ToolResult(output=f"File edited: {file_path}")

    async def _docker_bash(self, args: dict[str, Any]) -> ToolResult:
        """Execute bash command in container."""
        command = args.get("command", "")

        # Check for blocked commands
        if self._is_blocked_command(command):
            return ToolResult(
                error=f"Command blocked by policy: {command}",
                blocked=True,
            )

        return await self._docker_exec(command, timeout=60.0)

    async def _docker_glob(self, args: dict[str, Any]) -> ToolResult:
        """Find files matching pattern in container."""
        pattern = args.get("pattern", "")

        # Use find with -path for glob-like behavior
        # Convert glob pattern to find pattern
        cmd = f"find /workspace -path '/workspace/{pattern}' -type f 2>/dev/null | sed 's|^/workspace/||'"
        return await self._docker_exec(cmd)

    async def _docker_grep(self, args: dict[str, Any]) -> ToolResult:
        """Search files in container."""
        pattern = args.get("pattern", "")
        path = args.get("path", ".")

        safe_path = self._sanitize_path(path)
        # Escape single quotes in pattern
        safe_pattern = pattern.replace("'", "'\\''")

        cmd = f"grep -rn '{safe_pattern}' '{safe_path}' 2>/dev/null || echo 'No matches found.'"
        return await self._docker_exec(cmd, timeout=30.0)

    def _sanitize_path(self, path: str) -> str:
        """Sanitize file path for container execution.

        Prevents path traversal attacks through various encodings and patterns.
        """
        import pathlib

        # Remove leading slashes to make relative
        path = path.lstrip("/")

        # Detect path traversal patterns (common encodings and variations)
        traversal_patterns = [
            "..",  # Standard parent directory
            "%2e%2e",  # URL encoded ..
            "%252e",  # Double URL encoded
            "..%252f",  # Combined traversal and separator
            "....//",  # Obfuscated traversal
            "%2e%2e%2f",  # URL encoded ../
            "%2e%2e%5c",  # URL encoded ..\ (Windows)
            "0x2e",  # Hex encoding attempt
        ]

        path_lower = path.lower()
        for pattern in traversal_patterns:
            if pattern.lower() in path_lower:
                raise ValueError(f"Path traversal not allowed: {path}")

        # Remove any null bytes
        path = path.replace("\x00", "")

        # Limit path length to prevent DoS
        if len(path) > 1000:
            raise ValueError(f"Path too long: {len(path)} characters")

        # Normalize the path and verify it doesn't escape workspace
        try:
            normalized = pathlib.PurePosixPath(path).as_posix()
        except (ValueError, OSError) as e:
            raise ValueError(f"Invalid path: {e}") from e

        # Final check for escape attempts after normalization
        if normalized.startswith("..") or "/../" in f"/{normalized}":
            raise ValueError(f"Path traversal not allowed: {path}")

        # Ensure path is within workspace
        return f"/workspace/{normalized}"

    def _is_blocked_command(self, command: str) -> bool:
        """Check if command is blocked by security policy."""
        blocked_patterns = [
            r"rm\s+-rf\s+/",
            r"sudo\s+",
            r"chmod\s+777",
            r"curl.*\|\s*sh",
            r"curl.*\|\s*bash",
            r"wget.*\|\s*sh",
            r"wget.*\|\s*bash",
            r"eval\s*\(",
            r"docker\s+",  # Prevent docker-in-docker escape
            r"nsenter\s+",
            r"mount\s+",
        ]

        return any(re.search(pattern, command, re.IGNORECASE) for pattern in blocked_patterns)


# Backwards compatibility alias
Sandbox = LocalSandbox


def create_sandbox(
    agent: AgentConfig,
    settings: Settings | None = None,
    use_docker: bool = False,
    credentials: dict[str, str] | None = None,
) -> BaseSandbox:
    """Factory function to create appropriate sandbox.

    Args:
        agent: Agent configuration
        settings: Application settings
        use_docker: Whether to use Docker sandbox (default: False)
        credentials: Credentials to inject into sandbox environment

    Returns:
        Sandbox instance (LocalSandbox or DockerSandbox)
    """
    if use_docker:
        return DockerSandbox(agent, settings, credentials)
    return LocalSandbox(agent, settings)
