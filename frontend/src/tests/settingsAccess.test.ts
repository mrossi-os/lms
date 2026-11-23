// who opens which settings panel (Impostazioni / Impostazioni gestore).
import { describe, expect, it } from 'vitest'
import {
	canOpenGestoreSettings,
	isSettingsAdmin,
	resolveSettingsTarget,
} from '@/oslms/utils/settingsAccess'

const admin = { name: 'a@x.it', roles: ['System Manager'] }
const gestore = {
	name: 'g@x.it',
	roles: ['Gestore', 'Moderator'],
	is_gestore: true,
}
const both = {
	name: 'b@x.it',
	roles: ['System Manager', 'Gestore'],
	is_gestore: true,
}
const docente = { name: 'd@x.it', roles: ['Docente'], is_instructor: true }

describe('resolveSettingsTarget', () => {
	it('sends an administrator to the admin panel and resolves the Zoom alias', () => {
		expect(resolveSettingsTarget('Zoom Accounts', admin)).toEqual({
			panel: 'admin',
			key: 'Zoom',
		})
	})

	it('sends a Gestore to the manager panel for one of its tabs', () => {
		expect(resolveSettingsTarget('Members', gestore)).toEqual({
			panel: 'gestore',
			key: 'Members',
		})
	})

	it('resolves the Google Meet alias for a Gestore', () => {
		expect(resolveSettingsTarget('Google Meet Accounts', gestore)).toEqual({
			panel: 'gestore',
			key: 'Google Meet',
		})
	})

	it('opens nothing for a Gestore asking for an admin-only tab', () => {
		expect(resolveSettingsTarget('General', gestore)).toEqual({
			panel: 'none',
			key: 'General',
		})
	})

	it('prefers the admin panel for someone who is both', () => {
		expect(resolveSettingsTarget('Members', both)).toEqual({
			panel: 'admin',
			key: 'Members',
		})
	})

	it('opens nothing for a Docente', () => {
		expect(resolveSettingsTarget('Members', docente)).toEqual({
			panel: 'none',
			key: 'Members',
		})
	})

	it('opens nothing while the user is not loaded', () => {
		expect(resolveSettingsTarget('Members', undefined).panel).toBe('none')
	})
})

describe('role checks', () => {
	it('treats the Administrator user as admin even without roles', () => {
		expect(isSettingsAdmin({ name: 'Administrator', roles: [] })).toBe(true)
	})

	it('does not let a Docente open the manager panel', () => {
		expect(canOpenGestoreSettings(docente)).toBe(false)
	})

	it('lets a Gestore and an administrator open the manager panel', () => {
		expect(canOpenGestoreSettings(gestore)).toBe(true)
		expect(canOpenGestoreSettings(admin)).toBe(true)
	})
})
