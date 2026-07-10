<template>
	<Button
		variant="ghost"
		:disabled="loading"
		:aria-label="label"
		:title="label"
		@click="onClick"
		class="!bg-surface-gray-3 hover:!bg-surface-gray-3 active:!bg-surface-gray-3"
	>
		<template #icon>
			<LoadingIndicator v-if="loading" class="w-4 h-4" />
			<CircleStop v-else-if="playing" class="w-4 h-4 text-ink-blue-3" />
			<Volume2 v-else class="w-4 h-4" />
		</template>
	</Button>
</template>

<script setup>
import { computed } from 'vue'
import { Button, LoadingIndicator } from 'frappe-ui'
import { Volume2, CircleStop } from 'lucide-vue-next'
import { useTextToSpeech } from '@/oslms/composables/useTextToSpeech'

const props = defineProps({
	text: { type: String, required: true },
	id: { type: [String, Number], required: true },
	voice: { type: String, default: '' },
})

const { playingId, play, isLoading } = useTextToSpeech()

const playing = computed(() => playingId.value === props.id)
const loading = computed(() => isLoading(props.id))
const label = computed(() =>
	loading.value
		? __('Preparing audio…')
		: playing.value
			? __('Stop')
			: __('Read aloud'),
)

function onClick() {
	play(props.text, props.id, props.voice ? { voice: props.voice } : {})
}
</script>
