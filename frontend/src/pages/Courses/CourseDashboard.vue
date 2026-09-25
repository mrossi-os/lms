<template>
	<div class="p-5">
		<!-- OSLMS-CUSTOM: stat cards stack on mobile; 3 columns because the rating card is hidden -->
		<div class="grid grid-cols-1 sm:grid-cols-3 gap-5 mb-5 text-ink-gray-9">
			<NumberChartGraph
				:title="__('Enrolled')"
				:value="formatAmount(course.data?.enrollments)"
			/>
			<NumberChartGraph
				:title="__('Average Completion Rate')"
				:value="averageCompletionRate"
			/>
			<!-- OSLMS-CUSTOM: "Average Rating" card hidden (course reviews are disabled) -->
			<!-- <NumberChartGraph
				:title="__('Average Rating')"
				:value="course.data?.rating || 0"
			> 
				<template #prefix>
					<LucideStar class="size-5 text-transparent fill-amber-500" />
				</template>
			</NumberChartGraph>-->
			<NumberChartGraph :title="__('Lessons')" :value="course.data?.lessons" />
		</div>
		<div
			v-if="showStudentsEmptyState"
			class="flex min-h-[30vh] sm:min-h-[70vh] flex-col items-center justify-center gap-3 px-4 text-center"
		>
			<span class="lucide-users size-7.5 text-ink-gray-5" />
			<div class="flex flex-col items-center gap-1">
				<span class="text-lg-medium text-ink-gray-8">
					{{ __('No students enrolled yet') }}
				</span>
				<span class="text-p-base text-ink-gray-6">
					{{ __('Enroll students to track their progress here') }}
				</span>
			</div>
		</div>
		<!-- OSLMS-CUSTOM: students list and side charts stack in one column below lg -->
		<div v-else class="grid grid-cols-1 lg:grid-cols-[2fr_1fr] gap-5 items-start">
			<div class="min-w-0 border rounded-lg py-3 px-4 card">
				<div class="flex flex-wrap items-center justify-between gap-2 mb-3">
					<div class="text-lg-semibold text-ink-gray-9">
						{{ __('Students') }}
					</div>
					<div class="flex flex-wrap items-center gap-2">
						<!-- OSLMS-CUSTOM: sortable students list. On desktop the ResponsiveListView
						headers sort; phones get cards with no header at all, so there the sort lives
						in a control beside the search: pick a column, flip the direction. -->
						<Select
							v-if="isMobile"
							:modelValue="sortColumn"
							:options="studentSortOptions"
							:aria-label="__('Sort students by')"
							class="!w-36"
							@update:modelValue="(value) => toggleSort(String(value))"
						/>
						<Button
							v-if="isMobile"
							:aria-label="
								sortOrder === 'asc' ? __('Ascending') : __('Descending')
							"
							:title="sortOrder === 'asc' ? __('Ascending') : __('Descending')"
							@click="toggleSort(sortColumn)"
						>
							<template #icon>
								<span
									class="size-4"
									:class="
										sortOrder === 'asc'
											? 'lucide-arrow-up-narrow-wide'
											: 'lucide-arrow-down-wide-narrow'
									"
								/>
							</template>
						</Button>
						<!-- OSLMS-CUSTOM: compact search field labelled "Search by name" -->
						<FormControl
							v-model="searchFilter"
							class="small-form"
							:placeholder="__('Search by name')"
							:aria-label="__('Search students')"
							type="text"
						>
							<template #prefix>
								<span class="lucide-search size-4 text-ink-gray-5" />
							</template>
						</FormControl>
					</div>
				</div>
				<div class="sm:max-h-[63vh] sm:overflow-y-auto">
					<ResponsiveListView
						v-if="progressList.loading || progressList.data?.length"
						:columns="progressColumns"
						:rows="progressList.data || []"
						row-key="name"
						:options="studentListOptions"
						:sortColumn="sortColumn"
						:sortOrder="sortOrder"
						:bannerTo="studentsBannerDock"
						@sort="toggleSort"
					>
						<template #cell="{ column, row, value }">
							<span
								v-if="column.key === 'member_name'"
								class="flex items-center gap-2"
							>
								<Avatar
									:image="row.member_image as string"
									:label="String(value)"
									size="sm"
								/>
								<span class="min-w-0 truncate">{{ value }}</span>
							</span>
							<span
								v-else-if="column.key === 'progress'"
								class="flex items-center gap-2"
							>
								<ProgressBar
									:progress="Math.ceil(Number(value))"
									class="!mx-0 min-w-0 flex-1"
								/>
								<span class="text-xs shrink-0">
									{{ Math.ceil(Number(value)) }}%
								</span>
							</span>
							<span v-else-if="column.key === 'creation'">
								{{ dayjs(value as string).format('DD MMM YYYY') }}
							</span>
							<span v-else>{{ value }}</span>
						</template>
						<!-- OSLMS-CUSTOM: remove selected students (Administrator + Gestore); administrators may also purge their course data -->
						<template #selection-actions="{ unselectAll, selections }">
							<div class="flex gap-2">
								<Button
									variant="ghost"
									:label="__('Remove')"
									@click="confirmRemoveStudents(selections, unselectAll, false)"
								>
									<template #prefix>
										<span class="lucide-user-minus size-4" />
									</template>
								</Button>
								<Button
									v-if="canPurgeStudents"
									variant="ghost"
									theme="red"
									:aria-label="__('Remove and delete data')"
									:tooltip="__('Remove and delete data')"
									@click="confirmRemoveStudents(selections, unselectAll, true)"
								>
									<template #icon>
										<span class="lucide-trash-2 size-4" />
									</template>
								</Button>
							</div>
						</template>
					</ResponsiveListView>
					<div v-else class="min-h-[200px]">
						<EmptyStateLayout
							name="Students"
							icon="lucide-users"
							:title="__('No students match your search')"
							:description="__('Try a different name')"
						/>
					</div>
					<div
						v-if="progressList.data && progressList.hasNextPage"
						class="flex justify-center my-3"
					>
						<Button @click="progressList.next()">
							{{ __('Load More') }}
						</Button>
					</div>
					<!-- OSLMS-CUSTOM: selection banner kept in sight while this box scrolls the rows -->
					<div
						ref="studentsBannerDock"
						class="sticky bottom-0 z-20 [&>*]:!static [&>*]:pb-2 [&>*]:pt-2"
					/>
				</div>
			</div>
			<div class="min-w-0 space-y-5">
				<div
					v-if="chartDetails.data?.average_progress > 0"
					class="border rounded-lg p-4 card"
				>
					<div class="text-ink-gray-5 mb-4">
						{{ __('Progress Summary') }}
					</div>
					<div
						class="grid grid-cols-1 sm:grid-cols-[2fr_1fr] gap-4 items-center justify-between text-ink-gray-9"
					>
						<ul class="flex flex-col space-y-4 flex-1 text-sm list-none">
							<!-- OSLMS-CUSTOM: legend color by row position, because the labels are translated to Italian -->
							<li
								class="flex items-center text-ink-gray-7"
								v-for="(row, idx) in chartDetails.data?.progress_distribution"
								:key="row.name"
							>
								<div
									class="size-2 rounded"
									:style="{
										backgroundColor: `var(--${
											['red', 'amber', 'blue', 'green'][idx]
										}-400)`,
									}"
								></div>
								<Tooltip :text="row.name.split('(')[1].replace(')', '')">
									<div class="ms-2">
										{{ row.name.split('(')[0] }}
									</div>
								</Tooltip>
								<Tooltip :text="row.value">
									<div class="ms-auto">
										{{
											course.data?.enrollments
												? Math.round(
														(row.value / course.data.enrollments) * 100,
													)
												: 0
										}}%
									</div>
								</Tooltip>
							</li>
						</ul>
						<ECharts
							class="w-40 h-20 justify-self-center sm:justify-self-auto"
							:options="{
								color: progressColors,
								series: [
									{
										type: 'pie',
										radius: ['50%', '70%'],
										center: ['50%', '50%'],
										label: {
											show: false,
										},
										labelLine: {
											show: false,
										},
										emphasis: {
											label: {
												show: false,
											},
											scale: false,
										},
										legend: {
											show: false,
										},
										data: chartDetails.data?.progress_distribution || [],
									},
								],
								showInlineLabels: false,
							}"
						/>
					</div>
				</div>
				<div
					v-if="lessonProgress.data?.length"
					class="border rounded-lg pt-4 px-4 card"
				>
					<div class="flex items-center justify-between mb-4">
						<div class="text-ink-gray-5">
							{{ __('Lesson Completion') }}
						</div>
						<Select
							:options="lessonProgressSortingOptions"
							@update:modelValue="
								(value: string) => updateLessonProgress(value)
							"
							:placeholder="__('Sort by')"
							class="!w-32"
						/>
					</div>
					<ul
						class="divide-y sm:max-h-[40vh] divide-outline-elevation-2 text-ink-gray-7 sm:overflow-y-auto list-none"
					>
						<li
							v-for="progress in lessonProgress.data"
							:key="`${progress.chapter_idx}-${progress.idx}`"
							class="flex justify-between text-sm py-2 my-1 text-ink-gray-9"
						>
							<div class="">
								<span class="me-3 text-xs">
									{{ progress.chapter_idx }}.{{ progress.idx }}
								</span>
								<span>
									{{ progress.title }}
								</span>
							</div>
							<Tooltip :text="String(progress.completion_count)">
								<div>
									{{
										Math.ceil(
											(progress.completion_count / course.data?.enrollments) *
												100,
										)
									}}%
								</div>
							</Tooltip>
						</li>
					</ul>
				</div>
			</div>
		</div>
	</div>
	<StudentCourseProgress
		v-if="showProgressModal"
		v-model="showProgressModal"
		:course="course"
		:student="currentStudent"
		:lessons="lessonProgress"
	/>
