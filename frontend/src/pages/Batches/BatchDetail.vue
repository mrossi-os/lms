<template>
	<TabbedDetailPage
		ref="page"
		:tabs="tabs"
		:breadcrumbs="breadcrumbs"
		:published="Boolean(batch.data?.published)"
		:loading="!batch.data"
		:doc="batch"
		doc-prop="batch"
	>
		<template #actions="{ tab, instance }">
			<Badge v-if="tab?.key === 'settings' && instance?.isDirty" theme="orange">
				{{ __('Not Saved') }}
			</Badge>
			<Button
				v-if="tab?.key === 'settings' && isAdmin && !isMobile"
				:variant="batch.data?.published ? 'outline' : 'solid'"
				:theme="batch.data?.published ? 'red' : 'gray'"
				@click="togglePublishBatch"
			>
				{{ batch.data?.published ? __('Unpublish') : __('Publish') }}
			</Button>
			<Dropdown
				v-if="isAdmin && batchMenu(tab).length"
				:options="batchMenu(tab)"
				placement="left"
				side="left"
			>
				<template v-slot="{ open }">
					<Button
						variant="ghost"
						:label="__('Batch options')"
						:aria-expanded="open"
					>
						<template #icon>
							<span class="lucide-ellipsis-vertical w-4 h-4" />
						</template>
					</Button>
				</template>
			</Dropdown>
			<!-- OSLMS-CUSTOM: Import students button on the Dashboard tab (goToImport on the tab instance) -->
			<HeaderButton
				v-if="tab?.key === 'dashboard' && isAdmin"
				:label="__('Import')"
				icon="lucide-import"
				@click="instance?.goToImport?.()"
			/>
			<HeaderButton
				v-if="tab?.key === 'dashboard' && isAdmin"
				:label="__('Enroll')"
				icon="lucide-plus"
				variant="solid"
				@click="openStudentForm"
			/>
			<template v-if="tab?.key === 'announcements' && isAdmin && !readOnlyMode">
				<Tooltip
					v-if="!batch.data?.students?.length"
					:text="__('Add students to the batch to make an announcement')"
				>
					<HeaderButton
						:label="__('Make Announcement')"
						icon="lucide-send"
						disabled
					/>
				</Tooltip>
				<HeaderButton
					v-else
					:label="__('Make Announcement')"
					icon="lucide-send"
					@click="openAnnouncementModal"
				/>
			</template>
			<ShortcutTooltip
				v-if="tab?.key === 'settings' && isAdmin"
				:label="__('Save')"
				combo="Mod+S"
			>
				<HeaderButton
					:label="__('Save')"
					variant="solid"
					@click="instance?.submitBatch()"
				/>
			</ShortcutTooltip>
		</template>

		<template #solo>
			<BatchOverview v-if="batch.data" :batch="batch" />
			<SkeletonLoader v-else variant="course-page" />
		</template>

		<template #tab-body-discussions>
			<div class="w-[90%] lg:w-[75%] mx-auto mt-5">
				<Discussions
					doctype="LMS Batch"
					:docname="batch.data.name"
					:title="__('Discussions')"
					:key="batch.data.name"
					:singleThread="true"
					:scrollToBottom="false"
				/>
			</div>
		</template>
	</TabbedDetailPage>

	<router-view />
</template>
<script setup>
import {
	computed,
	inject,
	markRaw,
	onMounted,
	onUnmounted,
	provide,
	useTemplateRef,
	watch,
} from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
	Badge,
	Button,
	createResource,
	Dropdown,
	Tooltip,
	toast,
	usePageMeta,
} from 'frappe-ui'
import { sessionStore } from '@/stores/session'
import { useSettings } from '@/stores/settings'
import { useScreenSize } from '@/utils/composables'
import AdminBatchDashboard from '@/pages/Batches/components/AdminBatchDashboard.vue'
import StudentBatchDashboard from '@/pages/Batches/components/BatchDashboard.vue'
import BatchOverview from '@/pages/Batches/BatchOverview.vue'
import LiveClass from '@/pages/Batches/components/LiveClass.vue'
import Announcements from '@/pages/Batches/components/Announcements.vue'
import BatchForm from '@/pages/Batches/BatchForm.vue'
import Discussions from '@/components/Discussions.vue'
import HeaderButton from '@/components/HeaderButton.vue'
import ShortcutTooltip from '@/components/ShortcutTooltip.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import TabbedDetailPage from '@/components/Layouts/TabbedDetailPage.vue'
import { openBatchForm } from '@/composables/useBatchForms'

