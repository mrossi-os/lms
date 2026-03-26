import { computed } from 'vue'
import { createResource, toast } from 'frappe-ui'
import { CircleDot, CheckCircle, AlertCircle, Loader } from 'lucide-vue-next'

function normalizeStatus(value) {
	switch (value) {
		case 'ready':
		case 'indexed':
			return 'indexed'
		case 'processing':
		case 'pending':
			return 'pending'
		case 'failed':
			return 'failed'
		default:
			return 'not_ingested'
	}
}

function formatDate(dateStr) {
	if (!dateStr) return ''
	const date = new Date(dateStr)
	return date.toLocaleDateString(undefined, {
		month: 'short',
		day: 'numeric',
		hour: '2-digit',
		minute: '2-digit',
	})
}

export function useLessonIngestion(lesson, { onSuccess } = {}) {
	const lessonId = computed(() => lesson.value?.name || null)

	const ingestionTrigger = createResource({
		url: 'os_lms.os_lms.ai.api.start_lesson_ingestion',
		makeParams() {
			return { lesson_id: lessonId.value }
		},
		onSuccess() {
			toast.success(
				__('Indexing in progress. Please refresh the page in a few minutes.'),
			)
			onSuccess?.()
		},
		onError(error) {
			toast.error(error.messages?.[0] || __('Indexing failed'))
		},
	})

	const isIngesting = computed(() => ingestionTrigger.loading)

	const status = computed(() => {
		if (isIngesting.value) return 'processing'
		return normalizeStatus(lesson.value?.index_status)
	})

	const lastIngestedOn = computed(() => lesson.value?.indexed_at || null)

	const statusIcon = computed(() => {
		if (isIngesting.value) return Loader
		switch (status.value) {
			case 'indexed':
				return CheckCircle
			case 'failed':
				return AlertCircle
			default:
				return CircleDot
		}
	})

	const statusIconClass = computed(() => {
		if (isIngesting.value) return 'text-blue-500 animate-pulse'
		switch (status.value) {
			case 'indexed':
				return 'text-green-500'
			case 'failed':
				return 'text-red-500'
			default:
				return 'text-ink-gray-4'
		}
	})

	const startIngestion = () => {
		if (!lessonId.value || isIngesting.value || status.value === 'processing')
			return
		ingestionTrigger.submit().catch(() => { })
	}

	return {
		lessonId,
		isIngesting,
		status,
		lastIngestedOn,
		statusIcon,
		statusIconClass,
		startIngestion,
		formatDate,
	}
}
