"""Tests for keywords.py — TF-IDF keyword extraction."""

from yt_adr_feed.keywords import KeywordExtractor


class TestKeywordExtractor:
    def setup_method(self):
        self.extractor = KeywordExtractor(top_k=10)

    def test_extract_returns_list(self, sample_transcript):
        keywords = self.extractor.extract(sample_transcript)
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        assert len(keywords) <= 10

    def test_extract_finds_relevant_terms(self, sample_transcript):
        keywords = self.extractor.extract(sample_transcript)
        # Should find Kubernetes-related terms
        all_keywords = " ".join(keywords).lower()
        assert any(
            term in all_keywords
            for term in ["kubernetes", "cluster", "pods", "control", "deployments"]
        )

    def test_extract_deterministic(self, sample_transcript):
        """Same input must always produce same output."""
        result1 = self.extractor.extract(sample_transcript)
        result2 = self.extractor.extract(sample_transcript)
        assert result1 == result2

    def test_empty_text_returns_empty(self):
        assert self.extractor.extract("") == []
        assert self.extractor.extract("   ") == []

    def test_short_text_returns_empty(self):
        assert self.extractor.extract("hello world") == []

    def test_filters_stop_words(self, sample_transcript):
        keywords = self.extractor.extract(sample_transcript)
        filler_words = {"like", "just", "really", "basically", "gonna"}
        for kw in keywords:
            assert kw not in filler_words

    def test_custom_top_k(self, sample_transcript):
        extractor = KeywordExtractor(top_k=3)
        keywords = extractor.extract(sample_transcript)
        assert len(keywords) <= 3
