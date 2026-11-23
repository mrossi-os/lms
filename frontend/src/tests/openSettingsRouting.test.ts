// openSettings opens the panel the user can open
// (Impostazioni for administrators, Impostazioni gestore for Gestore).
import { beforeEach, describe, expect, it, vi } from 'vitest'

// '@/utils' pulls in Plyr, which reads matchMedia at import time.
const { toastErrorMock, settings, user } = vi.hoisted(() => {
	window.matchMedia ??= (() => ({
		matches: false,
		addEventListener: () => {},
		removeEventListener: () => {},
	})) as unknown as typeof window.matchMedia
	return {
		toastErrorMock: vi.fn(),
		settings: {} as Record<string, unknown>,
		user: { data: null as Record<string, unknown> | null },
	}
})

vi.mock('frappe-ui', () => ({
	call: vi.fn(),
	toast: { error: toastErrorMock },
	createResource: () => ({ data: null, reload: () => {}, fetch: () => {} }),
	Dialog: { name: 'Dialog', template: '<div><slot /></div>' },
	ErrorMessage: { name: 'ErrorMessage', template: '<div />' },
}))
vi.mock('@/stores/settings', () => ({ useSettings: () => settings }))
vi.mock('@/stores/user', () => ({
	usersStore: () => ({ userResource: user }),
}))

import { openSettings } from '@/utils'

const gestore = { name: 'g@x.it', roles: ['Gestore', 'Moderator'], is_gestore: true }
const admin = { name: 'a@x.it', roles: ['System Manager'] }

beforeEach(() => {
	toastErrorMock.mockReset()
	Object.assign(settings, {
		activeTab: null,
		isSettingsOpen: false,
		isSettingsMounted: true,
		isGestoreSettingsOpen: false,
		isGestoreSettingsMounted: true,
	})
})

describe('openSettings', () => {
	it('opens the manager panel on the Zoom tab for a Gestore', () => {
		user.data = gestore
		const close = vi.fn()
		expect(openSettings('Zoom Accounts', close)).toBe(true)
		expect(settings.activeTab).toBe('Zoom')
		expect(settings.isGestoreSettingsOpen).toBe(true)
		expect(settings.isSettingsOpen).toBe(false)
		expect(close).toHaveBeenCalled()
	})

	it('opens the admin panel on the Google Meet tab for an administrator', () => {
		user.data = admin
		expect(openSettings('Google Meet Accounts')).toBe(true)
		expect(settings.activeTab).toBe('Google Meet')
		expect(settings.isSettingsOpen).toBe(true)
		expect(settings.isGestoreSettingsOpen).toBe(false)
	})

	it('opens nothing for a Gestore asking for an admin-only tab', () => {
		user.data = gestore
		const close = vi.fn()
		expect(openSettings('General', close)).toBe(false)
		expect(toastErrorMock).toHaveBeenCalledWith(
			'This section is only available to administrators.',
		)
		expect(close).not.toHaveBeenCalled()
		expect(settings.isSettingsOpen).toBe(false)
		expect(settings.isGestoreSettingsOpen).toBe(false)
	})

	it('keeps the form open when the manager panel is not mounted (phone)', () => {
		user.data = gestore
		settings.isGestoreSettingsMounted = false
		const close = vi.fn()
		expect(openSettings('Members', close)).toBe(false)
		expect(toastErrorMock).toHaveBeenCalledWith(
			'Settings is only available on a larger screen.',
		)
		expect(close).not.toHaveBeenCalled()
	})
})
