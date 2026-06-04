import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { useAiContext } from './aiContext'

export const useAiChat = defineStore('ai-chat', () => {
	const messages = ref([])
	const question = ref('')
	const isLoading = ref(false)
	const lastCourse = ref(null)

	const aiContext = useAiContext()

	// Reset only when the user moves between two different non-null courses.
	// Transitions through null (navigating away then back to the same course)
	// must preserve the conversation.
	watch(
		() => aiContext.course,
		(newCourse) => {
			if (!newCourse) return
			if (lastCourse.value && lastCourse.value !== newCourse) {
				clear()
			}
			lastCourse.value = newCourse
		},
		{ immediate: true },
	)

	function addMessage(message) {
		messages.value.push(message)
	}

	function clear() {
		messages.value = []
		question.value = ''
		isLoading.value = false
	}

	return {
		messages,
		question,
		isLoading,
		addMessage,
		clear,
	}
})
