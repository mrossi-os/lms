<template>
	<div class="flex flex-col h-full">
		<!-- Header -->
		<div class="border-b px-4 py-3 flex items-center gap-3">
			<div class="flex-1">
				<div class="text-base font-semibold text-ink-gray-9">
					{{ scenarioName || __('Simulazione') }}
				</div>
				<div class="text-xs text-ink-gray-5">
					{{ personaSummary || __('Personaggio') }}
				</div>
			</div>
			<div
				v-if="showBudget"
				class="flex items-center gap-1 text-xs tabular-nums"
				:class="budgetLow ? 'text-ink-orange-6' : 'text-ink-gray-5'"
				:title="
					timeUp
						? __('Tempo scaduto: concludi la conversazione e premi Termina')
						: __('Tempo rimanente')
				"
			>
				<Clock class="w-3.5 h-3.5" />
				<span v-if="timeUp">{{ __('Tempo scaduto') }}</span>
				<span v-else>{{ formattedRemainingTime }}</span>
			</div>
			<Badge v-if="status" :label="statusLabel" :theme="statusTheme" />
			<Button
				v-if="!readOnly && !isTerminal"
				variant="outline"
				size="sm"
				@click="onEnd"
				:loading="ending"
			>
				{{ __('Termina') }}
			</Button>
		</div>

		<!-- Messages -->
		<div ref="scroller" class="flex-1 overflow-y-auto px-4 py-4 space-y-3">
			<div
				v-for="turn in renderableTurns"
				:key="turn.name || turn.turn_index"
				:class="[
					'max-w-[80%] rounded-lg px-3 py-2 text-sm whitespace-pre-wrap',
					turn.role === 'user'
						? 'bg-surface-blue-3 text-white ml-auto'
						: 'bg-surface-gray-2 text-ink-gray-9 mr-auto',
				]"
			>
				<div
					:class="[
						'text-xs mb-1 flex items-center gap-2',
						turn.role === 'user' ? 'text-white/80' : 'text-ink-gray-5',
					]"
				>
					<span>{{ turn.role === 'user' ? __('Tu') : rolePlayerLabel }}</span>
					<span
						v-if="turn.injection_attempt_detected"
						:class="turn.role === 'user' ? 'text-white' : 'text-ink-orange-5'"
						:title="__('Tentativo di prompt injection rilevato')"
						>⚠️</span
					>
				</div>
				<div v-if="turn._audioPending" class="flex items-center gap-2 text-ink-gray-5">
					<Mic class="w-4 h-4" />
					<span class="animate-pulse">…</span>
				</div>
				<div v-else>{{ turn.text_content }}</div>
				<SpeakButton
					v-if="ttsEnabled && turn.role !== 'user'"
					:text="turn.text_content"
					:id="turn.name || turn.turn_index"
					class="mt-1 -mb-1 shrink-0"
				/>
			</div>
			<div
				v-if="sending"
				class="flex items-center gap-2 text-ink-gray-5 text-sm"
			>
				<span class="animate-pulse">…</span>
				<span>{{ __('Il personaggio sta rispondendo') }}</span>
			</div>
		</div>

		<!-- Input -->
		<div v-if="!readOnly && !isTerminal" class="border-t p-3">
			<div v-if="inputLocked" class="mb-2 text-xs text-ink-orange-6">
				{{ __('Tempo scaduto. Premi «Termina» per concludere la simulazione.') }}
			</div>
			<div class="flex items-end gap-2">
				<textarea
					ref="inputEl"
					v-model="draft"
					rows="2"
					:placeholder="
						inputLocked
							? __('Tempo scaduto')
							: __('Scrivi al personaggio… (Cmd/Ctrl+Enter per inviare)')
					"
					class="flex-1 resize-none rounded-md border border-outline-gray-2 px-3 py-2 text-sm focus:border-outline-gray-3 focus:outline-none text-white disabled:opacity-60 disabled:cursor-not-allowed"
					:disabled="sending || inputLocked"
					@keydown.meta.enter.prevent="onSend"
					@keydown.ctrl.enter.prevent="onSend"
				/>
				<MicButton
					v-if="sttEnabled"
					raw
					:disabled="sending || inputLocked"
					class="shrink-0"
					@audio="$emit('send-audio', $event)"
				/>
				<Button
					variant="solid"
					:loading="sending"
					:disabled="!draft.trim() || inputLocked"
					@click="onSend"
				>
					{{ __('Invia') }}
				</Button>
			</div>
		</div>
		<div
			v-else-if="readOnly"
			class="border-t px-4 py-3 text-xs text-ink-gray-5"
		>
			{{ __('Sessione in sola lettura.') }}
		</div>
		<div v-else class="border-t px-4 py-3 text-xs text-ink-gray-5">
			{{ __('Sessione conclusa.') }}
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { Badge, Button } from 'frappe-ui'
import { Clock, Mic } from 'lucide-vue-next'
import { useSettings } from '@/stores/settings'
import MicButton from '@/oslms/components/ai/MicButton.vue'
import SpeakButton from '@/oslms/components/ai/SpeakButton.vue'

