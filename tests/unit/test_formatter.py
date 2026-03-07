"""Tests for formatter.py — Markdown ADR template rendering."""

from datetime import datetime

from yt_adr_feed.channels import VideoMetadata
from yt_adr_feed.formatter import ADRMarkdownFormatter
from yt_adr_feed.transcript import Chapter


class TestADRMarkdownFormatter:
    def setup_method(self):
        self.formatter = ADRMarkdownFormatter(file_prefix="TRANSCRIPT")
        self.video = VideoMetadata(
            id="abc123",
            title="What is RAG?",
            channel="IBM Technology",
            published_date=datetime(2026, 3, 1),
            url="https://www.youtube.com/watch?v=abc123",
            duration_seconds=600,
        )

    def test_format_produces_valid_markdown(self, sample_transcript):
        result = self.formatter.format(
            video=self.video,
            transcript=sample_transcript,
            topics=["kubernetes", "containers", "orchestration"],
            chapters=[
                Chapter(timestamp="0:00", title="Intro", start_seconds=0),
                Chapter(timestamp="5:00", title="Architecture", start_seconds=300),
            ],
            number=1,
            batch_id="batch-test",
        )

        assert "# TRANSCRIPT-001: What is RAG?" in result
        assert "## Source" in result
        assert "IBM Technology" in result
        assert "2026-03-01" in result
        assert "## Topics Detected" in result
        assert "- kubernetes" in result
        assert "## Chapter Markers" in result
        assert "**0:00** — Intro" in result
        assert "## Transcript" in result
        assert "batch-test" in result

    def test_format_no_chapters(self, sample_transcript):
        result = self.formatter.format(
            video=self.video,
            transcript=sample_transcript,
            topics=["test"],
            chapters=[],
            number=1,
            batch_id="batch-test",
        )
        assert "No chapter markers found" in result

    def test_format_no_topics(self, sample_transcript):
        result = self.formatter.format(
            video=self.video,
            transcript=sample_transcript,
            topics=[],
            chapters=[],
            number=1,
            batch_id="batch-test",
        )
        assert "No topics detected" in result

    def test_generate_filename(self):
        filename = self.formatter.generate_filename(self.video, 1)
        assert filename == "TRANSCRIPT-001-ibm-technology.md"

    def test_generate_filename_numbering(self):
        assert self.formatter.generate_filename(self.video, 42) == "TRANSCRIPT-042-ibm-technology.md"

    def test_duration_formatting(self):
        assert ADRMarkdownFormatter._format_duration(0) == "Unknown"
        assert ADRMarkdownFormatter._format_duration(90) == "1m 30s"
        assert ADRMarkdownFormatter._format_duration(3661) == "1h 1m 1s"

    def test_slugify(self):
        assert ADRMarkdownFormatter._slugify("IBM Technology") == "ibm-technology"
        assert ADRMarkdownFormatter._slugify("Hello World!!! @#$") == "hello-world"
