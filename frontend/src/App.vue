<template>
	<FrappeUIProvider>
		<Layout class="isolate text-p-base">
			<router-view />
		</Layout>
		<NotificationPanel />
		<InstallPrompt v-if="isMobile && !settings.data?.disable_pwa" />
		<Dialogs />
	</FrappeUIProvider>
</template>
<script setup>
import { FrappeUIProvider } from 'frappe-ui'
import { Dialogs } from '@/utils/dialogs'
import { computed } from 'vue'
import { useScreenSize } from './utils/composables'
// OSLMS-CUSTOM: AI tutor course context store (os_lms)
import { useAiContext } from '@/stores/aiContext'
import { useSettings } from '@/stores/settings'
import { useRouter, useRoute } from 'vue-router'
import DesktopLayout from './components/Layouts/DesktopLayout.vue'
import MobileLayout from './components/Layouts/MobileLayout.vue'
import NoSidebarLayout from './components/Layouts/NoSidebarLayout.vue'
import InstallPrompt from './components/InstallPrompt.vue'
import NotificationPanel from '@/components/Notifications/NotificationPanel.vue'

const { isMobile } = useScreenSize()
const router = useRouter()
const route = useRoute()
const aiContext = useAiContext()
const { settings } = useSettings()

// Derive the layout from the current route, not a navigation guard. Flipping it
// in beforeEach swaps the layout the instant a navigation starts (before a lazy
// route component resolves), which re-mounts <router-view> while the old page is
// still showing, flashing it back into view. A route-driven computed changes in
// the same tick as the route, so the swap and the page change happen together.
const noSidebar = computed(
	() => Boolean(route.query.fromLesson) || route.path === '/persona'
)

// OSLMS-CUSTOM: keep the AI tutor course context in sync with the current route
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
</script>
