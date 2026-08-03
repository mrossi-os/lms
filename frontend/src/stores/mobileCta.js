import { defineStore } from 'pinia'
import { ref } from 'vue'

// OSLMS-CUSTOM: tracks whether the current page renders a fixed bottom CTA bar on
// mobile (e.g. CourseOverview's "Continue Learning" bar). Global floating UI such
// as AiFixedButtons reads this to lift itself above the bar instead of overlapping.
export const useMobileCta = defineStore('mobile-cta', () => {
	const barVisible = ref(false)

	function setBar(visible) {
		barVisible.value = Boolean(visible)
	}

	return { barVisible, setBar }
})
