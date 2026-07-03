<template>
	<div class="flex flex-col h-screen max-w-3xl mx-auto">
		<div
			v-if="!session"
			class="flex-1 flex items-center justify-center text-ink-gray-5"
		>
			<span v-if="error">{{ error }}</span>
			<span v-else>{{ __('Caricamento sessione…') }}</span>
		</div>
		<template v-else>
			<div class="px-4 pt-3 flex items-center justify-between gap-3">
				<!-- Always offer a way back to the course the simulation
				belongs to (simulations are course-scoped). -->
				<router-link
					v-if="courseName"
					:to="{ name: 'CourseDetail', params: { courseName } }"
					class="text-sm text-ink-gray-5 hover:underline"
				>
					← {{ __('Torna al corso') }}
				</router-link>
				<span v-else />
				<!-- Concluded session opened read-only (e.g. via the debrief's
				"Trascrizione" link): offer a way back to the debrief. -->
				<router-link
					v-if="isTerminal"
					:to="{ name: 'SimulationDebrief', params: { sessionId } }"
					class="text-sm text-ink-gray-5 hover:underline"
				>
					{{ __('Vedi debrief') }} →
				</router-link>
			</div>
			<ChatSession
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
		</template>
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
const courseName = computed(() => session.value?.course || '')
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

// Track whether the session was ever observed as active (non-terminal) while on
// this page. We only auto-redirect to the debrief when the session *transitions*
// to terminal here (the user just ended it) — not when arriving at an already
// completed session (e.g. via the "Trascrizione" back-link from the debrief),
// which must stay to show the read-only transcript instead of bouncing back.
const wasActive = ref(false)

watch([session, isTerminal], ([currentSession, terminal]) => {
	if (!currentSession) return
	if (!terminal) {
		wasActive.value = true
		return
	}
	if (wasActive.value) {
		// Auto-redirect to the debrief page when the session ends.
		router.replace({
			name: 'SimulationDebrief',
			params: { sessionId: sessionId.value },
		})
	}
})
</script>