</template>
<script setup lang="ts">
import {
	Avatar,
	Button,
	call,
	createListResource,
	createResource,
	ECharts,
	FormControl,
	toast,
	Tooltip,
} from 'frappe-ui'
import Select from '@/components/Controls/Select.vue'
import { computed, inject, ref, watch } from 'vue'
import type dayjsType from 'dayjs'
import { formatAmount } from '@/utils'
import EmptyStateLayout from '@/components/Layouts/EmptyStateLayout.vue'
import NumberChartGraph from '@/components/NumberChartGraph.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import ResponsiveListView from '@/components/ResponsiveListView.vue'
import { useScreenSize } from '@/utils/composables'
import StudentCourseProgress from '@/pages/Courses/StudentCourseProgress.vue'
import { createDialog } from '@/utils/dialogs'

import type {
	CourseDetails,
	ListColumn,
	ListRow,
	ListViewOptions,
	Resource,
} from '@/types'

const props = defineProps<{
	course: Resource<CourseDetails | null>
}>()

const dayjs = inject<typeof dayjsType>('$dayjs')!
const searchFilter = ref<string | null>(null)

// OSLMS-CUSTOM: sortable students list (server-side orderBy)
// Server-side sorting for the students list. Keys map to real LMS Enrollment
// fields (member_name, progress) or the standard `creation` column, so sorting
// stays correct across the paginated "Load More" pages. Defaults mirror the
// list resource's initial `orderBy: 'creation desc'`.
const { isMobile } = useScreenSize()
const sortColumn = ref<string>('creation')
const sortOrder = ref<'asc' | 'desc'>('desc')

