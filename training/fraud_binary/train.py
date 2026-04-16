#!/usr/bin/env python3
"""Fine-tune a binary sequence classifier (fraud vs benign) and save_pretrained.

Examples:
  python training/fraud_binary/train.py --train data/train.csv --output-dir ./artifacts/fraud_binary/v1
  python training/fraud_binary/train.py --train train.jsonl --base-model hfl/chinese-roberta-wwm-ext --epochs 3
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
)

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.fraud_binary.data_io import read_labeled_auto


class FraudTextDataset(Dataset):
    def __init__(self, texts: list[str], labels: list[int], tokenizer, max_length: int):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.texts)

    def __getitem__(self, idx: int) -> dict:
        enc = self.tokenizer(
            self.texts[idx],
            truncation=True,
            max_length=self.max_length,
            padding="max_length",
            return_tensors="pt",
        )
        item = {k: v.squeeze(0) for k, v in enc.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


def split_train_eval(
    texts: list[str],
    labels: list[int],
    eval_ratio: float,
    seed: int,
) -> tuple[list[str], list[int], list[str], list[int]]:
    n = len(texts)
    idx = list(range(n))
    rng = random.Random(seed)
    rng.shuffle(idx)
    n_eval = max(1, int(n * eval_ratio)) if eval_ratio > 0 else 0
    if n_eval >= n:
        n_eval = max(1, n // 10)
    eval_i = set(idx[:n_eval])
    train_i = [i for i in idx if i not in eval_i]
    eval_i_list = [i for i in idx if i in eval_i]
    tr_t = [texts[i] for i in train_i]
    tr_y = [labels[i] for i in train_i]
    ev_t = [texts[i] for i in eval_i_list]
    ev_y = [labels[i] for i in eval_i_list]
    return tr_t, tr_y, ev_t, ev_y


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    acc = float((preds == labels).mean())
    tp = int(((preds == 1) & (labels == 1)).sum())
    fp = int(((preds == 1) & (labels == 0)).sum())
    fn = int(((preds == 0) & (labels == 1)).sum())
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-12)
    return {"accuracy": acc, "f1_fraud": f1, "precision_fraud": prec, "recall_fraud": rec}


def main() -> None:
    ap = argparse.ArgumentParser(description="Train binary fraud classifier (2-class).")
    ap.add_argument("--train", required=True, type=Path, help="labeled .csv / .json / .jsonl")
    ap.add_argument("--eval", type=Path, default=None, help="optional held-out file (same format)")
    ap.add_argument("--output-dir", required=True, type=Path, help="where to save_pretrained")
    ap.add_argument(
        "--base-model",
        default="hfl/chinese-roberta-wwm-ext",
        help="HF model id for AutoModelForSequenceClassification",
    )
    ap.add_argument("--text-column", default="text")
    ap.add_argument("--label-column", default="label")
    ap.add_argument("--label-fraud", default="1")
    ap.add_argument("--label-benign", default="0")
    ap.add_argument("--epochs", type=float, default=3.0)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max-length", type=int, default=256)
    ap.add_argument("--eval-ratio", type=float, default=0.1, help="if --eval omitted, split from train")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--weight-decay", type=float, default=0.01)
    args = ap.parse_args()

    texts, labels = read_labeled_auto(
        args.train,
        args.text_column,
        args.label_column,
        args.label_fraud,
        args.label_benign,
    )
    if not texts:
        raise SystemExit("No labeled rows in --train")
    if sum(labels) == 0 or sum(labels) == len(labels):
        raise SystemExit("Need both classes 0 and 1 in training data")

    if args.eval is not None:
        ev_texts, ev_labels = read_labeled_auto(
            args.eval,
            args.text_column,
            args.label_column,
            args.label_fraud,
            args.label_benign,
        )
        tr_texts, tr_labels = texts, labels
    else:
        tr_texts, tr_labels, ev_texts, ev_labels = split_train_eval(
            texts, labels, args.eval_ratio, args.seed
        )

    tokenizer = AutoTokenizer.from_pretrained(args.base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.base_model,
        num_labels=2,
        id2label={0: "benign", 1: "fraud"},
        label2id={"benign": 0, "fraud": 1},
    )

    train_ds = FraudTextDataset(tr_texts, tr_labels, tokenizer, args.max_length)
    eval_ds = FraudTextDataset(ev_texts, ev_labels, tokenizer, args.max_length)

    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    targs = TrainingArguments(
        output_dir=str(out),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.lr,
        weight_decay=args.weight_decay,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_fraud",
        greater_is_better=True,
        logging_steps=50,
        save_total_limit=2,
        seed=args.seed,
        fp16=torch.cuda.is_available(),
    )

    trainer = Trainer(
        model=model,
        args=targs,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        compute_metrics=compute_metrics,
    )
    trainer.train()
    tokenizer.save_pretrained(out)
    trainer.save_model(out)
    print(f"Saved model + tokenizer to {out.resolve()}")
    print("Infer: class 1 = fraud → use scripts/fraud_binary_predict.py with default --fraud-label-id 1")


if __name__ == "__main__":
    main()
