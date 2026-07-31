<template>
	<div v-if="batch.data" class="">
		<header
			class="sticky top-0 z-10 border-b flex items-center justify-between bg-surface-base px-3 py-2.5 sm:px-5"
		>
			<div class="flex items-center gap-x-2">
				<Breadcrumbs :items="breadcrumbs" />
				<Badge v-if="batch.data?.published" theme="green">
					{{ __('Published') }}
				</Badge>
			</div>
			<div class="flex items-center gap-x-2">
				<template v-if="currentTabKey === 'Settings' && isAdmin">
					<Badge v-if="childRef?.isDirty" theme="orange">
						{{ __('Not Saved') }}
					</Badge>
					<Button @click="childRef.deleteBatch()">
						<template #icon>
							<span class="lucide-trash-2 w-4 h-4" />
						</template>
					</Button>
					<ShortcutTooltip :label="__('Save')" combo="Mod+S">
						<Button variant="solid" @click="childRef.submitBatch()">
							{{ __('Save') }}
						</Button>
					</ShortcutTooltip>
				</template>
				<Dropdown
					v-else-if="isAdmin && batchMenu.length"
					:options="batchMenu"
					placement="left"
					side="left"
				>
					<template v-slot="{ open }">
						<Button variant="ghost">
							<template #icon>
								<span class="lucide-ellipsis-vertical w-4 h-4" />
							</template>
						</Button>
					</template>
				</Dropdown>
				<Button
					v-if="tabIndex === 1 && isAdmin"
					variant="outline"
					@click="childRef?.goToImport?.()"
				>
					<template #prefix>
						<span class="lucide-import size-4" />
					</template>
					{{ __('Import') }}
				</Button>
				<Button
					v-if="tabIndex === 1 && isAdmin"
					variant="solid"
					@click="childRef?.openEnrollModal?.()"
				>
					<template #prefix>
						<span class="lucide-plus size-4" />
					</template>
					{{ __('Enroll') }}
				</Button>
				<Tooltip
					v-if="currentTabKey === 'Announcements' && isAdmin && !readOnlyMode"
					:text="
						batch.data?.students?.length
							? ''
							: __('Add students to the batch to make an announcement')
					"
				>
					<Button
						variant="solid"
						:disabled="!batch.data?.students?.length"
						@click="childRef?.openAnnouncementModal?.()"
					>
						<template #prefix>
							<span class="lucide-send size-4" />
						</template>
						{{ __('Make Announcement') }}
					</Button>
				</Tooltip>
				<Button
					v-if="isAdmin"
					variant="solid"
					:theme="batch.data?.published ? 'red' : 'gray'"
					:loading="publishToggle.loading"
					@click="togglePublishBatch"
				>
					<span class="sm:hidden">
						{{ batch.data?.published ? __('Unpubl.') : __('Publish') }}
					</span>
					<span class="max-sm:hidden">
						{{ batch.data?.published ? __('Unpublish') : __('Publish') }}
					</span>
				</Button>
			</div>
		</header>
		<div>
			<BatchOverview
				v-if="!isAdmin && !isStudent && !isBatchValutatore"
				:batch="batch"
			/>
			<div v-else>
				<Tabs :tabs="tabs" v-model="tabIndex">
					<template #tab-item="{ tab }">
						<button
							class="flex items-center gap-1.5 text-base text-ink-gray-5 duration-300 ease-in-out hover:text-ink-gray-9 data-[state=active]:text-ink-gray-9 py-2.5 cursor-pointer"
						>
							<component v-if="tab.icon" :is="tab.icon" class="size-4" />
							{{ tab.label }}
							<Badge v-if="tabBadgeCount(tab.key)" theme="red" size="sm">
								{{ tabBadgeCount(tab.key) }}
							</Badge>
						</button>
					</template>
					<template #tab-panel="{ tab }">
						<div
							v-if="tab.key == 'Discussions'"
							class="w-[90%] lg:w-[75%] mx-auto mt-5"
						>
							<Discussions
								doctype="LMS Batch"
								:docname="batch.data.name"
								:title="__('Discussions')"
								:key="batch.data.name"
								:singleThread="true"
								:scrollToBottom="false"
							/>
						</div>

						<component
							v-else
							:is="tab.component"
							:batch="batch"
							ref="childRef"
						/>
					</template>
				</Tabs>
			</div>
		</div>
	</div>
	<BulkCertificates
		v-if="batch.data"
		v-model="openCertificateDialog"
		:batch="batch.data"
	/>
</template>
<script setup>
import {
	ClipboardPen,
	Laptop,
	List,
	Mail,
	MessageCircle,
	Settings2,
	TrendingUp,
} from 'lucide-vue-next'
import {
	computed,
	inject,
	markRaw,
	onMounted,
	onUnmounted,
	ref,
	watch,
} from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
	Badge,
	Breadcrumbs,
	Button,
	createResource,
	Dropdown,
	Tabs,
	Tooltip,
	toast,
	usePageMeta,
} from 'frappe-ui'
import { sessionStore } from '@/stores/session'
import { useSettings } from '@/stores/settings'
import AdminBatchDashboard from '@/pages/Batches/components/AdminBatchDashboard.vue'
import StudentBatchDashboard from '@/pages/Batches/components/BatchDashboard.vue'
import BatchOverview from '@/pages/Batches/BatchOverview.vue'
import LiveClass from '@/pages/Batches/components/LiveClass.vue'
import Announcements from '@/pages/Batches/components/Announcements.vue'
import BatchForm from '@/pages/Batches/BatchForm.vue'
import BulkCertificates from '@/pages/Batches/components/BulkCertificates.vue'
import Discussions from '@/components/Discussions.vue'
import ShortcutTooltip from '@/components/ShortcutTooltip.vue'

