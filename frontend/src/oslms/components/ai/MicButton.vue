<template>
	<Button
		v-if="isSupported"
		:variant="isRecording ? 'subtle' : 'ghost'"
		:theme="isRecording ? 'red' : 'gray'"
		:disabled="disabled || isTranscribing"
		:aria-label="label"
		:title="label"
		@click="toggle"
		:class="
			isRecording
				? ''
				: '!bg-surface-gray-3 hover:!bg-surface-gray-3 active:!bg-surface-gray-3'
		"
	>
		<template #icon>
			<LoadingIndicator v-if="isTranscribing" class="w-4 h-4" />
			<Square v-else-if="isRecording" class="w-4 h-4 animate-pulse" />
			<Mic v-else class="w-4 h-4" />
		</template>
	</Button>
</template>

<script setup>
import { computed } from 'vue'
import { Button, LoadingIndicator } from 'frappe-ui'
import { Mic, Square } from 'lucide-vue-next'
import { useSpeechToText } from '@/oslms/composables/useSpeechToText'

const props = defineProps({
	disabled: { type: Boolean, default: false },
	language: { type: String, default: 'it' },
})
const emit = defineEmits(['transcript'])

const { isRecording, isTranscribing, isSupported, toggle } = useSpeechToText({
	language: props.language,
	onTranscript: (text) => emit('transcript', text),
})

const label = computed(() =>
	isTranscribing.value
		? __('Transcribing…')
		: isRecording.value
			? __('Stop recording')
			: __('Record a question'),
)
</script>
