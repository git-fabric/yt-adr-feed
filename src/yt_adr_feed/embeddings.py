"""Local embedding inference via sentence-transformers.

No generative AI — deterministic mathematical transformation.
Same input always produces same vector output.
"""

from __future__ import annotations

import logging

from .exceptions import EmbeddingError

logger = logging.getLogger(__name__)

# Lazy-loaded to avoid import overhead when not needed
_model_cache: dict[str, object] = {}


class LocalEmbedder:
    """Generate text embeddings using sentence-transformers (CPU inference).

    Model: all-MiniLM-L6-v2
    - 384 dimensions
    - ~80MB model size
    - Fast on CPU (< 100ms per text)
    - Deterministic: same input → identical vector every time
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.vector_size = self._get_vector_size(model_name)
        self._model = None

    @property
    def model(self):
        """Lazy-load the model on first use."""
        if self._model is None:
            self._model = self._load_model(self.model_name)
        return self._model

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text into a vector.

        Deterministic: same input always produces identical output.
        """
        if not text:
            raise EmbeddingError("Cannot embed empty text")

        try:
            embedding = self.model.encode(text, convert_to_numpy=True, show_progress_bar=False)
            return embedding.tolist()
        except Exception as e:
            raise EmbeddingError(f"Embedding failed: {e}") from e

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts efficiently (batched inference).

        More efficient than calling embed_text() in a loop.
        """
        if not texts:
            return []

        try:
            embeddings = self.model.encode(
                texts, convert_to_numpy=True, show_progress_bar=False, batch_size=32
            )
            return embeddings.tolist()
        except Exception as e:
            raise EmbeddingError(f"Batch embedding failed: {e}") from e

    @staticmethod
    def _load_model(model_name: str):
        """Load sentence-transformers model (cached globally)."""
        if model_name in _model_cache:
            logger.debug(f"Using cached model: {model_name}")
            return _model_cache[model_name]

        logger.info(f"Loading embedding model: {model_name}")
        try:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(model_name)
            _model_cache[model_name] = model
            logger.info(f"Model loaded: {model_name}")
            return model
        except Exception as e:
            raise EmbeddingError(f"Failed to load model {model_name}: {e}") from e

    @staticmethod
    def _get_vector_size(model_name: str) -> int:
        """Return expected vector dimensions for known models."""
        sizes = {
            "all-MiniLM-L6-v2": 384,
            "all-MiniLM-L12-v2": 384,
            "all-mpnet-base-v2": 768,
            "paraphrase-MiniLM-L6-v2": 384,
        }
        return sizes.get(model_name, 384)
