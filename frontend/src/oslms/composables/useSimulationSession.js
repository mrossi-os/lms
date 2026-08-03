/**
 * Composable that owns a Simulation Session's runtime state.
 *
 * Responsibilities:
 * - Hydrate from `get_session` on mount
 * - Send user turns via `send_message`
 * - End the session via `end_session`
 * - Subscribe to realtime events for the session and append turns reactively
 *
 * Realtime channels (see backend orchestrator):
 *   simulation:turn_start     — user turn appended
 *   simulation:turn_complete  — assistant turn ready
 *   simulation:error          — surface to UI
 */
import { computed, inject, onUnmounted, ref, watch } from 'vue'
import { createResource, toast } from 'frappe-ui'
import { useSettings } from '@/stores/settings'
import { useTextToSpeech } from '@/oslms/composables/useTextToSpeech'
import { blobToBase64 } from '@/oslms/utils/audioApi'

const EVENTS = {
	TURN_START: 'simulation:turn_start',
	TURN_COMPLETE: 'simulation:turn_complete',
	ERROR: 'simulation:error',
}

export function useSimulationSession(sessionIdRef) {
	const socket = inject('$socket')

	const session = ref(null)
	const turns = ref([])
	const sending = ref(false)
	const ending = ref(false)
	const error = ref(null)

	const settingsStore = useSettings()
	const ttsEnabled = computed(() =>
		Boolean(settingsStore.settings?.data?.tts_enabled),
	)
	const { play, prime } = useTextToSpeech()

	const status = computed(() => session.value?.status || 'unknown')
	const isTerminal = computed(() =>
		['Completed', 'Abandoned', 'Error', 'Needs Review'].includes(status.value),
	)
	const turnCount = computed(() => turns.value.length)

	// True once the bot has delivered its closing replies after time-up: the
	// student can no longer send messages, only end the session via "Termina".
	// The session stays In Progress until they do (server-computed, re-synced
	// each reload).
	const inputLocked = computed(() => Boolean(session.value?.input_locked))

	// --- natural-close budget (time remaining only) ---

	// Time budget: seed from the server snapshot on each reload and tick down
	// locally. Using the server value (not client math on started_at) avoids
	// clock/timezone drift. null = no time cap; stays at 0 while the forced
	// close plays out after the time is up.
	const remainingSeconds = ref(null)
	let clockTicker = null
	function _syncClock() {
		const v = session.value?.remaining_seconds
		remainingSeconds.value = v === null || v === undefined ? null : Number(v)
	}
	function _startClock() {
		if (clockTicker) return
		clockTicker = setInterval(() => {
			if (remainingSeconds.value === null || isTerminal.value) return
			// Pause while a message is in flight: bot latency must not consume the
			// student's time. On reply the reload re-syncs to the server's active
			// remaining (which also excludes latency), so there's no visible jump.
			if (sending.value) return
			remainingSeconds.value = Math.max(0, remainingSeconds.value - 1)
		}, 1000)
	}
	function _stopClock() {
		if (clockTicker) {
			clearInterval(clockTicker)
			clockTicker = null
		}
	}
	watch(session, _syncClock)

	// --- resources ---

	const fetchResource = createResource({
		url: 'os_lms.os_lms.ai.simulations.api.get_session',
		makeParams() {
			return { session_id: sessionIdRef.value }
		},
		onSuccess(data) {
			if (data?.session) session.value = data.session
			if (data?.turns) turns.value = data.turns
		},
		onError(err) {
			error.value = err?.messages?.[0] || String(err)
		},
	})

	const sendResource = createResource({
		url: 'os_lms.os_lms.ai.simulations.api.send_message',
		method: 'POST',
		onError(err) {
			error.value = err?.messages?.[0] || __('Send failed')
			toast.error(error.value)
		},
	})

	const sendAudioResource = createResource({
		url: 'os_lms.os_lms.ai.simulations.api.send_message_audio',
		method: 'POST',
		onError(err) {
			error.value = err?.messages?.[0] || __('Send failed')
			toast.error(error.value)
		},
	})

	const endResource = createResource({
		url: 'os_lms.os_lms.ai.simulations.api.end_session',
		method: 'POST',
		onError(err) {
			error.value = err?.messages?.[0] || __('End failed')
			toast.error(error.value)
		},
	})

	// --- public API ---

	async function load() {
		if (!sessionIdRef.value) return
		return fetchResource.submit()
	}

	function _nextIndex() {
		return (turns.value[turns.value.length - 1]?.turn_index || 0) + 1
	}

	// text: typed message; audioBlob: recorded voice message. When TTS is on (or
	// an audio blob is present) we use the combined endpoint so the reply audio
	// comes back in the same call.
	async function send({ text = '', audioBlob = null } = {}) {
		if (sending.value) return
		const trimmed = (text || '').trim()
		if (!audioBlob && !trimmed) return
		const useCombined = Boolean(audioBlob) || ttsEnabled.value
		sending.value = true
		try {
			if (!useCombined) {
				await sendResource.submit({ session_id: sessionIdRef.value, text: trimmed })
				turns.value.push({
					role: 'user',
					text_content: trimmed,
					turn_index: _nextIndex(),
					_optimistic: true,
				})
				await load()
				return
			}

			// Combined path: optimistic user turn (audio-pending placeholder or
			// the typed text), then one call that does STT? -> LLM -> TTS?.
			turns.value.push(
				audioBlob
					? { role: 'user', _audioPending: true, turn_index: _nextIndex(), _optimistic: true }
					: { role: 'user', text_content: trimmed, turn_index: _nextIndex(), _optimistic: true },
			)
			const idx = turns.value.length - 1
			const params = audioBlob
				? {
						session_id: sessionIdRef.value,
						audio: await blobToBase64(audioBlob),
						mime: audioBlob.type || 'audio/webm',
						language: 'it',
						want_audio: ttsEnabled.value,
					}
				: {
						session_id: sessionIdRef.value,
						text: trimmed,
						language: 'it',
						want_audio: ttsEnabled.value,
					}
			const res = await sendAudioResource.submit(params)
			if (audioBlob && res?.question_text != null) {
				turns.value[idx].text_content = res.question_text
				turns.value[idx]._audioPending = false
			}
			if (res?.audio_base64) {
				prime(res.answer_text, res.audio_base64, res.mime)
				play(res.answer_text, res.assistant_turn)
			}
			await load()
		} finally {
			sending.value = false
		}
	}

	async function end(reason = 'completed') {
		if (ending.value || isTerminal.value) return
		ending.value = true
		try {
			await endResource.submit({ session_id: sessionIdRef.value, reason })
			await load()
		} finally {
			ending.value = false
		}
	}

	// Time up = the session is over: auto-complete it (which generates the
	// debrief) the moment the countdown reaches 0, instead of waiting for the
	// student to press "Termina" or leave. So "tempo scaduto = Completata"
	// always, regardless of what the student does next. Leaving BEFORE the time
	// is up is still handled as an abandonment by the page-level guard.
	watch(remainingSeconds, (val) => {
		if (
			val === 0 &&
			status.value === 'In Progress' &&
			!isTerminal.value &&
			!ending.value
		) {
			end('completed')
		}
	})

	// --- realtime ---

	function _matchesSession(payload) {
		return payload && payload.session === sessionIdRef.value
	}

	function _onTurnStart(payload) {
		if (!_matchesSession(payload)) return
		// We use this only as a typing indicator; nothing to mutate here yet.
	}

	function _onTurnComplete(payload) {
		if (!_matchesSession(payload)) return
		// Replace optimistic turns with a server reload.
		load()
	}

	function _onError(payload) {
		if (!_matchesSession(payload)) return
		error.value = payload.message || __('Simulation error')
		toast.error(error.value)
	}

	function subscribe() {
		if (!socket) return
		socket.on(EVENTS.TURN_START, _onTurnStart)
		socket.on(EVENTS.TURN_COMPLETE, _onTurnComplete)
		socket.on(EVENTS.ERROR, _onError)
	}

	function unsubscribe() {
		if (!socket) return
		socket.off(EVENTS.TURN_START, _onTurnStart)
		socket.off(EVENTS.TURN_COMPLETE, _onTurnComplete)
		socket.off(EVENTS.ERROR, _onError)
	}

	watch(
		sessionIdRef,
		(id, prev) => {
			if (prev) unsubscribe()
			if (id) {
				subscribe()
				load()
				_startClock()
			} else {
				_stopClock()
			}
		},
		{ immediate: true },
	)

	onUnmounted(() => {
		unsubscribe()
		_stopClock()
	})

	return {
		session,
		turns,
		status,
		isTerminal,
		turnCount,
		remainingSeconds,
		inputLocked,
		sending,
		ending,
		error,
		load,
		send,
		end,
	}
}
