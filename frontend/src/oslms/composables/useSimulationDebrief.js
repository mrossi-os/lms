/**
 * Composable that loads a debrief and waits for the background job to finish.
 *
 * Strategy:
 * - On mount, call get_debrief. If status is `ready`/`needs_review`/`failed`,
 *   we're done.
 * - Otherwise subscribe to `simulation:debrief_ready` / `simulation:debrief_failed`
 *   AND poll every 4s as a fallback (in case WS is missed).
 * - Poll caps at 60s; after that we surface a timeout but keep the WS active.
 */
import { computed, inject, onUnmounted, ref, watch } from 'vue'
import { createResource, toast } from 'frappe-ui'

const EVENTS = {
	READY: 'simulation:debrief_ready',
	FAILED: 'simulation:debrief_failed',
}

const POLL_INTERVAL_MS = 4000
const POLL_TIMEOUT_MS = 60000

export function useSimulationDebrief(sessionIdRef) {
	const socket = inject('$socket')

	const debrief = ref(null)
	const error = ref(null)
	const timedOut = ref(false)
	const startedAt = ref(0)
	let pollTimer = null

	const status = computed(() => debrief.value?.status || 'pending')
	const isReady = computed(() => ['ready', 'needs_review'].includes(status.value))
	const isFailed = computed(() => status.value === 'failed')

	const fetchResource = createResource({
		url: 'os_lms.os_lms.ai.simulations.api.get_debrief',
		makeParams() {
			return { session_id: sessionIdRef.value }
		},
		onSuccess(data) {
			if (!data) return
			debrief.value = data
			if (isReady.value || isFailed.value) {
				_stopPolling()
			}
		},
		onError(err) {
			error.value = err?.messages?.[0] || String(err)
			toast.error(error.value)
		},
	})

	async function load() {
		if (!sessionIdRef.value) return
		return fetchResource.submit()
	}

	function _matchesSession(payload) {
		return payload && payload.session === sessionIdRef.value
	}

	function _onReady(payload) {
		if (!_matchesSession(payload)) return
		load()
	}

	function _onFailed(payload) {
		if (!_matchesSession(payload)) return
		toast.error(__('Debrief generation failed.'))
		load()
	}

	function subscribe() {
		if (!socket) return
		socket.on(EVENTS.READY, _onReady)
		socket.on(EVENTS.FAILED, _onFailed)
	}

	function unsubscribe() {
		if (!socket) return
		socket.off(EVENTS.READY, _onReady)
		socket.off(EVENTS.FAILED, _onFailed)
	}

	function _startPolling() {
		startedAt.value = Date.now()
		_stopPolling()
		pollTimer = setInterval(() => {
			if (Date.now() - startedAt.value > POLL_TIMEOUT_MS) {
				timedOut.value = true
				_stopPolling()
				return
			}
			if (!isReady.value && !isFailed.value) load()
		}, POLL_INTERVAL_MS)
	}

	function _stopPolling() {
		if (pollTimer) {
			clearInterval(pollTimer)
			pollTimer = null
		}
	}

	watch(
		sessionIdRef,
		async (id, prev) => {
			if (prev) {
				unsubscribe()
				_stopPolling()
			}
			if (!id) return
			subscribe()
			await load()
			if (!isReady.value && !isFailed.value) _startPolling()
		},
		{ immediate: true },
	)

	onUnmounted(() => {
		unsubscribe()
		_stopPolling()
	})

	return { debrief, status, isReady, isFailed, error, timedOut, load }
}
