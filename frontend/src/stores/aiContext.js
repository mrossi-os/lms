import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export const useAiContext = defineStore('ai-context', () => {
	const course = ref(null)
	const lesson = ref(null)

	const isActive = computed(() => Boolean(course.value || lesson.value))

	function setContext({ course: courseName = null, lesson: lessonName = null } = {}) {
		course.value = courseName
		lesson.value = lessonName
	}

	function clearContext() {
		course.value = null
		lesson.value = null
	}

	return {
		course,
		lesson,
		isActive,
		setContext,
		clearContext,
	}
})
