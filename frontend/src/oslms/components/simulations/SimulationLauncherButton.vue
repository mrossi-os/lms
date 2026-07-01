<template>
	<div>
		<SimulationLauncher
			v-model="isOpen"
			:scenarios="scenarios"
			modality="chat"
		/>

		<button
			type="button"
			class="flex h-12 w-12 items-center justify-center rounded-full bg-surface-gray-10 text-ink-base shadow-lg transition hover:bg-surface-gray-9 focus:outline-none focus:ring-2 focus:ring-offset-2"
			:aria-label="__('Start a simulation')"
			@click="open"
		>
			<Bot class="size-5 stroke-1.5" />
		</button>
	</div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { Bot } from 'lucide-vue-next'
import { createResource } from 'frappe-ui'
import SimulationLauncher from '@/oslms/components/simulations/SimulationLauncher.vue'

const props = defineProps<{
	course?: string
	lesson?: string
}>()

const isOpen = ref(false)

const scenariosRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.list_my_scenarios',
	makeParams() {
		return { course: props.course || null }
	},
})

const scenarios = computed<unknown[]>(
	() => (scenariosRes.data as unknown[]) || [],
)

function open(): void {
	scenariosRes.submit()
	isOpen.value = true
}

// Refetch when the course context changes while the dialog is open, so the
// user always sees the scenarios for the current course.
watch(
	() => props.course,
	() => {
		if (isOpen.value) scenariosRes.submit()
	},
)
</script>
