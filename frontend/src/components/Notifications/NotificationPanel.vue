<!-- eslint-disable vue/no-v-html -->
<template>
	<Teleport to="body">
		<div
			v-if="panelVisible"
			ref="panelRef"
			class="fixed z-30 bg-surface-base transition-all duration-300 ease-in-out"
			:class="isMobile ? 'inset-0' : 'top-0 bottom-0'"
			:style="
				isMobile
					? {}
					: {
							left: sidebarLeft,
							width: '400px',
							boxShadow: '8px 0px 8px rgba(0, 0, 0, 0.1)',
						}
			"
		>
			<div class="flex h-full flex-col text-ink-gray-9">
				<div class="flex justify-between items-center">
					<div class="text-lg font-medium text-ink-gray-8 px-4 pt-[15px] pb-3">
						{{ __('Notifications') }}
					</div>
					<div class="flex gap-1 mr-3">
						<Tooltip v-if="hasUnread" :text="__('Mark all as read')">
							<Button variant="ghost" @click="markAllAsRead.submit">
								<template #icon>
									<span class="lucide-check-check size-4 text-ink-gray-7" />
								</template>
							</Button>
						</Tooltip>
						<Button v-if="isMobile" variant="ghost" @click="closeNotifications">
							<template #icon>
								<span class="lucide-x size-4 text-ink-gray-7" />
							</template>
						</Button>
					</div>
				</div>
				<TabButtons
					v-model="activeTab"
					:buttons="tabs"
					class="tab-buttons w-full px-4 py-1"
				/>
				<div class="flex h-full overflow-hidden">
					<div
						v-if="filtered.length"
						class="w-full divide-y divide-outline-gray-2 overflow-auto text-p-base"
					>
						<div
							v-for="n in filtered"
							:key="n.name"
							class="flex cursor-pointer items-start gap-2.5 px-4 py-2.5 hover:bg-surface-gray-2"
							@click="onSelect(n)"
						>
							<div class="mt-1 flex items-center gap-2.5">
								<div
									class="size-[5px] rounded-full"
									:class="n.read ? 'bg-transparent' : 'bg-surface-gray-7'"
								/>
								<Avatar
									:image="n.from_user_details?.user_image"
									:label="n.from_user_details?.full_name"
									size="lg"
								/>
							</div>
							<div>
								<div v-html="sanitizeHTML(n.subject)" />
								<div class="text-p-sm text-ink-gray-5">
									{{ dayjs(n.creation).fromNow() }}
								</div>
							</div>
						</div>
					</div>
					<EmptyStateLayout
						v-else
						name="Notifications"
						:title="emptyTitle"
						:description="emptyDescription"
						icon="lucide-bell"
						width="lg"
					/>
				</div>
			</div>
		</div>
	</Teleport>
</template>
<script setup>
import { Avatar, Button, TabButtons, Tooltip, toast } from 'frappe-ui'
import { computed, inject, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { onClickOutside } from '@vueuse/core'
import { sanitizeHTML } from '@/utils'
import { useSidebar } from '@/stores/sidebar'
import { useScreenSize } from '@/utils/composables'
import EmptyStateLayout from '@/components/Layouts/EmptyStateLayout.vue'
import {
	panelVisible,
	closeNotifications,
	notifications,
	markAsRead,
	markAllAsRead,
} from '@/stores/notifications'

const dayjs = inject('$dayjs')
const router = useRouter()
const sidebarStore = useSidebar()
const { isMobile } = useScreenSize()

const panelRef = ref(null)
const activeTab = ref('Unread')
// `value` keeps the logical key stable (the filter/empty-state code compares
// against 'Unread'/'Read') while `label` is translated for display.
const tabs = [
	{ label: __('Unread'), value: 'Unread' },
	{ label: __('Read'), value: 'Read' },
]

onClickOutside(panelRef, () => closeNotifications(), {
	ignore: ['[data-notifications-trigger]'],
})

const filtered = computed(() => {
	const data = notifications.data || []
	return activeTab.value === 'Unread'
		? data.filter((n) => !n.read)
		: data.filter((n) => n.read)
})

const emptyTitle = computed(() =>
	activeTab.value === 'Unread'
		? __('No unread notifications')
		: __('No read notifications'),
)

const emptyDescription = computed(() =>
	activeTab.value === 'Unread'
		? __("You're all caught up! Check back later for updates.")
		: __('Notifications you have read will appear here.'),
)

const sidebarLeft = computed(() =>
	sidebarStore.isSidebarCollapsed ? '3.5rem' : '14rem',
)

const hasUnread = computed(() => notifications.data?.some((n) => !n.read))

// Fetch on open (and refresh whenever the panel is reopened).
watch(panelVisible, (open) => {
	if (open) notifications.reload()
})

const onSelect = (n) => {
	if (!n.read) markAsRead.submit({ name: n.name })
	navigateToPage(n)
	closeNotifications()
}

const notifyUnavailable = () =>
	toast.warning(__('Unable to open this notification.'))

const navigateToPage = (log) => {
	if (!log.link) return

	// Notification links can be absolute or relative, may carry the /lms prefix,
	// and often include a tab fragment (e.g. .../batches/<name>#discussions). Peel
	// the fragment off so it becomes the route hash instead of leaking into the
	// route param, then normalize the path segments (drop empties + leading lms).
	const [rawPath, hash] = String(log.link).split('#')
	const segments = rawPath.split('/').filter(Boolean)
	if (segments[0] === 'lms') segments.shift()

	let target = null
	if (segments[0] === 'courses' && segments[1]) {
		target = { name: 'CourseDetail', params: { courseName: segments[1] } }
	} else if (segments[0] === 'batches') {
		const batchName = segments[1] === 'details' ? segments[2] : segments[1]
		if (batchName) target = { name: 'BatchDetail', params: { batchName } }
	} else if (segments[0] === 'assignment-submission' && segments[2]) {
		target = {
			name: 'AssignmentSubmission',
			params: { assignmentID: segments[1], submissionName: segments[2] },
		}
	}

	if (!target) {
		notifyUnavailable()
		return
	}
	if (hash) target.hash = `#${hash}`

	// Guard stale/unknown links (deleted docs, removed routes): warn instead of
	// letting the router throw an uncaught "No match" error.
	try {
		router.resolve(target)
	} catch (e) {
		notifyUnavailable()
		return
	}
	router.push(target).catch(() => notifyUnavailable())
}
</script>
<style scoped>
/* Stretch frappe-ui TabButtons to full width with two evenly split tabs that
   each fill (and highlight) their half. DOM: RadioGroupRoot(.tab-buttons) >
   flex container div > button[data-slot=tab-button] > Pill.
   Pattern from Helpdesk: desk/src/components/ticket-agent/TicketSidebar.vue */
:deep(.tab-buttons > div) {
	display: flex;
	width: 100%;
}
:deep(.tab-buttons [data-slot='tab-button']) {
	flex: 1 1 0%;
}
:deep(.tab-buttons [data-slot='tab-button'] > *) {
	display: flex;
	width: 100%;
	justify-content: center;
}
</style>
