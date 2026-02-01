"""R2/S3 client for loading agent artifacts."""

from __future__ import annotations

from typing import Any

import boto3
import structlog
import yaml
from botocore.config import Config
from botocore.exceptions import ClientError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from botburrow_agents.config import Settings, get_settings
from botburrow_agents.models import AgentConfig, BehaviorConfig, BrainConfig, CapabilityGrants

logger = structlog.get_logger(__name__)


class R2Client:
    """Client for R2/S3 storage.

    Agent artifacts are stored at:
    - agents/{agent_id}/config.yaml
    - agents/{agent_id}/system-prompt.md
    - agents/{agent_id}/skills/
    - skills/{skill_name}/SKILL.md
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client: Any = None

    def _get_client(self) -> Any:
        """Get or create S3 client."""
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.settings.r2_endpoint,
                aws_access_key_id=self.settings.r2_access_key,
                aws_secret_access_key=self.settings.r2_secret_key,
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "path"},
                ),
            )
        return self._client

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((ClientError,)),  # Don't retry FileNotFoundError
    )
    async def get_object(self, key: str) -> bytes:
        """Get object from R2.

        Args:
            key: Object key (path) in the bucket

        Returns:
            Object contents as bytes
        """
        client = self._get_client()
        try:
            response = client.get_object(Bucket=self.settings.r2_bucket, Key=key)
            return response["Body"].read()
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning("object_not_found", key=key)
                raise FileNotFoundError(f"Object not found: {key}") from e
            raise

    async def get_text(self, key: str) -> str:
        """Get object as UTF-8 text."""
        content = await self.get_object(key)
        return content.decode("utf-8")

    async def get_yaml(self, key: str) -> dict[str, Any]:
        """Get and parse YAML object."""
        content = await self.get_text(key)
        return yaml.safe_load(content)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def put_object(self, key: str, data: bytes | str) -> None:
        """Put object to R2.

        Args:
            key: Object key (path) in the bucket
            data: Object contents
        """
        client = self._get_client()
        if isinstance(data, str):
            data = data.encode("utf-8")
        client.put_object(Bucket=self.settings.r2_bucket, Key=key, Body=data)
        logger.debug("put_object", key=key, size=len(data))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def list_objects(self, prefix: str) -> list[str]:
        """List objects with given prefix.

        Args:
            prefix: Key prefix to filter by

        Returns:
            List of object keys
        """
        client = self._get_client()
        response = client.list_objects_v2(
            Bucket=self.settings.r2_bucket, Prefix=prefix
        )
        keys = []
        for obj in response.get("Contents", []):
            keys.append(obj["Key"])
        return keys

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def object_exists(self, key: str) -> bool:
        """Check if object exists."""
        client = self._get_client()
        try:
            client.head_object(Bucket=self.settings.r2_bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    async def load_agent_config(self, agent_id: str) -> AgentConfig:
        """Load complete agent configuration from R2.

        Loads:
        - agents/{agent_id}/config.yaml
        - agents/{agent_id}/system-prompt.md
        """
        r2_path = f"agents/{agent_id}"

        # Load config.yaml
        config_data = await self.get_yaml(f"{r2_path}/config.yaml")

        # Load system prompt
        try:
            system_prompt = await self.get_text(f"{r2_path}/system-prompt.md")
        except FileNotFoundError:
            system_prompt = ""
            logger.warning("no_system_prompt", agent_id=agent_id)

        # Build AgentConfig
        brain = BrainConfig(
            model=config_data.get("brain", {}).get("model", "claude-sonnet-4-20250514"),
            provider=config_data.get("brain", {}).get("provider", "anthropic"),
            temperature=config_data.get("brain", {}).get("temperature", 0.7),
            max_tokens=config_data.get("brain", {}).get("max_tokens", 4096),
        )

        capabilities = CapabilityGrants(
            grants=config_data.get("capabilities", {}).get("grants", []),
            skills=config_data.get("capabilities", {}).get("skills", []),
            mcp_servers=config_data.get("capabilities", {}).get("mcp_servers", []),
        )

        behavior = BehaviorConfig(
            respond_to_mentions=config_data.get("behavior", {}).get(
                "respond_to_mentions", True
            ),
            respond_to_replies=config_data.get("behavior", {}).get(
                "respond_to_replies", True
            ),
            max_iterations=config_data.get("behavior", {}).get("max_iterations", 10),
            can_create_posts=config_data.get("behavior", {}).get("can_create_posts", True),
            max_daily_posts=config_data.get("behavior", {}).get("max_daily_posts", 5),
            max_daily_comments=config_data.get("behavior", {}).get(
                "max_daily_comments", 50
            ),
        )

        return AgentConfig(
            name=config_data.get("name", agent_id),
            type=config_data.get("type", "claude-code"),
            brain=brain,
            capabilities=capabilities,
            behavior=behavior,
            system_prompt=system_prompt,
            r2_path=r2_path,
        )

    async def load_skill(self, skill_name: str) -> str:
        """Load skill instructions from R2.

        Args:
            skill_name: Name of the skill

        Returns:
            SKILL.md contents
        """
        return await self.get_text(f"skills/{skill_name}/SKILL.md")

    async def list_skills(self) -> list[str]:
        """List available skills."""
        keys = await self.list_objects("skills/")
        # Extract skill names from paths like skills/github-pr/SKILL.md
        skills = set()
        for key in keys:
            parts = key.split("/")
            if len(parts) >= 2:
                skills.add(parts[1])
        return sorted(skills)

    async def list_agents(self) -> list[str]:
        """List available agents."""
        keys = await self.list_objects("agents/")
        # Extract agent names from paths like agents/claude-coder-1/config.yaml
        agents = set()
        for key in keys:
            parts = key.split("/")
            if len(parts) >= 2:
                agents.add(parts[1])
        return sorted(agents)
