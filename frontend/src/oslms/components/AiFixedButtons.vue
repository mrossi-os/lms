<template>
	<div v-if="aiContext.isActive">
		<Transition name="ai-panel">
			<div
				v-if="openPanel"
				class="fixed bottom-24 end-6 z-50 w-[380px] max-w-[calc(100vw-3rem)] max-h-[70vh] flex flex-col bg-surface-white shadow-2xl rounded-lg border border-outline-gray-2 overflow-hidden"
			>
				<div class="flex items-center justify-between px-4 py-2 border-b border-outline-gray-2 bg-surface-gray-1">
					<div class="flex items-center gap-2 text-sm font-medium text-ink-gray-9">
						<component :is="activeButton?.icon" class="size-4 stroke-1.5" />
						{{ activeButton ? __(activeButton.label) : '' }}
					</div>
					<button
						type="button"
						class="text-ink-gray-5 hover:text-ink-gray-9 transition"
						:aria-label="__('Close')"
						@click="closePanel"
					>
						<X class="size-4 stroke-1.5" />
					</button>
				</div>
				<div class="flex-1 min-h-0 overflow-y-auto">
					<ChatBot
						v-if="openPanel === 'chat'"
						:courseId="aiContext.course ?? ''"
						:lessonId="aiContext.lesson ?? ''"
					/>
				</div>
			</div>
		</Transition>

		<div class="fixed bottom-6 end-6 z-50 flex flex-col gap-3">
			<button
				v-for="button in buttons"
				:key="button.key"
				type="button"
				class="flex h-12 w-12 items-center justify-center rounded-full shadow-lg transition focus:outline-none focus:ring-2 focus:ring-offset-2"
				:class="
					openPanel === button.key
						? 'bg-surface-gray-6 text-ink-white'
						: 'bg-surface-gray-7 text-ink-white hover:bg-surface-gray-6'
				"
				:aria-label="__(button.label)"
				:aria-expanded="openPanel === button.key"
				@click="togglePanel(button.key)"
			>
				<component :is="button.icon" class="size-5 stroke-1.5" />
			</button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Component } from 'vue'
import { Sparkles, X } from 'lucide-vue-next'
import ChatBot from '@/oslms/components/ai/ChatBot.vue'
import { useAiContext } from '@/stores/aiContext'

type PanelKey = 'chat'

interface ButtonDef {
	key: PanelKey
	label: string
	icon: Component
}

const aiContext = useAiContext()

const buttons: ButtonDef[] = [
	{ key: 'chat', label: 'AI Assistant', icon: Sparkles },
]

const openPanel = ref<PanelKey | null>(null)

const activeButton = computed<ButtonDef | null>(() => {
	if (!openPanel.value) return null
	return buttons.find((b) => b.key === openPanel.value) ?? null
})

function togglePanel(key: PanelKey): void {
	openPanel.value = openPanel.value === key ? null : key
}

function closePanel(): void {
	openPanel.value = null
}

defineExpose({ openPanel, togglePanel, closePanel })
</script>

<style scoped>
.ai-panel-enter-active,
.ai-panel-leave-active {
	transition: opacity 150ms ease, transform 150ms ease;
}
.ai-panel-enter-from,
.ai-panel-leave-to {
	opacity: 0;
	transform: translateY(8px);
}
</style>
