"""Qdrant vector database integration for transcript storage and search."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime

from .channels import VideoMetadata
from .exceptions import QdrantError

logger = logging.getLogger(__name__)


class QdrantManager:
    """Manage transcript storage in Qdrant vector database.

    Features:
    - Auto-creates collection if missing
    - Dedup by video_id (upsert prevents duplicates)
    - Semantic search via vector similarity
    - Metadata filtering by channel, date, topics
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        collection_name: str = "youtube_transcripts",
        vector_size: int = 384,
        api_key: str | None = None,
    ):
        self.collection_name = collection_name
        self.vector_size = vector_size

        try:
            from qdrant_client import QdrantClient

            self.client = QdrantClient(host=host, port=port, api_key=api_key)
        except Exception as e:
            raise QdrantError(f"Failed to connect to Qdrant at {host}:{port}: {e}") from e

        self._ensure_collection()

    def _ensure_collection(self):
        """Create collection if it doesn't exist."""
        from qdrant_client.models import Distance, VectorParams

        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)

            if not exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE,
                    ),
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            else:
                logger.debug(f"Qdrant collection exists: {self.collection_name}")

        except Exception as e:
            raise QdrantError(f"Failed to ensure collection: {e}") from e

    def store_transcript(
        self,
        video: VideoMetadata,
        transcript_text: str,
        embedding: list[float],
        topics: list[str],
        transcript_number: int,
        batch_id: str,
        metadata_tags: list[str] | None = None,
    ):
        """Store a transcript with its embedding and metadata in Qdrant.

        Uses video_id hash as point ID for deterministic dedup.
        """
        from qdrant_client.models import PointStruct

        # Deterministic point ID from video_id
        point_id = self._video_id_to_point_id(video.id)

        point = PointStruct(
            id=point_id,
            vector=embedding,
            payload={
                "video_id": video.id,
                "title": video.title,
                "channel": video.channel,
                "published_date": video.published_date.isoformat(),
                "url": video.url,
                "duration_seconds": video.duration_seconds,
                "transcript_text": transcript_text[:8000],  # Cap at 8000 chars (per ADR-003)
                "topics": topics,
                "metadata_tags": metadata_tags or [],
                "transcript_number": transcript_number,
                "batch_id": batch_id,
                "indexed_at": datetime.now().isoformat(),
            },
        )

        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point],
            )
            logger.info(
                f"Stored transcript in Qdrant: {video.title} ({video.id})",
                extra={"video_id": video.id, "point_id": point_id},
            )
        except Exception as e:
            raise QdrantError(f"Failed to store transcript {video.id}: {e}") from e

    def is_processed(self, video_id: str) -> bool:
        """Check if a video has already been processed (exists in Qdrant)."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        try:
            results = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[FieldCondition(key="video_id", match=MatchValue(value=video_id))]
                ),
                limit=1,
            )
            return len(results[0]) > 0
        except Exception:
            return False

    def search(self, query_embedding: list[float], limit: int = 5) -> list[dict]:
        """Semantic search for similar transcripts.

        Returns list of dicts with video metadata and similarity score.
        """
        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
            )
            return [
                {
                    "video_id": r.payload.get("video_id"),
                    "title": r.payload.get("title"),
                    "channel": r.payload.get("channel"),
                    "published_date": r.payload.get("published_date"),
                    "url": r.payload.get("url"),
                    "topics": r.payload.get("topics", []),
                    "score": r.score,
                }
                for r in results
            ]
        except Exception as e:
            raise QdrantError(f"Search failed: {e}") from e

    @staticmethod
    def _video_id_to_point_id(video_id: str) -> int:
        """Convert video ID string to deterministic integer point ID.

        Same video_id always produces same point_id (for upsert dedup).
        """
        hash_bytes = hashlib.sha256(video_id.encode()).digest()
        # Use first 8 bytes as unsigned int, mask to positive range
        return int.from_bytes(hash_bytes[:8], "big") % (2**63)
