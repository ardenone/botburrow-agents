"""Tests for schema migration system."""

from __future__ import annotations

import pytest

from botburrow_agents.schema_migration import (
    CURRENT_SCHEMA_VERSION,
    SCHEMA_BREAKING_CHANGES,
    SchemaMigrationError,
    SchemaVersion,
    SUPPORTED_VERSIONS,
    UnknownFieldWarning,
    get_migration_function,
    migrate_config,
    validate_and_migrate_agent_config,
)
from botburrow_agents.models import AgentConfig


class TestUnknownFieldWarning:
    """Tests for UnknownFieldWarning."""

    def test_create_warning(self):
        """Test creating a warning."""
        warning = UnknownFieldWarning("brain.unknown_field", "value")
        assert warning.field_path == "brain.unknown_field"
        assert warning.field_value == "value"
        assert warning.suggestion is None

    def test_warning_with_suggestion(self):
        """Test warning with suggestion."""
        warning = UnknownFieldWarning(
            "brain.api_key",
            "secret",
            suggestion="Did you mean 'api_key_env'?",
        )
        assert "Did you mean 'api_key_env'?" in str(warning)

    def test_warning_string_representation(self):
        """Test warning string representation."""
        warning = UnknownFieldWarning("test.field", "value")
        assert "test.field" in str(warning)

        warning_with_suggestion = UnknownFieldWarning(
            "test.field",
            "value",
            suggestion="Use 'other_field' instead",
        )
        assert "Use 'other_field' instead" in str(warning_with_suggestion)


class TestGetMigrationFunction:
    """Tests for get_migration_function."""

    def test_get_1_0_0_migration(self):
        """Test getting 1.0.0 migration function."""
        fn = get_migration_function("1.0.0")
        assert fn is not None
        assert callable(fn)

    def test_unsupported_version_raises_error(self):
        """Test that unsupported version raises error."""
        with pytest.raises(SchemaMigrationError) as exc_info:
            get_migration_function("99.99.99")
        assert "Unsupported schema version" in str(exc_info.value)
        assert "99.99.99" in str(exc_info.value)


class TestMigrateConfig:
    """Tests for migrate_config function."""

    def test_migrate_config_1_0_0(self):
        """Test migrating 1.0.0 config."""
        config = {
            "version": "1.0.0",
            "name": "test",
            "type": "native",
        }
        result, warnings = migrate_config(config)
        assert result["version"] == CURRENT_SCHEMA_VERSION
        assert result["name"] == "test"
        assert len(warnings) == 0

    def test_migrate_config_no_version_defaults_to_1_0_0(self):
        """Test that config without version defaults to 1.0.0."""
        config = {
            "name": "test",
            "type": "native",
        }
        result, warnings = migrate_config(config)
        assert result["version"] == CURRENT_SCHEMA_VERSION
        assert result["name"] == "test"

    def test_migrate_config_with_unknown_fields(self):
        """Test migration with unknown fields generates warnings."""
        config = {
            "version": "1.0.0",
            "name": "test",
            "deprecated_field": "old_value",
            "brain": {
                "model": "claude-sonnet-4-20250514",
                "unknown_brain_field": "brain_value",
            },
        }
        result, warnings = migrate_config(config)
        assert result["name"] == "test"
        assert len(warnings) == 2
        field_paths = {w.field_path for w in warnings}
        assert "deprecated_field" in field_paths
        assert "brain.unknown_brain_field" in field_paths

    def test_migrate_config_preserves_known_fields(self):
        """Test that migration preserves all known fields."""
        config = {
            "version": "1.0.0",
            "name": "test-agent",
            "display_name": "Test Agent",
            "description": "A test agent",
            "type": "native",
            "cache_ttl": 180,
            "brain": {
                "model": "gpt-4o-mini",
                "provider": "openai",
                "temperature": 0.5,
                "max_tokens": 2048,
            },
        }
        result, warnings = migrate_config(config)
        assert result["name"] == "test-agent"
        assert result["display_name"] == "Test Agent"
        assert result["description"] == "A test agent"
        assert result["type"] == "native"
        assert result["cache_ttl"] == 180
        assert result["brain"]["model"] == "gpt-4o-mini"
        assert result["brain"]["provider"] == "openai"
        assert result["brain"]["temperature"] == 0.5
        assert result["brain"]["max_tokens"] == 2048
        assert len(warnings) == 0

    def test_migrate_config_custom_target_version(self):
        """Test migration to custom target version."""
        config = {
            "version": "1.0.0",
            "name": "test",
        }
        result, warnings = migrate_config(config, target_version="1.0.0")
        assert result["version"] == "1.0.0"


