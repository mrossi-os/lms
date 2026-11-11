/**
 * OS Audit — time spent in a lesson (docs/audit-studenti/PIANO.md §5).
 *
 * get_lesson (os_lms override) returns `os_audit: { session, heartbeat_seconds,
 * inactivity_minutes }` only when the audit tracks this student on this course;
 * otherwise this composable does nothing at all.
 *
 * Every `heartbeat_seconds` the page tells the server it is still open, and
 * whether the student is *active* (tab visible and an interaction within the
 * inactivity threshold, or a video playing) or only *present*. With the tab
 * hidden nothing is sent. The seconds are computed by the server from the gaps
 * between signals, so this code only reports state.
 *
 * The last signals (tab hidden, page left, lesson changed) use
 * `fetch(..., { keepalive: true })`: unlike `sendBeacon` it can carry Frappe's
 * CSRF header.
 */
import { onBeforeUnmount, watch, type Ref } from 'vue'

const HEARTBEAT_URL = '/api/method/os_lms.os_lms.os_audit.heartbeat'
const QUIZ_START_URL = '/api/method/os_lms.os_lms.os_audit.quiz_start'
const INTERACTION_EVENTS = ['mousemove', 'mousedown', 'keydown', 'scroll', 'wheel', 'touchstart'] as const

export interface OsAuditConfig {
	session: string
	heartbeat_seconds?: number
	inactivity_minutes?: number
}

interface HeartbeatAnswer {
	session?: string
	stop?: number
}

function csrfHeaders(): Record<string, string> {
	const headers: Record<string, string> = {
		'Content-Type': 'application/json',
		Accept: 'application/json',
	}
	const token = (window as any).csrf_token
	if (token && token !== '{{ csrf_token }}') headers['X-Frappe-CSRF-Token'] = token
	return headers
}

async function post(url: string, body: Record<string, unknown>, keepalive = false): Promise<any> {
	const response = await fetch(url, {
		method: 'POST',
		headers: csrfHeaders(),
		body: JSON.stringify(body),
		credentials: 'same-origin',
		keepalive,
	})
	if (!response.ok) throw new Error(String(response.status))
	return (await response.json())?.message
}

export function isVideoPlaying(): boolean {
	const playing = Array.from(document.querySelectorAll('video')).some(
		(video) => !video.paused && !video.ended
	)
	// Plyr (YouTube/Vimeo embeds) marks its container while playing.
	return playing || Boolean(document.querySelector('.plyr--playing'))
}

/** Record the start of a quiz attempt; the server computes the duration at submit. */
export function recordQuizStart(quiz: string | undefined | null): void {
	if (!quiz) return
	post(QUIZ_START_URL, { quiz }).catch(() => {})
}

export function useOsAudit(lesson: { data?: any } | Ref<any>) {
	let session: string | null = null
	let intervalMs = 30_000
	let inactivityMs = 3 * 60_000
	let timer: ReturnType<typeof setInterval> | null = null
	let lastInteraction = Date.now()
	let listening = false

	const isActive = () =>
		document.visibilityState === 'visible' &&
		(Date.now() - lastInteraction < inactivityMs || isVideoPlaying())

	const onInteraction = () => {
		lastInteraction = Date.now()
	}

	const handleAnswer = (answer: HeartbeatAnswer | undefined, sentFor: string) => {
		if (session !== sentFor || !answer) return
		if (answer.stop) stop()
		else if (answer.session) session = answer.session
	}

	const send = (options: { close?: boolean; keepalive?: boolean } = {}) => {
		const current = session
		if (!current) return
		const body = { session: current, active: isActive() ? 1 : 0, close: options.close ? 1 : 0 }
		post(HEARTBEAT_URL, body, Boolean(options.keepalive))
			.then((answer) => handleAnswer(answer, current))
			.catch(() => {
				// Never disturb the lesson: a lost signal only costs its seconds.
			})
	}

	const tick = () => {
		if (document.visibilityState === 'visible') send()
	}

	const onVisibility = () => {
		// Hidden: one last signal (the server ignores it if too close to the previous).
		// Visible again: signal at once, so a long pause opens a new session promptly.
		if (document.visibilityState === 'hidden') send({ keepalive: true })
		else {
			lastInteraction = Date.now()
			send()
		}
	}

	const onPageHide = () => send({ close: true, keepalive: true })

	const listen = () => {
		if (listening) return
		listening = true
		INTERACTION_EVENTS.forEach((name) =>
			window.addEventListener(name, onInteraction, { passive: true, capture: true })
		)
		document.addEventListener('visibilitychange', onVisibility)
		window.addEventListener('pagehide', onPageHide)
	}

	const unlisten = () => {
		if (!listening) return
		listening = false
		INTERACTION_EVENTS.forEach((name) =>
			window.removeEventListener(name, onInteraction, { capture: true })
		)
		document.removeEventListener('visibilitychange', onVisibility)
		window.removeEventListener('pagehide', onPageHide)
	}

	function stop() {
		session = null
		if (timer) clearInterval(timer)
		timer = null
		unlisten()
	}

	const start = (config: OsAuditConfig) => {
		session = config.session
		intervalMs = Math.max(5, Number(config.heartbeat_seconds) || 30) * 1000
		inactivityMs = Math.max(1, Number(config.inactivity_minutes) || 3) * 60_000
		lastInteraction = Date.now()
		listen()
		timer = setInterval(tick, intervalMs)
	}

	const closeCurrent = () => {
		if (session) send({ close: true, keepalive: true })
		stop()
	}

	const config = () => {
		const data = 'value' in lesson ? (lesson as Ref<any>).value?.data : (lesson as any).data
		return (data?.os_audit as OsAuditConfig | undefined) || null
	}

	watch(
		() => config()?.session,
		(next) => {
			// A new lesson (or a reload) brings a new session: close the one in use first
			// (it may be a newer one the server opened after a long pause).
			if (session && session !== next) closeCurrent()
			if (session === next) return
			const current = config()
			if (next && current) start(current)
		},
		{ immediate: true }
	)

	onBeforeUnmount(closeCurrent)

	return { stop, isActive }
}
