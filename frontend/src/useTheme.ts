import { onBeforeUnmount, onMounted, ref } from "vue";

export type ThemePreference = "system" | "light" | "dark";
export type ResolvedTheme = "light" | "dark";

const STORAGE_KEY = "axocare-theme-preference";
const MEDIA_QUERY = "(prefers-color-scheme: dark)";

function isThemePreference(value: string | null): value is ThemePreference {
  return value === "system" || value === "light" || value === "dark";
}

function resolveTheme(preference: ThemePreference, mediaQuery?: MediaQueryList): ResolvedTheme {
  if (preference === "light" || preference === "dark") return preference;
  return mediaQuery?.matches ? "dark" : "light";
}

function applyTheme(theme: ResolvedTheme): void {
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

function readStoredPreference(storage?: Storage): ThemePreference {
  const stored = storage?.getItem(STORAGE_KEY) ?? null;
  return isThemePreference(stored) ? stored : "system";
}

export function initializeTheme(storage?: Storage, matchMediaFn?: typeof window.matchMedia): ThemePreference {
  if (typeof document === "undefined") return "system";
  const preference = readStoredPreference(storage ?? window.localStorage);
  const mediaQuery = (matchMediaFn ?? window.matchMedia.bind(window))(MEDIA_QUERY);
  applyTheme(resolveTheme(preference, mediaQuery));
  return preference;
}

export function useTheme(storage?: Storage, matchMediaFn?: typeof window.matchMedia) {
  const resolvedMatchMedia = matchMediaFn ?? window.matchMedia.bind(window);
  const resolvedStorage = storage ?? window.localStorage;
  const preference = ref<ThemePreference>("system");
  const resolvedTheme = ref<ResolvedTheme>("light");
  let mediaQuery: MediaQueryList | null = null;

  function syncTheme(): void {
    resolvedTheme.value = resolveTheme(preference.value, mediaQuery ?? undefined);
    applyTheme(resolvedTheme.value);
  }

  function handleSystemThemeChange(): void {
    if (preference.value === "system") syncTheme();
  }

  function setPreference(nextPreference: ThemePreference): void {
    preference.value = nextPreference;
    resolvedStorage.setItem(STORAGE_KEY, nextPreference);
    syncTheme();
  }

  onMounted(() => {
    preference.value = readStoredPreference(resolvedStorage);
    mediaQuery = resolvedMatchMedia(MEDIA_QUERY);
    syncTheme();
    mediaQuery.addEventListener("change", handleSystemThemeChange);
  });

  onBeforeUnmount(() => mediaQuery?.removeEventListener("change", handleSystemThemeChange));

  return { preference, resolvedTheme, setPreference };
}
