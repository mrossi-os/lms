<template>
	<!-- Voice runtime overlay (phase 2, voice): mounted once a session is
	     prepared and the student chose "Avvia voce". -->
	<Dialog
		v-if="voiceSessionId"
		v-model="voiceDialogOpen"
		:options="{ title: __('Simulazione vocale'), size: 'lg' }"
	>
		<template #body-content>
			<VoiceSession :session-id="voiceSessionId" @ended="onVoiceEnded" />
		</template>
	</Dialog>

	<Dialog
		v-model="visible"
		:options="{
			title: dialogTitle,
			size: 'lg',
		}"
	>
		<template #body-content>
			<!-- Phase 1: scenario selection -->
			<template v-if="step === 'select'">
				<div v-if="!scenarios?.length" class="text-sm text-ink-gray-5 py-4">
					{{ __('Nessuno scenario disponibile per questa lezione.') }}
				</div>
				<div v-else class="space-y-3">
					<!-- Selectable scenario card. It's a div (not a button) so the
					     "Tentativi" button can live inside it without nesting
					     interactive <button> elements; keyboard access is kept via
					     role/tabindex + enter/space handlers. -->
					<div
						v-for="sc in scenarios"
						:key="sc.name"
						role="button"
						:tabindex="preparing ? -1 : 0"
						class="w-full text-left border border-outline-gray-2 rounded-md p-3 hover:bg-surface-gray-1 flex items-center gap-3"
						:class="{
							'ring-2 ring-outline-gray-3': sc.name === selected,
							'opacity-50 pointer-events-none': preparing,
						}"
						@click="selected = sc.name"
						@keydown.enter="selected = sc.name"
						@keydown.space.prevent="selected = sc.name"
					>
						<div class="flex-1 min-w-0">
							<div class="font-medium text-ink-gray-9">
								{{ sc.scenario_name }}
							</div>
							<div class="text-xs text-ink-gray-5 mt-1 flex gap-3">
								<Badge :label="sc.difficulty" :theme="difficultyTheme(sc.difficulty)" />
								<span class="capitalize">{{ sc.modality }}</span>
							</div>
						</div>
						<!-- Per-scenario shortcut to the student's past attempts + scores.
						     @click.stop keeps it from also selecting the scenario. -->
						<Button
							variant="outline"
							size="sm"
							:disabled="preparing"
							@click.stop="viewAttempts(sc)"
						>
							<template #prefix><History class="size-4" /></template>
							{{ __('Tentativi') }}
						</Button>
					</div>
				</div>
			</template>

			<!-- Phase 1b: past attempts for a scenario -->
			<template v-else-if="step === 'attempts'">
				<div class="mb-3">
					<div class="text-xs text-ink-gray-5">
						{{ __('Tentativi precedenti') }}
					</div>
					<div class="font-medium text-ink-gray-9">
						{{ attemptsScenario?.scenario_name }}
					</div>
				</div>
				<div v-if="sessionsRes.loading" class="text-sm text-ink-gray-5 py-4">
					{{ __('Caricamento…') }}
				</div>
				<div
					v-else-if="!sessionsRes.data?.length"
					class="text-sm text-ink-gray-5 py-4"
				>
					{{ __('Non hai ancora svolto questo scenario.') }}
				</div>
				<table v-else class="w-full text-sm">
					<thead class="text-left text-ink-gray-5">
						<tr>
							<th class="py-2">{{ __('Data') }}</th>
							<th>{{ __('Modalità') }}</th>
							<th>{{ __('Stato') }}</th>
							<th>{{ __('Punteggio') }}</th>
							<th></th>
						</tr>
					</thead>
					<tbody class="text-ink-gray-9">
						<tr
							v-for="s in sessionsRes.data"
							:key="s.name"
							class="border-t border-outline-gray-1"
						>
							<td class="py-2">{{ formatDate(s.started_at) }}</td>
							<td class="capitalize">{{ s.modality }}</td>
							<td>
								<Badge :label="s.status" :theme="statusTheme(s.status)" />
							</td>
							<td>{{ formatScore(s.overall_score) }}</td>
							<td class="text-right">
								<Button
									v-if="isTerminal(s.status)"
									variant="subtle"
									size="sm"
									@click="goDebrief(s.name)"
								>
									{{ __('Rivedi') }}
								</Button>
							</td>
						</tr>
					</tbody>
				</table>
			</template>

			<!-- Phase 2: briefing -->
			<SimulationBriefing
				v-else
				:brief="brief"
				:modality="briefModality"
				:starting="beginning"
				@begin="onBegin"
			/>

			<div v-if="error" class="text-sm text-ink-red-3 mt-3">{{ error }}</div>
		</template>
		<template #actions>
			<div class="flex gap-2 justify-end">
				<Button
					v-if="step === 'briefing' || step === 'attempts'"
					@click="backToSelect"
				>
					{{ __('Indietro') }}
				</Button>
				<Button v-else @click="visible = false">{{ __('Annulla') }}</Button>
				<Button
					v-if="step === 'select'"
					variant="solid"
					:loading="preparing"
					:disabled="!selected"
					@click="onPrepare"
				>
					{{ __('Avvia') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Button, Dialog, createResource, toast } from 'frappe-ui'
import { History } from 'lucide-vue-next'
import VoiceSession from './VoiceSession.vue'
import SimulationBriefing from './SimulationBriefing.vue'
import { useSimulationBegin } from '../../composables/useSimulationBegin'

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	scenarios: { type: Array, default: () => [] },
	modality: { type: String, default: 'chat' },
})
const emit = defineEmits(['update:modelValue', 'started'])

