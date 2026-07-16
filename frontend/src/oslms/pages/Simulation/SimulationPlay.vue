<template>
	<div class="flex flex-col h-screen max-w-6xl mx-auto">
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
			<div class="flex flex-1 min-h-0 gap-4 px-4 pb-4">
				<ChatSession
					class="flex-1 min-w-0"
					:scenarioName="scenarioName"
					:persona="persona"
					:turns="turns"
					:status="session.status"
					:sending="sending"
					:ending="ending"
					:remainingSeconds="remainingSeconds"
					:inputLocked="inputLocked"
					@send="onSend"
					@send-audio="onSendAudio"
					@end="onEnd"
				/>
				<aside
					v-if="studentBrief"
					class="hidden md:block w-80 shrink-0 overflow-y-auto border border-outline-gray-2 rounded-md p-4 bg-surface-gray-1"
				>
					<div class="text-sm font-semibold text-ink-gray-9 mb-2">
						{{ __('Il tuo compito') }}
					</div>
					<div class="whitespace-pre-wrap text-sm text-ink-gray-7">
						{{ studentBrief }}
					</div>
				</aside>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, useRoute, useRouter } from 'vue-router'
import ChatSession from '@/oslms/components/simulations/ChatSession.vue'
import { useSimulationSession } from '@/oslms/composables/useSimulationSession.js'

const route = useRoute()
const router = useRouter()

const sessionId = computed(() => route.params.sessionId)
const {
	session,
	turns,
	sending,
	ending,
	isTerminal,
	error,
	send,
	end,
	remainingSeconds,
	inputLocked,
} = useSimulationSession(sessionId)

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
const studentBrief = computed(() => session.value?.student_brief || '')

async function onSend(text) {
	await send({ text })
}

async function onSendAudio(blob) {
	await send({ audioBlob: blob })
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

// --- Leaving an in-progress session ---
// Leaving the page or closing the tab while the session is still running closes
// it as "abandoned"; the server upgrades it to Completed if the time cap was
// already reached (so only Completed sessions get a debrief). The scheduled
// reaper is the backstop when the browser can't report (crash, hard tab-close).

const isActivePlay = () => session.value?.status === 'In Progress'

// In-app navigation (router): the page stays alive, so the normal async call
// completes. Skipped after "Termina" — the session is already terminal by then.
onBeforeRouteLeave(() => {
	if (isActivePlay()) end('abandoned')
	return true
})

// Tab close / refresh: fire a keepalive request that outlives the page.
function abandonBeacon() {
	if (!isActivePlay() || !sessionId.value) return
	const headers = { 'Content-Type': 'application/json' }
	if (window.csrf_token && window.csrf_token !== '{{ csrf_token }}') {
		headers['X-Frappe-CSRF-Token'] = window.csrf_token
	}
	// Best-effort; the server-side reaper closes it otherwise.
	fetch('/api/method/os_lms.os_lms.ai.simulations.api.end_session', {
		method: 'POST',
		keepalive: true,
		headers,
		body: JSON.stringify({ session_id: sessionId.value, reason: 'abandoned' }),
	}).catch(() => {})
}

onMounted(() => window.addEventListener('pagehide', abandonBeacon))
onBeforeUnmount(() => window.removeEventListener('pagehide', abandonBeacon))
</script>
