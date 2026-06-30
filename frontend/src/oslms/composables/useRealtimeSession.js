/**
 * Composable that owns a voice Session lifecycle.
 *
 * Responsibilities:
 * - Call create_voice_session to get an ephemeral provider token
 * - Open the user's microphone via getUserMedia
 * - Instantiate and drive the browser-side realtime transport
 * - Relay final transcripts to Frappe (best-effort: a dropped relay never kills the call)
 * - Enforce the client-side countdown timer: auto-stop at 0 seconds
 *
 * Audio never touches Frappe; only control calls + transcript text do.
 */
import { ref } from 'vue'
import { createResource } from 'frappe-ui'
import { createTransport } from './realtime/createTransport'

export function useRealtimeSession() {
	const state = ref('idle') // idle | connecting | connected | closed | error
	const transcript = ref([]) // [{ role, text }]
	const remainingSeconds = ref(0)
	const sessionId = ref(null)

	let transport = null
	let mediaStream = null
	let timer = null
	let startedAt = 0

	const createSessionRes = createResource({
		url: 'os_lms.os_lms.ai.realtime.api.create_voice_session',
		method: 'POST',
	})

	const endSessionRes = createResource({
		url: 'os_lms.os_lms.ai.realtime.api.end_voice_session',
		method: 'POST',
	})

	async function start(scenarioId) {
		if (['connecting', 'connected'].includes(state.value)) return
		state.value = 'connecting'
		try {
			const res = await createSessionRes.submit({
				scenario_id: scenarioId,
			})

			sessionId.value = res.session_id
			remainingSeconds.value = res.max_seconds
			startedAt = Date.now()

			mediaStream = await navigator.mediaDevices.getUserMedia({
				audio: true,
			})
			transport = createTransport(res)
			transport.onState((s) => {
				state.value = s
			})
			transport.onTranscript(({ role, text }) => {
				transcript.value.push({ role, text })
				relayTurn(role, text)
			})
			await transport.connect(mediaStream)
			startTimer(res.max_seconds)
		} catch {
			state.value = 'error'
			stopTimer()
			if (transport) {
				try {
					transport.close()
				} catch {
					// transport may not be fully initialized; ignore
				}
				transport = null
			}
			if (mediaStream) {
				mediaStream.getTracks().forEach((t) => t.stop())
				mediaStream = null
			}
			// Best-effort: end an orphaned server-side session to avoid burning daily quota.
			if (sessionId.value) {
				endSessionRes
					.submit({
						session_id: sessionId.value,
						reason: 'abandoned',
						seconds: 0,
					})
					.catch(() => {})
			}
			sessionId.value = null
			startedAt = 0
		}
	}

	function relayTurn(role, text) {
		// Create a fresh resource per call so concurrent relays don't clobber each other.
		createResource({
			url: 'os_lms.os_lms.ai.realtime.api.persist_transcript_turn',
			method: 'POST',
		})
			.submit({ session_id: sessionId.value, role, text })
			.catch(() => {
				// Best-effort relay: a dropped transcript must not kill the call.
			})
	}

	function startTimer(maxSeconds) {
		stopTimer()
		timer = setInterval(() => {
			const elapsed = Math.floor((Date.now() - startedAt) / 1000)
			remainingSeconds.value = Math.max(0, maxSeconds - elapsed)
			if (remainingSeconds.value <= 0) stop('completed')
		}, 1000)
	}

	function stopTimer() {
		if (timer) clearInterval(timer)
		timer = null
	}

	async function stop(reason = 'completed') {
		if (state.value === 'closed' || state.value === 'idle') return
		stopTimer()
		const seconds = startedAt
			? Math.floor((Date.now() - startedAt) / 1000)
			: 0
		try {
			transport?.close()
			mediaStream?.getTracks().forEach((t) => t.stop())
		} finally {
			if (sessionId.value) {
				await endSessionRes
					.submit({ session_id: sessionId.value, reason, seconds })
					.catch(() => {})
			}
			state.value = 'closed'
		}
	}

	return { state, transcript, remainingSeconds, sessionId, start, stop }
}