const showProgressModal = ref<boolean>(false)
const currentStudent = ref<Record<string, unknown> | null>(null)
type Filters = {
	course: string | undefined
	member_name?: string[]
}

const chartDetails = createResource({
	url: 'lms.lms.api.get_course_progress_distribution',
	makeParams() {
		return {
			course: props.course.data?.name,
		}
	},
	auto: true,
	// OSLMS-CUSTOM: Italian labels for the progress distribution legend
	onSuccess(data: any) {
		// Italian labels for the progress-distribution legend. The backend returns
		// English ("Just Started (0-30%)", ...); the "(range%)" suffix is kept so
		// the tooltip (row.name.split('(')[1]) still shows the percentage range.
		const labels: Record<string, string> = {
			'Just Started (0-30%)': 'Appena iniziato (0-30%)',
			'In Progress (30-60%)': 'In corso (30-60%)',
			'Advanced (60-99%)': 'Avanzato (60-99%)',
			'Completed (100%)': 'Completato (100%)',
		}
		data?.progress_distribution?.forEach((item: { name: string }) => {
			item.name = labels[item.name] || item.name
		})
	},
})

const progressList = createListResource({
	doctype: 'LMS Enrollment',
	filters: {
		course: props.course.data?.name,
	},
	fields: [
		'name',
		'member',
		'member_name',
		'member_image',
		'member_username',
		'progress',
		'creation',
	],
	// OSLMS-CUSTOM: explicit default order, mirrored by sortColumn/sortOrder
	orderBy: 'creation desc',
	pageLength: 100,
	auto: true,
	// Also how CourseEnrollmentForm reaches this list through
	// getCachedListResource after enrolling someone — it is a route of its own
	// now, so it has no way in through props.
	cache: ['courseProgress', props.course.data?.name],
})

const lessonProgress = createResource({
	url: 'lms.lms.api.get_lesson_completion_stats',
	params: {
		course: props.course.data?.name,
	},
	auto: true,
})

const updateLessonProgress = (value: string) => {
	if (value == 'completion_rate') {
		lessonProgress.data?.sort((a: any, b: any) => {
			const rateA = a.completion_count / (props.course.data?.enrollments || 1)
			const rateB = b.completion_count / (props.course.data?.enrollments || 1)
			return rateB - rateA
		})
	} else if (value == 'index') {
		lessonProgress.data?.sort((a: any, b: any) => {
			return a.chapter_idx - b.chapter_idx || a.idx - b.idx
		})
	}
}

