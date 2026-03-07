"""CLI interface for yt-adr-feed (Click-based)."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

from . import __version__
from .config import FeedsConfig, load_config
from .exceptions import YTAdrFeedError

logger = logging.getLogger("yt_adr_feed")


def setup_logging(level: str):
    """Configure structured JSON logging."""
    try:
        from pythonjsonlogger import jsonlogger

        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s"
        )
        handler.setFormatter(formatter)
    except ImportError:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)

    root = logging.getLogger("yt_adr_feed")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.addHandler(handler)


@click.group()
@click.version_option(version=__version__)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True),
    default=None,
    help="Path to channels.yaml config file",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"], case_sensitive=False),
    default="INFO",
    help="Logging level",
)
@click.pass_context
def cli(ctx, config_path, log_level):
    """yt-adr-feed: YouTube transcript monitor → Qdrant + GitHub ADR pipeline."""
    setup_logging(log_level)
    ctx.ensure_object(dict)

    if config_path:
        ctx.obj["config"] = load_config(config_path)
    ctx.obj["config_path"] = config_path


@cli.command()
@click.option("--output-dir", default="/tmp/adr-output", help="Output directory for markdown files")
@click.option("--qdrant-host", default=None, help="Override Qdrant host from config")
@click.option("--qdrant-port", default=None, type=int, help="Override Qdrant port from config")
@click.option("--skip-qdrant", is_flag=True, help="Skip Qdrant storage (markdown only)")
@click.option("--skip-git", is_flag=True, help="Skip git push (local output only)")
@click.option("--dry-run", is_flag=True, help="Show what would be processed without doing it")
@click.pass_context
def fetch(ctx, output_dir, qdrant_host, qdrant_port, skip_qdrant, skip_git, dry_run):
    """Fetch transcripts from configured channels, store in Qdrant, output markdown."""
    config: FeedsConfig = _require_config(ctx)

    # Apply CLI overrides
    if qdrant_host:
        config.qdrant.host = qdrant_host
    if qdrant_port:
        config.qdrant.port = qdrant_port

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    from .channels import YouTubeChannelMonitor
    from .formatter import ADRMarkdownFormatter
    from .keywords import KeywordExtractor
    from .transcript import ChapterExtractor, TranscriptFetcher

    fetcher = TranscriptFetcher()
    keyword_extractor = KeywordExtractor()
    formatter = ADRMarkdownFormatter(file_prefix=config.output.file_prefix)

    # Initialize optional components
    embedder = None
    qdrant = None

    if not skip_qdrant:
        try:
            from .embeddings import LocalEmbedder
            from .storage import QdrantManager

            embedder = LocalEmbedder(config.qdrant.embedding_model)
            qdrant = QdrantManager(
                host=config.qdrant.host,
                port=config.qdrant.port,
                collection_name=config.qdrant.collection_name,
                vector_size=config.qdrant.vector_size,
                api_key=config.qdrant.api_key,
            )
        except Exception as e:
            logger.warning(f"Qdrant unavailable, continuing without: {e}")
            skip_qdrant = True

    transcript_number = config.output.number_start
    files_written: dict[str, str] = {}

    for channel_cfg in config.channels:
        if not channel_cfg.enabled:
            logger.info(f"Skipping disabled channel: {channel_cfg.name}")
            continue

        logger.info(f"Processing channel: {channel_cfg.name} ({channel_cfg.id})")

        try:
            monitor = YouTubeChannelMonitor(
                channel_id=channel_cfg.id,
                max_age_days=channel_cfg.max_age_days,
            )
            videos = monitor.list_recent_videos(limit=channel_cfg.max_videos_per_run)
        except YTAdrFeedError as e:
            logger.error(f"Failed to fetch videos from {channel_cfg.name}: {e}")
            continue

        for video in videos:
            # Check if already processed
            if qdrant and qdrant.is_processed(video.id):
                logger.info(f"Already processed, skipping: {video.title} ({video.id})")
                continue

            if dry_run:
                click.echo(f"[DRY RUN] Would process: {video.title} ({video.id})")
                continue

            logger.info(f"Processing video: {video.title} ({video.id})")

            # Get full video details (description, chapters)
            try:
                video_details = monitor.get_video_details(video.id)
            except YTAdrFeedError:
                video_details = video

            # Fetch transcript
            try:
                transcript_text = fetcher.fetch(video.id)
            except YTAdrFeedError as e:
                logger.error(f"Transcript fetch failed for {video.id}: {e}")
                continue

            if not transcript_text:
                logger.warning(f"No transcript available for: {video.title}")
                continue

            # Extract keywords and chapters
            topics = keyword_extractor.extract(transcript_text)
            chapters = ChapterExtractor.from_yt_dlp_chapters(video_details.chapters)
            if not chapters and video_details.description:
                chapters = ChapterExtractor.from_description(video_details.description)

            # Format markdown
            markdown = formatter.format(
                video=video_details,
                transcript=transcript_text,
                topics=topics,
                chapters=chapters,
                number=transcript_number,
                batch_id=config.batch_id,
            )

            # Write markdown file
            filename = formatter.generate_filename(video_details, transcript_number)
            filepath = output_path / filename
            filepath.write_text(markdown)
            files_written[filename] = markdown
            logger.info(f"Wrote: {filepath}")

            # Store in Qdrant
            if embedder and qdrant:
                try:
                    embedding = embedder.embed_text(transcript_text)
                    qdrant.store_transcript(
                        video=video_details,
                        transcript_text=transcript_text,
                        embedding=embedding,
                        topics=topics,
                        transcript_number=transcript_number,
                        batch_id=config.batch_id,
                        metadata_tags=channel_cfg.metadata_tags,
                    )
                except YTAdrFeedError as e:
                    logger.error(f"Qdrant storage failed for {video.id}: {e}")

            transcript_number += 1

    # Summary
    click.echo(f"\nProcessed {len(files_written)} transcript(s)")
    click.echo(f"Output directory: {output_path}")
    click.echo(f"Batch ID: {config.batch_id}")

    if files_written and not skip_git and config.git:
        _push_to_git(config, files_written)


@cli.command()
@click.option("--output-dir", default="/tmp/adr-output", help="Directory with markdown files")
@click.pass_context
def push(ctx, output_dir):
    """Push existing transcript files to GitHub via PR."""
    config: FeedsConfig = _require_config(ctx)

    if not config.git:
        click.echo("Error: git config not set in channels.yaml", err=True)
        sys.exit(1)

    output_path = Path(output_dir)
    if not output_path.exists():
        click.echo(f"Error: Output directory not found: {output_path}", err=True)
        sys.exit(1)

    # Collect markdown files
    files = {}
    for md_file in sorted(output_path.glob("TRANSCRIPT-*.md")):
        files[md_file.name] = md_file.read_text()

    if not files:
        click.echo("No transcript files found to push.")
        return

    _push_to_git(config, files)


@cli.command()
@click.option("--query", required=True, help="Search query text")
@click.option("--qdrant-host", default=None, help="Override Qdrant host")
@click.option("--top-k", default=5, type=int, help="Number of results")
@click.option("--output-format", type=click.Choice(["text", "json"]), default="text")
@click.pass_context
def search(ctx, query, qdrant_host, top_k, output_format):
    """Search Qdrant for transcripts by semantic similarity."""
    config: FeedsConfig = _require_config(ctx)

    if qdrant_host:
        config.qdrant.host = qdrant_host

    from .embeddings import LocalEmbedder
    from .storage import QdrantManager

    embedder = LocalEmbedder(config.qdrant.embedding_model)
    qdrant = QdrantManager(
        host=config.qdrant.host,
        port=config.qdrant.port,
        collection_name=config.qdrant.collection_name,
        vector_size=config.qdrant.vector_size,
        api_key=config.qdrant.api_key,
    )

    query_embedding = embedder.embed_text(query)
    results = qdrant.search(query_embedding, limit=top_k)

    if output_format == "json":
        click.echo(json.dumps(results, indent=2))
    else:
        if not results:
            click.echo("No results found.")
            return
        for i, r in enumerate(results, 1):
            click.echo(f"\n{i}. [{r['score']:.3f}] {r['title']}")
            click.echo(f"   Channel: {r['channel']}")
            click.echo(f"   Date: {r['published_date']}")
            click.echo(f"   URL: {r['url']}")
            click.echo(f"   Topics: {', '.join(r.get('topics', []))}")


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate config file and connectivity."""
    config: FeedsConfig = _require_config(ctx)

    click.echo(f"Config: OK")
    click.echo(f"  Channels: {len(config.channels)} configured")
    for ch in config.channels:
        status = "enabled" if ch.enabled else "disabled"
        click.echo(f"    - {ch.name} ({ch.id}) [{status}]")

    click.echo(f"  Qdrant: {config.qdrant.host}:{config.qdrant.port}")
    try:
        from .storage import QdrantManager

        qdrant = QdrantManager(
            host=config.qdrant.host,
            port=config.qdrant.port,
            collection_name=config.qdrant.collection_name,
            vector_size=config.qdrant.vector_size,
            api_key=config.qdrant.api_key,
        )
        click.echo(f"    Connection: OK")
        click.echo(f"    Collection: {config.qdrant.collection_name}")
    except Exception as e:
        click.echo(f"    Connection: FAILED ({e})")

    if config.git:
        click.echo(f"  Git: {config.git.repo_url}")
        click.echo(f"    Target branch: {config.git.branch_target}")
    else:
        click.echo(f"  Git: Not configured")


def _require_config(ctx) -> FeedsConfig:
    """Get config from context, exit if not loaded."""
    config = ctx.obj.get("config")
    if not config:
        click.echo("Error: --config is required", err=True)
        sys.exit(1)
    return config


def _push_to_git(config: FeedsConfig, files: dict[str, str]):
    """Execute the git PR workflow."""
    from .git_ops import GitWorkflow

    git = GitWorkflow(
        repo_url=config.git.repo_url,
        branch_target=config.git.branch_target,
        author_name=config.git.author_name,
        author_email=config.git.author_email,
        branch_prefix=config.git.branch_prefix,
        transcript_dir=config.git.transcript_dir,
    )

    try:
        click.echo(f"\nPushing {len(files)} file(s) to GitHub...")
        git.clone()
        branch_name = git.create_branch(config.batch_id)
        git.add_files(files)
        git.commit(config.batch_id, len(files))
        git.push(branch_name)
        pr_url = git.create_pr(branch_name, config.batch_id, files)
        click.echo(f"PR created: {pr_url}")
    except YTAdrFeedError as e:
        click.echo(f"Git push failed: {e}", err=True)
    finally:
        git.cleanup()