const props = defineProps({
	scenarioName: { type: String, default: '' },
	persona: { type: Object, default: null }, // parsed generated_persona
	turns: { type: Array, default: () => [] },
	status: { type: String, default: 'In Progress' },
	sending: { type: Boolean, default: false },
	ending: { type: Boolean, default: false },
	readOnly: { type: Boolean, default: false },
	// Time-based natural-close budget. null = no time cap configured.
	remainingSeconds: { type: Number, default: null },
	// True once the bot's closing replies are done: disable the textarea + send,
	// leaving only "Termina" (the session is not auto-ended).
	inputLocked: { type: Boolean, default: false },
})

// 'send' carries typed text; 'send-audio' carries a recorded Blob. The parent
// (useSimulationSession) decides which endpoint to call and drives playback.
const emit = defineEmits(['send', 'send-audio', 'end'])

const draft = ref('')
const scroller = ref(null)
const inputEl = ref(null)

// The textarea is disabled while `sending`, which drops focus. Restore it once
// the reply returns and the box is re-enabled, so the user can keep typing
// without clicking back in — unless the session has meanwhile become
// terminal/read-only (the textarea is then unmounted).
watch(
	() => props.sending,
	(isSending, was) => {
		if (
			was &&
			!isSending &&
			!props.readOnly &&
			!props.inputLocked &&
			!isTerminal.value
		) {
			nextTick(() => inputEl.value?.focus())
		}
	},
)

// Audio control visibility (mirrors the tutor). Playback + autoplay are handled
// upstream in useSimulationSession from the combined-endpoint response.
const settingsStore = useSettings()
const sttEnabled = computed(() =>
	Boolean(settingsStore.settings?.data?.stt_enabled),
)
const ttsEnabled = computed(() =>
	Boolean(settingsStore.settings?.data?.tts_enabled),
)

const personaSummary = computed(() => {
	const p = props.persona
	if (!p) return ''
	const parts = [
		p.name,
		p.role && p.company ? `${p.role} di ${p.company}` : p.role || p.company,
	]
	return parts.filter(Boolean).join(' — ')
})

const rolePlayerLabel = computed(() => props.persona?.name || __('Personaggio'))

const isTerminal = computed(() =>
	['Completed', 'Abandoned', 'Error', 'Needs Review'].includes(props.status),
)

const statusTheme = computed(() => {
	switch (props.status) {
		case 'In Progress':
			return 'blue'
		case 'Completed':
			return 'green'
		case 'Error':
			return 'red'
		case 'Needs Review':
			return 'orange'
		default:
			return 'gray'
	}
})

// Translate the backend status enum for display (the raw value drives logic).
const statusLabel = computed(
	() =>
		({
			Ready: __('Pronta'),
			'In Progress': __('In corso'),
			Completed: __('Completata'),
			Abandoned: __('Abbandonata'),
			Error: __('Errore'),
			'Needs Review': __('Da revisionare'),
		})[props.status] || props.status,
)

const renderableTurns = computed(() =>
	(props.turns || []).filter((t) => t.role !== 'system'),
)

// Time budget indicator: hidden once terminal and when no time cap is set.
const showBudget = computed(
	() => !isTerminal.value && props.remainingSeconds !== null,
)
const timeUp = computed(
	() => props.remainingSeconds !== null && Number(props.remainingSeconds) <= 0,
)
const formattedRemainingTime = computed(() => {
	const total = Math.max(0, Math.floor(Number(props.remainingSeconds) || 0))
	const m = Math.floor(total / 60)
	const s = total % 60
	return `${m}:${String(s).padStart(2, '0')}`
})
const budgetLow = computed(
	() => props.remainingSeconds !== null && Number(props.remainingSeconds) <= 60,
)

watch(
	() => props.turns.length,
	async () => {
		await nextTick()
		const el = scroller.value
		if (el) el.scrollTop = el.scrollHeight
	},
)

function onSend() {
	const text = draft.value.trim()
	if (!text || props.sending || props.inputLocked) return
	emit('send', text)
	draft.value = ''
}

function onEnd() {
	emit('end', 'completed')
}
</script>
