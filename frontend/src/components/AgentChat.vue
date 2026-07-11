<script setup lang="ts">
import { nextTick, ref, watch } from "vue";
import { renderMarkdown } from "../markdown";
import { useAgentChat } from "../useAgentChat";

const question = ref("");
const log = ref<HTMLElement>();
const { messages, processing, status, error, submit, cancel, clear } = useAgentChat();

async function send(): Promise<void> {
  const value = question.value;
  if (!value.trim() || processing.value) return;
  question.value = "";
  await submit(value);
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== "Enter" || event.shiftKey) return;
  event.preventDefault();
  void send();
}

function assistantHtml(content: string): string {
  return renderMarkdown(content);
}

watch([messages, status, error], async () => {
  await nextTick();
  log.value?.scrollTo({ top: log.value.scrollHeight, behavior: "smooth" });
}, { deep: true });
</script>

<template>
  <section class="panel agent-panel">
    <div class="panel-header">
      <div><p class="eyebrow">Aquarium assistant</p><h2>Ask Axocare</h2></div>
      <button v-if="messages.length" type="button" class="button-secondary button-small" :disabled="processing" @click="clear">Clear</button>
    </div>
    <div ref="log" class="agent-log" aria-live="polite" aria-label="Agent conversation">
      <div v-if="!messages.length" class="agent-welcome">Ask about current conditions, temperature trends, cooling activity, or predictions.</div>
      <article v-for="(message, index) in messages" :key="index" class="agent-message" :class="message.role">
        <span>{{ message.role === "user" ? "You" : "Axocare" }}</span>
        <p v-if="message.role === 'user'" class="agent-text">{{ message.content }}</p>
        <div v-else class="agent-markdown" v-html="assistantHtml(message.content)"></div>
      </article>
      <div v-if="status" class="agent-status" role="status">{{ status }}</div>
      <div v-if="error" class="agent-error" role="alert">{{ error }}</div>
    </div>
    <form class="agent-form" @submit.prevent="send">
      <label for="agent-question" class="sr-only">Question for the aquarium assistant</label>
      <textarea id="agent-question" v-model="question" maxlength="4000" rows="2" placeholder="How is the aquarium right now?" :disabled="processing" @keydown="handleKeydown"></textarea>
      <button v-if="processing" type="button" class="button-secondary" @click="cancel">Stop</button>
      <button v-else type="submit" :disabled="!question.trim()">Ask</button>
    </form>
  </section>
</template>
