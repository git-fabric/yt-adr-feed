"""YouTube channel monitoring via yt-dlp (no API key required)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import yt_dlp

from .exceptions import YouTubeError

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    """Metadata for a single YouTube video."""

    id: str
    title: str
    channel: str
    published_date: datetime
    url: str
    duration_seconds: int = 0
    description: str = ""
    chapters: list[dict] = field(default_factory=list)


class YouTubeChannelMonitor:
    """Monitor a YouTube channel for recent videos using yt-dlp.

    No YouTube API key required — uses yt-dlp's extraction.
    """

    def __init__(self, channel_id: str, max_age_days: int = 30):
        self.channel_id = channel_id
        self.max_age_days = max_age_days
        self._cutoff = datetime.now() - timedelta(days=max_age_days)

    def list_recent_videos(self, limit: int = 5) -> list[VideoMetadata]:
        """Fetch recent videos from channel.

        Uses yt-dlp extract_flat to get video list without downloading.
        Returns VideoMetadata list sorted by date (newest first).
        """
        # Build channel URL — handle both @handle and channel ID formats
        if self.channel_id.startswith("@"):
            url = f"https://www.youtube.com/{self.channel_id}/videos"
        elif self.channel_id.startswith("UC"):
            url = f"https://www.youtube.com/channel/{self.channel_id}/videos"
        else:
            url = f"https://www.youtube.com/{self.channel_id}/videos"

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": "in_playlist",
            "playlist_items": f"1:{limit * 2}",  # Fetch extra to account for age filtering
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            raise YouTubeError(f"Failed to fetch channel {self.channel_id}: {e}") from e

        if not info or "entries" not in info:
            logger.warning(f"No videos found for channel {self.channel_id}")
            return []

        videos = []
        for entry in info["entries"]:
            if entry is None:
                continue

            video = self._parse_entry(entry, info.get("channel", self.channel_id))
            if video and video.published_date >= self._cutoff:
                videos.append(video)

            if len(videos) >= limit:
                break

        logger.info(
            f"Found {len(videos)} recent videos from {self.channel_id}",
            extra={"channel": self.channel_id, "video_count": len(videos)},
        )
        return videos

    def get_video_details(self, video_id: str) -> VideoMetadata:
        """Fetch full metadata for a single video (including description/chapters)."""
        url = f"https://www.youtube.com/watch?v={video_id}"
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            raise YouTubeError(f"Failed to fetch video {video_id}: {e}") from e

        upload_date = info.get("upload_date", "")
        if upload_date:
            published = datetime.strptime(upload_date, "%Y%m%d")
        else:
            published = datetime.now()

        return VideoMetadata(
            id=info.get("id", video_id),
            title=info.get("title", "Unknown"),
            channel=info.get("channel", "Unknown"),
            published_date=published,
            url=info.get("webpage_url", url),
            duration_seconds=info.get("duration", 0) or 0,
            description=info.get("description", ""),
            chapters=info.get("chapters", []) or [],
        )

    def _parse_entry(self, entry: dict, channel_name: str) -> VideoMetadata | None:
        """Parse a flat playlist entry into VideoMetadata."""
        video_id = entry.get("id")
        if not video_id:
            return None

        # Flat extraction may not have upload_date — we'll get it from full fetch later
        upload_date = entry.get("upload_date", "")
        if upload_date:
            try:
                published = datetime.strptime(upload_date, "%Y%m%d")
            except ValueError:
                published = datetime.now()
        else:
            # If no date in flat extraction, assume recent (will verify in full fetch)
            published = datetime.now()

        return VideoMetadata(
            id=video_id,
            title=entry.get("title", "Unknown"),
            channel=channel_name,
            published_date=published,
            url=entry.get("url", f"https://www.youtube.com/watch?v={video_id}"),
            duration_seconds=entry.get("duration", 0) or 0,
        )