class TestValidateAndMigrateAgentConfig:
    """Tests for validate_and_migrate_agent_config function."""

    def test_validate_minimal_config(self):
        """Test validation of minimal config."""
        raw_config = {
            "name": "minimal-agent",
            "type": "claude-code",
            "brain": {},
        }
        config, warnings = validate_and_migrate_agent_config(raw_config, "minimal-agent")
        assert isinstance(config, AgentConfig)
        assert config.name == "minimal-agent"
        assert config.type == "claude-code"
        assert len(warnings) == 0

    def test_validate_full_config(self):
        """Test validation of full config."""
        raw_config = {
            "version": "1.0.0",
            "name": "full-agent",
            "display_name": "Full Agent",
            "description": "A full config agent",
            "type": "native",
            "cache_ttl": 180,
            "brain": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_base": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_API_KEY",
                "temperature": 0.7,
                "max_tokens": 4096,
            },
            "capabilities": {
                "grants": ["github:read", "hub:write"],
                "skills": ["test-skill"],
                "mcp_servers": ["github"],
                "shell": {
                    "enabled": True,
                    "allowed_commands": ["git", "python"],
                    "timeout_seconds": 300,
                },
                "spawning": {
                    "can_propose": True,
                    "allowed_templates": ["code-specialist"],
                },
            },
            "interests": {
                "topics": ["python", "kubernetes"],
                "communities": ["m/code-help"],
                "keywords": ["bug", "help"],
                "follow_agents": ["other-agent"],
            },
            "behavior": {
                "respond_to_mentions": True,
                "max_iterations": 20,
                "discovery": {
                    "enabled": True,
                    "frequency": "hourly",
                    "min_confidence": 0.8,
                },
                "limits": {
                    "max_daily_posts": 10,
                    "max_daily_comments": 50,
                    "max_responses_per_thread": 5,
                },
            },
            "memory": {
                "enabled": True,
                "remember": {
                    "conversations_with": ["user1"],
                    "projects_worked_on": True,
                },
                "max_size_mb": 200,
                "retrieval": {
                    "strategy": "embedding_search",
                    "max_context_items": 15,
                },
            },
        }
        config, warnings = validate_and_migrate_agent_config(raw_config, "full-agent")
        assert isinstance(config, AgentConfig)
        assert config.name == "full-agent"
        assert config.display_name == "Full Agent"
        assert config.description == "A full config agent"
        assert config.type == "native"
        assert config.cache_ttl == 180
        assert config.brain.provider == "openai"
        assert config.brain.model == "gpt-4o-mini"
        assert config.brain.api_base == "https://api.openai.com/v1"
        assert config.brain.api_key_env == "OPENAI_API_KEY"
        assert "github:read" in config.capabilities.grants
        assert config.capabilities.shell.enabled is True
        assert config.capabilities.spawning.can_propose is True
        assert "python" in config.interests.topics
        assert config.behavior.discovery.enabled is True
        assert config.behavior.limits.max_responses_per_thread == 5
        assert config.memory.enabled is True
        assert len(warnings) == 0

    def test_validate_with_unknown_fields_generates_warnings(self):
        """Test that unknown fields generate warnings."""
        raw_config = {
            "name": "test-agent",
            "type": "native",
            "brain": {
                "model": "claude-sonnet-4-20250514",
            },
            "unknown_top_level": "value",
            "capabilities": {
                "unknown_cap": "value",
            },
        }
        config, warnings = validate_and_migrate_agent_config(raw_config, "test-agent")
        assert isinstance(config, AgentConfig)
        assert len(warnings) >= 2
        field_paths = {w.field_path for w in warnings}
        assert "unknown_top_level" in field_paths
        assert "capabilities.unknown_cap" in field_paths

    def test_validate_uses_agent_id_as_name_fallback(self):
        """Test that agent_id is used as name fallback."""
        raw_config = {
            "type": "native",
            "brain": {},
        }
        config, warnings = validate_and_migrate_agent_config(raw_config, "fallback-name")
        assert isinstance(config, AgentConfig)
        assert config.name == "fallback-name"

    def test_validate_with_mcp_server_variants(self):
        """Test validation with different MCP server formats."""
        raw_config = {
            "name": "mcp-agent",
            "type": "native",
            "brain": {
                "model": "claude-sonnet-4-20250514",
            },
            "capabilities": {
                "mcp_servers": [
                    "string-server",
                    {"name": "object-server", "command": "node"},
                ],
            },
        }
        config, warnings = validate_and_migrate_agent_config(raw_config, "mcp-agent")
        assert isinstance(config, AgentConfig)
        assert len(config.capabilities.mcp_servers) == 2
        assert config.capabilities.mcp_servers[0] == "string-server"
        assert config.capabilities.mcp_servers[1]["name"] == "object-server"


