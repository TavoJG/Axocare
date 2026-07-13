CREATE TABLE agent_conversation_summaries (
    conversation_id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    summarized_message_count INTEGER NOT NULL CHECK (summarized_message_count >= 0),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES agent_conversations (id) ON DELETE CASCADE
);
