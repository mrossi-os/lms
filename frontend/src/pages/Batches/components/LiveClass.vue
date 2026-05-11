<template>
	<div class="p-5">
		<div
			v-if="isAdmin() && !hasProviderAccount()"
			class="flex lg:items-center gap-x-2 mb-5 bg-surface-amber-1 px-3 py-2 rounded-lg text-ink-amber-3"
		>
			<AlertCircle class="size-7 md:size-4 stroke-1.5" />
			<span class="leading-5">
				{{
					__(
						'Please select a conferencing provider and add an account to the batch to create live classes.',
					)
				}}
			</span>
		</div>

		<div class="flex items-center justify-between gap-3 flex-wrap">
			<div class="text-lg font-semibold text-ink-gray-9">
				{{ __('Live Class') }}
			</div>
			<div class="flex items-center gap-2">
				<FormControl
					v-model="sortField"
					type="select"
					size="sm"
					:options="sortFieldOptions"
				/>
				<Tooltip
					:text="
						sortOrder === 'asc' ? __('Crescente') : __('Decrescente')
					"
				>
					<Button
						:variant="'subtle'"
						@click="toggleSortOrder"
						:aria-label="
							sortOrder === 'asc' ? __('Crescente') : __('Decrescente')
						"
					>
						<template #icon>
							<ArrowUp v-if="sortOrder === 'asc'" class="w-4 h-4" />
							<ArrowDown v-else class="w-4 h-4" />
						</template>
					</Button>
				</Tooltip>
				<Button v-if="canCreateClass()" @click="openCreateModal">
					<template #prefix>
						<Plus class="h-4 w-4" />
					</template>
					<span>
						{{ __('Add') }}
					</span>
				</Button>
			</div>
		</div>
		<div
			v-if="liveClasses.data?.length"
			class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5 mt-5"
		>
			<div
				v-for="cls in liveClasses.data"
				class="relative flex flex-col border rounded-md h-full text-ink-gray-7 hover:border-outline-gray-3 p-3 card"
				:class="{
					'cursor-pointer': isAdmin() && cls.attendees > 0,
				}"
				@click="
					() => {
						openAttendanceModal(cls)
					}
				"
			>
				<div v-if="isAdmin()" class="absolute top-2 right-2" @click.stop>
					<Dropdown
						:options="[
							{
								label: __('Edit'),
								icon: 'edit-2',
								onClick: () => openEditModal(cls),
							},
							{
								label: __('Delete'),
								icon: 'trash-2',
								onClick: () => openDeleteModal(cls),
							},
						]"
					>
						<template #default>
							<Button :variant="'ghost'">
								<template #icon>
									<MoreVertical class="w-4 h-4" />
								</template>
							</Button>
						</template>
					</Dropdown>
				</div>
				<div class="font-semibold text-ink-gray-9 mb-1 pr-8">
					{{ cls.title }}
				</div>
				<div class="short-introduction">
					{{ cls.description }}
				</div>
				<div class="mt-auto space-y-3">
					<div class="flex items-center gap-x-2">
						<Calendar class="w-4 h-4 stroke-1.5" />
						<span>
							{{ dayjs(cls.date).format('DD MMMM YYYY') }}
						</span>
					</div>
					<div class="flex items-center gap-x-2">
						<Clock class="w-4 h-4 stroke-1.5" />
						<span>
							{{ dayjs(getClassStart(cls)).format('hh:mm A') }} -
							{{ dayjs(getClassEnd(cls)).format('hh:mm A') }}
						</span>
					</div>
					<div
						v-if="isAdmin() && canModeratorAccessClass(cls)"
						class="flex items-center gap-x-2 text-ink-gray-9 mt-auto"
						@click.stop
					>
						<button
							type="button"
							@click="startClass(cls)"
							:disabled="startLiveClass.loading"
							class="w-full cursor-pointer inline-flex items-center justify-center gap-2 transition-colors focus:outline-none text-ink-gray-8 bg-surface-gray-2 hover:bg-surface-gray-3 active:bg-surface-gray-4 focus-visible:ring focus-visible:ring-outline-gray-3 h-7 text-base px-2 rounded disabled:opacity-50 disabled:cursor-not-allowed"
						>
							<Monitor class="h-4 w-4 stroke-1.5" />
							{{ hasHostStarted(cls) ? __('Open') : __('Start') }}
						</button>
					</div>
					<div
						v-else-if="canStudentJoin(cls)"
						class="flex items-center gap-x-2 text-ink-gray-9 mt-auto"
					>
						<a
							:href="cls.join_url"
							target="_blank"
							@click.stop
							class="w-full cursor-pointer inline-flex items-center justify-center gap-2 transition-colors focus:outline-none text-ink-gray-8 bg-surface-gray-2 hover:bg-surface-gray-3 active:bg-surface-gray-4 focus-visible:ring focus-visible:ring-outline-gray-3 h-7 text-base px-2 rounded"
						>
							<Video class="h-4 w-4 stroke-1.5" />
							{{ __('Join') }}
						</a>
					</div>
					<Tooltip
						v-else-if="showStudentJoinDisabled(cls)"
						:text="__('Waiting for the host to start the class')"
						placement="right"
					>
						<div class="flex items-center gap-x-2 mt-auto" @click.stop>
							<button
								type="button"
								disabled
								class="w-full inline-flex items-center justify-center gap-2 text-ink-gray-5 bg-surface-gray-2 h-7 text-base px-2 rounded opacity-60 cursor-not-allowed"
							>
								<Video class="h-4 w-4 stroke-1.5" />
								{{ __('Join') }}
							</button>
						</div>
					</Tooltip>
					<Tooltip
						v-else-if="hasClassEnded(cls)"
						:text="__('This class has ended')"
						placement="right"
					>
						<div class="flex items-center gap-x-2 text-ink-amber-3 w-fit">
							<Info class="w-4 h-4 stroke-1.5" />
							<span>
								{{ __('Ended') }}
							</span>
						</div>
					</Tooltip>
				</div>
			</div>
		</div>
		<div v-else class="text-ink-gray-7 mt-5">
			{{ __('No live classes scheduled') }}
		</div>
		<div
			v-if="totalPages > 1"
			class="flex items-center justify-between border-t pt-3 mt-5"
		>
			<div class="text-sm text-ink-gray-5">
				{{ __('Page {0} of {1}').format(currentPage, totalPages) }}
			</div>
			<div class="flex items-center space-x-2">
				<Button :disabled="currentPage <= 1" @click="currentPage--">
					<template #prefix>
						<ChevronLeft class="w-4 h-4" />
					</template>
					{{ __('Previous') }}
				</Button>
				<Button :disabled="currentPage >= totalPages" @click="currentPage++">
					<template #suffix>
						<ChevronRight class="w-4 h-4" />
					</template>
					{{ __('Next') }}
				</Button>
			</div>
		</div>
	</div>

	<LiveClassModal
		v-if="showLiveClassModal"
		v-model="showLiveClassModal"
		:batch="batch.data?.name"
		:zoomAccount="batch.data?.zoom_account"
		:googleMeetAccount="batch.data?.google_meet_account"
		:conferencingProvider="batch.data?.conferencing_provider"
		:liveClass="editingClass"
		v-model:reloadLiveClasses="liveClasses"
	/>

	<LiveClassAttendance
		v-if="showAttendance"
		v-model="showAttendance"
		:live_class="attendanceFor"
	/>

	<Dialog
		v-if="deletingClass"
		v-model="showDeleteDialog"
		:options="{
			title: __('Delete live class'),
			actions: [
				{
					label: __('Cancel'),
					onClick: ({ close }) => close(),
				},
				{
					label: __('Delete'),
					variant: 'solid',
					theme: 'red',
					onClick: ({ close }) => confirmDelete(close),
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-3 text-ink-gray-7 text-sm leading-5">
				<p>
					{{
						__(
							'Sei sicuro di voler eliminare la lezione {0}? Questa azione non si può annullare.',
						).format(deletingClass.title)
					}}
				</p>
				<label class="flex items-start gap-2 cursor-pointer">
					<input
						type="checkbox"
						v-model="notifyStudentsOnDelete"
						class="mt-0.5"
					/>
					<span>
						{{
							__(
								'Notifica gli studenti del batch via email + notifica in piattaforma.',
							)
						}}
					</span>
				</label>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import {
	createResource,
	Button,
	FormControl,
	Tooltip,
	Dialog,
	Dropdown,
	toast,
} from 'frappe-ui'

const JOIN_WINDOW_MINUTES_BEFORE = 15
import {
	Plus,
	Clock,
	Calendar,
	Video,
	Monitor,
	Info,
	AlertCircle,
	MoreVertical,
	ChevronLeft,
	ChevronRight,
	ArrowUp,
	ArrowDown,
} from 'lucide-vue-next'
import { computed, inject, ref, watch } from 'vue'
import LiveClassModal from '@/components/Modals/LiveClassModal.vue'
import LiveClassAttendance from '@/components/Modals/LiveClassAttendance.vue'

const JOIN_WINDOW_MINUTES_BEFORE = 15
const PAGE_SIZE = 20

const user = inject('$user')
const showLiveClassModal = ref(false)
const dayjs = inject('$dayjs')
const readOnlyMode = window.read_only_mode
const showAttendance = ref(false)
const attendanceFor = ref(null)
const editingClass = ref(null)
const deletingClass = ref(null)
const showDeleteDialog = ref(false)
const notifyStudentsOnDelete = ref(true)

const props = defineProps({
	batch: {
		type: Object,
		required: true,
	},
})

const currentPage = ref(1)
const sortField = ref('creation')
const sortOrder = ref('desc')

const sortFieldOptions = [
	{ label: __('Data creazione'), value: 'creation' },
	{ label: __('Data lezione'), value: 'date' },
]

const computedOrderBy = computed(() => {
	if (sortField.value === 'date') {
		return `date ${sortOrder.value}, time ${sortOrder.value}`
	}
	return `creation ${sortOrder.value}`
})

const listFilters = computed(() => ({
	batch_name: props.batch.data?.name,
}))

const liveClasses = createResource({
	url: 'frappe.client.get_list',
	makeParams() {
		return {
			doctype: 'LMS Live Class',
			fields: [
				'name',
				'title',
				'description',
				'time',
				'date',
				'duration',
				'timezone',
				'attendees',
				'start_url',
				'join_url',
				'started_at',
				'owner',
				'conferencing_provider',
				'batch_name',
			],
			filters: listFilters.value,
			order_by: computedOrderBy.value,
			limit_start: (currentPage.value - 1) * PAGE_SIZE,
			limit_page_length: PAGE_SIZE,
		}
	},
	auto: true,
})

const liveClassesCount = createResource({
	url: 'frappe.client.get_count',
	makeParams() {
		return {
			doctype: 'LMS Live Class',
			filters: listFilters.value,
		}
	},
	auto: true,
})

const totalPages = computed(() =>
	Math.max(1, Math.ceil((liveClassesCount.data || 0) / PAGE_SIZE)),
)

const refreshList = () => {
	liveClasses.reload()
}

const resetToFirstPage = () => {
	if (currentPage.value !== 1) {
		currentPage.value = 1
	} else {
		refreshList()
	}
	liveClassesCount.reload()
}

watch(currentPage, refreshList)
watch([sortField, sortOrder], () => {
	if (currentPage.value !== 1) {
		currentPage.value = 1
	} else {
		refreshList()
	}
})
watch(showLiveClassModal, (isOpen, wasOpen) => {
	if (wasOpen && !isOpen) {
		resetToFirstPage()
	}
})

const toggleSortOrder = () => {
	sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
}

const fetchLiveClassDetails = createResource({
	url: 'frappe.client.get',
	makeParams(values) {
		return {
			doctype: 'LMS Live Class',
			name: values.name,
		}
	},
})

const deleteLiveClass = createResource({
	url: 'os_lms.os_lms.api.delete_live_class',
})

const startLiveClass = createResource({
	url: 'os_lms.os_lms.api.start_live_class',
})

const openCreateModal = () => {
	editingClass.value = null
	showLiveClassModal.value = true
}

const openEditModal = async (cls) => {
	const full = await fetchLiveClassDetails.submit({ name: cls.name })
	editingClass.value = full
	showLiveClassModal.value = true
}

const openDeleteModal = (cls) => {
	deletingClass.value = cls
	notifyStudentsOnDelete.value = true
	showDeleteDialog.value = true
}

const confirmDelete = (close) => {
	deleteLiveClass.submit(
		{
			name: deletingClass.value.name,
			notify_students: notifyStudentsOnDelete.value ? 1 : 0,
		},
		{
			onSuccess() {
				toast.success(__('Lezione eliminata'))
				resetToFirstPage()
				deletingClass.value = null
				close()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		},
	)
}

const hasProviderAccount = () => {
	const data = props.batch.data
	if (data?.conferencing_provider === 'Zoom' && data?.zoom_account) return true
	if (
		data?.conferencing_provider === 'Google Meet' &&
		data?.google_meet_account
	)
		return true
	return false
}

const canCreateClass = () => {
	if (readOnlyMode) return false
	if (!hasProviderAccount()) return false
	return isAdmin()
}

const isAdmin = () => {
	return user.data?.is_moderator || user.data?.is_evaluator
}

const getClassStart = (cls) => {
	return new Date(`${cls.date}T${cls.time}`)
}

const getClassEnd = (cls) => {
	const classStart = getClassStart(cls)
	return new Date(classStart.getTime() + cls.duration * 60000)
}

const hasClassEnded = (cls) => {
	const classEnd = getClassEnd(cls)
	const now = new Date()
	return now > classEnd
}

const isWithinJoinWindow = (cls) => {
	const now = new Date()
	const start = getClassStart(cls)
	const end = getClassEnd(cls)
	const windowOpen = new Date(
		start.getTime() - JOIN_WINDOW_MINUTES_BEFORE * 60000,
	)
	return now >= windowOpen && now <= end
}

const hasHostStarted = (cls) => Boolean(cls.started_at)

const canStudentJoin = (cls) =>
	isWithinJoinWindow(cls) && hasHostStarted(cls) && Boolean(cls.join_url)

const showStudentJoinDisabled = (cls) =>
	isWithinJoinWindow(cls) &&
	!hasHostStarted(cls) &&
	!hasClassEnded(cls) &&
	Boolean(cls.join_url)

const canModeratorAccessClass = (cls) => {
	if (hasClassEnded(cls)) return false
	if (cls.date !== dayjs().format('YYYY-MM-DD')) return false
	return true
}

const startClass = (cls) => {
	const fallbackUrl = cls.start_url || cls.join_url
	startLiveClass.submit(
		{ name: cls.name },
		{
			onSuccess(data) {
				const url = data?.start_url || fallbackUrl
				if (url) window.open(url, '_blank', 'noopener')
				liveClasses.reload()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
				if (fallbackUrl) window.open(fallbackUrl, '_blank', 'noopener')
			},
		},
	)
}

const openAttendanceModal = (cls) => {
	if (!isAdmin()) return
	if (cls.attendees <= 0) return
	attendanceFor.value = cls
	showAttendance.value = true
}
</script>
<style>
.short-introduction {
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	text-overflow: ellipsis;
	width: 100%;
	overflow: hidden;
	margin: 0.25rem 0 1.5rem;
	line-height: 1.5;
}
</style>
