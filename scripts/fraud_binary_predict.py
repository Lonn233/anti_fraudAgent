#!/usr/bin/env python3
"""Load save_pretrained fraud classifier; read JSON/CSV and print p_fraud per row.

Examples:
  python scripts/fraud_binary_predict.py --model ./artifacts/fraud_binary/v1 --input data.csv
  python scripts/fraud_binary_predict.py --model ./artifacts/fraud_binary/v1 --input data.jsonl --text-column content
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from training.fraud_binary.infer import fraud_probabilities, load_classifier, resolve_device


def read_texts_csv(path: Path, text_column: str) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or text_column not in reader.fieldnames:
            raise SystemExit(f"CSV missing column {text_column!r}; have {reader.fieldnames}")
        return [str(row.get(text_column) or "").strip() for row in reader]


def read_texts_json(path: Path, text_column: str) -> list[str]:
    raw = path.read_text(encoding="utf-8-sig")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise SystemExit("JSON root must be an array of objects")
    out: list[str] = []
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            raise SystemExit(f"Item {i} is not an object")
        if text_column not in row:
            raise SystemExit(f"Item {i} missing key {text_column!r}")
        out.append(str(row[text_column] or "").strip())
    return out


def read_texts_jsonl(path: Path, text_column: str) -> list[str]:
    out: list[str] = []
    with path.open(encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if text_column not in row:
                raise SystemExit(f"Line {line_no} missing key {text_column!r}")
            out.append(str(row[text_column] or "").strip())
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Predict P(fraud) from CSV or JSON/JSONL.")
    p.add_argument("--model", required=True, type=Path, help="save_pretrained directory")
    p.add_argument("--input", required=True, type=Path, help=".csv, .json (array), or .jsonl")
    p.add_argument("--text-column", default="text", help="column / key name (default: text)")
    p.add_argument("--batch-size", type=int, default=8)
    p.add_argument("--max-length", type=int, default=512)
    p.add_argument("--fraud-label-id", type=int, default=1, help="class index for fraud when num_labels>=2")
    p.add_argument("--device", default="auto", help="auto | cpu | cuda | cuda:0 ...")
    args = p.parse_args()

    if not args.model.is_dir():
        raise SystemExit(f"--model is not a directory: {args.model}")

    suf = args.input.suffix.lower()
    if suf == ".csv":
        texts = read_texts_csv(args.input, args.text_column)
    elif suf == ".jsonl":
        texts = read_texts_jsonl(args.input, args.text_column)
    elif suf == ".json":
        texts = read_texts_json(args.input, args.text_column)
    else:
        raise SystemExit("Unsupported --input suffix; use .csv, .json, or .jsonl")

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
    for i, (t, pr) in enumerate(zip(texts, probs)):
        preview = t[:80] + ("…" if len(t) > 80 else "")
        print(f"[{i}] p_fraud={pr:.6f}\t{preview!r}")


if __name__ == "__main__":
    main()