class TestSchemaVersion:
    """Tests for SchemaVersion class."""

    def test_parse_valid_version(self):
        """Test parsing valid version strings."""
        v = SchemaVersion("1.2.3")
        assert v.parts == (1, 2, 3)
        assert v.version_str == "1.2.3"

    def test_parse_version_with_less_parts(self):
        """Test parsing version with less than 3 parts."""
        v1 = SchemaVersion("1.2")
        assert v1.parts == (1, 2, 0)

        v2 = SchemaVersion("1")
        assert v2.parts == (1, 0, 0)

    def test_parse_invalid_version(self):
        """Test parsing invalid version defaults to 0.0.0."""
        v = SchemaVersion("invalid")
        assert v.parts == (0, 0, 0)

    def test_none_version(self):
        """Test None version string."""
        v = SchemaVersion(None)
        assert v.parts == (0, 0, 0)
        assert str(v) == "unversioned"

    def test_version_comparison(self):
        """Test version comparison operators."""
        v1 = SchemaVersion("1.0.0")
        v2 = SchemaVersion("1.0.1")
        v3 = SchemaVersion("1.1.0")
        v4 = SchemaVersion("2.0.0")

        assert v1 < v2
        assert v2 < v3
        assert v3 < v4
        assert v1 <= v2
        assert v2 >= v1
        assert v1 == SchemaVersion("1.0.0")
        assert v1 != v2

    def test_version_str_representation(self):
        """Test string representation of versions."""
        v1 = SchemaVersion("1.2.3")
        assert str(v1) == "1.2.3"
        assert repr(v1) == "SchemaVersion('1.2.3')"

        v2 = SchemaVersion(None)
        assert str(v2) == "unversioned"


class TestCurrentSchemaVersion:
    """Tests for CURRENT_SCHEMA_VERSION constant."""

    def test_current_version_is_1_0_0(self):
        """Test that current version is 1.0.0."""
        assert CURRENT_SCHEMA_VERSION == "1.0.0"

    def test_current_version_in_supported(self):
        """Test that current version is in supported versions."""
        assert CURRENT_SCHEMA_VERSION in SUPPORTED_VERSIONS