const router = useRouter()

const selected = ref(null)
const preparing = ref(false)
const error = ref(null)
const step = ref('select') // select | attempts | briefing
const brief = ref('')
const preparedSessionId = ref(null)
const briefModality = ref('chat')
const attemptsScenario = ref(null)

const dialogTitle = computed(() => {
	if (step.value === 'briefing') return __('Preparati alla simulazione')
	if (step.value === 'attempts') return __('Tentativi precedenti')
	return __('Avvia una simulazione')
})

const { beginning, voiceSessionId, begin, clearVoice } = useSimulationBegin()

const voiceDialogOpen = computed({
	get: () => Boolean(voiceSessionId.value),
	set: (v) => {
		if (!v) clearVoice()
	},
})

const selectedScenario = computed(() =>
	props.scenarios?.find((sc) => sc.name === selected.value),
)

const visible = computed({
	get: () => props.modelValue,
	set: (v) => emit('update:modelValue', v),
})

watch(visible, (v) => {
	if (v) {
		selected.value = props.scenarios?.[0]?.name || null
		error.value = null
		step.value = 'select'
	}
})

const prepareRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.prepare_session',
	method: 'POST',
})

// Loaded on demand when the student opens a scenario's past attempts.
const sessionsRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.list_my_sessions',
	method: 'GET',
})

// A scenario declaring modality "both" is prepared as "voice" so the backend
// gate passes; the briefing then offers both chat and voice buttons.
function requestedModality(scMod) {
	if (scMod === 'both') return 'voice'
	return scMod || props.modality
}

async function onPrepare() {
	if (!selected.value) return
	preparing.value = true
	error.value = null
	try {
		const result = await prepareRes.submit({
			scenario_id: selected.value,
			modality: requestedModality(selectedScenario.value?.modality),
		})
		if (!result?.session_id) throw new Error(__('Preparazione fallita.'))
		preparedSessionId.value = result.session_id
		brief.value = result.brief
		briefModality.value = selectedScenario.value?.modality || 'chat'
		step.value = 'briefing'
		emit('started', result)
	} catch (e) {
		error.value = e.messages?.[0] || e.message || String(e)
		toast.error(error.value)
	} finally {
		preparing.value = false
	}
}

async function onBegin(mode) {
	if (mode === 'voice') visible.value = false
	await begin({ sessionId: preparedSessionId.value, mode })
}

function backToSelect() {
	step.value = 'select'
	error.value = null
}

function viewAttempts(sc) {
	attemptsScenario.value = sc
	error.value = null
	step.value = 'attempts'
	sessionsRes.submit({ scenario: sc.name })
}

function goDebrief(sessionId) {
	visible.value = false
	router.push({ name: 'SimulationDebrief', params: { sessionId } })
}

function onVoiceEnded() {
	clearVoice()
}

function difficultyTheme(diff) {
	return { easy: 'green', medium: 'blue', hard: 'orange' }[diff] || 'gray'
}

const TERMINAL = ['Completed', 'Abandoned', 'Error', 'Needs Review']
function isTerminal(status) {
	return TERMINAL.includes(status)
}

function statusTheme(status) {
	return (
		{
			Ready: 'gray',
			'In Progress': 'blue',
			Completed: 'green',
			Abandoned: 'orange',
			Error: 'red',
			'Needs Review': 'orange',
		}[status] || 'gray'
	)
}

function formatDate(dt) {
	if (!dt) return '—'
	const d = new Date(dt)
	const pad = (n) => String(n).padStart(2, '0')
	const date = `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`
	const time = `${pad(d.getHours())}:${pad(d.getMinutes())}`
	return `${date}, ${time}`
}

function formatScore(score) {
	return score != null ? `${score}/100` : '—'
}
</script>
