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

	function setLesson(lessonName) {
		console.log(lessonName)
		lesson.value = lessonName
	}

	function clearContext() {
		course.value = null
		lesson.value = null
	}

	function syncFromRoute(route) {
		const params = route?.params ?? {}
		if (!params.courseName) {
			clearContext()
			return
		}
		course.value = params.courseName
		lesson.value = ''
	}

	return {
		course,
		lesson,
		isActive,
		setContext,
		clearContext,
		syncFromRoute,
		setLesson
	}
})
