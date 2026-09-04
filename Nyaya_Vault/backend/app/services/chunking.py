from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    text: str
    page_number: int | None = None


def chunk_text(text: str, *, max_chars: int = 1200, overlap: int = 180) -> list[TextChunk]:
    clean = (text or "").replace("\x00", " ").strip()
    if not clean:
        return []
    max_chars = max(200, max_chars)
    overlap = max(0, min(overlap, max_chars // 2))

    chunks: list[TextChunk] = []
    start = 0
    index = 0
    length = len(clean)
    while start < length:
        hard_end = min(start + max_chars, length)
        end = hard_end
        if hard_end < length:
            floor = start + max_chars // 2
            for separator in ("\n\n", "\n", ". ", " "):
                candidate = clean.rfind(separator, floor, hard_end)
                if candidate > floor:
                    end = candidate + len(separator)
                    break
        part = clean[start:end].strip()
        if part:
            chunks.append(TextChunk(index=index, text=part))
            index += 1
        if end >= length:
            break
        next_start = max(end - overlap, start + 1)
        start = next_start
    return chunks
