"""Keyword extraction using TF-IDF — no AI, pure statistics."""

from __future__ import annotations

import logging
import re

from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

# Domain-specific stop words to filter out common but uninformative terms
DOMAIN_STOP_WORDS = {
    "like", "know", "thing", "think", "going", "right", "really",
    "just", "actually", "basically", "okay", "yeah", "well",
    "gonna", "wanna", "gotta", "let", "say", "said", "see",
    "look", "way", "lot", "kind", "stuff", "make", "got",
    "come", "want", "need", "use", "used", "using",
}


class KeywordExtractor:
    """Extract keywords from transcript text using TF-IDF.

    No generative AI — deterministic statistical method.
    Same input always produces same output.
    """

    def __init__(self, top_k: int = 10, ngram_range: tuple[int, int] = (1, 2)):
        self.top_k = top_k
        self.ngram_range = ngram_range

    def extract(self, text: str) -> list[str]:
        """Extract top keywords from text using TF-IDF scoring.

        Supports unigrams and bigrams for more meaningful phrases.
        Returns sorted list of keywords (highest TF-IDF first).
        """
        if not text or len(text.split()) < 10:
            return []

        # Preprocess: lowercase, remove non-alpha
        cleaned = self._preprocess(text)

        try:
            # Split text into pseudo-documents (sentences) for better TF-IDF scoring
            # Single-document TF-IDF doesn't differentiate well
            sentences = [s.strip() for s in cleaned.replace(".", "\n").split("\n") if s.strip()]
            if len(sentences) < 2:
                sentences = [cleaned]

            vectorizer = TfidfVectorizer(
                max_features=self.top_k * 3,  # Get extras to filter from
                stop_words="english",
                ngram_range=self.ngram_range,
                min_df=1,
                max_df=0.95 if len(sentences) > 5 else 1.0,
                token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b",  # Alpha-only tokens, 2+ chars
            )
            tfidf_matrix = vectorizer.fit_transform(sentences)
        except ValueError:
            # Empty vocabulary (text too short or all stop words)
            return []

        feature_names = vectorizer.get_feature_names_out()
        # Sum TF-IDF scores across all pseudo-documents for each term
        scores = tfidf_matrix.toarray().sum(axis=0)

        # Pair features with scores, filter domain stop words, sort by score
        keyword_scores = []
        for name, score in zip(feature_names, scores):
            if score > 0 and not self._is_stop_phrase(name):
                keyword_scores.append((name, score))

        keyword_scores.sort(key=lambda x: x[1], reverse=True)

        return [kw for kw, _ in keyword_scores[: self.top_k]]

    @staticmethod
    def _preprocess(text: str) -> str:
        """Normalize text for TF-IDF processing."""
        text = text.lower()
        # Remove URLs
        text = re.sub(r"https?://\S+", "", text)
        # Remove special characters but keep spaces
        text = re.sub(r"[^a-zA-Z\s]", " ", text)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _is_stop_phrase(phrase: str) -> bool:
        """Check if a phrase is a domain-specific stop phrase."""
        words = phrase.split()
        # Filter if ALL words in the phrase are stop words
        return all(w in DOMAIN_STOP_WORDS for w in words)