const router = useRouter()
// Read by every form opener below. TabbedDetailPage still keeps the active tab
// in route.hash (:143, :158), so a form route opened without it re-renders the
// page on its first tab.
const route = useRoute()
const { brand } = sessionStore()
const settingsStore = useSettings()
const { isMobile } = useScreenSize()
const user = inject('$user')
const socket = inject('$socket')
const page = useTemplateRef('page')
const readOnlyMode = window.read_only_mode

// OSLMS-CUSTOM: batch tab -> notification section for the unread badges
const TAB_KEY_TO_SECTION = {
	classes: 'classes',
	announcements: 'announcements',
	discussions: 'discussions',
}

const props = defineProps({
	batchName: {
		type: String,
		required: true,
	},
})

const batch = createResource({
	url: 'lms.lms.utils.get_batch_details',
	makeParams: () => ({
		batch: props.batchName,
	}),
	auto: true,
	onSuccess: (data) => {
		if (!data) {
			router.push({ name: 'Batches' })
		}
	},
})

// The router reuses this component when you go straight from one batch to
// another (the command palette does exactly that), so setup does not run a
// second time. Without this the page would keep showing the batch you
// arrived on. The `cache` key is gone for the same reason: it was read once at
// setup, so a reload would have written the new batch into the old one's
// entry.
watch(
	() => props.batchName,
	() => batch.reload()
)

// The forms in the <router-view> below change what this endpoint reports —
// enrolling a student moves Seats Left on the overlay. Having no cache key is
// what makes them unable to reach it themselves, so it is handed down.
provide('reloadBatchDetails', () => batch.reload())

// OSLMS-CUSTOM: opening a tab marks its batch notifications as read
const markTabNotificationsRead = createResource({
	url: 'os_lms.os_lms.api.mark_batch_tab_notifications_read',
})

const tabBadgeCount = (key) => {
	const section = TAB_KEY_TO_SECTION[key]
	if (!section) return 0
	return batch.data?.tab_notifications?.[section] || 0
}

// TabbedDetailPage keeps the active tab key in route.hash (it pushes the hash
// on tab change and follows hash-only navigation, e.g. a batch notification
// link), so the hash is the active tab. Re-checked when the batch reloads too,
// since the counters arrive with get_batch_details.
const handleActiveTab = () => {
	const key = route.hash.replace('#', '')
	const section = TAB_KEY_TO_SECTION[key]
	if (!section || !tabBadgeCount(key)) return
	if (!tabs.value.some((tab) => tab.key === key && (tab.when ?? true))) return
	markTabNotificationsRead.submit(
		{ batch: props.batchName, section },
		{
			onSuccess() {
				if (batch.data?.tab_notifications) {
					batch.data.tab_notifications[section] = 0
				}
			},
		},
	)
}

watch([() => route.hash, () => batch.data], handleActiveTab)

const onNotificationsPublished = () => {
	batch.reload()
}

onMounted(() => {
	// OSLMS-CUSTOM: reload the batch (and its tab badges) on new notifications
	socket.on('publish_lms_notifications', onNotificationsPublished)
})

onUnmounted(() => {
	socket.off('publish_lms_notifications', onNotificationsPublished)
})

const isAdmin = computed(() => {
	return Boolean(
		// OSLMS-CUSTOM: Docente manages batches like a moderator
		user.data?.is_moderator || user.data?.is_evaluator || user.data?.is_docente,
	)
})

// A "Valutatore" of this batch gets the admin Dashboard + the live class and
// announcements tabs (read-only), but NOT the Settings tab nor publish controls.
// OSLMS-CUSTOM: Valutatore of this batch (flag computed server-side)
const isBatchValutatore = computed(() => {
	return Boolean(batch.data?.is_valutatore)
})

const isStudent = computed(() => {
	return Boolean(batch.data?.students?.includes(user.data?.name))
})

