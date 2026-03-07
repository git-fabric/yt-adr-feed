"""Transcript fetching and cleaning via youtube-transcript-api."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from .exceptions import TranscriptError

logger = logging.getLogger(__name__)


@dataclass
class Chapter:
    """A chapter marker from a YouTube video."""

    timestamp: str  # "5:30" or "1:05:30"
    title: str
    start_seconds: float


class TranscriptFetcher:
    """Fetch and clean YouTube video transcripts.

    Prefers manual (human-created) transcripts over auto-generated.
    No API key required.
    """

    def __init__(self, languages: list[str] | None = None):
        self.languages = languages or ["en"]

    def fetch(self, video_id: str) -> str | None:
        """Fetch transcript for a video, returning cleaned text.

        Returns None if no transcript is available.
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        except (TranscriptsDisabled, VideoUnavailable) as e:
            logger.warning(f"Transcripts unavailable for {video_id}: {e}")
            return None
        except Exception as e:
            raise TranscriptError(f"Failed to list transcripts for {video_id}: {e}") from e

        # Try manual transcript first, then auto-generated
        transcript = None
        try:
            transcript = transcript_list.find_manually_created_transcript(self.languages)
            logger.debug(f"Found manual transcript for {video_id}")
        except NoTranscriptFound:
            try:
                transcript = transcript_list.find_generated_transcript(self.languages)
                logger.debug(f"Using auto-generated transcript for {video_id}")
            except NoTranscriptFound:
                logger.warning(f"No transcript in {self.languages} for {video_id}")
                return None

        try:
            entries = transcript.fetch()
        except Exception as e:
            raise TranscriptError(f"Failed to fetch transcript content for {video_id}: {e}") from e

        return self._clean_transcript(entries)

    @staticmethod
    def _clean_transcript(entries: list[dict]) -> str:
        """Clean raw transcript entries into readable text.

        - Removes consecutive duplicate lines (common in auto-generated)
        - Strips HTML tags and special characters
        - Joins into flowing paragraphs
        """
        if not entries:
            return ""

        texts = []
        prev_text = ""

        for entry in entries:
            text = entry.get("text", "").strip()
            if not text:
                continue

            # Strip HTML tags (e.g., <font>, <i>) that sometimes appear
            text = re.sub(r"<[^>]+>", "", text)

            # Remove [Music], [Applause], etc.
            text = re.sub(r"\[.*?\]", "", text).strip()

            if not text:
                continue

            # Skip consecutive duplicates
            if text == prev_text:
                continue

            texts.append(text)
            prev_text = text

        # Join with spaces, then normalize whitespace
        joined = " ".join(texts)
        joined = re.sub(r"\s+", " ", joined).strip()

        return joined


class ChapterExtractor:
    """Extract chapter markers from video description or yt-dlp chapters."""

    # Pattern: "0:00 Intro" or "01:05:30 Main Topic"
    CHAPTER_PATTERN = re.compile(
        r"^(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\s+(.+)$", re.MULTILINE
    )

    @classmethod
    def from_description(cls, description: str) -> list[Chapter]:
        """Extract chapters from video description text."""
        chapters = []
        for match in cls.CHAPTER_PATTERN.finditer(description):
            hours = int(match.group(1) or 0)
            minutes = int(match.group(2))
            seconds = int(match.group(3))

            total_seconds = hours * 3600 + minutes * 60 + seconds

            # Format timestamp
            if hours > 0:
                timestamp = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                timestamp = f"{minutes}:{seconds:02d}"

            chapters.append(
                Chapter(
                    timestamp=timestamp,
                    title=match.group(4).strip(),
                    start_seconds=total_seconds,
                )
            )

        return chapters

    @classmethod
    def from_yt_dlp_chapters(cls, chapters: list[dict]) -> list[Chapter]:
        """Convert yt-dlp chapter format to our Chapter dataclass."""
        result = []
        for ch in chapters:
            start = ch.get("start_time", 0)
            title = ch.get("title", "Untitled")

            hours = int(start // 3600)
            minutes = int((start % 3600) // 60)
            seconds = int(start % 60)

            if hours > 0:
                timestamp = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                timestamp = f"{minutes}:{seconds:02d}"

            result.append(
                Chapter(timestamp=timestamp, title=title, start_seconds=start)
            )

        return result
