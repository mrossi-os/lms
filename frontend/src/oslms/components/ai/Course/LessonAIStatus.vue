<template>
	<div class="flex items-center space-x-1.5">
		<span
			v-if="lastIngestedOn && status === 'completed'"
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
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { Tooltip, createResource } from 'frappe-ui'
import { CircleDot, CheckCircle, AlertCircle, Clock, Loader } from 'lucide-vue-next'

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
	if (isIngesting.value) return Loader
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
	if (isIngesting.value) return 'text-blue-500'
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

const tooltipText = computed(() => {
	if (isIngesting.value) return __('Indexing in progress...')
	switch (status.value) {
		case 'completed': {
			let text = needsUpdate.value
				? __('Content changed. Click to re-index.')
				: __('Indexed')
			if (chunkCount.value) {
				text += ` · ${chunkCount.value} ${__('chunks')}`
			}
			return text
		}
		case 'pending':
			return __('Indexing in progress...')
		case 'failed':
			return __('Indexing failed. Click to retry.')
		default:
			return __('Not indexed. Click to index for AI.')
	}
})

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
	url: 'os_lms.os_lms.ai.api.get_lesson_ingestion_status',
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
	url: 'os_lms.os_lms.ai.api.start_lesson_ingestion',
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
	if (!props.lessonId || isIngesting.value || status.value === 'pending') return
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
