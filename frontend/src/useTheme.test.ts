import { defineComponent, nextTick } from "vue";
import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";
import { initializeTheme, useTheme, type ThemePreference } from "./useTheme";

function createMatchMedia(matches = false) {
  const listeners = new Set<() => void>();
  return {
    matchMedia: vi.fn(() => ({
      matches,
      media: "(prefers-color-scheme: dark)",
      onchange: null,
      addEventListener: vi.fn((_event: string, callback: () => void) => listeners.add(callback)),
      removeEventListener: vi.fn((_event: string, callback: () => void) => listeners.delete(callback)),
      addListener: vi.fn((callback: () => void) => listeners.add(callback)),
      removeListener: vi.fn((callback: () => void) => listeners.delete(callback)),
      dispatchEvent: vi.fn(() => true)
    }) as unknown as MediaQueryList),
    trigger(nextMatches: boolean) {
      matches = nextMatches;
      const mediaQuery = (this.matchMedia.mock.results[0]?.value ?? null) as MediaQueryList | null;
      if (mediaQuery) Object.defineProperty(mediaQuery, "matches", { configurable: true, value: nextMatches });
      listeners.forEach((listener) => listener());
    }
  };
}

afterEach(() => {
  window.localStorage.clear();
  delete document.documentElement.dataset.theme;
  document.documentElement.style.colorScheme = "";
});

function mountComposable(matchMediaFn: typeof window.matchMedia) {
  let state!: ReturnType<typeof useTheme>;
  mount(defineComponent({ setup() { state = useTheme(window.localStorage, matchMediaFn); return () => null; } }));
  return state;
}

describe("useTheme", () => {
  it("initializes from system preference by default", () => {
    const media = createMatchMedia(true);
    const preference = initializeTheme(window.localStorage, media.matchMedia);
    expect(preference).toBe<ThemePreference>("system");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.style.colorScheme).toBe("dark");
  });

  it("persists explicit selections", async () => {
    const media = createMatchMedia(false);
    const state = mountComposable(media.matchMedia);
    await nextTick();
    state.setPreference("dark");
    expect(state.preference.value).toBe("dark");
    expect(state.resolvedTheme.value).toBe("dark");
    expect(window.localStorage.getItem("axocare-theme-preference")).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("tracks system changes while in system mode", async () => {
    const media = createMatchMedia(false);
    const state = mountComposable(media.matchMedia);
    await nextTick();
    expect(state.resolvedTheme.value).toBe("light");
    media.trigger(true);
    await nextTick();
    expect(state.resolvedTheme.value).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});
