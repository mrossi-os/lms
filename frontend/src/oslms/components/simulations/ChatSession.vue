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
			<Badge v-if="status" :label="status" :theme="statusTheme" />
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
					>⚠️</span>
				</div>
				<div>{{ turn.text_content }}</div>
			</div>
			<div v-if="sending" class="flex items-center gap-2 text-ink-gray-5 text-sm">
				<span class="animate-pulse">…</span>
				<span>{{ __('Il personaggio sta rispondendo') }}</span>
			</div>
		</div>

		<!-- Input -->
		<div v-if="!readOnly && !isTerminal" class="border-t p-3">
			<div class="flex items-end gap-2">
				<textarea
					v-model="draft"
					rows="2"
					:placeholder="__('Scrivi al personaggio… (Cmd/Ctrl+Enter per inviare)')"
					class="flex-1 resize-none rounded-md border border-outline-gray-2 px-3 py-2 text-sm focus:border-outline-gray-3 focus:outline-none"
					:disabled="sending"
					@keydown.meta.enter.prevent="onSend"
					@keydown.ctrl.enter.prevent="onSend"
				/>
				<Button
					variant="solid"
					:loading="sending"
					:disabled="!draft.trim()"
					@click="onSend"
				>
					{{ __('Invia') }}
				</Button>
			</div>
		</div>
		<div v-else-if="readOnly" class="border-t px-4 py-3 text-xs text-ink-gray-5">
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

const props = defineProps({
	scenarioName: { type: String, default: '' },
	persona: { type: Object, default: null }, // parsed generated_persona
	turns: { type: Array, default: () => [] },
	status: { type: String, default: 'In Progress' },
	sending: { type: Boolean, default: false },
	ending: { type: Boolean, default: false },
	readOnly: { type: Boolean, default: false },
})

const emit = defineEmits(['send', 'end'])

const draft = ref('')
const scroller = ref(null)

const personaSummary = computed(() => {
	const p = props.persona
	if (!p) return ''
	const parts = [p.name, p.role && p.company ? `${p.role} di ${p.company}` : p.role || p.company]
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

const renderableTurns = computed(() =>
	(props.turns || []).filter((t) => t.role !== 'system'),
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
	if (!text || props.sending) return
	emit('send', text)
	draft.value = ''
}

function onEnd() {
	emit('end', 'completed')
}
</script>
