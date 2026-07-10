import { defineComponent, nextTick } from "vue";
import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { dashboard } from "./test/fixtures";
import { useDashboard } from "./useDashboard";

afterEach(() => vi.useRealTimers());

function mountComposable(fetcher: typeof fetch) {
  let state!: ReturnType<typeof useDashboard>;
  const wrapper = mount(defineComponent({ setup() { state = useDashboard(fetcher); return () => null; } }));
  return { wrapper, state };
}

describe("useDashboard", () => {
  it("loads the API with expected parameters and retains data after an error", async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => dashboard })
      .mockResolvedValueOnce({ ok: false, status: 503 });
    const { state } = mountComposable(fetcher as unknown as typeof fetch);
    await vi.waitFor(() => expect(state.dashboard.value).toEqual(dashboard));
    expect(fetcher.mock.calls[0][0]).toContain("span_minutes=60&event_limit=20");
    await state.load();
    expect(state.error.value).toBe("API returned 503");
    expect(state.dashboard.value).toEqual(dashboard);
  });

  it("uses a ten-second minimum polling interval and cleans it up", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn().mockResolvedValue({ ok: true, json: async () => dashboard });
    const { wrapper } = mountComposable(fetcher as unknown as typeof fetch);
    await Promise.resolve(); await Promise.resolve(); await nextTick();
    expect(fetcher).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(9999);
    expect(fetcher).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(fetcher).toHaveBeenCalledTimes(2);
    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(10000);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("continues polling after a failed request", async () => {
    vi.useFakeTimers();
    const fetcher = vi.fn()
      .mockResolvedValueOnce({ ok: false, status: 503 })
      .mockResolvedValue({ ok: true, json: async () => dashboard });
    mountComposable(fetcher as unknown as typeof fetch);
    await Promise.resolve(); await Promise.resolve(); await nextTick();
    await vi.advanceTimersByTimeAsync(10000);
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});