watch([searchFilter], () => {
	let filters: Filters = {
		course: props.course.data?.name,
	}

	if (searchFilter.value) {
		filters.member_name = ['like', `%${searchFilter.value}%`]
	}

	progressList.update({
		filters: filters,
	})
	progressList.reload()
})

// OSLMS-CUSTOM: sortable students list
// Toggle sorting on a students-list column. Clicking the active column flips
// its direction; clicking a different column starts ascending. `update` merges
// only `orderBy`, leaving the current search `filters` intact.
const toggleSort = (key: string) => {
	if (sortColumn.value === key) {
		sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
	} else {
		sortColumn.value = key
		sortOrder.value = 'asc'
	}
	progressList.update({ orderBy: `${sortColumn.value} ${sortOrder.value}` })
	progressList.reload()
}

const averageCompletionRate = computed(() => {
	let value = Math.ceil(chartDetails.data?.average_progress) || 0
	return value + '%'
})

const showStudentsEmptyState = computed(
	() =>
		!progressList.loading && !progressList.data?.length && !searchFilter.value,
)

const progressColors = computed(() =>
	['red', 'amber', 'blue', 'green'].map((color) => `var(--${color}-400)`)
)

const progressColumns = computed<ListColumn[]>(() => {
	return [
		{
			label: __('Name'),
			key: 'member_name',
			width: '40%',
		},
		{
			label: __('Progress'),
			key: 'progress',
			width: '30%',
		},
		{
			label: __('Enrolled On'),
			key: 'creation',
			align: 'left',
		},
	]
})

// OSLMS-CUSTOM: sortable students list; the sort control offers the list columns
const studentSortOptions = computed(() =>
	progressColumns.value.map((column) => ({
		label: column.label,
		value: column.key,
	}))
)

// OSLMS-CUSTOM: student removal. Administrator + Gestore remove the enrollment
// only (data kept); administrators may also purge the student's course data.
// The server enforces the same rules (os_lms course_students).
const user = inject<any>('$user')
const studentsBannerDock = ref<HTMLElement | null>(null)
const canRemoveStudents = computed(() => {
	const roles: string[] = user?.data?.roles || []
	return roles.includes('System Manager') || roles.includes('Gestore')
})
const canPurgeStudents = computed(() =>
	Boolean(user?.data?.roles?.includes('System Manager')),
)

const studentListOptions = computed<ListViewOptions>(() => ({
	selectable: canRemoveStudents.value,
	showTooltip: false,
	onRowClick: (row: ListRow) => {
		currentStudent.value = row
		showProgressModal.value = true
	},
}))

let removingStudents = false
const confirmRemoveStudents = (
	selections: Iterable<string>,
	unselectAll: () => void,
	purge: boolean,
) => {
	const enrollments = Array.from(selections)
	if (!enrollments.length) return
	const count = enrollments.length
	createDialog({
		title: purge
			? __('Remove and delete all data?')
			: __('Remove from this course?'),
		message: purge
			? count === 1
				? __(
						'The selected student will be removed and all their data in this course will be deleted: progress, quiz, assignment and exercise submissions, notes, reviews, AI assistant and simulation history, and certificates. A TrueSkills badge already issued stays valid on TrueSkills.',
					)
				: __(
						'{0} students will be removed and all their data in this course will be deleted: progress, quiz, assignment and exercise submissions, notes, reviews, AI assistant and simulation history, and certificates. A TrueSkills badge already issued stays valid on TrueSkills.',
					).format(count)
			: count === 1
				? __(
						'The selected student will be removed from this course. Their progress, submissions and certificates are kept and come back if they are enrolled again.',
					)
				: __(
						'{0} students will be removed from this course. Their progress, submissions and certificates are kept and come back if they are enrolled again.',
					).format(count),
		actions: [
			{
				label: purge ? __('Remove and delete data') : __('Remove'),
				theme: 'red',
				variant: 'solid',
				async onClick({ close }: { close: () => void }) {
					if (removingStudents) return
					removingStudents = true
					try {
						await call('os_lms.os_lms.course_students.remove_course_students', {
							course: props.course.data?.name,
							enrollments,
							purge,
						})
					} catch (err: any) {
						toast.error(
							err?.messages?.[0] || __('Could not remove the students.'),
						)
						return
					} finally {
						removingStudents = false
					}
					close()
					unselectAll()
					progressList.reload()
					chartDetails.reload()
					lessonProgress.reload()
					props.course.reload()
					toast.success(__('Students removed successfully'))
				},
			},
		],
	})
}

const lessonProgressSortingOptions = [
	{
		label: __('Lesson Index'),
		value: 'index',
		onClick() {
			updateLessonProgress('index')
		},
	},
	{
		label: __('Completion Rate'),
		value: 'completion_rate',
		onClick() {
			updateLessonProgress('completion_rate')
		},
	},
]
</script>
