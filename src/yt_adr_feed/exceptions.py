"""Custom exception hierarchy for yt-adr-feed."""


class YTAdrFeedError(Exception):
    """Base exception for all yt-adr-feed errors."""

    pass


class ConfigError(YTAdrFeedError):
    """Invalid configuration (YAML parse, validation, missing fields)."""

    pass


class YouTubeError(YTAdrFeedError):
    """YouTube channel access or yt-dlp failure."""

    pass


class TranscriptError(YTAdrFeedError):
    """Transcript fetch or parse failure."""

    pass


class EmbeddingError(YTAdrFeedError):
    """Embedding model load or inference failure."""

    pass


class QdrantError(YTAdrFeedError):
    """Qdrant connection or storage failure."""

    pass


class GitError(YTAdrFeedError):
    """Git or GitHub operation failure."""

    pass
