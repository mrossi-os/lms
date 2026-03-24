<template>
	<div class="flex items-center space-x-1.5">
		<span
			v-if="lastIngestedOn && status === 'indexed'"
			class="text-xs text-ink-gray-5 whitespace-nowrap"
		>
			{{ formatDate(lastIngestedOn) }}
		</span>
		<Tooltip :text="tooltipText" placement="top">
			<button
				class="flex items-center justify-center p-0.5 rounded hover:bg-surface-gray-3"
				:disabled="!lessonId || isIngesting || status === 'pending'"
				@click.prevent.stop="startIngestion"
			>
				<component
					:is="statusIcon"
					class="h-4 w-4"
					:class="[statusIconClass, { 'animate-spin': isIngesting }]"
				/>
			</button>
		</Tooltip>
	</div>
</template>

<script setup>
import { computed, toRef } from 'vue'
import { Tooltip } from 'frappe-ui'
import { useLessonIngestion } from '@/oslms/composables/useLessonIngestion'

const props = defineProps({
	lesson: {
		type: Object,
		default: null,
	},
})

const emit = defineEmits(['update'])

const {
	lessonId,
	isIngesting,
	status,
	lastIngestedOn,
	statusIcon,
	statusIconClass,
	startIngestion,
	formatDate,
} = useLessonIngestion(toRef(props, 'lesson'), {
	onSuccess: () => emit('update'),
})

const tooltipText = computed(() => {
	if (isIngesting.value) return __('Indexing in progress...')
	switch (status.value) {
		case 'indexed':
			return __('Indexed')
		case 'failed':
			return __('Indexing failed. Click to retry.')
		default:
			return __('Not indexed. Click to index for AI.')
	}
})
</script>
