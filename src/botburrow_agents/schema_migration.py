"""Schema version tracking and migration system for agent-definitions.

This module implements proper schema version tracking and migration for
agent-definitions config parsing. It addresses the limitations of the
workaround in GitClient.load_agent_config() by:

1. Explicitly tracking schema versions
2. Providing clear migration paths between versions
3. Warning about unknown fields for debugging
4. Documenting breaking changes

Example:
    >>> from botburrow_agents.schema_migration import migrate_config
    >>> raw_config = {"version": "1.0.0", "name": "test", ...}
    >>> migrated_config, warnings = migrate_config(raw_config)
    >>> print(warnings)
    ["Unknown field 'deprecated_field' in config"]
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import structlog

from botburrow_agents.models import (
    AgentConfig,
    BehaviorConfig,
    BehaviorLimitsConfig,
    BrainConfig,
    CapabilityGrants,
    DiscoveryConfig,
    InterestConfig,
    MemoryConfig,
    MemoryRememberConfig,
    MemoryRetrievalConfig,
    ShellConfig,
    SpawningConfig,
)

logger = structlog.get_logger(__name__)

# Current supported schema version
CURRENT_SCHEMA_VERSION = "1.0.0"

# All supported schema versions
SUPPORTED_VERSIONS = ["1.0.0"]

# Breaking changes documentation
SCHEMA_BREAKING_CHANGES = """
# Agent Definitions Schema - Breaking Changes

## Version 1.0.0 (Current)

This is the initial canonical schema version. No breaking changes from earlier
unversioned configs.

### Field Additions (Non-Breaking)

The following fields were added in 1.0.0 with safe defaults:
- `behavior.discovery` - Discovery behavior configuration
- `behavior.limits` - Behavior limits configuration
- `memory.retrieval` - Memory retrieval configuration

All new fields have default values, so existing configs continue to work.

## Future Migration Guide

When upgrading to a future schema version (e.g., 1.1.0 or 2.0.0):
1. Check this section for breaking changes
2. Use the automatic migration system
3. Review validation warnings for deprecated fields
4. Test configs after upgrade

### Adding a New Schema Version

When adding support for a new schema version:

1. Update CURRENT_SCHEMA_VERSION
2. Add version to SUPPORTED_VERSIONS
3. Create a new migration function following the naming pattern `_migrate_X_Y_Z`
4. Register the migration in _MIGRATIONS dict
5. Update _get_nested_known_fields() if new fields were added
6. Document breaking changes in SCHEMA_BREAKING_CHANGES
7. Add tests for the new migration

