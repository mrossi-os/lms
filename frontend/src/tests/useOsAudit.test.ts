/**
 * OS Audit lesson heartbeat (oslms/composables/useOsAudit.ts, PIANO §5): the page
 * only reports state; the server computes the seconds.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, reactive } from 'vue'
import { mount } from '@vue/test-utils'
import { recordQuizStart, useOsAudit } from '../oslms/composables/useOsAudit'

type Lesson = { data: any }

let visibility: DocumentVisibilityState = 'visible'
const fetchMock = vi.fn()

function answer(message: any) {
	return Promise.resolve({ ok: true, json: () => Promise.resolve({ message }) })
}

function bodies() {
	return fetchMock.mock.calls.map(([, init]) => ({ ...JSON.parse(init.body), keepalive: init.keepalive }))
}

function mountWith(lesson: Lesson) {
	const Host = defineComponent({
		setup() {
			useOsAudit(lesson)
			return () => h('div')
		},
	})
	return mount(Host)
}

const tracked = (session = 'S1') => ({
	name: 'lesson-1',
	os_audit: { session, heartbeat_seconds: 30, inactivity_minutes: 3 },
})

beforeEach(() => {
	vi.useFakeTimers()
	visibility = 'visible'
	vi.spyOn(document, 'visibilityState', 'get').mockImplementation(() => visibility)
	fetchMock.mockReset()
	fetchMock.mockImplementation(() => answer({ session: 'S1' }))
	vi.stubGlobal('fetch', fetchMock)
	;(window as any).csrf_token = 'token-1'
})

afterEach(() => {
	vi.useRealTimers()
	vi.unstubAllGlobals()
	vi.restoreAllMocks()
})

describe('useOsAudit', () => {
	it('does nothing when get_lesson brings no audit session', async () => {
		const wrapper = mountWith(reactive({ data: { name: 'lesson-1' } }))
		await vi.advanceTimersByTimeAsync(120_000)
		wrapper.unmount()
		expect(fetchMock).not.toHaveBeenCalled()
	})

	it('sends a heartbeat every 30 s with the CSRF header, active after an interaction', async () => {
		const wrapper = mountWith(reactive({ data: tracked() }))
		window.dispatchEvent(new Event('mousemove'))
		await vi.advanceTimersByTimeAsync(30_000)
		expect(fetchMock).toHaveBeenCalledTimes(1)
		const [url, init] = fetchMock.mock.calls[0]
		expect(url).toBe('/api/method/os_lms.os_lms.os_audit.heartbeat')
		expect(init.method).toBe('POST')
		expect(init.headers['X-Frappe-CSRF-Token']).toBe('token-1')
		expect(bodies()[0]).toMatchObject({ session: 'S1', active: 1, close: 0 })
		wrapper.unmount()
	})

	it('reports present, not active, past the inactivity threshold', async () => {
		const wrapper = mountWith(reactive({ data: tracked() }))
		await vi.advanceTimersByTimeAsync(4 * 60_000)
		expect(bodies().at(-1)).toMatchObject({ active: 0 })
		wrapper.unmount()
	})

	it('counts a playing video as active', async () => {
		const wrapper = mountWith(reactive({ data: tracked() }))
		const player = document.createElement('div')
		player.className = 'plyr plyr--playing'
		document.body.appendChild(player)
		await vi.advanceTimersByTimeAsync(4 * 60_000)
		expect(bodies().at(-1)).toMatchObject({ active: 1 })
		player.remove()
		wrapper.unmount()
	})

	it('sends nothing while hidden, one keepalive signal when hiding', async () => {
		const wrapper = mountWith(reactive({ data: tracked() }))
		visibility = 'hidden'
		document.dispatchEvent(new Event('visibilitychange'))
		expect(bodies()).toEqual([expect.objectContaining({ keepalive: true, close: 0, hidden: 1 })])
		await vi.advanceTimersByTimeAsync(120_000)
		expect(fetchMock).toHaveBeenCalledTimes(1)
		wrapper.unmount()
	})

	it('signals at once when visible again and goes on in the session the server gives', async () => {
		const wrapper = mountWith(reactive({ data: tracked('S1') }))
		visibility = 'hidden'
		document.dispatchEvent(new Event('visibilitychange'))
		await vi.advanceTimersByTimeAsync(60_000)
		fetchMock.mockImplementationOnce(() => answer({ session: 'S2' }))
		visibility = 'visible'
		document.dispatchEvent(new Event('visibilitychange'))
		expect(bodies().at(-1)).toMatchObject({ session: 'S1', hidden: 0, close: 0, active: 1 })
		await vi.advanceTimersByTimeAsync(30_000)
		expect(bodies().at(-1)).toMatchObject({ session: 'S2', hidden: 0 })
		wrapper.unmount()
	})

	it('closes the session with keepalive when the page is left', async () => {
		const wrapper = mountWith(reactive({ data: tracked() }))
		window.dispatchEvent(new Event('pagehide'))
		expect(bodies()[0]).toMatchObject({ close: 1, keepalive: true })
		wrapper.unmount()
	})

	it('closes the old session and uses the new one on a lesson change', async () => {
		const lesson = reactive({ data: tracked('S1') })
		const wrapper = mountWith(lesson)
		lesson.data = tracked('S2')
		await nextTick()
		expect(bodies()[0]).toMatchObject({ session: 'S1', close: 1 })
		fetchMock.mockImplementation(() => answer({ session: 'S2' }))
		await vi.advanceTimersByTimeAsync(30_000)
		expect(bodies().at(-1)).toMatchObject({ session: 'S2', close: 0 })
		wrapper.unmount()
	})

	it('follows a new session from the server and stops when told to', async () => {
		fetchMock.mockImplementationOnce(() => answer({ session: 'S9' }))
		const wrapper = mountWith(reactive({ data: tracked('S1') }))
		await vi.advanceTimersByTimeAsync(30_000)
		fetchMock.mockImplementation(() => answer({ stop: 1 }))
		await vi.advanceTimersByTimeAsync(30_000)
		expect(bodies().at(-1)).toMatchObject({ session: 'S9' })
		const sent = fetchMock.mock.calls.length
		await vi.advanceTimersByTimeAsync(120_000)
		expect(fetchMock).toHaveBeenCalledTimes(sent)
		wrapper.unmount()
	})

	it('never throws when the network fails', async () => {
		fetchMock.mockImplementation(() => Promise.reject(new Error('offline')))
		const wrapper = mountWith(reactive({ data: tracked() }))
		await vi.advanceTimersByTimeAsync(30_000)
		wrapper.unmount()
		expect(fetchMock).toHaveBeenCalled()
	})

	it('records a quiz start', async () => {
		recordQuizStart('quiz-1')
		recordQuizStart(undefined)
		expect(fetchMock).toHaveBeenCalledTimes(1)
		expect(fetchMock.mock.calls[0][0]).toBe('/api/method/os_lms.os_lms.os_audit.quiz_start')
		expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ quiz: 'quiz-1' })
	})
})

// Phase 3 (PIANO §15): videos, PDFs and downloads travel with the heartbeat.
describe('useOsAudit, videos and files', () => {
	const collecting = (flags = { track_videos: 1, track_files: 1 }) => ({
		name: 'lesson-1',
		os_audit: { session: 'S1', heartbeat_seconds: 30, inactivity_minutes: 3, ...flags },
	})

	function fakeVideo(state: Record<string, any>) {
		const el = document.createElement('video')
		for (const [key, value] of Object.entries({ currentSrc: '/files/a.mp4', duration: 100, ended: false, paused: true, currentTime: 0, ...state }))
			Object.defineProperty(el, key, { value, writable: true, configurable: true })
		document.body.appendChild(el)
		return el as HTMLVideoElement & Record<string, any>
	}

	const fire = (el: EventTarget, type: string, init?: CustomEventInit) =>
		el.dispatchEvent(init ? new CustomEvent(type, init) : new Event(type))

	async function sentEvents() {
		await vi.advanceTimersByTimeAsync(30_000)
		return bodies().at(-1)
	}

	afterEach(() => {
		document.body.innerHTML = ''
	})

	it('collects nothing when the audit does not ask for it', async () => {
		const wrapper = mountWith(reactive({ data: collecting({ track_videos: 0, track_files: 0 }) }))
		fire(fakeVideo({ currentTime: 5 }), 'play')
		const body = await sentEvents()
		expect(body.events).toBeUndefined()
		expect(body.video_seconds).toBeUndefined()
		wrapper.unmount()
	})

	it('sends play, pause and end with the video and the position', async () => {
		const wrapper = mountWith(reactive({ data: collecting() }))
		const video = fakeVideo({ currentTime: 5.2 })
		fire(video, 'play')
		fire(video, 'play') // the same event twice in a row is one event
		video.currentTime = 40
		fire(video, 'pause')
		// The pause the browser fires right before the end is not recorded.
		video.currentTime = 100
		video.ended = true
		fire(video, 'pause')
		fire(video, 'ended')
		expect((await sentEvents()).events).toEqual([
			{ type: 'video_play', source: '/files/a.mp4', position: 5.2, duration: 100 },
			{ type: 'video_pause', source: '/files/a.mp4', position: 40, duration: 100 },
			{ type: 'video_ended', source: '/files/a.mp4', position: 100, duration: 100 },
		])
		wrapper.unmount()
	})

	it('counts the Plyr event on the media once, not its copy on the container', async () => {
		const wrapper = mountWith(reactive({ data: collecting() }))
		const container = document.createElement('div')
		const media = document.createElement('div')
		container.appendChild(media)
		document.body.appendChild(container)
		const plyr = {
			media,
			elements: { container },
			currentTime: 12,
			duration: 300,
			paused: false,
			source: 'https://player.vimeo.com/video/123',
		}
		fire(media, 'play', { detail: { plyr } })
		fire(container, 'play', { detail: { plyr }, bubbles: true })
		expect((await sentEvents()).events).toEqual([
			{ type: 'video_play', source: 'https://player.vimeo.com/video/123', position: 12, duration: 300 },
		])
		wrapper.unmount()
	})

	it('counts the container copy once when YouTube took the media out of the page', async () => {
		const wrapper = mountWith(reactive({ data: collecting() }))
		const container = document.createElement('div')
		container.innerHTML = '<iframe src="https://www.youtube-nocookie.com/embed/abc"></iframe>'
		document.body.appendChild(container)
		// Plyr keeps a reference to the element the YouTube API replaced.
		const media = document.createElement('div')
		const plyr = {
			media,
			elements: { container },
			currentTime: 0,
			duration: 180,
			paused: false,
			source: 'https://www.youtube.com/watch?v=abc',
		}
		const both = (type: string) => {
			fire(media, type, { detail: { plyr } })
			fire(container, type, { detail: { plyr }, bubbles: true })
		}
		both('play')
		for (let second = 1; second <= 3; second++) {
			vi.advanceTimersByTime(1000)
			plyr.currentTime = second
			both('timeupdate')
		}
		plyr.paused = true
		both('pause')
		const body = await sentEvents()
		expect(body.events).toEqual([
			{ type: 'video_play', source: 'https://www.youtube.com/watch?v=abc', position: 0, duration: 180 },
			{ type: 'video_pause', source: 'https://www.youtube.com/watch?v=abc', position: 3, duration: 180 },
		])
		expect(body.video_seconds).toBe(2)
		wrapper.unmount()
	})

	it('keeps one name per YouTube video and drops the pauses it resumes from at once', async () => {
		const wrapper = mountWith(reactive({ data: collecting() }))
		const container = document.createElement('div')
		document.body.appendChild(container)
		const plyr = {
			media: document.createElement('div'),
			elements: { container },
			currentTime: 0,
			duration: 143,
			paused: false,
			source: 'https://www.youtube.com/watch?v=abc',
		}
		const at = (type: string, time: number, url = `https://www.youtube.com/watch?t=${Math.floor(time)}&v=abc`) => {
			plyr.currentTime = time
			plyr.source = url
			fire(container, type, { detail: { plyr }, bubbles: true })
		}
		// What Plyr reported on staging: play, pause and play again while starting...
		at('play', 0, 'https://www.youtube.com/watch?v=abc')
		at('pause', 0, 'https://www.youtube.com/watch?v=abc')
		vi.advanceTimersByTime(400)
		at('play', 5)
		vi.advanceTimersByTime(5000)
		at('timeupdate', 78)
		// ...then pause, play, skip, pause, play around a skip.
		at('pause', 78)
		at('play', 78)
		at('seeking', 78)
		at('seeked', 118)
		at('pause', 118)
		vi.advanceTimersByTime(300)
		at('play', 119)
		vi.advanceTimersByTime(7000)
		at('pause', 126)
		expect((await sentEvents()).events).toEqual([
			{ type: 'video_play', source: 'https://www.youtube.com/watch?v=abc', position: 0, duration: 143 },
			{ type: 'video_seek', source: 'https://www.youtube.com/watch?v=abc', from: 78, position: 118, duration: 143 },
			{ type: 'video_pause', source: 'https://www.youtube.com/watch?v=abc', position: 126, duration: 143 },
		])
		wrapper.unmount()
	})

	it('names a Vimeo embed by its player iframe when Plyr has no source', async () => {
		const wrapper = mountWith(reactive({ data: collecting() }))
		const media = document.createElement('div')
		media.innerHTML =
			'<iframe src="https://player.vimeo.com/video/1176116607?loop=false&h=464f910a1b"></iframe>'
		document.body.appendChild(media)
		const plyr = { media, currentTime: 3, duration: 450, paused: false, source: undefined }
		fire(media, 'play', { detail: { plyr } })
		expect((await sentEvents()).events).toEqual([
			{ type: 'video_play', source: 'https://player.vimeo.com/video/1176116607', position: 3, duration: 450 },
		])
		wrapper.unmount()
	})

	it('leaves out the pause and play Plyr makes around a skip', async () => {
		const wrapper = mountWith(reactive({ data: collecting() }))
		const video = fakeVideo({ currentTime: 7, paused: false, duration: 458 })
		fire(video, 'play')
		vi.advanceTimersByTime(5000)
		// Plyr on Vimeo: pause, play at the new point, then seeked.
		fire(video, 'seeking')
		fire(video, 'pause')
		video.currentTime = 348
		fire(video, 'play')
		fire(video, 'seeked')
		vi.advanceTimersByTime(4000)
		video.currentTime = 352
		fire(video, 'pause')
		expect((await sentEvents()).events.map((e: any) => [e.type, e.position])).toEqual([
			['video_play', 7],
			['video_seek', 348],
			['video_pause', 352],
		])
		wrapper.unmount()
	})

	it('merges a drag on the progress bar into one skip and drops a skip that snaps back', async () => {
		const wrapper = mountWith(reactive({ data: collecting() }))
		const video = fakeVideo({ currentTime: 10 })
		fire(video, 'timeupdate')
		for (const position of [30, 55, 80]) {
			fire(video, 'seeking')
			video.currentTime = position
			fire(video, 'seeked')
			vi.advanceTimersByTime(300)
		}
		// Skipping blocked by the course: the video jumps forward and back.
		vi.advanceTimersByTime(3000)
		fire(video, 'seeking')
		video.currentTime = 95
		fire(video, 'seeked')
		fire(video, 'seeking')
		video.currentTime = 80
		fire(video, 'seeked')
		expect((await sentEvents()).events).toEqual([
			{ type: 'video_seek', source: '/files/a.mp4', from: 10, position: 80, duration: 100 },
		])
		wrapper.unmount()
	})

	it('sends the time a video was playing, counted once with two videos', async () => {
		const wrapper = mountWith(reactive({ data: collecting() }))
		const first = fakeVideo({ paused: false })
		const second = fakeVideo({ paused: false })
		for (let i = 0; i < 40; i++) {
			fire(first, 'timeupdate')
			fire(second, 'timeupdate')
			vi.advanceTimersByTime(250)
		}
		// 10 s of wall time; the first tick only starts the count.
		expect((await sentEvents()).video_seconds).toBe(10)
		wrapper.unmount()
	})

	it('records platform files opened from a link, nothing else', async () => {
		const wrapper = mountWith(reactive({ data: collecting() }))
		document.body.innerHTML = `
			<a id="file" href="/files/slides%20v2.pdf"><span id="icon"></span></a>
			<a id="private" href="/private/files/data.zip"></a>
			<a id="outside" href="https://example.com/files/x.pdf"></a>
			<a id="page" href="/lms/courses"></a>
			<a id="gated" download href="/api/method/lms.lms.doctype.course_lesson.course_lesson.serve_resource?file_url=/private/files/message%20%285%29.txt"></a>`
		const click = (id: string, init: MouseEventInit = {}) =>
			document.getElementById(id)!.dispatchEvent(new MouseEvent(init.button === undefined ? 'click' : 'auxclick', { bubbles: true, ...init }))
		click('icon')
		click('private', { button: 1 })
		click('private', { button: 2 })
		click('outside')
		click('page')
		click('gated')
		expect((await sentEvents()).events).toEqual([
			{ type: 'download', file: '/files/slides v2.pdf' },
			{ type: 'download', file: '/private/files/data.zip' },
			// A private lesson file goes through the gated endpoint: the file is its parameter.
			{ type: 'download', file: '/private/files/message (5).txt' },
		])
		wrapper.unmount()
	})

	it('records a PDF once, when half of it is on screen', async () => {
		let notify: (entries: any[]) => void = () => {}
		const observed: Element[] = []
		vi.stubGlobal(
			'IntersectionObserver',
			class {
				constructor(callback: any) {
					notify = callback
				}
				observe(el: Element) {
					observed.push(el)
				}
				unobserve() {}
				disconnect() {}
			}
		)
		document.body.innerHTML = '<div class="pdf-block"><a href="/files/handout.pdf"></a></div>'
		const wrapper = mountWith(reactive({ data: collecting() }))
		const block = document.querySelector('.pdf-block')!
		expect(observed).toEqual([block])
		notify([{ target: block, isIntersecting: false }])
		notify([{ target: block, isIntersecting: true }])
		notify([{ target: block, isIntersecting: true }])
		expect((await sentEvents()).events).toEqual([{ type: 'pdf_open', file: '/files/handout.pdf' }])
		wrapper.unmount()
	})
})
