<template>
	<!--
		Voice-scenario path: rendered as a separate dialog overlay so the user
		gets a full session UI without navigating away. The chat path below is
		untouched.
	-->
	<Dialog
		v-if="voiceScenarioId"
		v-model="voiceDialogOpen"
		:options="{
			title: __('Simulazione vocale'),
			size: 'lg',
		}"
	>
		<template #body-content>
			<VoiceSession :scenario-id="voiceScenarioId" @ended="onVoiceEnded" />
		</template>
	</Dialog>

	<Dialog
		v-model="visible"
		:options="{
			title: __('Avvia una simulazione'),
			size: 'lg',
		}"
	>
		<template #body-content>
			<div v-if="!scenarios?.length" class="text-sm text-ink-gray-5 py-4">
				{{ __('Nessuno scenario disponibile per questa lezione.') }}
			</div>
			<div v-else class="space-y-3">
				<button
					v-for="sc in scenarios"
					:key="sc.name"
					type="button"
					:disabled="starting"
					class="w-full text-left border border-outline-gray-2 rounded-md p-3 hover:bg-surface-gray-1 disabled:opacity-50"
					:class="{
						'ring-2 ring-outline-gray-3': sc.name === selected,
					}"
					@click="selected = sc.name"
				>
					<div class="font-medium text-ink-gray-9">
						{{ sc.scenario_name }}
					</div>
					<div class="text-xs text-ink-gray-5 mt-1 flex gap-3">
						<Badge
							:label="sc.difficulty"
							:theme="difficultyTheme(sc.difficulty)"
						/>
						<span class="capitalize">{{ sc.modality }}</span>
						<span v-if="sc.time_limit_minutes">
							{{ sc.time_limit_minutes }} {{ __('min') }}
						</span>
					</div>
				</button>
			</div>
			<div v-if="error" class="text-sm text-ink-red-3 mt-3">
				{{ error }}
			</div>
		</template>
		<template #actions>
			<div class="flex gap-2 justify-end">
				<Button @click="visible = false">{{ __('Annulla') }}</Button>
				<Button
					variant="solid"
					:loading="starting"
					:disabled="!selected"
					@click="onStart"
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
import VoiceSession from './VoiceSession.vue'

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	scenarios: { type: Array, default: () => [] },
	modality: { type: String, default: 'chat' },
})
const emit = defineEmits(['update:modelValue', 'started'])

const router = useRouter()
const selected = ref(null)
const starting = ref(false)
const error = ref(null)

// Voice-scenario branch: scenario name while a voice session dialog is open.
const voiceScenarioId = ref(null)
const voiceDialogOpen = computed({
	get: () => Boolean(voiceScenarioId.value),
	set: (v) => {
		if (!v) voiceScenarioId.value = null
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
		// Default to the first scenario when the dialog opens.
		selected.value = props.scenarios?.[0]?.name || null
		error.value = null
	}
})

const startResource = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.start_session',
	method: 'POST',
})

async function onStart() {
	if (!selected.value) return

	// Branch: voice scenarios bypass start_session and open VoiceSession directly.
	if (selectedScenario.value?.modality === 'voice') {
		voiceScenarioId.value = selected.value
		visible.value = false
		return
	}

	starting.value = true
	error.value = null
	try {
		const result = await startResource.submit({
			scenario_id: selected.value,
			modality: props.modality,
		})
		if (!result?.session) throw new Error(__('Avvio fallito.'))
		emit('started', result)
		visible.value = false
		router.push({
			name: 'SimulationPlay',
			params: { sessionId: result.session },
		})
	} catch (e) {
		error.value = e.messages?.[0] || e.message || String(e)
		toast.error(error.value)
	} finally {
		starting.value = false
	}
}

function onVoiceEnded() {
	voiceScenarioId.value = null
}

function difficultyTheme(diff) {
	return { easy: 'green', medium: 'blue', hard: 'orange' }[diff] || 'gray'
}
</script>
