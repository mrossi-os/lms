<template>
	<div>
		<Transition name="ai-panel">
			<div
				v-if="isOpen"
				class="fixed bottom-24 end-6 z-50 w-[380px] max-w-[calc(100vw-3rem)] max-h-[70vh] flex flex-col bg-surface-white shadow-2xl rounded-lg border border-outline-gray-2 overflow-hidden"
			>
				<div class="flex items-center justify-between px-4 py-2 border-b border-outline-gray-2 bg-surface-gray-1">
					<div class="flex items-center gap-2 text-sm font-medium text-ink-gray-9">
						<Sparkles class="size-4 stroke-1.5" />
						{{ __('AI Assistant') }}
					</div>
					<div class="flex items-center gap-2">
						<button
							type="button"
							class="text-ink-gray-5 hover:text-ink-red-3 transition disabled:opacity-40 disabled:cursor-not-allowed"
							:aria-label="__('Clear chat')"
							:disabled="!chat.messages.length"
							@click="clearChat"
						>
							<Trash2 class="size-4 stroke-1.5" />
						</button>
						<button
							type="button"
							class="text-ink-gray-5 hover:text-ink-gray-9 transition"
							:aria-label="__('Close')"
							@click="close"
						>
							<X class="size-4 stroke-1.5" />
						</button>
					</div>
				</div>
				<div class="flex-1 min-h-0 overflow-y-auto">
					<ChatBot
						:courseId="aiContext.course ?? ''"
						:lessonId="aiContext.lesson ?? ''"
					/>
				</div>
			</div>
		</Transition>

		<button
			type="button"
			class="flex h-12 w-12 items-center justify-center rounded-full shadow-lg transition focus:outline-none focus:ring-2 focus:ring-offset-2"
			:class="
				isOpen
					? 'bg-surface-gray-6 text-ink-white'
					: 'bg-surface-gray-7 text-ink-white hover:bg-surface-gray-6'
			"
			:aria-label="isOpen ? __('Close AI assistant') : __('Open AI assistant')"
			:aria-expanded="isOpen"
			@click="toggle"
		>
			<Sparkles class="size-5 stroke-1.5" />
		</button>
	</div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Sparkles, Trash2, X } from 'lucide-vue-next'
import ChatBot from '@/oslms/components/ai/ChatBot.vue'
import { useAiContext } from '@/stores/aiContext'
import { useAiChat } from '@/stores/aiChat'

const aiContext = useAiContext()
const chat = useAiChat()
const isOpen = ref<boolean>(false)

function clearChat(): void {
	chat.clear()
}

function toggle(): void {
	isOpen.value = !isOpen.value
}

function close(): void {
	isOpen.value = false
}

defineExpose({ isOpen, toggle, close })
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