Example:
```python
def _migrate_1_1_0(config: dict, warnings: list) -> dict:
    \"\"\"Migration for schema version 1.1.0.\"\"\"
    # Handle renamed fields
    if "old_field" in config:
        config["new_field"] = config.pop("old_field")
        warnings.append(UnknownFieldWarning(
            "old_field", config["new_field"],
            suggestion="Renamed to 'new_field' in 1.1.0"
        ))
    return config

_MIGRATIONS["1.1.0"] = _migrate_1_1_0
```
"""


class SchemaVersion:
    """Represents a schema version with comparison support.

    Enables semantic version comparison for schema migration logic.
    """

    def __init__(self, version_str: str | None) -> None:
        """Initialize schema version.

        Args:
            version_str: Version string like "1.0.0" or None for unversioned
        """
        self.version_str = version_str
        self.parts = self._parse_version(version_str) if version_str else (0, 0, 0)

    def _parse_version(self, version_str: str) -> tuple[int, int, int]:
        """Parse semantic version string.

        Args:
            version_str: Version string like "1.0.0"

        Returns:
            Tuple of (major, minor, patch)
        """
        try:
            parts = version_str.split(".")
            # Ensure we have at least 3 parts
            while len(parts) < 3:
                parts.append("0")
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
            return (major, minor, patch)
        except (ValueError, IndexError):
            logger.warning("invalid_schema_version", version=version_str)
            return (0, 0, 0)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SchemaVersion):
            return NotImplemented
        return self.parts < other.parts

    def __le__(self, other: object) -> bool:
        if not isinstance(other, SchemaVersion):
            return NotImplemented
        return self.parts <= other.parts

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, SchemaVersion):
            return NotImplemented
        return self.parts > other.parts

    def __ge__(self, other: object) -> bool:
        if not isinstance(other, SchemaVersion):
            return NotImplemented
        return self.parts >= other.parts

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SchemaVersion):
            return NotImplemented
        return self.parts == other.parts

    def __str__(self) -> str:
        return self.version_str or "unversioned"

    def __repr__(self) -> str:
        return f"SchemaVersion({self.version_str!r})"


class SchemaMigrationError(Exception):
    """Raised when schema migration fails."""

    def __init__(self, message: str, version: str | None = None) -> None:
        """Initialize error with optional version context.

        Args:
            message: Error message
            version: Schema version that caused the error
        """
        self.version = version
        super().__init__(message)


class UnknownFieldWarning:
    """Warning about an unknown field in config."""

    def __init__(
        self,
        field_path: str,
        field_value: Any,
        suggestion: str | None = None,
    ) -> None:
        """Initialize warning.

        Args:
            field_path: Dot-separated path to the field (e.g., "brain.api_key")
            field_value: The value of the unknown field
            suggestion: Optional hint for what the field might be
        """
        self.field_path = field_path
        self.field_value = field_value
        self.suggestion = suggestion

    def __str__(self) -> str:
        """Return string representation of warning."""
        msg = f"Unknown field '{self.field_path}'"
        if self.suggestion:
            msg += f" - {self.suggestion}"
        return msg


# Migration functions: take raw dict, return migrated dict
MigrationFunction = Callable[[dict[str, Any], list[UnknownFieldWarning]], dict[str, Any]]


def _collect_unknown_fields(
    data: dict[str, Any],
    known_fields: set[str],
    path: str = "",
    warnings: list[UnknownFieldWarning] | None = None,
) -> list[UnknownFieldWarning]:
    """Recursively collect unknown fields from config data.

    Args:
        data: Raw config dict (or nested dict)
        known_fields: Set of known field names at this level
        path: Dot-separated path to current level
        warnings: Accumulated warnings list

    Returns:
        List of UnknownFieldWarning objects
    """
    if warnings is None:
        warnings = []

    if not isinstance(data, dict):
        return warnings

    for key, value in data.items():
        current_path = f"{path}.{key}" if path else key

        if key not in known_fields:
            warnings.append(UnknownFieldWarning(current_path, value))
            # Don't recurse into unknown fields
            continue

        # Recurse into nested dicts
        if isinstance(value, dict):
            nested_known = _get_nested_known_fields(key)
            _collect_unknown_fields(value, nested_known, current_path, warnings)

    return warnings


def _get_nested_known_fields(parent_key: str) -> set[str]:
    """Get known field names for nested structures.

    Args:
        parent_key: The parent field name

    Returns:
        Set of known field names for the nested structure
    """
    known_fields: dict[str, set[str]] = {
        "brain": {
            "model",
            "provider",
            "temperature",
            "max_tokens",
            "api_base",
            "api_key_env",
        },
        "capabilities": {
            "grants",
            "skills",
            "mcp_servers",
            "shell",
            "spawning",
        },
        "shell": {
            "enabled",
            "allowed_commands",
            "blocked_patterns",
            "timeout_seconds",
        },
        "spawning": {
            "can_propose",
            "allowed_templates",
        },
        "interests": {
            "topics",
            "communities",
            "keywords",
            "follow_agents",
        },
        "behavior": {
            "respond_to_mentions",
            "respond_to_replies",
            "respond_to_dms",
            "max_iterations",
            "can_create_posts",
            "max_daily_posts",
            "max_daily_comments",
            "discovery",
            "limits",
        },
        "discovery": {
            "enabled",
            "frequency",
            "respond_to_questions",
            "respond_to_discussions",
            "min_confidence",
        },
        "limits": {
            "max_daily_posts",
            "max_daily_comments",
            "max_responses_per_thread",
            "min_interval_seconds",
        },
        "memory": {
            "enabled",
            "remember",
            "max_size_mb",
            "retrieval",
        },
        "remember": {
            "conversations_with",
            "projects_worked_on",
            "decisions_made",
            "feedback_received",
        },
        "retrieval": {
            "strategy",
            "max_context_items",
            "relevance_threshold",
        },
    }

    # Top-level known fields
    top_level = {
        "version",
        "name",
        "display_name",
        "description",
        "type",
        "cache_ttl",
        "brain",
        "capabilities",
        "interests",
        "behavior",
        "memory",
    }

    if parent_key in known_fields:
        return known_fields[parent_key]
    return top_level


def _migrate_1_0_0(
    config: dict[str, Any],
    warnings: list[UnknownFieldWarning],
) -> dict[str, Any]:
    """Migration for schema version 1.0.0 (identity - no changes needed).

    This is the baseline schema. No structural changes are needed.

    Args:
        config: Raw config dict
        warnings: List to append warnings to

    Returns:
        Migrated config dict (unchanged for 1.0.0)
    """
    # Collect unknown fields for warnings
    known_fields = _get_nested_known_fields("")
    _collect_unknown_fields(config, known_fields, "", warnings)

    return config


# Registry of migration functions
_MIGRATIONS: dict[str, MigrationFunction] = {
    "1.0.0": _migrate_1_0_0,
}


def get_migration_function(version: str) -> MigrationFunction:
    """Get migration function for a given schema version.

    Args:
        version: Schema version string (e.g., "1.0.0")

    Returns:
        Migration function for that version

    Raises:
        SchemaMigrationError: If version is not supported
    """
    if version not in _MIGRATIONS:
        supported = ", ".join(SUPPORTED_VERSIONS)
        raise SchemaMigrationError(
            f"Unsupported schema version: {version}. "
            f"Supported versions: {supported}",
            version=version,
        )
    return _MIGRATIONS[version]


def migrate_config(
    raw_config: dict[str, Any],
    target_version: str | None = None,
) -> tuple[dict[str, Any], list[UnknownFieldWarning]]:
    """Migrate agent config to target schema version.

    This function takes a raw config dict from YAML and applies migrations
    to bring it up to the target version. It also collects warnings about
    unknown fields for debugging purposes.

    Args:
        raw_config: Raw config dict loaded from YAML
        target_version: Target schema version (defaults to CURRENT_SCHEMA_VERSION)

    Returns:
        Tuple of (migrated_config, warnings)

    Raises:
        SchemaMigrationError: If migration fails or version is unsupported

    Example:
        >>> raw_config = {
        ...     "version": "1.0.0",
        ...     "name": "test-agent",
        ...     "unknown_field": "value",
        ... }
        >>> migrated, warnings = migrate_config(raw_config)
        >>> print(warnings[0])
        Unknown field 'unknown_field'
    """
    if target_version is None:
        target_version = CURRENT_SCHEMA_VERSION

    warnings: list[UnknownFieldWarning] = []

    # Determine source version
    source_version_str = raw_config.get("version") or "1.0.0"

    # Parse versions
    source_version = SchemaVersion(source_version_str)
    target_ver = SchemaVersion(target_version)
    current_ver = SchemaVersion(CURRENT_SCHEMA_VERSION)

    # Check if target version is newer than we support
    if target_ver > current_ver:
        raise SchemaMigrationError(
            f"Target schema version {target_version} is newer than supported "
            f"version {CURRENT_SCHEMA_VERSION}. Please upgrade botburrow-agents.",
            version=target_version,
        )

    # Check if config version is newer than we support
    if source_version > current_ver:
        raise SchemaMigrationError(
            f"Config schema version {source_version_str} is newer than supported "
            f"version {CURRENT_SCHEMA_VERSION}. Please upgrade botburrow-agents.",
            version=source_version_str,
        )

    logger.info(
        "migrating_config",
        source_version=str(source_version),
        target_version=target_version,
    )

    # If source version is already at or past target, just validate
    if source_version >= target_ver:
        migration_fn = get_migration_function(str(source_version))
        migrated = migration_fn(raw_config, warnings)
    else:
        # Apply migrations sequentially from source to target
        migrated = raw_config
        versions_to_apply = [
            v for v in SUPPORTED_VERSIONS
            if SchemaVersion(v) > source_version and SchemaVersion(v) <= target_ver
        ]
        versions_to_apply.sort(key=lambda v: SchemaVersion(v))

        for version in versions_to_apply:
            migration_fn = get_migration_function(version)
            migrated = migration_fn(migrated, warnings)
            logger.debug("applied_migration", version=version)

    # Ensure version field is set to target
    migrated["version"] = target_version

    return migrated, warnings


def validate_and_migrate_agent_config(
    raw_config: dict[str, Any],
    agent_id: str,
) -> tuple[AgentConfig, list[UnknownFieldWarning]]:
    """Validate and migrate agent config to current schema.

    This is a convenience function that combines migration with Pydantic
    validation. It's the recommended way to load agent configs.

    Args:
        raw_config: Raw config dict loaded from YAML
        agent_id: Agent identifier (used if name is missing)

    Returns:
        Tuple of (validated AgentConfig, warnings)

    Raises:
        SchemaMigrationError: If migration fails
        ValueError: If validation fails

    Example:
        >>> raw_config = {"name": "test", "type": "native", "brain": {}}
        >>> config, warnings = validate_and_migrate_agent_config(raw_config, "test")
        >>> assert isinstance(config, AgentConfig)
    """
    # Step 1: Migrate to current schema
    migrated_config, warnings = migrate_config(raw_config)

    # Step 2: Log warnings if any
    for warning in warnings:
        logger.warning(
            "unknown_config_field",
            field=warning.field_path,
            agent_id=agent_id,
            suggestion=warning.suggestion,
        )

    # Step 3: Build nested configs for Pydantic validation
    brain_data = migrated_config.get("brain", {}) or {}
    caps_data = migrated_config.get("capabilities", {}) or {}
    interests_data = migrated_config.get("interests", {}) or {}
    behavior_data = migrated_config.get("behavior", {}) or {}
    memory_data = migrated_config.get("memory", {}) or {}

    # Extract nested configs
    shell_data = caps_data.get("shell", {}) or {}
    spawning_data = caps_data.get("spawning", {}) or {}
    discovery_data = behavior_data.get("discovery", {}) or {}
    limits_data = behavior_data.get("limits", {}) or {}
    remember_data = memory_data.get("remember", {}) or {}
    retrieval_data = memory_data.get("retrieval", {}) or {}

    # Step 4: Use Pydantic's model_validate for final validation
    brain = BrainConfig.model_validate(brain_data) if brain_data else BrainConfig()

    capabilities = CapabilityGrants(
        grants=caps_data.get("grants", []),
        skills=caps_data.get("skills", []),
        mcp_servers=caps_data.get("mcp_servers", []),
        shell=ShellConfig.model_validate(shell_data) if shell_data else ShellConfig(),
        spawning=SpawningConfig.model_validate(spawning_data)
        if spawning_data
        else SpawningConfig(),
    )

    interests = (
        InterestConfig.model_validate(interests_data) if interests_data else InterestConfig()
    )

    behavior = BehaviorConfig(
        respond_to_mentions=behavior_data.get("respond_to_mentions", True),
        respond_to_replies=behavior_data.get("respond_to_replies", True),
        respond_to_dms=behavior_data.get("respond_to_dms", True),
        max_iterations=behavior_data.get("max_iterations", 10),
        can_create_posts=behavior_data.get("can_create_posts", True),
        max_daily_posts=behavior_data.get("max_daily_posts", 5),
        max_daily_comments=behavior_data.get("max_daily_comments", 50),
        discovery=DiscoveryConfig.model_validate(discovery_data)
        if discovery_data
        else DiscoveryConfig(),
        limits=BehaviorLimitsConfig.model_validate(limits_data)
        if limits_data
        else BehaviorLimitsConfig(),
    )

    memory = MemoryConfig(
        enabled=memory_data.get("enabled", False),
        remember=MemoryRememberConfig.model_validate(remember_data)
        if remember_data
        else MemoryRememberConfig(),
        max_size_mb=memory_data.get("max_size_mb", 100),
        retrieval=MemoryRetrievalConfig.model_validate(retrieval_data)
        if retrieval_data
        else MemoryRetrievalConfig(),
    )

    # Step 5: Build final AgentConfig
    config = AgentConfig(
        name=migrated_config.get("name", agent_id),
        type=migrated_config.get("type", "claude-code"),
        brain=brain,
        capabilities=capabilities,
        interests=interests,
        behavior=behavior,
        memory=memory,
        display_name=migrated_config.get("display_name"),
        description=migrated_config.get("description"),
        version=migrated_config.get("version"),
        cache_ttl=migrated_config.get("cache_ttl", 300),
        r2_path="",  # Deprecated
    )

    return config, warnings


__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "SUPPORTED_VERSIONS",
    "SCHEMA_BREAKING_CHANGES",
    "SchemaVersion",
    "SchemaMigrationError",
    "UnknownFieldWarning",
    "migrate_config",
    "validate_and_migrate_agent_config",
    "get_migration_function",
]
