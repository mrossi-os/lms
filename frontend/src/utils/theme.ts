import { ref } from 'vue'

// Theme is controlled by the backend (LMSA Settings → theme). The watcher in
// App.vue applies the resolved value as soon as `get_lms_settings` resolves;
// localStorage acts only as a cache to avoid the initial flash.
const theme = ref<'light' | 'dark'>(localStorage.getItem('theme') as 'light' | 'dark' || 'light')

// OSLMS-CUSTOM: users cannot switch theme; it is fixed by the admin
const toggleTheme = () => {
	// no-op: theme is fixed by the sysadmin via LMSA Settings.
}

const applyTheme = (value: 'light' | 'dark') => {
	document.documentElement.setAttribute('data-theme', value)
	localStorage.setItem('theme', value)
	theme.value = value
}

// OSLMS-CUSTOM: applyTheme stays exported for the admin-theme watcher in App.vue
export { applyTheme, toggleTheme, theme }