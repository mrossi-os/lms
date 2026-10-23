import { ref } from 'vue'
import type { MobileRowGroup } from '@/components/Settings/mobileSettings'
import { translationsLoaded } from '@/translation'

// High contrast is a second switch next to light/dark, not a third theme: it
// sets <html data-contrast="more">, and styles/theme/elite/high-contrast.css
// remaps the frappe-ui tokens under that attribute in both themes. Brand
// Customize colors never apply under it (see os_lms branding.py).
//
// 'system' follows the OS "increase contrast" setting until the user picks;
// the choice is per device, like the colour mode. Keep the resolution rules in
// step with the index.html bootstrap — tests/highContrast.test.ts checks both.
export type ContrastPreference = 'more' | 'normal' | 'system'

const PREFERENCE_KEY = 'contrastPreference'

const prefersMoreContrast = (): boolean =>
	typeof window !== 'undefined' &&
	typeof window.matchMedia === 'function' &&
	window.matchMedia('(prefers-contrast: more)').matches

const storedPreference = (): ContrastPreference => {
	const stored = localStorage.getItem(PREFERENCE_KEY)
	return stored === 'more' || stored === 'normal' ? stored : 'system'
}

const resolve = (preference: ContrastPreference): boolean =>
	preference === 'system' ? prefersMoreContrast() : preference === 'more'

const contrastPreference = ref<ContrastPreference>(storedPreference())
const highContrast = ref<boolean>(resolve(contrastPreference.value))

const paint = (on: boolean): void => {
	if (on) document.documentElement.setAttribute('data-contrast', 'more')
	else document.documentElement.removeAttribute('data-contrast')
	highContrast.value = on
}

const setContrastPreference = (preference: ContrastPreference): void => {
	contrastPreference.value = preference
	localStorage.setItem(PREFERENCE_KEY, preference)
	paint(resolve(preference))
}

// Flipping the switch is an explicit choice, so it stops following the OS.
const toggleContrast = (): void => {
	setContrastPreference(highContrast.value ? 'normal' : 'more')
}

if (typeof document !== 'undefined') paint(highContrast.value)

if (typeof window !== 'undefined' && typeof window.matchMedia === 'function') {
	window
		.matchMedia('(prefers-contrast: more)')
		.addEventListener('change', () => {
			if (contrastPreference.value === 'system') paint(resolve('system'))
		})
}

export const CONTRAST_ACTION = 'high-contrast'

// The phone "You" page lists this row right after "Colour mode". Tapping it
// toggles directly: two states need no sheet.
// Reading translationsLoaded makes the page's computed rebuild once the
// messages land; the values here (and Colour mode's) are translated in script,
// so they would otherwise stay English after a cold load.
export const withContrastRow = (
	groups: MobileRowGroup[],
	on: boolean,
): MobileRowGroup[] => {
	void translationsLoaded.value
	return groups.map((group) => {
		const at = group.rows.findIndex((row) => row.key === 'colour-mode')
		if (at < 0) return group
		const rows = [...group.rows]
		rows.splice(at + 1, 0, {
			key: CONTRAST_ACTION,
			label: 'High contrast',
			icon: 'lucide-contrast',
			value: on ? __('Active') : __('Inactive'),
			action: CONTRAST_ACTION,
		})
		return { ...group, rows }
	})
}

export {
	contrastPreference,
	highContrast,
	setContrastPreference,
	toggleContrast,
}
