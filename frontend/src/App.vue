<template>
	<FrappeUIProvider>
		<Layout class="isolate text-p-base">
			<router-view />
		</Layout>
		<Dialogs />
	</FrappeUIProvider>
</template>
<script setup>
import { FrappeUIProvider } from 'frappe-ui'
import { Dialogs } from '@/utils/dialogs'
import { computed, onUnmounted, ref, watch } from 'vue'
import { useScreenSize } from './utils/composables'
import { useAiContext } from '@/stores/aiContext'
import { useSettings } from '@/stores/settings'
import { applyTheme } from '@/utils/theme'
import { useRouter } from 'vue-router'
import DesktopLayout from './components/Layouts/DesktopLayout.vue'
import MobileLayout from './components/Layouts/MobileLayout.vue'
import NoSidebarLayout from './components/Layouts/NoSidebarLayout.vue'

const { isMobile } = useScreenSize()
const router = useRouter()
const noSidebar = ref(false)
const aiContext = useAiContext()

// Backend-driven theme: LMSA Settings → theme overrides any local preference.
const settingsStore = useSettings()
watch(
	() => settingsStore.settings.data?.theme,
	(value) => {
		if (value === 'light' || value === 'dark') {
			applyTheme(value)
		}
	},
	{ immediate: true },
)

router.beforeEach((to, from, next) => {
	if (to.query.fromLesson || to.path === '/persona') {
		noSidebar.value = true
	} else {
		noSidebar.value = false
	}
	next()
})

router.afterEach((to) => {
	aiContext.syncFromRoute(to)
})

const Layout = computed(() => {
	if (noSidebar.value) {
		return NoSidebarLayout
	}
	if (isMobile.value) {
		return MobileLayout
	}
	return DesktopLayout
})

onUnmounted(() => {
	noSidebar.value = false
})
</script>
