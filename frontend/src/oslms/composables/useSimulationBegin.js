/**
 * Shared "phase 2" start logic for a prepared simulation session.
 * chat  -> begin_session then navigate to the play page.
 * voice -> expose the session id so the caller can mount <VoiceSession>.
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { createResource, toast } from 'frappe-ui'

export function useSimulationBegin() {
	const router = useRouter()
	const beginning = ref(false)
	const voiceSessionId = ref(null)

	const beginRes = createResource({
		url: 'os_lms.os_lms.ai.simulations.api.begin_session',
		method: 'POST',
	})

	async function begin({ sessionId, mode }) {
		if (!sessionId) return
		if (mode === 'voice') {
			voiceSessionId.value = sessionId
			return
		}
		beginning.value = true
		try {
			await beginRes.submit({ session_id: sessionId })
			router.push({ name: 'SimulationPlay', params: { sessionId } })
		} catch (e) {
			toast.error(e.messages?.[0] || e.message || String(e))
		} finally {
			beginning.value = false
		}
	}

	function clearVoice() {
		voiceSessionId.value = null
	}

	return { beginning, voiceSessionId, begin, clearVoice }
}