const tabs = computed(() => {
	// OSLMS-CUSTOM: a Valutatore of this batch gets the tabs, not the public overview
	const enrolled = isAdmin.value || isStudent.value || isBatchValutatore.value
	// OSLMS-CUSTOM: per-batch Valutatore gets the admin dashboard tab
	const adminDashboard = isAdmin.value || isBatchValutatore.value
	return [
		{
			key: 'overview',
			label: __('Overview'),
			component: markRaw(BatchOverview),
			icon: 'lucide-list',
			when: enrolled,
			flow: true,
		},
		{
			key: 'dashboard',
			label: __('Dashboard'),
			component: markRaw(AdminBatchDashboard),
			icon: 'lucide-trending-up',
			when: adminDashboard,
		},
		{
			key: 'dashboard',
			label: __('Dashboard'),
			component: markRaw(StudentBatchDashboard),
			icon: 'lucide-clipboard-pen',
			when: !adminDashboard && isStudent.value,
		},
		{
			key: 'classes',
			label: __('Classes'),
			component: markRaw(LiveClass),
			icon: 'lucide-laptop',
			// OSLMS-CUSTOM: Classes tab hidden when live classes are disabled site-wide
			when:
				enrolled && settingsStore.settings.data?.enable_live_classes !== 0,
			// OSLMS-CUSTOM: unread notification badge (rendered by TabbedDetailPage)
			badge: tabBadgeCount('classes'),
		},
		{
			key: 'announcements',
			label: __('Announcements'),
			component: markRaw(Announcements),
			icon: 'lucide-mail',
			when: enrolled,
			badge: tabBadgeCount('announcements'),
		},
		{
			key: 'discussions',
			label: __('Discussions'),
			component: markRaw(Discussions),
			icon: 'lucide-message-circle',
			when: enrolled,
			badge: tabBadgeCount('discussions'),
		},
		{
			key: 'settings',
			label: __('Settings'),
			component: markRaw(BatchForm),
			icon: 'lucide-settings-2',
			when: isAdmin.value,
			flow: true,
		},
	]
})

const openAnnouncementModal = () => {
	openBatchForm(router, 'NewAnnouncement', props.batchName, route.hash)
}

const openStudentForm = () => {
	openBatchForm(router, 'NewBatchStudent', props.batchName, route.hash)
}

const publishToggle = createResource({
	url: 'frappe.client.set_value',
	makeParams() {
		return {
			doctype: 'LMS Batch',
			name: batch.data?.name,
			fieldname: 'published',
			value: batch.data?.published ? 0 : 1,
		}
	},
	onSuccess() {
		toast.success(
			batch.data?.published ? __('Batch unpublished') : __('Batch published'),
		)
		batch.reload()
	},
	onError(err) {
		toast.error(err.messages?.[0] || __('Could not update publish status'))
	},
})

const togglePublishBatch = () => {
	publishToggle.submit()
}

const batchMenu = (tab) => {
	const options = []
	if (batch.data?.certification) {
		options.push({
			label: __('Generate Certificates'),
			icon: 'lucide-award',
			onClick: () => {
				openBatchForm(router, 'BulkCertificates', props.batchName, route.hash)
			},
		})
	}
	if (tab?.key !== 'settings') return options
	if (isMobile.value) {
		options.push({
			label: batch.data?.published
				? __('Unpublish batch')
				: __('Publish batch'),
			icon: batch.data?.published ? 'lucide-globe-lock' : 'lucide-globe',
			onClick: togglePublishBatch,
		})
	}
	options.push({
		label: __('Delete batch'),
		icon: 'lucide-trash-2',
		theme: 'red',
		onClick: () => page.value?.instanceFor('settings')?.deleteBatch(),
	})
	return options
}

const breadcrumbs = computed(() => {
	const crumbs = [{ label: __('Batches'), route: { name: 'Batches' } }]
	if (batch.data) {
		crumbs.push({
			label: batch.data.title,
			route: { name: 'BatchDetail', params: { batchName: batch.data.name } },
		})
	}
	return crumbs
})

usePageMeta(() => {
	return {
		title: batch?.data?.title,
		icon: brand.favicon,
	}
})
</script>
<style>
.batch-description p {
	margin-bottom: 1rem;
	line-height: 1.7;
}

.batch-description li {
	line-height: 1.7;
}

.batch-description ol {
	list-style: auto;
	margin: revert;
	padding: revert;
}

.batch-description strong {
	font-weight: 600;
	color: theme('colors.gray.900') !important;
}
</style>
