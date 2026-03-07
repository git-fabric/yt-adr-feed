"""Tests for config.py — YAML parsing and validation."""

import pytest
from yt_adr_feed.config import load_config, FeedsConfig, ConfigError


class TestLoadConfig:
    def test_load_valid_config(self, sample_config_path):
        config = load_config(sample_config_path)
        assert isinstance(config, FeedsConfig)
        assert len(config.channels) == 1
        assert config.channels[0].name == "Test Channel"
        assert config.channels[0].id == "@TestChannel"

    def test_config_defaults(self, sample_config_path):
        config = load_config(sample_config_path)
        assert config.qdrant.host == "localhost"
        assert config.qdrant.port == 6333
        assert config.qdrant.vector_size == 384
        assert config.qdrant.embedding_model == "all-MiniLM-L6-v2"

    def test_missing_file_raises(self):
        with pytest.raises(ConfigError, match="not found"):
            load_config("/nonexistent/path.yaml")

    def test_empty_config_raises(self, tmp_path):
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        with pytest.raises(ConfigError, match="empty"):
            load_config(empty_file)

    def test_invalid_yaml_raises(self, tmp_path):
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("{{invalid: yaml: [}")
        with pytest.raises(ConfigError):
            load_config(bad_file)

    def test_env_var_substitution(self, tmp_path, monkeypatch):
        monkeypatch.setenv("TEST_HOST", "qdrant.prod.local")
        config_content = """
channels:
  - id: "@Test"
    name: "Test"
qdrant:
  host: "${TEST_HOST}"
"""
        config_file = tmp_path / "env.yaml"
        config_file.write_text(config_content)
        config = load_config(config_file)
        assert config.qdrant.host == "qdrant.prod.local"

    def test_batch_id_generated(self, sample_config_path):
        config = load_config(sample_config_path)
        assert config.batch_id.startswith("batch-")

    def test_channel_disabled(self, tmp_path):
        config_content = """
channels:
  - id: "@Disabled"
    name: "Disabled Channel"
    enabled: false
"""
        config_file = tmp_path / "disabled.yaml"
        config_file.write_text(config_content)
        config = load_config(config_file)
        assert config.channels[0].enabled is False