const router = useRouter()
const route = useRoute()
const { brand } = sessionStore()
const settingsStore = useSettings()
const user = inject('$user')
const socket = inject('$socket')
const childRef = ref(null)
const tabIndex = ref(0)
const tabs = ref([])
const openCertificateDialog = ref(false)

const TAB_KEY_TO_SECTION = {
	Classes: 'classes',
	Announcements: 'announcements',
	Discussions: 'discussions',
}

const props = defineProps({
	batchName: {
		type: String,
		required: true,
	},
})

const updateTabIndex = () => {
	const hash = route.hash
	if (hash) {
		tabs.value.forEach((tab, index) => {
			if (tab.key?.toLowerCase() === hash.replace('#', '')) {
				tabIndex.value = index
			}
		})
	}
}

const markTabNotificationsRead = createResource({
	url: 'os_lms.os_lms.api.mark_batch_tab_notifications_read',
})

const tabBadgeCount = (key) => {
	const section = TAB_KEY_TO_SECTION[key]
	if (!section) return 0
	return batch.data?.tab_notifications?.[section] || 0
}

const handleActiveTab = () => {
	const tab = tabs.value[tabIndex.value]
	if (!tab) return
	const section = TAB_KEY_TO_SECTION[tab.key]
	if (!section) return
	if (!tabBadgeCount(tab.key)) return
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

watch(tabIndex, () => {
	const tab = tabs.value[tabIndex.value]
	if (tab.key.toLowerCase() != route.hash.replace('#', '')) {
		router.push({ ...route, hash: `#${tab.key.toLowerCase()}` })
	}
	handleActiveTab()
})

const onNotificationsPublished = () => {
	batch.reload()
}

onMounted(() => {
	socket.on('publish_lms_notifications', onNotificationsPublished)
})

onUnmounted(() => {
	socket.off('publish_lms_notifications', onNotificationsPublished)
})

const batch = createResource({
	url: 'lms.lms.utils.get_batch_details',
	cache: ['batch', props.batchName],
	params: {
		batch: props.batchName,
	},
	auto: true,
	onSuccess: (data) => {
		if (!data) {
			router.push({ name: 'Batches' })
		}
	},
})

watch(batch, () => {
	updateTabs()
	updateTabIndex()
	handleActiveTab()
})

// Keep the active tab in sync when only the URL hash changes (e.g. clicking a
// batch notification while already inside the batch): the component is not
// remounted and `batch` does not reload, so watch(batch) never fires.
watch(() => route.hash, updateTabIndex)

const updateTabs = () => {
	addToTabs('Overview', __('Overview'), markRaw(BatchOverview), List)
	if (!user.data) return
	if (isAdmin.value || isBatchValutatore.value) {
		addToTabs(
			'Dashboard',
			__('Dashboard'),
			markRaw(AdminBatchDashboard),
			TrendingUp,
		)
	} else if (isStudent.value) {
		addToTabs(
			'Dashboard',
			__('Dashboard'),
			markRaw(StudentBatchDashboard),
			ClipboardPen,
		)
	}
	if (settingsStore.settings.data?.enable_live_classes !== 0) {
		addToTabs('Classes', __('Classes'), markRaw(LiveClass), Laptop)
	}
	addToTabs('Announcements', __('Announcements'), markRaw(Announcements), Mail)
	addToTabs(
		'Discussions',
		__('Discussions'),
		markRaw(Discussions),
		MessageCircle,
	)
	if (isAdmin.value) {
		addToTabs('Settings', __('Settings'), markRaw(BatchForm), Settings2)
	}
}

const addToTabs = (key, label, component, icon) => {
	if (!tabs.value.some((tab) => tab.key === key)) {
		tabs.value.push({
			key,
			label,
			component,
			icon,
		})
	}
}

const isAdmin = computed(() => {
	return (
		user.data?.is_moderator || user.data?.is_evaluator || user.data?.is_docente
	)
})

// A "Valutatore" of this batch gets the admin Dashboard + the live class and
// announcements tabs (read-only), but NOT the Settings tab nor publish controls.
const isBatchValutatore = computed(() => {
	return Boolean(batch.data?.is_valutatore)
})

const isStudent = computed(() => {
	return batch.data?.students?.includes(user.data?.name)
})

// Compare against the tab KEY (untranslated), not the label: the label is run
// through __() so it becomes e.g. "Annunci" in Italian and would never match.
const currentTabKey = computed(() => tabs.value[tabIndex.value]?.key)

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

// Announcements moved to a dedicated, tab-scoped header button; the "..." menu
// only carries batch-wide admin actions now (and hides itself when empty).
const batchMenu = computed(() => {
	if (!batch.data?.certification) {
		return []
	}
	return [
		{
			label: __('Generate Certificates'),
			onClick() {
				openCertificateDialog.value = true
			},
			condition: () => batch.data?.certification,
		},
	]
})

const breadcrumbs = computed(() => {
	let crumbs = [{ label: __('Batches'), route: { name: 'Batches' } }]
	crumbs.push({
		label: batch?.data?.title,
		route: { name: 'BatchDetail', params: { batchName: batch?.data?.name } },
	})
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
