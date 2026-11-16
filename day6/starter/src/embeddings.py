"""Local Qwen embedding model; CUDA is required, never silently falls back."""
import time
from typing import Protocol

import torch
from sentence_transformers import SentenceTransformer


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class QwenEmbedder:
    """Run Qwen3-Embedding-0.6B locally on CUDA in FP16."""

    dimensions = 1024

    def __init__(self, model_name: str = "Qwen/Qwen3-Embedding-0.6B", batch_size: int = 8,
                 revision: str | None = None, local_files_only: bool = False,
                 max_seq_length: int = 512) -> None:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is required for the selected local embedding model")
        self.model_name = model_name
        self.batch_size = batch_size
        load_started = time.perf_counter()
        self.model = SentenceTransformer(model_name, revision=revision, local_files_only=local_files_only,
                                         device="cuda", model_kwargs={"torch_dtype": torch.float16})
        self.model.max_seq_length = max_seq_length
        probe = self.model.encode(["GPU embedding initialization check"], convert_to_numpy=True, normalize_embeddings=True)
        if probe.shape != (1, self.dimensions) or not torch.isfinite(torch.as_tensor(probe)).all():
            raise RuntimeError(f"Unexpected model output shape or values: {probe.shape}")
        torch.cuda.synchronize()
        self.load_seconds = time.perf_counter() - load_started

    def _validate_tokens(self, texts: list[str]) -> None:
        tokenized = self.model.tokenizer(texts, add_special_tokens=True, truncation=False, padding=False)
        lengths = [len(row) for row in tokenized["input_ids"]]
        over = [(index, length) for index, length in enumerate(lengths) if length > self.model.max_seq_length]
        if over:
            index, length = over[0]
            raise ValueError(f"Input {index} has {length} tokens; limit is {self.model.max_seq_length}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        self._validate_tokens(texts)
        torch.cuda.synchronize()
        started = time.perf_counter()
        vectors = self.model.encode(texts, batch_size=self.batch_size, convert_to_numpy=True,
                                    normalize_embeddings=True, show_progress_bar=True)
        torch.cuda.synchronize()
        self.last_encode_seconds = time.perf_counter() - started
        if vectors.shape != (len(texts), self.dimensions) or not torch.isfinite(torch.as_tensor(vectors)).all():
            raise ValueError("Embedding output failed dimensions/finite validation")
        return vectors.astype("float32").tolist()

    def embed_query(self, question: str) -> list[float]:
        prompt = self.model.prompts.get("query", "")
        self._validate_tokens([prompt + question])
        torch.cuda.synchronize()
        started = time.perf_counter()
        vector = self.model.encode([question], prompt_name="query", convert_to_numpy=True,
                                   normalize_embeddings=True)
        torch.cuda.synchronize()
        self.last_encode_seconds = time.perf_counter() - started
        if vector.shape != (1, self.dimensions) or not torch.isfinite(torch.as_tensor(vector)).all():
            raise ValueError("Query embedding failed dimensions/finite validation")
        return vector[0].astype("float32").tolist()
