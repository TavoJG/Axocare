<script setup lang="ts">
import { formatTemperature, formatTime } from "../formatters";
import type { RelayEvent } from "../types";
defineProps<{ events: RelayEvent[] }>();
</script>
<template><div class="panel"><div class="panel-header"><div><p class="eyebrow">Relay events</p><h2>Cooling activity</h2></div></div><div class="events"><div v-if="!events.length" class="empty compact">No relay events recorded.</div><article v-for="event in events" v-else :key="event.id" class="event"><div><strong>{{ event.relay_on ? "Relay on" : "Relay off" }}</strong><span>{{ event.reason.replace(/_/g, " ") }}</span></div><div class="event-meta"><span>{{ formatTemperature(event.temperature_c) }}</span><time :datetime="event.recorded_at">{{ formatTime(event.recorded_at) }}</time></div></article></div></div></template>
