from __future__ import annotations


def chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """按段落优先、再按固定窗口分段（带重叠）。"""
    text = text.strip()
    if not text:
        return []

    overlap = max(0, min(overlap, max_chars - 1)) if max_chars > 1 else 0
    raw_parts: list[str] = []
    for block in text.replace("\r\n", "\n").replace("\r", "\n").split("\n\n"):
        b = block.strip()
        if b:
            raw_parts.append(b)

    if not raw_parts:
        raw_parts = [text]

    merged: list[str] = []
    buf = ""
    for p in raw_parts:
        if not buf:
            buf = p
            continue
        if len(buf) + 1 + len(p) <= max_chars:
            buf = f"{buf}\n{p}"
        else:
            merged.append(buf)
            buf = p
    if buf:
        merged.append(buf)

    chunks: list[str] = []
    for segment in merged:
        if len(segment) <= max_chars:
            chunks.append(segment)
            continue
        start = 0
        while start < len(segment):
            end = min(start + max_chars, len(segment))
            piece = segment[start:end].strip()
            if piece:
                chunks.append(piece)
            if end >= len(segment):
                break
            start = max(end - overlap, start + 1)

    return [c for c in chunks if c]
