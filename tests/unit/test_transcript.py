"""Tests for transcript.py — Cleaning and chapter extraction."""

from yt_adr_feed.transcript import TranscriptFetcher, ChapterExtractor, Chapter


class TestTranscriptCleaning:
    def test_clean_removes_duplicates(self):
        entries = [
            {"text": "Hello world", "start": 0, "duration": 2},
            {"text": "Hello world", "start": 2, "duration": 2},
            {"text": "Something new", "start": 4, "duration": 2},
        ]
        result = TranscriptFetcher._clean_transcript(entries)
        assert result == "Hello world Something new"

    def test_clean_removes_html_tags(self):
        entries = [
            {"text": "<font color='#fff'>Hello</font>", "start": 0, "duration": 2},
        ]
        result = TranscriptFetcher._clean_transcript(entries)
        assert result == "Hello"

    def test_clean_removes_annotations(self):
        entries = [
            {"text": "[Music]", "start": 0, "duration": 2},
            {"text": "Real content", "start": 2, "duration": 2},
            {"text": "[Applause]", "start": 4, "duration": 2},
        ]
        result = TranscriptFetcher._clean_transcript(entries)
        assert result == "Real content"

    def test_clean_empty_entries(self):
        assert TranscriptFetcher._clean_transcript([]) == ""

    def test_clean_normalizes_whitespace(self):
        entries = [
            {"text": "  Hello   world  ", "start": 0, "duration": 2},
            {"text": "  Foo   bar  ", "start": 2, "duration": 2},
        ]
        result = TranscriptFetcher._clean_transcript(entries)
        assert "  " not in result


class TestChapterExtractor:
    def test_from_description(self):
        description = """Check out our video on Kubernetes!
0:00 Intro
1:30 What is Kubernetes
5:00 Architecture Overview
8:00 Summary and Wrap Up
"""
        chapters = ChapterExtractor.from_description(description)
        assert len(chapters) == 4
        assert chapters[0].title == "Intro"
        assert chapters[0].timestamp == "0:00"
        assert chapters[1].start_seconds == 90
        assert chapters[2].title == "Architecture Overview"

    def test_from_description_with_hours(self):
        description = "1:05:30 Advanced Topics"
        chapters = ChapterExtractor.from_description(description)
        assert len(chapters) == 1
        assert chapters[0].timestamp == "1:05:30"
        assert chapters[0].start_seconds == 3930

    def test_from_description_no_chapters(self):
        description = "This is just a regular description without any timestamps."
        chapters = ChapterExtractor.from_description(description)
        assert chapters == []

    def test_from_yt_dlp_chapters(self):
        yt_chapters = [
            {"start_time": 0, "title": "Intro", "end_time": 90},
            {"start_time": 90, "title": "Main Content", "end_time": 300},
        ]
        chapters = ChapterExtractor.from_yt_dlp_chapters(yt_chapters)
        assert len(chapters) == 2
        assert chapters[0].title == "Intro"
        assert chapters[1].timestamp == "1:30"
