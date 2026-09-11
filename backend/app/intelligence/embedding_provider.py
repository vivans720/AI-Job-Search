from abc import ABC, abstractmethod
from typing import Sequence
import structlog
from fastembed import TextEmbedding

from app.config import settings

logger = structlog.get_logger(__name__)


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Embed a single text string into a float vector."""
        pass

    @abstractmethod
    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed multiple text strings."""
        pass


class BGEEmbeddingProvider(EmbeddingProvider):
    """Local embedding provider using BAAI/bge-small-en-v1.5 via fastembed."""

    _instance: "BGEEmbeddingProvider | None" = None
    _model: TextEmbedding | None = None

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL
        if BGEEmbeddingProvider._model is None:
            logger.info("loading_embedding_model", model=self.model_name)
            BGEEmbeddingProvider._model = TextEmbedding(model_name=self.model_name)
            logger.info("embedding_model_loaded", model=self.model_name)
        self.model = BGEEmbeddingProvider._model

    def embed(self, text: str) -> list[float]:
        cleaned = text.strip()
        if not cleaned:
            return [0.0] * settings.EMBEDDING_DIMENSIONS
        embeddings = list(self.model.embed([cleaned]))
        return [float(x) for x in embeddings[0]]

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        cleaned = [t.strip() for t in texts]
        if not cleaned:
            return []
        embeddings = list(self.model.embed(cleaned))
        return [[float(x) for x in vector] for vector in embeddings]


_default_embedding_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    global _default_embedding_provider
    if _default_embedding_provider is None:
        _default_embedding_provider = BGEEmbeddingProvider()
    return _default_embedding_provider
