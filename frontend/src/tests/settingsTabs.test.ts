// OSLMS-CUSTOM: tab definitions shared by Settings.vue and the manager panel.
import { describe, expect, it, vi } from 'vitest'

// The tab components are only referenced, never rendered, here.
const { stub } = vi.hoisted(() => ({
	stub: (name: string) => ({ default: { name } }),
}))
vi.mock('@/components/Settings/Members.vue', () => stub('Members'))
vi.mock('@/components/Settings/Categories.vue', () => stub('Categories'))
vi.mock('@/components/Settings/EmailTemplate/EmailTemplatePage.vue', () =>
	stub('EmailTemplatePage'),
)
vi.mock('@/components/Settings/BrandSettings.vue', () => stub('BrandSettings'))
vi.mock('@/components/Settings/ZoomSettings.vue', () => stub('ZoomSettings'))
vi.mock('@/components/Settings/GoogleMeetSettings.vue', () =>
	stub('GoogleMeetSettings'),
)
vi.mock('@/components/Settings/GoogleCalendarSettings.vue', () =>
	stub('GoogleCalendarSettings'),
)
vi.mock('@/oslms/components/ai/Settings/AISettings.vue', () => stub('AISettings'))
vi.mock('@/oslms/components/ai/Settings/PromptSettings.vue', () =>
	stub('PromptSettings'),
)
vi.mock('@/oslms/components/ai/Settings/SimulationLimitsSettings.vue', () =>
	stub('SimulationLimitsSettings'),
)
vi.mock('@/oslms/components/trueskills/TrueSkillsSettings.vue', () =>
	stub('TrueSkillsSettings'),
)
vi.mock('@/oslms/components/eliteApi/EliteApiSettings.vue', () =>
	stub('EliteApiSettings'),
)
vi.mock('@/oslms/components/AccountDeletionRequestsSettings.vue', () =>
	stub('AccountDeletionRequestsSettings'),
)
const { userData } = vi.hoisted(() => ({
	userData: { show_account_deletion_requests: true } as Record<string, unknown>,
}))
vi.mock('@/stores/user', () => ({
	usersStore: () => ({ userResource: { data: userData } }),
}))

import { GESTORE_SETTINGS_TAB_KEYS } from '@/oslms/utils/settingsAccess'
import {
	applyTabConditions,
	brandingTab,
	buildGestoreSettingsTabs,
	categoriesTab,
	courseProgressTab,
	emailTemplatesTab,
	googleCalendarTab,
	googleMeetTab,
	membersTab,
	welcomeTab,
	zoomTab,
} from '@/oslms/utils/settingsTabs'

const fieldNames = (tab: any): string[] =>
	(tab.sections || []).flatMap((section: any) =>
		section.columns.flatMap((column: any) =>
			column.fields.map((field: any) => field.name),
		),
	)

describe('shared settings tabs', () => {
	it('gives every builder its stable key', () => {
		expect(courseProgressTab().key).toBe('Course Progress')
		expect(categoriesTab().key).toBe('Categories')
		expect(emailTemplatesTab().key).toBe('Email Templates')
		expect(membersTab().key).toBe('Members')
		expect(zoomTab().key).toBe('Zoom')
		expect(googleMeetTab().key).toBe('Google Meet')
		expect(googleCalendarTab().key).toBe('Google Calendar')
		expect(brandingTab().key).toBe('Branding')
		expect(welcomeTab().key).toBe('Welcome Video')
	})

	it('keeps the Course Progress fields', () => {
		expect(fieldNames(courseProgressTab())).toEqual([
			'lesson_dwell_time',
			'enforce_video_completion',
			'enforce_assignment_completion',
			'enforce_quiz_completion',
		])
	})

	it('keeps the Welcome fields', () => {
		expect(fieldNames(welcomeTab())).toEqual([
			'welcome_notification_enabled',
			'welcome_notification_message',
			'welcome_video_enabled',
			'welcome_video_title',
			'welcome_video_subtitle',
			'welcome_video_file',
		])
	})

	it('renders Branding through its own component', () => {
		expect(brandingTab().template).toBeDefined()
		expect(fieldNames(brandingTab())).toEqual(['app_name', 'banner_image', 'favicon'])
	})

	it('passes the caller condition to Google Calendar', () => {
		const condition = () => true
		expect(googleCalendarTab(condition).condition).toBe(condition)
	})
})

describe('manager settings panel', () => {
	const keys = () =>
		applyTabConditions(buildGestoreSettingsTabs()).flatMap((group: any) =>
			group.items.map((item: any) => item.key),
		)

	it('shows exactly the tabs a Gestore may open', () => {
		userData.show_account_deletion_requests = true
		expect(new Set(keys())).toEqual(new Set(GESTORE_SETTINGS_TAB_KEYS))
		expect(keys()).toHaveLength(GESTORE_SETTINGS_TAB_KEYS.length)
	})

	it('hides deletion requests when there is nothing to review', () => {
		userData.show_account_deletion_requests = false
		expect(keys()).not.toContain('Account deletion requests')
		expect(keys()).toHaveLength(GESTORE_SETTINGS_TAB_KEYS.length - 1)
	})

	it('never shows an administrator-only tab', () => {
		userData.show_account_deletion_requests = true
		for (const key of ['General', 'Badges', 'Sidebar', 'Signup', 'SEO', 'Raven', 'AI', 'Accounts', 'Corsi', 'Classi', 'Privacy']) {
			expect(keys()).not.toContain(key)
		}
	})
})
