"""
Tests for SEIF Context Registry — the global index of .seif contexts.

Tests cover:
  - Registry creation and persistence
  - Context registration and deduplication
  - Listing and filtering
  - Unregistration
  - Health checks (missing directories)
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from seif.context.registry import (
    REGISTRY_PROTOCOL,
    load_registry,
    save_registry,
    register_context,
    unregister_context,
    find_context_entry,
    find_context_by_name,
    list_contexts,
    update_sync_timestamp,
    detect_unregistered_contexts,
    get_registry_path,
)


@pytest.fixture
def tmp_home(tmp_path):
    """Create a temporary home directory with ~/.seif/."""
    seif_home = tmp_path / ".seif"
    seif_home.mkdir()
    with patch("seif.context.registry.get_user_home", return_value=seif_home):
        with patch("seif.context.registry.get_registry_path",
                   return_value=seif_home / "registry.json"):
            yield tmp_path, seif_home


@pytest.fixture
def sample_context(tmp_path):
    """Create a sample .seif/ directory."""
    ctx_dir = tmp_path / "my-project" / ".seif"
    ctx_dir.mkdir(parents=True)
    # Add a mapper.json to make it look real
    (ctx_dir / "mapper.json").write_text('{"protocol": "SEIF-MAPPER-v1", "modules": []}')
    (ctx_dir / "config.json").write_text('{"autonomous_context": true}')
    return ctx_dir


class TestRegistryCreation:
    """Tests for registry initialization."""

    def test_load_creates_empty_registry(self, tmp_home):
        """Loading a non-existent registry creates a fresh one."""
        _, seif_home = tmp_home
        registry = load_registry()
        assert registry["protocol"] == REGISTRY_PROTOCOL
        assert registry["contexts"] == []
        assert "created_at" in registry

    def test_save_creates_file(self, tmp_home):
        """Saving a registry creates the JSON file."""
        _, seif_home = tmp_home
        registry = load_registry()
        path = save_registry(registry)
        assert path.exists()
        # Check permissions (owner-only)
        mode = oct(path.stat().st_mode)[-3:]
        assert mode == "600"

    def test_save_and_reload(self, tmp_home):
        """Saved registry can be reloaded identically."""
        _, seif_home = tmp_home
        registry = load_registry()
        registry["contexts"].append({"name": "test", "path": "/tmp/test"})
        save_registry(registry)
        reloaded = load_registry()
        assert len(reloaded["contexts"]) == 1
        assert reloaded["contexts"][0]["name"] == "test"


class TestContextRegistration:
    """Tests for registering contexts."""

    def test_register_new_context(self, tmp_home, sample_context):
        """Registering a new context adds it to the registry."""
        entry = register_context(str(sample_context))
        assert entry["name"] == "my-project"
        assert entry["visibility"] == "private"
        assert entry["remote"] is None
        assert "created_at" in entry

    def test_register_with_custom_name(self, tmp_home, sample_context):
        """Custom name overrides directory name."""
        entry = register_context(str(sample_context), name="work-acme")
        assert entry["name"] == "work-acme"

    def test_register_with_remote(self, tmp_home, sample_context):
        """Remote URL is stored correctly."""
        entry = register_context(
            str(sample_context),
            remote="seifprotocol.com/andre/my-project",
            visibility="public",
        )
        assert entry["remote"] == "seifprotocol.com/andre/my-project"
        assert entry["visibility"] == "public"

    def test_register_deduplicates(self, tmp_home, sample_context):
        """Registering the same path twice updates instead of duplicating."""
        register_context(str(sample_context), name="first")
        register_context(str(sample_context), name="updated")
        registry = load_registry()
        assert len(registry["contexts"]) == 1
        assert registry["contexts"][0]["name"] == "updated"

    def test_register_multiple_contexts(self, tmp_home, tmp_path):
        """Multiple distinct contexts are tracked independently."""
        for name in ["work", "personal", "family"]:
            ctx_dir = tmp_path / name / ".seif"
            ctx_dir.mkdir(parents=True)
            register_context(str(ctx_dir), name=name)

        registry = load_registry()
        assert len(registry["contexts"]) == 3
        names = {c["name"] for c in registry["contexts"]}
        assert names == {"work", "personal", "family"}


class TestContextLookup:
    """Tests for finding contexts."""

    def test_find_by_path(self, tmp_home, sample_context):
        """Find context entry by its .seif/ path."""
        register_context(str(sample_context), name="test")
        registry = load_registry()
        found = find_context_entry(registry, str(sample_context))
        assert found is not None
        assert found["name"] == "test"

    def test_find_by_name(self, tmp_home, sample_context):
        """Find context entry by its name."""
        register_context(str(sample_context), name="my-project")
        registry = load_registry()
        found = find_context_by_name(registry, "my-project")
        assert found is not None
        assert found["path"] == str(sample_context.resolve())

    def test_find_missing_returns_none(self, tmp_home):
        """Looking up a non-existent context returns None."""
        registry = load_registry()
        assert find_context_entry(registry, "/nonexistent") is None
        assert find_context_by_name(registry, "ghost") is None


class TestContextListing:
    """Tests for listing contexts with health status."""

    def test_list_empty(self, tmp_home):
        """Empty registry returns empty list."""
        assert list_contexts() == []

    def test_list_with_health(self, tmp_home, sample_context):
        """Listed contexts include health indicators."""
        register_context(str(sample_context))
        results = list_contexts()
        assert len(results) == 1
        ctx = results[0]
        assert ctx["exists"] is True
        assert ctx["has_mapper"] is True
        assert ctx["has_config"] is True
        assert ctx["module_count"] >= 0

    def test_list_detects_missing_directory(self, tmp_home, tmp_path):
        """Missing directories are flagged as not existing."""
        ghost_path = tmp_path / "deleted-project" / ".seif"
        register_context(str(ghost_path), name="ghost")
        results = list_contexts()
        assert len(results) == 1
        assert results[0]["exists"] is False


class TestContextUnregistration:
    """Tests for removing contexts."""

    def test_unregister_existing(self, tmp_home, sample_context):
        """Unregistering a known context removes it."""
        register_context(str(sample_context))
        assert unregister_context(str(sample_context)) is True
        registry = load_registry()
        assert len(registry["contexts"]) == 0

    def test_unregister_missing(self, tmp_home):
        """Unregistering a non-existent context returns False."""
        assert unregister_context("/nonexistent") is False


class TestSyncTimestamp:
    """Tests for sync tracking."""

    def test_update_sync_timestamp(self, tmp_home, sample_context):
        """Sync timestamp gets updated."""
        register_context(str(sample_context))
        update_sync_timestamp(str(sample_context))
        registry = load_registry()
        entry = registry["contexts"][0]
        assert entry["last_sync"] is not None


class TestRegistryProtocol:
    """Tests for protocol compliance."""

    def test_protocol_version(self, tmp_home):
        """Registry always has correct protocol identifier."""
        registry = load_registry()
        save_registry(registry)
        reloaded = load_registry()
        assert reloaded["protocol"] == "SEIF-REGISTRY-v1"

    def test_corrupt_file_recreates(self, tmp_home):
        """Corrupt registry file triggers fresh creation."""
        _, seif_home = tmp_home
        reg_path = seif_home / "registry.json"
        reg_path.write_text("not json {{{")
        registry = load_registry()
        assert registry["protocol"] == REGISTRY_PROTOCOL
        assert registry["contexts"] == []