class TestSupportedVersions:
    """Tests for SUPPORTED_VERSIONS constant."""

    def test_supported_versions_is_list(self):
        """Test that supported versions is a list."""
        assert isinstance(SUPPORTED_VERSIONS, list)

    def test_supported_versions_contains_1_0_0(self):
        """Test that supported versions contains 1.0.0."""
        assert "1.0.0" in SUPPORTED_VERSIONS


class TestSchemaBreakingChanges:
    """Tests for breaking changes documentation."""

    def test_breaking_changes_doc_exists(self):
        """Test that breaking changes documentation exists."""
        assert SCHEMA_BREAKING_CHANGES is not None
        assert len(SCHEMA_BREAKING_CHANGES) > 0

    def test_breaking_changes_contains_version_info(self):
        """Test that breaking changes contains version information."""
        assert "1.0.0" in SCHEMA_BREAKING_CHANGES
        assert "Version" in SCHEMA_BREAKING_CHANGES

    def test_breaking_changes_contains_migration_guide(self):
        """Test that breaking changes contains migration guide."""
        assert "Migration" in SCHEMA_BREAKING_CHANGES or "migration" in SCHEMA_BREAKING_CHANGES.lower()


class TestSchemaMigrationError:
    """Tests for SchemaMigrationError."""

    def test_error_message(self):
        """Test error message formatting."""
        error = SchemaMigrationError("Test error message")
        assert "Test error message" in str(error)

    def test_raising_error(self):
        """Test raising the error."""
        with pytest.raises(SchemaMigrationError) as exc_info:
            raise SchemaMigrationError("Migration failed")
        assert "Migration failed" in str(exc_info.value)

    def test_error_with_version(self):
        """Test error with version context."""
        error = SchemaMigrationError("Test error", version="2.0.0")
        assert error.version == "2.0.0"


class TestIntegrationWithGitClient:
    """Integration tests with GitClient patterns."""

    def test_nested_discovery_and_limits(self):
        """Test nested discovery and limits configs."""
        raw_config = {
            "name": "test-agent",
            "type": "native",
            "brain": {},
            "behavior": {
                "respond_to_mentions": True,
                "discovery": {
                    "enabled": True,
                    "frequency": "daily",
                    "respond_to_questions": True,
                },
                "limits": {
                    "max_daily_posts": 5,
                    "max_daily_comments": 25,
                },
            },
        }
        config, warnings = validate_and_migrate_agent_config(raw_config, "test-agent")
        assert config.behavior.discovery.enabled is True
        assert config.behavior.discovery.frequency == "daily"
        assert config.behavior.limits.max_daily_posts == 5
        assert config.behavior.limits.max_daily_comments == 25
        assert len(warnings) == 0

    def test_nested_memory_configs(self):
        """Test nested remember and retrieval configs."""
        raw_config = {
            "name": "test-agent",
            "type": "native",
            "brain": {},
            "memory": {
                "enabled": True,
                "remember": {
                    "conversations_with": ["user1", "user2"],
                    "decisions_made": True,
                },
                "retrieval": {
                    "strategy": "keyword",
                    "max_context_items": 5,
                },
            },
        }
        config, warnings = validate_and_migrate_agent_config(raw_config, "test-agent")
        assert config.memory.enabled is True
        assert "user1" in config.memory.remember.conversations_with
        assert config.memory.remember.decisions_made is True
        assert config.memory.retrieval.strategy == "keyword"
        assert config.memory.retrieval.max_context_items == 5
        assert len(warnings) == 0

    def test_empty_nested_configs_use_defaults(self):
        """Test that empty nested configs use defaults."""
        raw_config = {
            "name": "test-agent",
            "type": "native",
            "brain": {},
            "capabilities": {},
            "behavior": {},
            "memory": {},
        }
        config, warnings = validate_and_migrate_agent_config(raw_config, "test-agent")
        # Check defaults are applied
        assert config.behavior.respond_to_mentions is True
        assert config.behavior.discovery.enabled is False
        assert config.memory.enabled is False
        assert len(warnings) == 0
