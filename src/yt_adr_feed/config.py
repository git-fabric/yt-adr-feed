"""Configuration schema and YAML parser for yt-adr-feed."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .exceptions import ConfigError


class ChannelConfig(BaseModel):
    """Configuration for a single YouTube channel to monitor."""

    id: str = Field(description="YouTube channel handle (e.g., '@IBMTechnology') or channel ID")
    name: str = Field(description="Display name for this channel")
    enabled: bool = True
    max_age_days: int = Field(30, description="Skip videos older than N days")
    max_videos_per_run: int = Field(5, description="Max videos to process per run")
    metadata_tags: list[str] = Field(default_factory=list, description="Custom tags for Qdrant metadata")


class QdrantConfig(BaseModel):
    """Qdrant vector database connection settings."""

    host: str = "localhost"
    port: int = 6333
    grpc_port: int = 6334
    api_key: str | None = Field(None, description="Optional API key (from K8s Secret or env)")
    collection_name: str = "youtube_transcripts"
    embedding_model: str = "all-MiniLM-L6-v2"
    vector_size: int = 384


class GitConfig(BaseModel):
    """Git/GitHub workflow configuration."""

    repo_url: str = Field(description="GitHub HTTPS or SSH URL")
    branch_target: str = "main"
    author_name: str = "yt-adr-feed"
    author_email: str = "yt-adr-feed@noreply.github.com"
    branch_prefix: str = "transcripts/"
    commit_template: str = "docs(transcripts): add batch {batch_id}"
    transcript_dir: str = Field(
        "transcripts", description="Directory in repo where transcript files are stored"
    )


class OutputConfig(BaseModel):
    """Output file settings."""

    dir: str = Field("/tmp/adr-output", description="Local directory for markdown output")
    file_prefix: str = "TRANSCRIPT"
    number_start: int = Field(1, description="Starting transcript number for this run")


class FeedsConfig(BaseModel):
    """Root configuration schema."""

    channels: list[ChannelConfig]
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    git: GitConfig | None = None
    output: OutputConfig = Field(default_factory=OutputConfig)
    batch_id: str = Field(
        default_factory=lambda: f"batch-{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}",
        description="Unique identifier for this processing run",
    )


def load_config(path: str | Path) -> FeedsConfig:
    """Load and validate channels.yaml configuration.

    Supports environment variable substitution for ${VAR_NAME} patterns.
    """
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")

    try:
        raw_text = path.read_text()
    except OSError as e:
        raise ConfigError(f"Cannot read config file: {e}") from e

    # Substitute environment variables (${VAR_NAME} syntax)
    for key, value in os.environ.items():
        raw_text = raw_text.replace(f"${{{key}}}", value)

    try:
        raw = yaml.safe_load(raw_text)
    except yaml.YAMLError as e:
        raise ConfigError(f"Invalid YAML: {e}") from e

    if not raw:
        raise ConfigError("Config file is empty")

    try:
        return FeedsConfig(**raw)
    except Exception as e:
        raise ConfigError(f"Config validation error: {e}") from e
