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
			title: step === 'briefing' ? __('Preparati alla simulazione') : __('Avvia una simulazione'),
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
					<button
						v-for="sc in scenarios"
						:key="sc.name"
						type="button"
						:disabled="preparing"
						class="w-full text-left border border-outline-gray-2 rounded-md p-3 hover:bg-surface-gray-1 disabled:opacity-50"
						:class="{ 'ring-2 ring-outline-gray-3': sc.name === selected }"
						@click="selected = sc.name"
					>
						<div class="font-medium text-ink-gray-9">
							{{ sc.scenario_name }}
						</div>
						<div class="text-xs text-ink-gray-5 mt-1 flex gap-3">
							<Badge :label="sc.difficulty" :theme="difficultyTheme(sc.difficulty)" />
							<span class="capitalize">{{ sc.modality }}</span>
						</div>
					</button>
				</div>
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
				<Button v-if="step === 'briefing'" @click="backToSelect">
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
import { Badge, Button, Dialog, createResource, toast } from 'frappe-ui'
import VoiceSession from './VoiceSession.vue'
import SimulationBriefing from './SimulationBriefing.vue'
import { useSimulationBegin } from '../../composables/useSimulationBegin'

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	scenarios: { type: Array, default: () => [] },
	modality: { type: String, default: 'chat' },
})
const emit = defineEmits(['update:modelValue', 'started'])

const selected = ref(null)
const preparing = ref(false)
const error = ref(null)
const step = ref('select') // select | briefing
const brief = ref('')
const preparedSessionId = ref(null)
const briefModality = ref('chat')

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

function onVoiceEnded() {
	clearVoice()
}

function difficultyTheme(diff) {
	return { easy: 'green', medium: 'blue', hard: 'orange' }[diff] || 'gray'
}
</script>
