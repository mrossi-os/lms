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
 * The signal sent when the tab is hidden says so (`hidden: 1`): the server
 * pauses the session there, so the hidden time is never credited, and answers
 * the first signal after the tab is visible again with a new session.
 *
 * The last signals (tab hidden, page left, lesson changed) use
 * `fetch(..., { keepalive: true })`: unlike `sendBeacon` it can carry Frappe's
 * CSRF header.
 *
 * Phase 3 (when the config says `track_videos` / `track_files`): the page also
 * collects what happens to the videos (play, pause, skip, end, and how long a
 * video was playing), the PDFs scrolled into view and the platform files
 * opened or downloaded, and sends them with the next signal. Everything is
 * listened to on the document, in the capture phase, so no lesson block needs
 * to know about the audit: media events do not bubble, but they still pass
 * through the capture phase. Plyr re-dispatches each media event on its own
 * container: only the one on the media element counts.
 */
import { onBeforeUnmount, watch, type Ref } from 'vue'

const HEARTBEAT_URL = '/api/method/os_lms.os_lms.os_audit.heartbeat'
const QUIZ_START_URL = '/api/method/os_lms.os_lms.os_audit.quiz_start'
const INTERACTION_EVENTS = ['mousemove', 'mousedown', 'keydown', 'scroll', 'wheel', 'touchstart'] as const

export interface OsAuditConfig {
	session: string
	heartbeat_seconds?: number
	inactivity_minutes?: number
	track_videos?: number
	track_files?: number
}

export interface ClientEvent {
	type: string
	source?: string
	position?: number
	duration?: number
	from?: number
	file?: string
}

const MEDIA_EVENTS = ['play', 'pause', 'seeking', 'seeked', 'ended', 'timeupdate'] as const
const PDF_SELECTOR = '.pdf-block, iframe[type="application/pdf"]'
const PLATFORM_FILE = /^\/(private\/)?files\//
// Events kept while waiting for the next signal, and sent per signal.
const QUEUE_LIMIT = 100
const EVENTS_PER_SIGNAL = 30
// Successive skips of the same video closer than this are one skip (dragging
// the progress bar fires many).
const SEEK_MERGE_MS = 2000
// The same media event twice this close is one event.
const DUPLICATE_MS = 300
// timeupdate fires a few times a second while playing; a longer gap is not
// playing time (the video was paused or buffering).
const MAX_PLAY_TICK_MS = 1500

/**
 * The path of a same-site URL. Private lesson files are served through the
 * access-gated serve_resource endpoint (lms rewrite_private_media): for those
 * the file is the `file_url` parameter, not the endpoint.
 */
