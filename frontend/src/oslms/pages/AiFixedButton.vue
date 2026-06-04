<template>
	<div>
		<Transition name="chat-fade">
			<div
				v-if="isOpen"
				class="fixed bottom-24 end-6 z-50 w-[380px] max-w-[calc(100vw-3rem)] max-h-[70vh] flex flex-col bg-surface-white shadow-2xl rounded-lg border border-outline-gray-2 overflow-hidden"
			>
				<div class="flex items-center justify-between px-4 py-2 border-b border-outline-gray-2 bg-surface-gray-1">
					<div class="flex items-center gap-2 text-sm font-medium text-ink-gray-9">
						<Sparkles class="size-4 stroke-1.5" />
						{{ __('AI Assistant') }}
					</div>
					<button
						type="button"
						class="text-ink-gray-5 hover:text-ink-gray-9 transition"
						:aria-label="__('Close AI assistant')"
						@click="close"
					>
						<X class="size-4 stroke-1.5" />
					</button>
				</div>
				<div class="flex-1 min-h-0 overflow-y-auto">
					<ChatBot :courseId="course" :lessonId="lesson ?? ''" />
				</div>
			</div>
		</Transition>

		<button
			type="button"
			class="fixed bottom-6 end-6 z-50 flex h-12 w-12 items-center justify-center rounded-full bg-surface-gray-7 text-ink-white shadow-lg transition hover:bg-surface-gray-6 focus:outline-none focus:ring-2 focus:ring-offset-2"
			:aria-label="isOpen ? __('Close AI assistant') : __('Open AI assistant')"
			@click="toggle"
		>
			<X v-if="isOpen" class="size-5 stroke-1.5" />
			<Sparkles v-else class="size-5 stroke-1.5" />
		</button>
	</div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Sparkles, X } from 'lucide-vue-next'
import ChatBot from '@/oslms/components/ai/ChatBot.vue'

const props = defineProps<{
	course: string
	lesson: string | null
}>()

const isOpen = ref<boolean>(false)

function toggle(): void {
	isOpen.value = !isOpen.value
}

function close(): void {
	isOpen.value = false
}

defineExpose({ isOpen, toggle, close })
</script>

<style scoped>
.chat-fade-enter-active,
.chat-fade-leave-active {
	transition: opacity 150ms ease, transform 150ms ease;
}
.chat-fade-enter-from,
.chat-fade-leave-to {
	opacity: 0;
	transform: translateY(8px);
}
</style>
