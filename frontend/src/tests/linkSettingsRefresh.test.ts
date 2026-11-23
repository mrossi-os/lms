// Link reloads its options when a settings panel closes, so a Category or
// Zoom account created there shows up in the dropdown that opened it.
// Both panels count: Impostazioni (admin) and Impostazioni gestore.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import { nextTick, reactive } from 'vue'

const { reloadMock, settings } = vi.hoisted(() => ({
	reloadMock: vi.fn(),
	settings: {} as Record<string, unknown>,
}))

vi.mock('frappe-ui', () => ({
	Combobox: {
		name: 'Combobox',
		props: ['options', 'modelValue', 'open', 'align'],
		emits: ['update:open'],
		template: `<div />`,
	},
	Button: { template: `<button />` },
	FormControl: { template: `<input />` },
	FormLabel: { template: `<label />` },
	createResource: () => ({
		data: [],
		loading: false,
		update: () => {},
		reload: reloadMock,
		fetch: () => {},
	}),
}))

vi.mock('@/stores/settings', async () => {
	const { reactive: makeReactive } = await import('vue')
	const store = makeReactive(settings)
	return { useSettings: () => store }
})

import Link from '@/components/Controls/Link.vue'
import { useSettings } from '@/stores/settings'

const store = useSettings() as unknown as Record<string, unknown>

// The store is shared: a Link left mounted by an earlier test would reload too.
enableAutoUnmount(afterEach)

beforeEach(() => {
	vi.useFakeTimers()
	reloadMock.mockReset()
	Object.assign(store, {
		settings: { data: {} },
		isSettingsOpen: false,
		isGestoreSettingsOpen: false,
	})
})

const mountOpenedLink = async () => {
	const wrapper = mount(Link, {
		props: { doctype: 'LMS Category' },
		global: { mocks: { __: (s: string) => s } },
	})
	// Opening the dropdown loads the options once.
	wrapper.findComponent({ name: 'Combobox' }).vm.$emit('update:open', true)
	await nextTick()
	reloadMock.mockReset()
	return wrapper
}

const openAndClose = async (flag: string) => {
	store[flag] = true
	await nextTick()
	vi.advanceTimersByTime(250)
	store[flag] = false
	await nextTick()
	vi.advanceTimersByTime(250)
}

describe('Link options after a settings panel closes', () => {
	it('reloads when the admin settings panel closes', async () => {
		await mountOpenedLink()
		await openAndClose('isSettingsOpen')
		expect(reloadMock).toHaveBeenCalledTimes(1)
	})

	it('reloads when the manager settings panel closes', async () => {
		await mountOpenedLink()
		await openAndClose('isGestoreSettingsOpen')
		expect(reloadMock).toHaveBeenCalledTimes(1)
	})
})
