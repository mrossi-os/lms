<!-- frontend/src/oslms/components/simulations/SimulationBriefing.vue -->
<template>
	<div class="space-y-4">
		<div
			class="whitespace-pre-wrap text-sm text-ink-gray-8 border border-outline-gray-2 rounded-md p-4 bg-surface-gray-1"
		>
			{{ brief || __('Nessun briefing disponibile.') }}
		</div>
		<!-- The voice runtime hits create_voice_session, which is gated by the
		     global `realtime_enabled` flag. If it's off, don't offer voice: a
		     voice-only scenario shows an explanation instead of a dead button;
		     a "both" scenario silently falls back to chat only. -->
		<div v-if="voiceOnlyButUnavailable" class="text-sm text-ink-gray-5">
			{{ __('La modalità vocale non è al momento disponibile.') }}
		</div>
		<div class="flex gap-2 justify-end">
			<template v-if="modality === 'both'">
				<Button
					v-if="realtimeEnabled"
					variant="outline"
					:loading="starting"
					@click="emit('begin', 'voice')"
				>
					{{ __('Avvia voce') }}
				</Button>
				<Button
					variant="solid"
					:loading="starting"
					@click="emit('begin', 'chat')"
				>
					{{ __('Avvia chat') }}
				</Button>
			</template>
			<Button
				v-else-if="modality !== 'voice' || realtimeEnabled"
				variant="solid"
				:loading="starting"
				@click="emit('begin', modality)"
			>
				{{ modality === 'voice' ? __('Avvia voce') : __('Avvia chat') }}
			</Button>
		</div>
	</div>
</template>

<script setup>
import { computed } from 'vue'
import { Button } from 'frappe-ui'
import { useSettings } from '@/stores/settings'

const props = defineProps({
	brief: { type: String, default: '' },
	modality: { type: String, default: 'chat' },
	starting: { type: Boolean, default: false },
})
const emit = defineEmits(['begin'])

const settingsStore = useSettings()
const realtimeEnabled = computed(() =>
	Boolean(settingsStore.settings?.data?.realtime_enabled),
)
// A voice-only scenario the student can't start because realtime is disabled
// globally — surface a clear notice rather than an empty action row.
const voiceOnlyButUnavailable = computed(
	() => props.modality === 'voice' && !realtimeEnabled.value,
)
</script>
