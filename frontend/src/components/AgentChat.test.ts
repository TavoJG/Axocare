import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import AgentChat from "./AgentChat.vue";

const submit = vi.fn().mockResolvedValue(undefined);
const cancel = vi.fn();
const clear = vi.fn();

vi.mock("../useAgentChat", () => ({
  useAgentChat: () => ({
    messages: ref([]),
    processing: ref(false),
    status: ref(""),
    error: ref(null),
    submit,
    cancel,
    clear
  })
}));

describe("AgentChat", () => {
  beforeEach(() => {
    submit.mockClear();
    cancel.mockClear();
    clear.mockClear();
  });

  it("submits on Enter and preserves Shift+Enter for multiline input", async () => {
    const wrapper = mount(AgentChat);
    const textarea = wrapper.get("textarea");

    await textarea.setValue("How is the tank?");
    await textarea.trigger("keydown", { key: "Enter" });
    expect(submit).toHaveBeenCalledWith("How is the tank?");

    await textarea.setValue("Line one");
    await textarea.trigger("keydown", { key: "Enter", shiftKey: true });
    expect(submit).toHaveBeenCalledTimes(1);
  });
});
