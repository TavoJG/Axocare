from __future__ import annotations

from axocare_agent.memory import build_summary, summary_message


def test_build_summary_appends_new_turns_to_existing_summary() -> None:
    summary = build_summary(
        "- User: Earlier question",
        [("assistant", "Earlier answer"), ("user", "Follow-up question")],
    )

    assert summary == (
        "- User: Earlier question\n"
        "- Assistant: Earlier answer\n"
        "- User: Follow-up question"
    )


def test_summary_message_wraps_summary_for_prompt() -> None:
    assert summary_message("- User: Earlier question") == {
        "role": "system",
        "content": "Conversation memory summary:\n- User: Earlier question",
    }
