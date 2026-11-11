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
