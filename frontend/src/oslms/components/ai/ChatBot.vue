<template>
	<div
		v-if="settingsStore.settings?.data?.ai_enabled"
		class="flex flex-col h-full border-b p-4 card"
	>
		<div class="text-lg font-semibold mb-4 text-ink-gray-9">
			{{ __('AI Tutor') }}
		</div>
		<div
			ref="messagesContainer"
			id="messagesContainer"
			class="flex-1 overflow-y-auto space-y-4 mb-4 min-h-[200px] max-h-[400px]"
		>
			<div v-if="messages.length === 0" class="text-ink-gray-5 text-sm">
				{{
					__(
						'Ask a question about this lesson to get help from the AI assistant.',
					)
				}}
			</div>
			<div
				v-for="(message, index) in messages"
				:key="index"
				:class="[
					'p-3 rounded-lg',
					message.role === 'user'
						? 'bg-surface-gray-2 ml-8'
						: 'bg-blue-700 mr-8',
				]"
			>
				<div class="text-xs font-medium text-ink-gray-5 mb-1">
					{{ message.role === 'user' ? __('You') : __('AI Assistant') }}
				</div>
				<div
					v-if="message.role === 'assistant'"
					class="text-sm text-ink-gray-9 prose prose-sm max-w-none chatbot-markdown"
					v-html="renderMarkdown(message.content)"
				></div>
				<div v-else class="text-sm text-ink-gray-9 whitespace-pre-wrap">
					{{ message.content }}
				</div>
				<div
					v-if="message.sources && message.sources.length > 0"
					class="mt-2 pt-2 border-t border-outline-gray-2"
				>
					<div class="text-xs text-ink-gray-5 mb-1">
						{{ __('Sources:') }}
					</div>
					<div class="flex flex-wrap gap-1">
						<span
							v-for="(source, sIndex) in message.sources"
							:key="sIndex"
							class="text-xs bg-surface-gray-3 px-2 py-0.5 rounded"
						>
							{{ source }}
						</span>
					</div>
				</div>
			</div>
			<div v-if="isLoading" class="flex items-center space-x-2 p-3">
				<div class="animate-pulse flex space-x-1">
					<div class="w-2 h-2 bg-ink-gray-4 rounded-full"></div>
					<div
						class="w-2 h-2 bg-ink-gray-4 rounded-full animation-delay-200"
					></div>
					<div
						class="w-2 h-2 bg-ink-gray-4 rounded-full animation-delay-400"
					></div>
				</div>
				<span class="text-sm text-ink-gray-5">{{ __('Thinking...') }}</span>
			</div>
		</div>
		<div class="flex items-end space-x-2">
			<textarea
				v-model="question"
				:placeholder="__('Ask a question about this lesson...')"
				class="flex-1 resize-none rounded-md border border-outline-gray-2 px-3 py-2 text-sm focus:border-outline-gray-3 focus:outline-none"
				rows="2"
				@keydown.enter.exact.prevent="sendQuestion"
				:disabled="isLoading"
			></textarea>
			<Button
				variant="solid"
				@click="sendQuestion"
				:disabled="!question.trim() || isLoading"
			>
				<template #icon>
					<Send class="w-4 h-4" />
				</template>
			</Button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { Button, call, toast } from 'frappe-ui'
import { Send } from 'lucide-vue-next'
import { useSettings } from '@/stores/settings'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({
	html: false,
	linkify: true,
	breaks: true,
})

const renderMarkdown = (text: string): string => md.render(text || '')

const settingsStore = useSettings()

interface Message {
	role: 'user' | 'assistant'
	content: string
	sources?: string[]
}

const props = defineProps<{
	courseId: string
	lessonId: string
}>()

const messages = ref<Message[]>([])
const question = ref('')
const isLoading = ref(false)
const messagesContainer = ref<HTMLElement | null>(null)

const scrollToBottom = () => {
	nextTick(() => {
		if (messagesContainer.value) {
			messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
		}
	})
}

const sendQuestion = async () => {
	const trimmedQuestion = question.value.trim()
	if (!trimmedQuestion || isLoading.value) return

	messages.value.push({
		role: 'user',
		content: trimmedQuestion,
	})
	question.value = ''
	isLoading.value = true
	scrollToBottom()

	try {
		const response = await call('os_lms.os_lms.ai.api.ask_lmsa_chat', {
			lesson_id: props.lessonId,
			question: trimmedQuestion,
		})

		messages.value.push({
			role: 'assistant',
			content: response.answer || __('Sorry, I could not find an answer.'),
			sources: [],
		})
	} catch (error: any) {
		const errorMessage =
			error?.message || error?.exc || __('Failed to get response')
		messages.value.push({
			role: 'assistant',
			content: __('Error: ') + errorMessage,
		})
		toast.error(errorMessage)
	} finally {
		isLoading.value = false
		scrollToBottom()
	}
}
</script>

<style scoped>
.animation-delay-200 {
	animation-delay: 0.2s;
}
.animation-delay-400 {
	animation-delay: 0.4s;
}
.chatbot-markdown {
	overflow-wrap: anywhere;
	word-break: break-word;
}
.chatbot-markdown :deep(pre),
.chatbot-markdown :deep(code) {
	white-space: pre-wrap;
	overflow-wrap: anywhere;
	word-break: break-word;
}
.chatbot-markdown :deep(a) {
	overflow-wrap: anywhere;
}
.chatbot-markdown :deep(p) {
	margin: 0 0 0.5rem;
}
.chatbot-markdown :deep(p:last-child) {
	margin-bottom: 0;
}
.chatbot-markdown :deep(ul),
.chatbot-markdown :deep(ol) {
	padding-left: 1.25rem;
	margin: 0.25rem 0;
}
.chatbot-markdown :deep(code) {
	background: rgba(0, 0, 0, 0.15);
	padding: 0.1rem 0.3rem;
	border-radius: 3px;
	font-size: 0.85em;
}
.chatbot-markdown :deep(strong) {
	font-weight: 600;
}
.chatbot-markdown :deep(a) {
	text-decoration: underline;
}
</style>
