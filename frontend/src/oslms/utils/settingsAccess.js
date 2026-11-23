// who opens which settings panel.
// "Impostazioni" (Settings.vue) is for administrators; "Impostazioni gestore"
// (SettingsGestore.vue) for Gestore and administrators. The server enforces the
// same split on LMS Settings (os_lms settings_access.py).
// Design: docs/superpowers/specs/2026-11-18-impostazioni-gestore-design.md

export const SETTINGS_ADMIN_ROLES = ['System Manager', 'Administrator']

// Stable keys of the tabs in the manager panel (see buildGestoreSettingsTabs).
export const GESTORE_SETTINGS_TAB_KEYS = [
	'Course Progress',
	'Categories',
	'Email Templates',
	'Members',
	'Zoom',
	'Google Meet',
	'Google Calendar',
	'Branding',
	'Welcome Video',
	'TrueSkills API',
	'Elite API',
	'Account deletion requests',
	'Prompt AI',
	'Limiti simulazioni AI',
]

// Names some callers use for a tab whose key is different (BatchForm's account links).
export const SETTINGS_TAB_ALIASES = {
	'Zoom Accounts': 'Zoom',
	'Google Meet Accounts': 'Google Meet',
}

export const isSettingsAdmin = (userData) => {
	if (!userData) return false
	if (userData.name === 'Administrator') return true
	const roles = userData.roles || []
	return SETTINGS_ADMIN_ROLES.some((role) => roles.includes(role))
}

export const isSettingsGestore = (userData) => Boolean(userData?.is_gestore)

export const canOpenGestoreSettings = (userData) =>
	isSettingsAdmin(userData) || isSettingsGestore(userData)

export const resolveSettingsTarget = (category, userData) => {
	const key = SETTINGS_TAB_ALIASES[category] || category
	if (isSettingsAdmin(userData)) return { panel: 'admin', key }
	if (isSettingsGestore(userData) && GESTORE_SETTINGS_TAB_KEYS.includes(key)) {
		return { panel: 'gestore', key }
	}
	return { panel: 'none', key }
}
