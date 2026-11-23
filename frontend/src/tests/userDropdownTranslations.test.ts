// The user menu is a computed() of __() labels. On a cold load it is built
// before the translations arrive; it must rebuild once they land instead of
// keeping the English labels.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'

vi.mock('frappe-ui', () => ({
	call: vi.fn(),
	toast: { success: vi.fn(), error: vi.fn() },
	createResource: () => ({ data: null, reload: () => {}, fetch: () => {} }),
	Dropdown: { name: 'Dropdown', props: ['options'], template: '<div />' },
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('@/stores/session', () => ({
	sessionStore: () => ({
		logout: { submit: vi.fn() },
		branding: { data: null },
		isLoggedIn: true,
	}),
}))
vi.mock('@/stores/user', () => ({
	usersStore: () => ({
		userResource: { data: { name: 'a@x.it', roles: ['System Manager'] } },
	}),
}))
vi.mock('@/stores/settings', () => ({ useSettings: () => ({}) }))
vi.mock('@/utils', () => ({ convertToTitleCase: (s: string) => s }))
vi.mock('@/utils/theme', () => ({ toggleTheme: vi.fn(), theme: { value: 'light' } }))
vi.mock('@/oslms/utils/contrast', async () => {
	const { ref } = await import('vue')
	return { highContrast: ref(false), toggleContrast: vi.fn() }
})
vi.mock('@/utils/dialogs', () => ({ createDialog: vi.fn() }))
vi.mock('@/components/Settings/Settings.vue', () => ({ default: { template: '<div />' } }))
vi.mock('@/oslms/components/Settings/SettingsGestore.vue', () => ({
	default: { template: '<div />' },
}))

import UserDropdown from '@/components/Sidebar/UserDropdown.vue'
import { translate, translationsLoaded } from '@/translation'

afterEach(() => {
	delete (window as any).translatedMessages
	translationsLoaded.value = false
})

describe('user menu labels', () => {
	it('switches to the translated labels once the messages land', async () => {
		delete (window as any).translatedMessages
		translationsLoaded.value = false
		vi.stubGlobal('__', translate)
		const wrapper = mount(UserDropdown, { global: { mocks: { __: translate } } })
		const labels = () =>
			(wrapper.findComponent({ name: 'Dropdown' }).props('options') as any[])
				.flatMap((group) => group.items)
				.map((item) => item.label)

		expect(labels()).toContain('Toggle Theme')

		;(window as any).translatedMessages = {
			'Toggle Theme': 'Cambia Tema',
			'Manager Settings': 'Impostazioni gestore',
		}
		translationsLoaded.value = true
		await nextTick()

		expect(labels()).toContain('Cambia Tema')
		expect(labels()).toContain('Impostazioni gestore')
	})
})
