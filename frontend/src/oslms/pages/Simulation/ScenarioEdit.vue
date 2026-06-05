<template>
	<ScenarioEditor
		:scenarioName="name || ''"
		:initialCourse="name ? '' : courseQuery"
		@saved="goBack"
	/>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ScenarioEditor from '@/oslms/components/simulations/ScenarioEditor.vue'

const props = defineProps({
	name: { type: String, default: '' },
})

const route = useRoute()
const router = useRouter()

const courseQuery = computed(() => String(route.query.course || ''))
const fromQuery = computed(() => String(route.query.from || ''))

function goBack(result) {
	if (fromQuery.value === 'admin') {
		router.push({ name: 'InstructorReports', query: { tab: 'scenarios' } })
		return
	}
	const courseName = result?.lms_course || courseQuery.value
	if (courseName) {
		router.push({
			name: 'CourseDetail',
			params: { courseName },
		})
		return
	}
	router.push({ name: 'InstructorReports' })
}
</script>
