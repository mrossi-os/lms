/**
 * The batch Valutatore observes live classes and never starts them (decision of
 * 2026-11-23). LiveClassCard gets them as `observer`: no Start/Open button, but
 * the participant Join link for the whole join window, even before the host has
 * started the class. Hosts (`isAdmin`) keep Start/Open; students keep waiting
 * for the host.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import dayjs from 'dayjs'
import LiveClassCard from '@/components/LiveClassCard.vue'

vi.mock('frappe-ui', () => ({
	createResource: () => ({ loading: false, submit: vi.fn() }),
	toast: { error: vi.fn() },
	Badge: { props: ['label'], template: '<span>{{ label }}</span>' },
	Tooltip: { props: ['text'], template: '<div><slot /></div>' },
}))

vi.mock('@/utils/openExternal', () => ({ openExternal: vi.fn() }))

vi.stubGlobal('__', (text: string) => text)

// 10:10 on the class day: the class runs from 10:00 to 11:00.
const NOW = new Date('2026-11-24T10:10:00')

function liveClass(overrides: Record<string, unknown> = {}) {
	return {
		name: 'lc-1',
		title: 'Kick-off',
		description: '',
		date: '2026-11-24',
		time: '10:00:00',
		duration: 60,
		join_url: 'https://zoom.us/j/111',
		started_at: null,
		...overrides,
	}
}

function mountCard(props: Record<string, unknown>) {
	return mount(LiveClassCard, {
		props: { cls: liveClass(), ...props },
		global: {
			provide: { $dayjs: dayjs },
			directives: { external: {} },
			mocks: { __: (text: string) => text },
		},
	})
}

const startButton = (wrapper: ReturnType<typeof mountCard>) =>
	wrapper.findAll('button').find((b) => ['Start', 'Open'].includes(b.text()))

const joinLink = (wrapper: ReturnType<typeof mountCard>) =>
	wrapper.findAll('a').find((a) => a.text() === 'Join')

beforeEach(() => {
	vi.useFakeTimers({ toFake: ['Date'] })
	vi.setSystemTime(NOW)
})

afterEach(() => {
	vi.useRealTimers()
})

describe('LiveClassCard for the batch Valutatore', () => {
	it('never offers Start to an observer, even before the host starts', () => {
		const wrapper = mountCard({ observer: true })
		expect(startButton(wrapper)).toBeUndefined()
		expect(joinLink(wrapper)?.attributes('href')).toContain('join_live_class?name=lc-1')
	})

	it('never offers Open to an observer once the class has started', () => {
		const wrapper = mountCard({
			observer: true,
			cls: liveClass({ started_at: '2026-11-24 10:01:00' }),
		})
		expect(startButton(wrapper)).toBeUndefined()
		expect(joinLink(wrapper)).toBeDefined()
	})

	it('lets an observer join from 15 minutes before the start', () => {
		const wrapper = mountCard({ observer: true, cls: liveClass({ time: '10:20:00' }) })
		expect(joinLink(wrapper)).toBeDefined()
	})

	it('shows nothing to join outside the join window', () => {
		const wrapper = mountCard({ observer: true, cls: liveClass({ time: '11:00:00' }) })
		expect(joinLink(wrapper)).toBeUndefined()
		expect(startButton(wrapper)).toBeUndefined()
	})

	it('keeps Start for a host who is also the observer', () => {
		const wrapper = mountCard({ isAdmin: true, observer: true })
		expect(startButton(wrapper)?.text()).toBe('Start')
	})

	it('keeps the student waiting for the host', () => {
		const wrapper = mountCard({})
		expect(joinLink(wrapper)).toBeUndefined()
		expect(startButton(wrapper)).toBeUndefined()
		const disabledJoin = wrapper.findAll('button').find((b) => b.text() === 'Join')
		expect(disabledJoin?.attributes('disabled')).toBeDefined()
	})
})
