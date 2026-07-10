import { onBeforeUnmount, ref } from "vue";
import type { AgentChatMessage } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

type SseEvent = { event: string; data: unknown };

export function parseSseBlock(block: string): SseEvent | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split(/\r?\n/)) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return null;
  try { return { event, data: JSON.parse(data.join("\n")) }; }
  catch { throw new Error("The agent returned an invalid stream response."); }
}

export function useAgentChat(fetcher: typeof fetch = fetch) {
  const messages = ref<AgentChatMessage[]>([]);
  const processing = ref(false);
  const status = ref<string | null>(null);
  const error = ref<string | null>(null);
  let controller: AbortController | null = null;

  async function submit(rawQuestion: string): Promise<void> {
    const question = rawQuestion.trim();
    if (!question || processing.value) return;
    const history = messages.value.slice(-12);
    messages.value.push({ role: "user", content: question });
    processing.value = true;
    status.value = "Thinking…";
    error.value = null;
    controller = new AbortController();

    try {
      const response = await fetcher(`${API_BASE}/api/agent/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ question, history }),
        signal: controller.signal
      });
      if (!response.ok) throw new Error(`Agent API returned ${response.status}`);
      if (!response.body) throw new Error("The agent stream is unavailable in this browser.");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let completed = false;
      while (true) {
        const { done, value } = await reader.read();
        buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
        const blocks = buffer.split("\n\n");
        buffer = done ? "" : blocks.pop() ?? "";
        for (const block of blocks) {
          const item = parseSseBlock(block);
          if (!item) continue;
          const data = item.data as Record<string, unknown>;
          if (item.event === "status") status.value = data.stage === "processing" ? "Checking aquarium data…" : String(data.stage ?? "Thinking…");
          if (item.event === "answer" && typeof data.answer === "string") messages.value.push({ role: "assistant", content: data.answer });
          if (item.event === "error") throw new Error(typeof data.message === "string" ? data.message : "The aquarium agent is unavailable.");
          if (item.event === "done") completed = true;
        }
        if (done) break;
      }
      if (!completed) throw new Error("The agent stream ended before completion.");
    } catch (reason) {
      if (reason instanceof DOMException && reason.name === "AbortError") status.value = "Stopped";
      else error.value = reason instanceof Error ? reason.message : "The aquarium agent is unavailable.";
    } finally {
      processing.value = false;
      if (status.value !== "Stopped") status.value = null;
      controller = null;
    }
  }

  function cancel(): void { controller?.abort(); }
  function clear(): void { if (!processing.value) { messages.value = []; error.value = null; status.value = null; } }
  onBeforeUnmount(cancel);
  return { messages, processing, status, error, submit, cancel, clear };
}