function sitePath(url: URL): string {
	if (url.pathname.endsWith('.serve_resource')) {
		const file = url.searchParams.get('file_url')
		if (file) return file.split(/[?#]/)[0]
	}
	return decodeURI(url.pathname)
}

/** A same-site URL as its path (files are recorded by path), anything else as is. */
export function sourcePath(url: string | undefined | null): string {
	if (!url) return ''
	try {
		const parsed = new URL(url, window.location.href)
		return parsed.origin === window.location.origin ? sitePath(parsed) : parsed.href
	} catch {
		return url
	}
}

/** The platform file a link points to, or '' when it is not one. */
export function platformFile(href: string | undefined | null): string {
	if (!href) return ''
	try {
		const url = new URL(href, window.location.href)
		if (url.origin !== window.location.origin) return ''
		const path = sitePath(url)
		return PLATFORM_FILE.test(path) ? path : ''
	} catch {
		return ''
	}
}

/**
 * The media element an event is about, with its Plyr instance when it has one,
 * or null when the event is Plyr's copy on its container (counted once only).
 */
export function mediaOf(event: Event): { el: any; plyr: any } | null {
	const target = event.target as any
	const plyr = (event as CustomEvent).detail?.plyr
	if (plyr) return target === plyr.media ? { el: target, plyr } : null
	return typeof HTMLMediaElement !== 'undefined' && target instanceof HTMLMediaElement
		? { el: target, plyr: null }
		: null
}

/**
 * The video of a Plyr embed when Plyr does not know it: Vimeo does not answer
 * Plyr's getVideoUrl() for unlisted videos, so `plyr.source` stays empty. The
 * player iframe still carries the video id in its path; its query (player
 * options) is left out.
 */
export function embedSource(el: Element | null | undefined): string {
	const src = el?.querySelector?.('iframe')?.getAttribute('src')
	if (!src) return ''
	try {
		const url = new URL(src)
		return url.origin + url.pathname
	} catch {
		return ''
	}
}

function pdfFile(el: Element): string {
	if (el.tagName === 'IFRAME') return platformFile(el.getAttribute('src')?.split('#')[0])
	const link = el.querySelector('a[href]')
	return platformFile(link?.getAttribute('href'))
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
	let trackVideos = false
	let trackFiles = false
	let queue: ClientEvent[] = []
	let videoMs = 0
	let lastPlayTick = 0
	const positions = new WeakMap<object, number>()
	const seekFrom = new WeakMap<object, number>()
	const lastSeen = new WeakMap<object, { type: string; at: number }>()
	let lastSeekAt = 0
	// When each queued event happened (kept out of the payload).
	const queuedAt = new WeakMap<ClientEvent, number>()
	const pdfsSeen = new Set<string>()
	let pdfObserver: IntersectionObserver | null = null
	let domObserver: MutationObserver | null = null
	let scanTimer: ReturnType<typeof setTimeout> | null = null

	const isActive = () =>
		document.visibilityState === 'visible' &&
		(Date.now() - lastInteraction < inactivityMs || isVideoPlaying())

	const onInteraction = () => {
		lastInteraction = Date.now()
	}

	const handleAnswer = (answer: HeartbeatAnswer | undefined, sentFor: string) => {
		if (session !== sentFor || !answer) return
		if (answer.stop) stop()
		else if (answer.session && answer.session !== session) {
			// A new session counts its own video time from zero.
			session = answer.session
			videoMs = 0
		}
	}

	const push = (event: ClientEvent) => {
		if (queue.length >= QUEUE_LIMIT) return
		queuedAt.set(event, Date.now())
		queue.push(event)
	}

	// Plyr skips a Vimeo/YouTube video as pause, jump, play: the pause and play
	// of the same video right before the skip belong to the skip.
	const dropSkipNoise = (source: string, now: number) => {
		queue = queue.filter(
			(e) =>
				!(
					(e.type === 'video_pause' || e.type === 'video_play') &&
					e.source === source &&
					now - (queuedAt.get(e) ?? 0) < SEEK_MERGE_MS
				)
		)
	}

	const onMedia = (event: Event) => {
		if (!trackVideos) return
		const media = mediaOf(event)
		if (!media) return
		const { el, plyr } = media
		const position = Number(plyr ? plyr.currentTime : el.currentTime) || 0
		const paused = Boolean(plyr ? plyr.paused : el.paused)
		const now = Date.now()
		if (event.type === 'timeupdate') {
			positions.set(el, position)
			if (paused) return
			// Wall-clock time with a video playing, counted once even with two
			// videos playing together.
			if (lastPlayTick && now - lastPlayTick <= MAX_PLAY_TICK_MS) videoMs += now - lastPlayTick
			lastPlayTick = now
			return
		}
		if (event.type === 'seeking') {
			if (!seekFrom.has(el)) seekFrom.set(el, positions.get(el) ?? position)
			return
		}
		// Skips have their own merge below: two in a row are a drag, not a duplicate.
		if (event.type !== 'seeked') {
			const previous = lastSeen.get(el)
			if (previous && previous.type === event.type && now - previous.at < DUPLICATE_MS) return
			lastSeen.set(el, { type: event.type, at: now })
		}

		const duration = Number(plyr ? plyr.duration : el.duration) || undefined
		const source = sourcePath(plyr ? plyr.source || embedSource(el) : el.currentSrc || el.src)
		if (!source) return
		if (event.type === 'seeked') {
			const from = seekFrom.get(el) ?? positions.get(el) ?? position
			seekFrom.delete(el)
			positions.set(el, position)
			dropSkipNoise(source, now)
			const last = queue[queue.length - 1]
			if (last?.type === 'video_seek' && last.source === source && now - lastSeekAt < SEEK_MERGE_MS) {
				last.position = position
			} else {
				push({ type: 'video_seek', source, from, position, duration })
			}
			lastSeekAt = now
			return
		}
		// The browser pauses a video right before it ends: the end says it all.
		if (event.type === 'pause' && (el.ended || (duration && duration - position < 0.5))) return
		if (event.type !== 'play') lastPlayTick = 0
		push({ type: `video_${event.type}`, source, position, duration })
	}

	const onLinkClick = (event: MouseEvent) => {
		if (!trackFiles) return
		if (event.type === 'auxclick' && event.button !== 1) return
		const link = (event.target as Element | null)?.closest?.('a[href]')
		const file = platformFile(link?.getAttribute('href'))
		if (file) push({ type: 'download', file })
	}

	const scanPdfs = () => {
		scanTimer = null
		if (!pdfObserver) return
		document.querySelectorAll(PDF_SELECTOR).forEach((el) => {
			if ((el as any)._osAuditObserved) return
			;(el as any)._osAuditObserved = true
			pdfObserver!.observe(el)
		})
	}

	const watchPdfs = () => {
		if (typeof IntersectionObserver === 'undefined') return
		// A PDF counts as viewed once at least half of it is on screen.
		pdfObserver = new IntersectionObserver(
			(entries) => {
				entries.forEach((entry) => {
					if (!entry.isIntersecting) return
					pdfObserver?.unobserve(entry.target)
					const file = pdfFile(entry.target)
					if (!file || pdfsSeen.has(file)) return
					pdfsSeen.add(file)
					push({ type: 'pdf_open', file })
				})
			},
			{ threshold: 0.5 }
		)
		scanPdfs()
		// Lesson blocks render after the page: look again when the DOM changes.
		if (typeof MutationObserver !== 'undefined') {
			domObserver = new MutationObserver(() => {
				if (!scanTimer) scanTimer = setTimeout(scanPdfs, 500)
			})
			domObserver.observe(document.body, { childList: true, subtree: true })
		}
	}

	const unwatchPdfs = () => {
		pdfObserver?.disconnect()
		domObserver?.disconnect()
		if (scanTimer) clearTimeout(scanTimer)
		pdfObserver = domObserver = scanTimer = null
		document.querySelectorAll(PDF_SELECTOR).forEach((el) => delete (el as any)._osAuditObserved)
	}

	const send = (options: { close?: boolean; hidden?: boolean; keepalive?: boolean } = {}) => {
		const current = session
		if (!current) return
		const body: Record<string, unknown> = {
			session: current,
			active: isActive() ? 1 : 0,
			close: options.close ? 1 : 0,
			hidden: options.hidden ? 1 : 0,
		}
		// A skip back to where the video was is not a skip (blocked skipping
		// snaps the video back).
		const events = queue
			.splice(0, EVENTS_PER_SIGNAL)
			.filter((e) => e.type !== 'video_seek' || Math.round(e.from ?? -1) !== Math.round(e.position ?? -2))
		if (events.length) body.events = events
		// A lost signal loses its events, like its seconds: the lesson never waits.
		if (trackVideos) body.video_seconds = Math.round(videoMs / 1000)
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
		// Hidden: one last signal, which pauses the session on the server.
		// Visible again: signal at once, so the visit goes on in a new session promptly.
		if (document.visibilityState === 'hidden') send({ hidden: true, keepalive: true })
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
		if (trackVideos)
			MEDIA_EVENTS.forEach((name) => document.addEventListener(name, onMedia, { capture: true }))
		if (trackFiles) {
			document.addEventListener('click', onLinkClick, { capture: true })
			document.addEventListener('auxclick', onLinkClick, { capture: true })
			watchPdfs()
		}
	}

	const unlisten = () => {
		if (!listening) return
		listening = false
		INTERACTION_EVENTS.forEach((name) =>
			window.removeEventListener(name, onInteraction, { capture: true })
		)
		document.removeEventListener('visibilitychange', onVisibility)
		window.removeEventListener('pagehide', onPageHide)
		MEDIA_EVENTS.forEach((name) => document.removeEventListener(name, onMedia, { capture: true }))
		document.removeEventListener('click', onLinkClick, { capture: true })
		document.removeEventListener('auxclick', onLinkClick, { capture: true })
		unwatchPdfs()
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
		trackVideos = Boolean(Number(config.track_videos))
		trackFiles = Boolean(Number(config.track_files))
		queue = []
		videoMs = 0
		lastPlayTick = 0
		pdfsSeen.clear()
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
