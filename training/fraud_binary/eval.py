#!/usr/bin/env python3
"""Evaluate a save_pretrained binary classifier on labeled CSV or JSON/JSONL.

Labels: 0 = benign, 1 = fraud (override with --label-fraud / --label-benign).

Examples:
  python training/fraud_binary/eval.py --model ./artifacts/fraud_binary/v1 --input labeled.csv
  python training/fraud_binary/eval.py --model ./artifacts/v1 --input data.jsonl --threshold 0.5
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.fraud_binary.data_io import read_labeled_auto
from training.fraud_binary.infer import fraud_probabilities, load_classifier, resolve_device


def metrics_binary(y_true: list[int], y_score: list[float], threshold: float) -> dict[str, float]:
    y_pred = [1 if s >= threshold else 0 for s in y_score]
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    acc = (tp + tn) / max(len(y_true), 1)
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-12)
    return {"accuracy": acc, "precision_fraud": prec, "recall_fraud": rec, "f1_fraud": f1, "tp": tp, "tn": tn, "fp": fp, "fn": fn}


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate fraud classifier on labeled data.")
    ap.add_argument("--model", required=True, type=Path, help="save_pretrained directory")
    ap.add_argument("--input", required=True, type=Path, help=".csv, .json, or .jsonl")
    ap.add_argument("--text-column", default="text")
    ap.add_argument("--label-column", default="label")
    ap.add_argument("--label-fraud", default="1", help="raw label value meaning fraud")
    ap.add_argument("--label-benign", default="0", help="raw label value meaning benign")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--max-length", type=int, default=512)
    ap.add_argument("--fraud-label-id", type=int, default=1)
    ap.add_argument("--device", default="auto")
    args = ap.parse_args()

    if not args.model.is_dir():
        raise SystemExit(f"--model is not a directory: {args.model}")

    try:
        texts, labels = read_labeled_auto(
            args.input,
            args.text_column,
            args.label_column,
            args.label_fraud,
            args.label_benign,
        )
    except ValueError as e:
        raise SystemExit(str(e)) from e

    if not texts:
        raise SystemExit("No labeled rows found (check columns and label values)")

    dev = resolve_device(None if args.device == "auto" else args.device)
    model, tokenizer, dev = load_classifier(str(args.model), device=dev)
    probs = fraud_probabilities(
        model,
        tokenizer,
        dev,
        texts,
        batch_size=args.batch_size,
        max_length=args.max_length,
        fraud_label_id=args.fraud_label_id,
    )
    m = metrics_binary(labels, probs, args.threshold)
    print(f"n={len(texts)} threshold={args.threshold}")
    for k in ("accuracy", "precision_fraud", "recall_fraud", "f1_fraud"):
        print(f"{k}: {m[k]:.4f}")
    print(f"tp={m['tp']} tn={m['tn']} fp={m['fp']} fn={m['fn']}")


if __name__ == "__main__":
    main()
