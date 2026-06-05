<template>
	<div class="flex flex-col h-screen max-w-3xl mx-auto">
		<div v-if="!session" class="flex-1 flex items-center justify-center text-ink-gray-5">
			<span v-if="error">{{ error }}</span>
			<span v-else>{{ __('Caricamento sessione…') }}</span>
		</div>
		<ChatSession
			v-else
			class="flex-1"
			:scenarioName="scenarioName"
			:persona="persona"
			:turns="turns"
			:status="session.status"
			:sending="sending"
			:ending="ending"
			@send="onSend"
			@end="onEnd"
		/>
	</div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ChatSession from '@/oslms/components/simulations/ChatSession.vue'
import { useSimulationSession } from '@/oslms/composables/useSimulationSession.js'

const route = useRoute()
const router = useRouter()

const sessionId = computed(() => route.params.sessionId)
const { session, turns, sending, ending, isTerminal, error, send, end } =
	useSimulationSession(sessionId)

const scenarioName = computed(() => session.value?.scenario || '')
const persona = computed(() => {
	const raw = session.value?.generated_persona
	if (!raw) return null
	try {
		return JSON.parse(raw)
	} catch {
		return null
	}
})

async function onSend(text) {
	await send(text)
}

async function onEnd(reason) {
	await end(reason)
}

watch(isTerminal, (terminal) => {
	if (terminal) {
		// Auto-redirect to the debrief page when the session ends.
		router.replace({ name: 'SimulationDebrief', params: { sessionId: sessionId.value } })
	}
})
</script>
