"""Load labeled text rows from CSV / JSON / JSONL (shared by train.py and eval.py)."""

from __future__ import annotations

import csv
import json
from pathlib import Path


def read_labeled_csv(
    path: Path,
    text_column: str,
    label_column: str,
    label_fraud: str,
    label_benign: str,
) -> tuple[list[str], list[int]]:
    texts: list[str] = []
    labels: list[int] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("Empty CSV")
        for col in (text_column, label_column):
            if col not in reader.fieldnames:
                raise ValueError(f"CSV missing column {col!r}; have {reader.fieldnames}")
        for row in reader:
            t = str(row.get(text_column) or "").strip()
            y_raw = str(row.get(label_column) or "").strip()
            if y_raw == label_fraud:
                y = 1
            elif y_raw == label_benign:
                y = 0
            else:
                continue
            texts.append(t)
            labels.append(y)
    return texts, labels


def read_labeled_json_array(
    path: Path,
    text_column: str,
    label_column: str,
    label_fraud: str,
    label_benign: str,
) -> tuple[list[str], list[int]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError("JSON root must be an array")
    texts: list[str] = []
    labels: list[int] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        if text_column not in row or label_column not in row:
            continue
        t = str(row[text_column] or "").strip()
        y_raw = str(row[label_column] or "").strip()
        if y_raw == label_fraud:
            y = 1
        elif y_raw == label_benign:
            y = 0
        else:
            continue
        texts.append(t)
        labels.append(y)
    return texts, labels


def read_labeled_jsonl(
    path: Path,
    text_column: str,
    label_column: str,
    label_fraud: str,
    label_benign: str,
) -> tuple[list[str], list[int]]:
    texts: list[str] = []
    labels: list[int] = []
    with path.open(encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if text_column not in row or label_column not in row:
                continue
            t = str(row[text_column] or "").strip()
            y_raw = str(row[label_column] or "").strip()
            if y_raw == label_fraud:
                y = 1
            elif y_raw == label_benign:
                y = 0
            else:
                continue
            texts.append(t)
            labels.append(y)
    return texts, labels


def read_labeled_auto(
    path: Path,
    text_column: str,
    label_column: str,
    label_fraud: str,
    label_benign: str,
) -> tuple[list[str], list[int]]:
    suf = path.suffix.lower()
    if suf == ".csv":
        return read_labeled_csv(path, text_column, label_column, label_fraud, label_benign)
    if suf == ".jsonl":
        return read_labeled_jsonl(path, text_column, label_column, label_fraud, label_benign)
    if suf == ".json":
        return read_labeled_json_array(path, text_column, label_column, label_fraud, label_benign)
    raise ValueError(f"Unsupported suffix {suf!r}; use .csv, .json, or .jsonl")
