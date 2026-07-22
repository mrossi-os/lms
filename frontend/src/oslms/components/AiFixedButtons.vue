<template>
	<div
		v-if="aiContext.isActive"
		class="fixed end-3 z-50 flex flex-col gap-3"
		:class="
			mobileCta.barVisible ? 'bottom-36 sm:bottom-6' : 'bottom-20 sm:bottom-9'
		"
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
import { useMobileCta } from '@/stores/mobileCta'

const settings = useSettings()
const aiContext = useAiContext()
// OSLMS-CUSTOM: lift the floating AI buttons above a page's fixed bottom CTA bar
// (e.g. CourseOverview's "Continue Learning" bar) so they never overlap it.
const mobileCta = useMobileCta()

const aiEnabled = computed<boolean>(() =>
	Boolean(settings.settings?.data?.ai_enabled),
)
const simulationsEnabled = computed<boolean>(() =>
	Boolean(settings.settings?.data?.simulations_enabled),
)
</script>
