<template>
	<div class="border rounded-lg p-4 bg-surface-gray-1">
		<div class="flex items-center justify-between mb-3">
			<h3 class="text-sm font-medium text-ink-gray-9">
				{{ __('AI Assistant') }}
			</h3>
			<component
				:is="statusIcon"
				class="w-4 h-4"
				:class="statusIconClass"
			/>
		</div>

		<div class="text-xs text-ink-gray-5 mb-3">
			<template v-if="status === 'not_ingested'">
				{{ __('Content not indexed. Index to enable AI chat.') }}
			</template>
			<template v-else-if="status === 'pending'">
				{{ __('Indexing in progress...') }}
			</template>
			<template v-else-if="status === 'completed'">
				<span v-if="needsUpdate" class="text-amber-600">
					{{ __('Content changed. Re-index to update.') }}
				</span>
				<span v-else>
					{{ __('Indexed') }}
					<span v-if="chunkCount"> ({{ chunkCount }} {{ __('chunks') }})</span>
					<span v-if="lastIngestedOn">
						· {{ formatDate(lastIngestedOn) }}
					</span>
				</span>
			</template>
			<template v-else-if="status === 'failed'">
				{{ __('Indexing failed. Try again.') }}
			</template>
		</div>

		<Button
			:variant="needsUpdate || status !== 'completed' ? 'solid' : 'outline'"
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
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { Button, createResource } from 'frappe-ui'
import { CircleDot, CheckCircle, AlertCircle, Clock } from 'lucide-vue-next'

const props = defineProps({
	lessonId: {
		type: String,
		default: null,
	},
})

const status = ref('not_ingested')
const chunkCount = ref(0)
const lastIngestedOn = ref(null)
const needsUpdate = ref(false)
const isIngesting = ref(false)
let pollInterval = null

const statusIcon = computed(() => {
	switch (status.value) {
		case 'completed':
			return needsUpdate.value ? AlertCircle : CheckCircle
		case 'pending':
			return Clock
		case 'failed':
			return AlertCircle
		default:
			return CircleDot
	}
})

const statusIconClass = computed(() => {
	switch (status.value) {
		case 'completed':
			return needsUpdate.value ? 'text-amber-500' : 'text-green-500'
		case 'pending':
			return 'text-blue-500 animate-pulse'
		case 'failed':
			return 'text-red-500'
		default:
			return 'text-ink-gray-4'
	}
})

const formatDate = (dateStr) => {
	if (!dateStr) return ''
	const date = new Date(dateStr)
	return date.toLocaleDateString(undefined, {
		month: 'short',
		day: 'numeric',
		hour: '2-digit',
		minute: '2-digit',
	})
}

const normalizeStatus = (value) => {
        switch (value) {
                case 'ready':
                case 'completed':
                        return 'completed'
                case 'processing':
                case 'pending':
                        return 'pending'
                case 'failed':
                        return 'failed'
                case 'not_ingested':
                        return 'not_ingested'
                default:
                        return value || 'not_ingested'
        }
}

const ingestionStatus = createResource({
        url: 'lms.lms.ai.api.get_lesson_ingestion_status',
        makeParams() {
                return { lesson_id: props.lessonId }
        },
        onSuccess(data) {
                status.value = normalizeStatus(data.status)
                chunkCount.value = data.chunk_count || 0
                lastIngestedOn.value = data.last_ingested_on
                needsUpdate.value = data.needs_update || false

                if (status.value === 'pending' && !pollInterval) {
                        startPolling()
                } else if (status.value !== 'pending' && pollInterval) {
                        stopPolling()
                }
        },
})

const ingestionTrigger = createResource({
	url: 'lms.lms.ai.api.start_lesson_ingestion',
	makeParams() {
		return { lesson_id: props.lessonId }
	},
        onSuccess(data) {
                isIngesting.value = false
                if (data.status === 'success' || data.status === 'completed') {
                        status.value = 'completed'
                        chunkCount.value = data.chunk_count || 0
                        needsUpdate.value = false
                        lastIngestedOn.value = new Date().toISOString()
                } else {
                        status.value = normalizeStatus(data.status || 'failed')
                        if (data.status === 'unchanged') {
                                ingestionStatus.fetch()
                        }
                }
        },
	onError() {
		isIngesting.value = false
		status.value = 'failed'
	},
})

const startIngestion = () => {
	if (!props.lessonId) return
	isIngesting.value = true
	status.value = 'pending'
	ingestionTrigger.submit()
}

const startPolling = () => {
	pollInterval = setInterval(() => {
		if (props.lessonId) {
			ingestionStatus.fetch()
		}
	}, 3000)
}

const stopPolling = () => {
	if (pollInterval) {
		clearInterval(pollInterval)
		pollInterval = null
	}
}

watch(
	() => props.lessonId,
	(newId) => {
		if (newId) {
			ingestionStatus.fetch()
		} else {
			status.value = 'not_ingested'
			chunkCount.value = 0
			lastIngestedOn.value = null
			needsUpdate.value = false
		}
	},
	{ immediate: true }
)

onMounted(() => {
	if (props.lessonId) {
		ingestionStatus.fetch()
	}
})

onUnmounted(() => {
	stopPolling()
})
</script>
