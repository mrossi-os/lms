<template>
	<div class="grid grid-cols-2 gap-5 w-5/6 mx-auto p-4">
		<div>
			<div class="flex items-center gap-3">
				<h3 class="text-sm font-medium text-ink-gray-9">
					{{ __('AI Assistant') }}
				</h3>
				<component :is="statusIcon" class="w-4 h-4" :class="statusIconClass" />
			</div>
			<div class="text-xs text-ink-gray-5 mb-3">
				<template v-if="status === 'not_ingested'">
					{{ __('Content not indexed. Index to enable AI chat.') }}
				</template>
				<template v-else-if="status === 'pending'">
					{{ __('Indexing in progress...') }}
				</template>
				<template v-else-if="status === 'indexed'">
					<span>
						{{ __('Indexed') }}
						<span v-if="lastIngestedOn">
							· {{ formatDate(lastIngestedOn) }}
						</span>
					</span>
				</template>
				<template v-else-if="status === 'failed'">
					{{ __('Indexing failed. Try again.') }}
				</template>
			</div>
		</div>
		<div>
			<Button
				:variant="status !== 'indexed' ? 'solid' : 'outline'"
				size="sm"
				class="w-full"
				:loading="isIngesting"
				:disabled="!lessonId || status === 'pending'"
				@click="startIngestion"
			>
				<template v-if="status === 'not_ingested'">
					{{ __('Index for AI') }}
				</template>
				<template v-else-if="status === 'pending'">
					{{ __('Indexing...') }}
				</template>
				<template v-else>
					{{ __('Re-index') }}
				</template>
			</Button>
		</div>
	</div>
</template>

<script setup>
import { toRef } from 'vue'
import { Button } from 'frappe-ui'
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
</script>
