<!-- frontend/src/oslms/components/simulations/SimulationBriefing.vue -->
<template>
	<div class="space-y-4">
		<div
			class="whitespace-pre-wrap text-sm text-ink-gray-8 border border-outline-gray-2 rounded-md p-4 bg-surface-gray-1"
		>
			{{ brief || __('Nessun briefing disponibile.') }}
		</div>
		<div class="flex gap-2 justify-end">
			<template v-if="modality === 'both'">
				<Button
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
				v-else
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
import { Button } from 'frappe-ui'

defineProps({
	brief: { type: String, default: '' },
	modality: { type: String, default: 'chat' },
	starting: { type: Boolean, default: false },
})
const emit = defineEmits(['begin'])
</script>
