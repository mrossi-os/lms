<template>
	<div
		v-if="aiContext.isActive"
		class="fixed bottom-20 end-6 z-50 flex flex-col gap-3 sm:bottom-6"
	>
		<AiChatButton
			v-if="aiEnabled"
			:course="aiContext.course"
			:lesson="aiContext.lesson"
		/>
		<SimulationLauncherButton
			v-if="simulationsEnabled"
			:course="aiContext.course ?? ''"
			:lesson="aiContext.lesson ?? ''"
		/>
	</div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AiChatButton from '@/oslms/components/ai/AiChatButton.vue'
import SimulationLauncherButton from '@/oslms/components/simulations/SimulationLauncherButton.vue'
import { useAiContext } from '@/stores/aiContext'
import { useSettings } from '@/stores/settings'

const settings = useSettings()
const aiContext = useAiContext()

const aiEnabled = computed<boolean>(
	() => Boolean(settings.settings?.data?.ai_enabled),
)
const simulationsEnabled = computed<boolean>(
	() => Boolean(settings.settings?.data?.simulations_enabled),
)
</script>
