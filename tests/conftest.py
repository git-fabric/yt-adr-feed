"""Shared pytest fixtures for yt-adr-feed tests."""

import pytest
from datetime import datetime
from pathlib import Path


@pytest.fixture
def sample_config_path(tmp_path):
    """Create a temporary channels.yaml for testing."""
    config_content = """
channels:
  - id: "@TestChannel"
    name: "Test Channel"
    enabled: true
    max_age_days: 30
    max_videos_per_run: 3
    metadata_tags:
      - testing
      - demo

qdrant:
  host: "localhost"
  port: 6333
  collection_name: "test_transcripts"
  embedding_model: "all-MiniLM-L6-v2"
  vector_size: 384

output:
  dir: "{output_dir}"
  file_prefix: "TRANSCRIPT"
  number_start: 1
""".format(output_dir=str(tmp_path / "output"))

    config_file = tmp_path / "channels.yaml"
    config_file.write_text(config_content)
    return config_file


@pytest.fixture
def sample_video_metadata():
    """Create sample VideoMetadata for testing."""
    from yt_adr_feed.channels import VideoMetadata

    return VideoMetadata(
        id="dQw4w9WgXcQ",
        title="What is Kubernetes?",
        channel="IBM Technology",
        published_date=datetime(2026, 3, 1),
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        duration_seconds=480,
        description="0:00 Intro\n1:30 What is K8s\n5:00 Architecture\n8:00 Summary",
        chapters=[],
    )


@pytest.fixture
def sample_transcript():
    """Sample cleaned transcript text."""
    return (
        "Today we're going to talk about Kubernetes. Kubernetes is an open source "
        "container orchestration platform that automates the deployment, scaling, "
        "and management of containerized applications. It was originally designed "
        "by Google and is now maintained by the Cloud Native Computing Foundation. "
        "The key components include pods, services, deployments, and namespaces. "
        "Pods are the smallest deployable units that can be created and managed "
        "in Kubernetes. A service is an abstraction which defines a logical set "
        "of pods and a policy by which to access them. Deployments provide "
        "declarative updates to applications. Namespaces provide a mechanism "
        "for isolating groups of resources within a single cluster. "
        "Kubernetes architecture consists of a control plane and worker nodes. "
        "The control plane manages the worker nodes and the pods in the cluster. "
        "The API server is the front end for the Kubernetes control plane. "
        "etcd is a consistent and highly available key value store used as "
        "the backing store for all cluster data."
    )
