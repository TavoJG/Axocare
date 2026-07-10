import { defineComponent } from "vue";
import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { parseSseBlock, useAgentChat } from "./useAgentChat";

function streamResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  return new Response(new ReadableStream({
    start(controller) { chunks.forEach((chunk) => controller.enqueue(encoder.encode(chunk))); controller.close(); }
  }), { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

function mountChat(fetcher: typeof fetch) {
  let state!: ReturnType<typeof useAgentChat>;
  const wrapper = mount(defineComponent({ setup() { state = useAgentChat(fetcher); return () => null; } }));
  return { wrapper, state };
}

describe("agent SSE integration", () => {
  it("parses named JSON SSE events", () => {
    expect(parseSseBlock('event: answer\ndata: {"answer":"Stable"}')).toEqual({ event: "answer", data: { answer: "Stable" } });
  });

  it("handles events split across arbitrary response chunks", async () => {
    const fetcher = vi.fn().mockResolvedValue(streamResponse([
      'event: status\ndata: {"stage":"pro',
      'cessing"}\n\nevent: answer\ndata: {"answer":"The tank is stable."}\n',
      '\nevent: done\ndata: {}\n\n'
    ]));
    const { state } = mountChat(fetcher as typeof fetch);
    await state.submit(" How is it? ");
    expect(state.messages.value).toEqual([
      { role: "user", content: "How is it?" },
      { role: "assistant", content: "The tank is stable." }
    ]);
    const request = JSON.parse(fetcher.mock.calls[0][1].body);
    expect(request).toEqual({ question: "How is it?", history: [] });
    expect(state.error.value).toBeNull();
  });

  it("sends at most twelve prior messages and exposes safe stream errors", async () => {
    const fetcher = vi.fn().mockResolvedValue(streamResponse([
      'event: error\ndata: {"message":"Agent unavailable"}\n\n'
    ]));
    const { state } = mountChat(fetcher as typeof fetch);
    state.messages.value = Array.from({ length: 14 }, (_, index) => ({ role: index % 2 ? "assistant" : "user", content: `message ${index}` } as const));
    await state.submit("latest?");
    const request = JSON.parse(fetcher.mock.calls[0][1].body);
    expect(request.history).toHaveLength(12);
    expect(request.history[0].content).toBe("message 2");
    expect(state.error.value).toBe("Agent unavailable");
  });
});
