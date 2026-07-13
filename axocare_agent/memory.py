"""Conversation memory helpers for durable agent summaries."""

from __future__ import annotations

from collections.abc import Sequence

SUMMARY_HEADER = "Conversation memory summary"
MAX_SUMMARY_CHARS = 1_200


def build_summary(
    existing_summary: str | None,
    messages: Sequence[tuple[str, str]],
    *,
    max_chars: int = MAX_SUMMARY_CHARS,
) -> str:
    """Merge existing memory with older chat turns into one bounded summary."""
    lines = existing_summary.splitlines() if existing_summary else []

    for role, content in messages:
        lines.append(_summary_line(role, content))

    return _trim_summary(lines, max_chars=max_chars)


def summary_message(summary: str | None) -> dict[str, str] | None:
    """Render persisted summary text as a system message for the model."""
    if not summary:
        return None
    return {
        "role": "system",
        "content": f"{SUMMARY_HEADER}:\n{summary}",
    }


def _summary_line(role: str, content: str) -> str:
    prefix = "User" if role == "user" else "Assistant"
    compact = " ".join(content.split())
    clipped = compact[:180].rstrip()
    if len(compact) > len(clipped):
        clipped = clipped.rstrip(". ") + "..."
    return f"- {prefix}: {clipped}"


def _trim_summary(lines: Sequence[str], *, max_chars: int) -> str:
    kept = list(lines)
    while len("\n".join(kept)) > max_chars and len(kept) > 2:
        del kept[1]
    summary = "\n".join(kept)
    if len(summary) <= max_chars:
        return summary
    return summary[: max_chars - 3].rstrip() + "..."
