<template>
	<div
		v-if="settingsStore.settings?.data?.ai_enabled"
		class="flex flex-col h-full  p-4"
	>
		<div
			ref="messagesContainer"
			id="messagesContainer"
			class="flex-1 overflow-y-auto space-y-4 mb-4 min-h-[200px] max-h-[400px] pr-1"
		>
			<div v-if="chat.messages.length === 0" class="text-ink-gray-5 text-sm">
				{{
					__(
						'Ask a question about this lesson to get help from the AI assistant.',
					)
				}}
			</div>
			<div
				v-for="(message, index) in chat.messages"
				:key="index"
				:class="[
					'p-3 rounded-lg',
					message.role === 'user'
						? 'bg-surface-gray-2 ml-8'
						: 'bg-surface-blue-3 mr-8',
				]"
			>
				<div class="text-xs font-medium text-ink-gray-5 mb-1">
					{{ message.role === 'user' ? __('You') : __('AI Assistant') }}
				</div>
				<div
					v-if="message.role === 'assistant'"
					class="flex items-end gap-1.5"
				>
					<div
						class="flex-1 text-sm text-ink-gray-9 prose prose-sm max-w-none chatbot-markdown"
						v-html="renderMarkdown(message.content)"
					></div>
					<SpeakButton
						v-if="ttsEnabled"
						:text="message.content"
						:id="index"
						class="shrink-0 -mb-1"
					/>
				</div>
				<div v-else class="text-sm text-ink-gray-9 whitespace-pre-wrap">
					<span
						v-if="message.audioPending"
						class="flex items-center gap-2 text-ink-gray-5"
					>
						<Mic class="w-4 h-4" />
						<span class="animate-pulse">…</span>
					</span>
					<template v-else>{{ message.content }}</template>
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
			<div v-if="chat.isLoading" class="flex items-center space-x-2 p-3">
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
				v-model="chat.question"
				:placeholder="__('Ask a question about this lesson...')"
				class="flex-1 resize-none rounded-md border border-outline-gray-2 px-3 py-2 text-sm text-ink-gray-8 focus:border-outline-gray-3 focus:outline-none"
				rows="2"
				@keydown.enter.exact.prevent="sendQuestion"
				:disabled="chat.isLoading"
			></textarea>
			<MicButton
				v-if="sttEnabled"
				raw
				:disabled="chat.isLoading"
				@audio="onAudioMessage"
			/>
			<Button
				variant="solid"
				@click="sendQuestion"
				:disabled="!chat.question.trim() || chat.isLoading"
			>
				<template #icon>
					<Send class="w-4 h-4" />
				</template>
			</Button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { Button, call, toast } from 'frappe-ui'
import { Send, Mic } from 'lucide-vue-next'
import { useSettings } from '@/stores/settings'
import { useAiChat } from '@/stores/aiChat'
import MicButton from '@/oslms/components/ai/MicButton.vue'
import SpeakButton from '@/oslms/components/ai/SpeakButton.vue'
import { useTextToSpeech } from '@/oslms/composables/useTextToSpeech'
import { blobToBase64 } from '@/oslms/utils/audioApi'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({
	html: false,
	linkify: true,
	breaks: true,
})

const renderMarkdown = (text: string): string => md.render(text || '')

const settingsStore = useSettings()
const chat = useAiChat()

const sttEnabled = computed(() =>
	Boolean(settingsStore.settings?.data?.stt_enabled),
)
const ttsEnabled = computed(() =>
	Boolean(settingsStore.settings?.data?.tts_enabled),
)
const ttsAutoplayOnStt = computed(() =>
	Boolean(settingsStore.settings?.data?.tts_autoplay_on_stt),
)

const { play, prime } = useTextToSpeech()

interface Message {
	role: 'user' | 'assistant'
	content: string
	sources?: string[]
	audioPending?: boolean
}

const props = defineProps<{
	courseId: string
	lessonId: string
}>()

const messagesContainer = ref<HTMLElement | null>(null)

const scrollToBottom = () => {
	nextTick(() => {
		if (messagesContainer.value) {
			messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
		}
	})
}

// Restore scroll position when the component remounts (e.g., the chat panel
// was closed and reopened — store state survives, but the DOM is new).
onMounted(scrollToBottom)
watch(() => chat.messages.length, scrollToBottom)

// Voice message: record -> one combined call (STT -> LLM -> TTS) -> play.
const onAudioMessage = async (blob: Blob) => {
	if (chat.isLoading) return
	const history = chat.messages.map((m) => ({ from: m.role, message: m.content }))
	chat.addMessage({ role: 'user', content: '', audioPending: true })
	const userIdx = chat.messages.length - 1
	chat.isLoading = true
	try {
		const audio = await blobToBase64(blob)
		const res = await call('os_lms.os_lms.ai.tutor.api.ask_audio', {
			course: props.courseId,
			lesson: props.lessonId,
			audio,
			mime: blob.type || 'audio/webm',
			language: 'it',
			history,
			want_audio: ttsEnabled.value,
		})
		chat.messages[userIdx].content = res.question_text || ''
		chat.messages[userIdx].audioPending = false
		const answer = res.answer_text || __('Sorry, I could not find an answer.')
		chat.addMessage({ role: 'assistant', content: answer, sources: [] })
		if (res.audio_base64) {
			prime(answer, res.audio_base64, res.mime)
			if (ttsAutoplayOnStt.value) play(answer, chat.messages.length - 1)
		}
	} catch (error: any) {
		chat.messages[userIdx].audioPending = false
		const msg = error?.message || error?.exc || __('Failed to get response')
		chat.addMessage({ role: 'assistant', content: __('Error: ') + msg })
		toast.error(msg)
	} finally {
		chat.isLoading = false
	}
}

const sendQuestion = async () => {
	const trimmedQuestion = chat.question.trim()
	if (!trimmedQuestion || chat.isLoading) return

	// Snapshot the prior conversation before appending the current question,
	// so the backend receives `question` separately from `history`.
	const history = chat.messages.map((m) => ({
		from: m.role,
		message: m.content,
	}))

	chat.addMessage({
		role: 'user',
		content: trimmedQuestion,
	})
	chat.question = ''
	chat.isLoading = true

	try {
		// When TTS is on, use the combined endpoint so the reply audio comes
		// back in the same call (typed messages don't autoplay — priming makes
		// the read button instant).
		const useAudio = ttsEnabled.value
		const response = await call(
			`os_lms.os_lms.ai.tutor.api.${useAudio ? 'ask_audio' : 'ask'}`,
			{
				course: props.courseId,
				lesson: props.lessonId,
				question: trimmedQuestion,
				history,
				...(useAudio ? { want_audio: true } : {}),
			},
		)

		const answer =
			(useAudio ? response.answer_text : response.answer) ||
			__('Sorry, I could not find an answer.')
		chat.addMessage({
			role: 'assistant',
			content: answer,
			sources: [],
		})

		if (useAudio && response.audio_base64) {
			prime(answer, response.audio_base64, response.mime)
		}
	} catch (error: any) {
		const errorMessage =
			error?.message || error?.exc || __('Failed to get response')
		chat.addMessage({
			role: 'assistant',
			content: __('Error: ') + errorMessage,
		})
		toast.error(errorMessage)
	} finally {
		chat.isLoading = false
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
