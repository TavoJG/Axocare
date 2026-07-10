<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { ApiSettings } from "../types";

const props = defineProps<{ settings: ApiSettings }>();
const stream = ref<HTMLImageElement>();
const streamSrc = ref("");
const streamError = ref<string | null>(null);
let retryTimer: number | undefined;
let retryCount = 0;

function start(): void {
  window.clearTimeout(retryTimer);
  if (!props.settings.camera_stream_url) {
    streamSrc.value = "";
    streamError.value = "Camera stream URL not configured";
    return;
  }
  streamError.value = null;
  const url = new URL(props.settings.camera_stream_url, window.location.href);
  url.searchParams.set("t", String(Date.now()));
  streamSrc.value = url.toString();
}

function loaded(): void {
  window.clearTimeout(retryTimer);
  retryCount = 0;
  streamError.value = null;
}

function failed(): void {
  streamError.value = "Camera stream unavailable";
  const delay = Math.min(1000 * 2 ** retryCount, 15000);
  retryCount += 1;
  window.clearTimeout(retryTimer);
  retryTimer = window.setTimeout(() => {
    if (props.settings.camera_enabled && !document.hidden) start();
  }, delay);
}

function visibilityChanged(): void {
  if (!document.hidden && props.settings.camera_enabled) start();
}

watch(() => [props.settings.camera_enabled, props.settings.camera_stream_url], ([enabled]) => {
  retryCount = 0;
  if (enabled) start(); else { streamSrc.value = ""; streamError.value = null; }
}, { immediate: true });
onMounted(() => document.addEventListener("visibilitychange", visibilityChanged));
onBeforeUnmount(() => { window.clearTimeout(retryTimer); document.removeEventListener("visibilitychange", visibilityChanged); });
</script>

<template>
  <section v-if="settings.camera_enabled" class="panel camera-panel">
    <div class="panel-header"><div><p class="eyebrow">Live camera</p><h2>Tank view</h2></div><span class="muted">{{ settings.camera_width }}x{{ settings.camera_height }} at {{ settings.camera_fps }} fps</span></div>
    <div class="camera-frame">
      <div v-if="streamError" class="camera-error" role="status">{{ streamError }}</div>
      <img v-show="!streamError && streamSrc" ref="stream" :src="streamSrc || undefined" alt="Live aquarium camera stream" @load="loaded" @error="failed" />
    </div>
  </section>
</template>
