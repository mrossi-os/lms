<template>
	<div v-if="batch.data" class="">
		<header
			class="sticky top-0 z-10 border-b flex items-center justify-between main-page-header px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs :items="breadcrumbs" />
			<div
				v-if="tabs[tabIndex]?.key === 'Settings' && isAdmin"
				class="flex items-center space-x-2"
			>
				<Badge v-if="childRef?.isDirty" theme="orange">
					{{ __('Not Saved') }}
				</Badge>
				<Button @click="childRef.deleteBatch()">
					<template #icon>
						<Trash2 class="w-4 h-4 stroke-1.5" />
					</template>
				</Button>
				<Button variant="solid" @click="childRef.submitBatch()">
					{{ __('Save') }}
				</Button>
			</div>
			<Dropdown
				v-else-if="isAdmin && batchMenu.length"
				:options="batchMenu"
				placement="left"
				side="left"
			>
				<template v-slot="{ open }">
					<Button variant="ghost">
						<template #icon>
							<EllipsisVertical class="w-4 h-4 stroke-1.5" />
						</template>
					</Button>
				</template>
			</Dropdown>
		</header>
		<div>
			<BatchOverview v-if="!isAdmin && !isStudent" :batch="batch" />
			<div v-else>
				<Tabs :tabs="tabs" v-model="tabIndex">
					<template #tab-item="{ tab }">
						<button
							class="flex items-center gap-1.5 text-base text-ink-gray-5 duration-300 ease-in-out hover:text-ink-gray-9 data-[state=active]:text-ink-gray-9 py-2.5 cursor-pointer"
						>
							<component v-if="tab.icon" :is="tab.icon" class="size-4" />
							{{ tab.label }}
							<Badge
								v-if="tabBadgeCount(tab.key)"
								theme="red"
								size="sm"
							>
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
	EllipsisVertical,
	Laptop,
	List,
	Mail,
	MessageCircle,
	SendIcon,
	Settings2,
	Trash2,
	TrendingUp,
} from 'lucide-vue-next'
import { computed, inject, markRaw, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
	Badge,
	Breadcrumbs,
	Button,
	createResource,
	Dropdown,
	Tabs,
	usePageMeta,
} from 'frappe-ui'
import { sessionStore } from '@/stores/session'
import AdminBatchDashboard from '@/pages/Batches/components/AdminBatchDashboard.vue'
import StudentBatchDashboard from '@/pages/Batches/components/BatchDashboard.vue'
import BatchOverview from '@/pages/Batches/BatchOverview.vue'
import LiveClass from '@/pages/Batches/components/LiveClass.vue'
import Announcements from '@/pages/Batches/components/Announcements.vue'
import BatchForm from '@/pages/Batches/BatchForm.vue'
import BulkCertificates from '@/pages/Batches/components/BulkCertificates.vue'
import Discussions from '@/components/Discussions.vue'

const router = useRouter()
const route = useRoute()
const { brand } = sessionStore()
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

const updateTabs = () => {
	addToTabs('Overview', __('Overview'), markRaw(BatchOverview), List)
	if (!user.data) return
	if (isAdmin.value) {
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
	addToTabs('Classes', __('Classes'), markRaw(LiveClass), Laptop)
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
	return user.data?.is_moderator || user.data?.is_evaluator
})

const isStudent = computed(() => {
	return batch.data?.students?.includes(user.data?.name)
})

const batchMenu = computed(() => {
	if (!batch.data?.certification) {
		return []
	}
	let options = [
		{
			label: __('Generate Certificates'),
			onClick() {
				openCertificateDialog.value = true
			},
			condition: () => batch.data?.certification,
		},
	]
	return options
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
