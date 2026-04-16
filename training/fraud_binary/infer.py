"""Load a Hugging Face save_pretrained binary (or single-logit) classifier and score texts."""

from __future__ import annotations

import logging
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logger = logging.getLogger(__name__)


def resolve_device(explicit: str | None) -> torch.device:
    if explicit and explicit != "auto":
        return torch.device(explicit)
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def load_classifier(model_dir: str, device: torch.device | None = None) -> tuple[Any, Any, torch.device]:
    dev = device or resolve_device(None)
    tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
    model = AutoModelForSequenceClassification.from_pretrained(model_dir, local_files_only=True)
    model.eval()
    model.to(dev)
    return model, tokenizer, dev


@torch.inference_mode()
def fraud_probabilities(
    model: Any,
    tokenizer: Any,
    device: torch.device,
    texts: list[str],
    *,
    batch_size: int = 8,
    max_length: int = 512,
    fraud_label_id: int = 1,
) -> list[float]:
    """Return P(fraud) per text.

    - num_labels==2: softmax over logits, take index ``fraud_label_id`` (default 1 = fraud).
    - num_labels==1: sigmoid(logit) as fraud probability.
    """
    n = model.config.num_labels
    out: list[float] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        enc = tokenizer(
            batch,
            padding=True,
            truncation=True,
            max_length=max_length,
            return_tensors="pt",
        )
        enc = {k: v.to(device) for k, v in enc.items()}
        logits = model(**enc).logits
        if n == 1:
            probs = torch.sigmoid(logits.squeeze(-1))
            out.extend(float(x) for x in probs.cpu().tolist())
        elif n >= 2:
            if fraud_label_id < 0 or fraud_label_id >= n:
                raise ValueError(f"fraud_label_id {fraud_label_id} out of range for num_labels={n}")
            probs = torch.softmax(logits, dim=-1)[:, fraud_label_id]
            out.extend(float(x) for x in probs.cpu().tolist())
        else:
            raise ValueError(f"Unsupported num_labels={n}")
    return out
