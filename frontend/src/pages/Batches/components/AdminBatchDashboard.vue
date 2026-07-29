<template>
	<div v-if="batch?.data" class="p-5">
		<div class="grid grid-cols-2 md:grid-cols-4 gap-5 mb-8">
			<NumberChartGraph
				:title="__('Enrolled')"
				:value="formatAmount(batch.data?.students?.length) || 0"
			/>

			<NumberChartGraph
				:title="__('Certified')"
				:value="batchStats.data?.certified_count || 0"
			/>

			<NumberChartGraph
				:title="__('Courses')"
				:value="batch?.data?.courses?.length || 0"
			/>

			<NumberChartGraph
				:title="__('Assessments')"
				:value="batch?.data?.assessments?.length || 0"
			/>
		</div>

		<div
			v-if="showStudentsEmptyState"
			class="flex min-h-[70vh] flex-col items-center justify-center gap-3 px-4 text-center"
		>
			<span class="lucide-users size-7.5 text-ink-gray-5" />
			<div class="flex flex-col items-center gap-1">
				<span class="text-xl-medium text-ink-gray-8">
					{{ __('No students enrolled yet') }}
				</span>
				<span class="text-p-base text-ink-gray-6">
					{{ __('Enroll students to track their progress here.') }}
				</span>
			</div>
		</div>
		<div
			v-else
			class="grid grid-cols-1 lg:grid-cols-[3fr_2fr] gap-5 items-start"
		>
			<div class="border rounded-lg py-3 px-4 order-2 lg:order-1 card">
				<div class="flex items-center justify-between gap-x-2 mb-3">
					<div class="text-xl-semibold text-ink-gray-9">
						{{ __('Students') }}
					</div>
					<div class="flex items-center gap-x-2">
						<FormControl
							v-model="searchFilter"
							:placeholder="__('Search')"
							type="text"
						>
							<template #prefix>
								<span class="lucide-search size-4 text-ink-gray-5" />
							</template>
						</FormControl>
						<Dropdown :options="exportMenu" placement="right">
							<Button variant="outline">
								<template #prefix>
									<span class="lucide-download size-4" />
								</template>
								{{ __('Export Statistics') }}
							</Button>
						</Dropdown>
					</div>
				</div>
				<div class="max-h-[63vh] overflow-y-auto">
					<ListView
						v-if="students.loading || students.data?.length"
						:columns="studentColumns"
						:rows="sortedStudents"
						rowKey="name"
						:options="{
							selectable: isFullAdmin,
							showTooltip: false,
							onRowClick: (row: any) => {
								currentStudent = row.member
								showProgressModal = true
							},
						}"
					>
						<ListHeader
							class="mb-2 grid items-center gap-x-4 rounded bg-surface-gray-2 p-2"
						>
							<ListHeaderItem
								:item="item"
								v-for="item in studentColumns"
								:key="item.key"
								class="cursor-pointer select-none"
								@click="toggleSort(item.key)"
							>
								<template #suffix>
									<LucideChevronUp
										v-if="sortColumn === item.key"
										class="size-3.5 shrink-0 text-ink-gray-7 transition-transform duration-200"
										:class="sortOrder === 'desc' ? 'rotate-180' : ''"
									/>
									<LucideChevronsUpDown
										v-else
										class="size-3.5 shrink-0 text-ink-gray-4"
									/>
								</template>
							</ListHeaderItem>
						</ListHeader>
						<ListRows>
							<ListRow v-for="row in sortedStudents" :key="row.name" :row="row">
								<template #default="{ column, item }">
									<ListRowItem
										:item="row[column.key]"
										:align="column.align"
										class="w-full"
									>
										<template #prefix>
											<div v-if="column.key == 'member_name'">
												<Avatar
													class="flex items-center"
													:image="row['member_image']"
													:label="item"
													size="sm"
												/>
											</div>
											<ProgressBar
												v-else-if="column.key == 'progress'"
												:progress="getStudentProgress(row.member)"
												class="!mx-0 !me-4"
											/>
										</template>
										<div v-if="column.key == 'creation'">
											{{ dayjs(row[column.key]).format('DD MMM YYYY') }}
										</div>
										<div
											v-else-if="column.key == 'progress'"
											class="text-xs !mx-0 w-10 text-right shrink-0"
										>
											{{ getStudentProgress(row.member) }}%
										</div>
										<div v-else>
											{{ row[column.key].toString() }}
										</div>
									</ListRowItem>
								</template>
							</ListRow>
						</ListRows>
						<ListSelectBanner class="!min-w-0">
							<template #actions="{ unselectAll, selections }">
								<div class="flex gap-2">
									<Button
										variant="ghost"
										@click="removeStudents(selections, unselectAll)"
									>
										<LucideTrash2 class="h-4 w-4 stroke-1.5" />
									</Button>
								</div>
							</template>
						</ListSelectBanner>
					</ListView>
					<div v-else class="min-h-[200px]">
						<EmptyStateLayout
							name="Students"
							icon="lucide-users"
							:title="
								searchFilter
									? __('No students match your search')
									: __('No students enrolled yet')
							"
							:description="
								searchFilter
									? __('Try a different name.')
									: __('Enroll students to track their progress here.')
							"
						/>
					</div>
					<div
						v-if="students.data && students.hasNextPage"
						class="flex justify-center my-3"
					>
						<Button @click="students.next()">
							{{ __('Load More') }}
						</Button>
					</div>
				</div>
			</div>

			<div class="order-1 lg:order-2 space-y-5">
				<!-- <div class="card">
					<BatchFeedback v-if="batch.data" :batch="batch.data.name" />
				</div> -->

				<div
					v-if="progressSummaryTotal || batch.data?.courses?.length"
					class="border rounded-lg pt-4 px-4 card"
				>
					<Select
						v-if="batch.data?.courses?.length"
						v-model="selectedCourse"
						:options="courseOptions"
						class="mb-4"
					/>

					<!-- Batch-wide student distribution: averaged over every batch
					course, so it does not follow the course selector above. -->
					<div v-if="progressSummaryTotal">
						<div class="text-ink-gray-5 mb-4">
							{{ __('Progress Summary') }}
						</div>
						<div
							class="grid grid-cols-[2fr_1fr] items-center justify-between text-ink-gray-9"
						>
							<div class="flex flex-col space-y-4 flex-1 text-sm">
								<div
									class="flex items-center text-ink-gray-7"
									v-for="(bucket, idx) in progressSummary"
									:key="bucket.name"
								>
									<div
										class="size-2 rounded shrink-0"
										:style="{ backgroundColor: progressSummaryColors[idx] }"
									></div>
									<Tooltip :text="bucket.range">
										<div class="ms-2">
											{{ __(bucket.label) }}
										</div>
									</Tooltip>
									<Tooltip :text="String(bucket.value)">
										<div class="ms-auto">
											{{
												Math.round((bucket.value / progressSummaryTotal) * 100)
											}}%
										</div>
									</Tooltip>
								</div>
							</div>
							<ECharts
								class="w-40 h-20"
								:options="progressSummaryChartOptions"
							/>
						</div>
					</div>

					<div
						v-if="batch.data?.courses?.length"
						:class="progressSummaryTotal ? 'border-t mt-4 pt-4' : ''"
					>
						<div class="text-ink-gray-5 mb-4">
							{{ __('Course Progress') }}
						</div>
						<div
							v-if="progressStats.loading"
							class="text-sm text-ink-gray-5 py-2"
						>
							{{ __('Loading...') }}
						</div>
						<template v-else>
							<ECharts
								v-if="showProgressChart"
								class="w-full h-48 mb-2"
								:options="progressChartOptions"
							/>
							<div
								v-if="!selectedCourse"
								class="divide-y max-h-[40vh] divide-outline-elevation-2 text-ink-gray-7 overflow-y-auto"
							>
								<div
									v-for="(course, idx) in progressStats.data?.courses"
									:key="course.course"
									class="flex justify-between items-center gap-x-2 text-sm py-2 my-1 text-ink-gray-9"
								>
									<div class="flex items-center gap-x-2">
										<div
											class="size-2 rounded shrink-0"
											:style="{ backgroundColor: sliceColor(idx) }"
										></div>
										<span>{{ course.title }}</span>
									</div>
									<span>{{ Math.round(course.avg_progress) }}%</span>
								</div>
							</div>
							<div
								v-else-if="progressStats.data?.lessons?.length"
								class="divide-y max-h-[40vh] divide-outline-elevation-2 text-ink-gray-7 overflow-y-auto"
							>
								<div
									v-for="(lesson, idx) in progressStats.data.lessons"
									:key="lesson.lesson_name"
									class="flex justify-between items-center gap-x-2 text-sm py-2 my-1 text-ink-gray-9"
								>
									<div class="flex items-center gap-x-2">
										<div
											class="size-2 rounded shrink-0"
											:style="{ backgroundColor: sliceColor(idx) }"
										></div>
										<div>
											<span class="me-3 text-xs">
												{{ lesson.chapter_idx }}.{{ lesson.idx }}
											</span>
											<span>{{ lesson.title }}</span>
										</div>
									</div>
									<Tooltip :text="String(lesson.completion_count)">
										<div>{{ completionPct(lesson.completion_count) }}%</div>
									</Tooltip>
								</div>
							</div>
							<div v-else class="text-sm text-ink-gray-5 py-2">
								{{ __('No lessons in this course') }}
							</div>
						</template>
					</div>
				</div>
			</div>
		</div>
	</div>
	<StudentModal
		v-if="showEnrollmentModal"
		v-model="showEnrollmentModal"
		:batch="batch"
		:students="students"
	/>
	<BatchStudentProgress
		v-if="showProgressModal"
		v-model="showProgressModal"
		:student="currentStudent"
		:batch="batch?.data?.name"
	/>
</template>
<script setup lang="ts">
import {
	ECharts,
	createResource,
	createListResource,
	FormControl,
	ListView,
	ListHeader,
	ListHeaderItem,
	ListRows,
	ListRow,
	ListRowItem,
	ListSelectBanner,
	Avatar,
	Button,
	Dropdown,
	Tooltip,
	toast,
} from 'frappe-ui'
import Select from '@/components/Controls/Select.vue'
import { computed, inject, ref, watch } from 'vue'
import type dayjsType from 'dayjs'
import { formatAmount } from '@/utils'
import colors from '@/utils/frappe-ui-colors.json'
import BatchFeedback from '@/pages/Batches/components/BatchFeedback.vue'
import BatchStudentProgress from '@/pages/Batches/components/BatchStudentProgress.vue'
import NumberChartGraph from '@/components/NumberChartGraph.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import StudentModal from '@/components/Modals/StudentModal.vue'
import EmptyStateLayout from '@/components/Layouts/EmptyStateLayout.vue'
import { useRouter } from 'vue-router'

const dayjs = inject<typeof dayjsType>('$dayjs')!
const user = inject<{ data?: Record<string, any> }>('$user')
const router = useRouter()

// A "Valutatore" of this batch sees the dashboard read-only: hide enroll/import
// and student removal, which require full batch-admin rights.
const isFullAdmin = computed(
	() =>
		user?.data?.is_moderator ||
		user?.data?.is_evaluator ||
		user?.data?.is_docente,
)
const searchFilter = ref<string | null>(null)

// Column sorting for the students list. `member_name` and `creation` are real
// LMS Batch Enrollment fields sorted server-side (correct across the paginated
// "Load More" pages); `progress` is derived client-side from `batchStats` (see
// `getStudentProgress`), so it has no backing column and is reordered
// client-side over the loaded rows instead. Defaults mirror the list resource's
// initial `orderBy: 'creation desc'`.
const sortColumn = ref<string>('creation')
const sortOrder = ref<'asc' | 'desc'>('desc')
const showEnrollmentModal = ref<boolean>(false)
const showProgressModal = ref<boolean>(false)
const currentStudent = ref<any>(null)

function openEnrollModal() {
	showEnrollmentModal.value = true
}

defineExpose({ openEnrollModal, goToImport })

const props = defineProps<{
	batch: { [key: string]: any } | null
}>()

function goToImport() {
	const now = dayjs().format('YYYY-MM-DD HH:mm:ss')
	const importName = `LMS Batch Enrollment Import on ${now}`
	router.push(`/data-import/${encodeURIComponent(importName)}`)
}

// Single call for the dashboard summary: certified count + per-student average
// course progress. Keeps one network round-trip on page load.
const batchStats = createResource({
	url: 'os_lms.os_lms.api.get_batch_certified_count',
	cache: ['batch_stats', props.batch?.data?.name],
	params: {
		batch: props.batch?.data?.name,
	},
	auto: true,
})

const students = createListResource({
	doctype: 'LMS Batch Enrollment',
	filters: {
		batch: props.batch?.data?.name,
	},
	fields: [
		'name',
		'member',
		'member_name',
		'member_username',
		'member_image',
		'creation',
	],
	orderBy: 'creation desc',
	auto: true,
})

const getStudentProgress = (member: string) =>
	Math.ceil(batchStats.data?.students_progress?.[member] || 0)

// Rows rendered in the students list. For the two server-sortable columns this
// is just the resource data (already ordered by `orderBy`); for `progress` —
// which has no backing DB column — reorder the loaded rows client-side by the
// client-computed progress value.
const sortedStudents = computed(() => {
	const rows = students.data || []
	if (sortColumn.value !== 'progress') return rows
	const dir = sortOrder.value === 'asc' ? 1 : -1
	return [...rows].sort(
		(a: any, b: any) =>
			(getStudentProgress(a.member) - getStudentProgress(b.member)) * dir,
	)
})

// Course-progress panel: no course selected -> per-course averages across the
// batch's students; a course selected -> per-lesson completion for that course,
// scoped to the batch (see os_lms.os_lms.api.get_batch_progress_stats).
const selectedCourse = ref<string>('')

const progressStats = createResource({
	url: 'os_lms.os_lms.api.get_batch_progress_stats',
	makeParams() {
		return {
			batch: props.batch?.data?.name,
			course: selectedCourse.value || undefined,
		}
	},
	auto: true,
})

watch(selectedCourse, () => {
	progressStats.reload()
})

const courseOptions = computed(() => [
	{ label: __('All Courses'), value: '' },
	...(props.batch?.data?.courses || []).map((course: any) => ({
		label: course.title,
		value: course.course,
	})),
])

const completionPct = (count: number) => {
	const total = progressStats.data?.students_count || 0
	return total ? Math.ceil((count / total) * 100) : 0
}

// Donut palette. It cycles when the batch has more courses (or the course more
// lessons) than hues; the list rows below reuse `sliceColor` with the same index
// so they double as the chart legend.
const theme = ref<'darkMode' | 'lightMode'>(
	localStorage.getItem('theme') == 'dark' ? 'darkMode' : 'lightMode',
)

const chartHues = [
	'blue',
	'green',
	'amber',
	'purple',
	'teal',
	'pink',
	'orange',
	'cyan',
	'violet',
	'red',
] as const

const sliceColor = (idx: number) =>
	colors[theme.value][chartHues[idx % chartHues.length]][400]

// Progress summary: how the batch's students spread over the same buckets the
// course dashboard uses (see get_progress_distribution in lms.lms.api). It is
// derived client-side from `batchStats.students_progress` — which already holds
// every enrolled student's average progress across the batch courses — so the
// card costs no extra request. Buckets read the same rounded value shown in the
// students list, keeping a student displayed as 100% inside "Completed".
const progressBuckets = [
	{ label: 'Just Started', range: '0-30%', hue: 'red' },
	{ label: 'In Progress', range: '30-60%', hue: 'amber' },
	{ label: 'Advanced', range: '60-99%', hue: 'blue' },
	{ label: 'Completed', range: '100%', hue: 'green' },
] as const

const bucketIndex = (progress: number) => {
	if (progress >= 100) return 3
	if (progress >= 60) return 2
	if (progress >= 30) return 1
	return 0
}

const progressSummary = computed(() => {
	const counts = [0, 0, 0, 0]
	const students = batchStats.data?.students_progress || {}
	for (const member of Object.keys(students)) {
		counts[bucketIndex(getStudentProgress(member))] += 1
	}
	// `label` stays untranslated here and goes through __() in the template, so
	// the legend still translates when the dictionary loads after this computed
	// first evaluates. The donut never renders names (labels/tooltip are off).
	return progressBuckets.map((bucket, idx) => ({
		name: bucket.label,
		label: bucket.label,
		range: bucket.range,
		value: counts[idx],
	}))
})

const progressSummaryTotal = computed(() =>
	progressSummary.value.reduce((total, bucket) => total + bucket.value, 0),
)

const progressSummaryColors = computed(() =>
	progressBuckets.map((bucket) => colors[theme.value][bucket.hue][400]),
)

const progressSummaryChartOptions = computed(() => ({
	color: progressSummaryColors.value,
	series: [
		{
			type: 'pie' as const,
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
			data: progressSummary.value.map((bucket) => ({
				name: bucket.name,
				value: bucket.value,
			})),
		},
	],
}))

// The donut follows the course selector: no course selected -> one slice per
// batch course weighted by its average progress; a course selected -> one slice
// per lesson weighted by how many batch students completed it.
const progressChartData = computed(() => {
	if (!selectedCourse.value) {
		return (progressStats.data?.courses || []).map((course: any) => ({
			name: course.title,
			value: Math.round(course.avg_progress),
			detail: `${Math.round(course.avg_progress)}%`,
		}))
	}
	return (progressStats.data?.lessons || []).map((lesson: any) => ({
		name: `${lesson.chapter_idx}.${lesson.idx} ${lesson.title}`,
		value: lesson.completion_count,
		detail: `${lesson.completion_count} (${completionPct(
			lesson.completion_count,
		)}%)`,
	}))
})

const showProgressChart = computed(() =>
	progressChartData.value.some((slice) => slice.value > 0),
)

const progressChartOptions = computed(() => ({
	color: progressChartData.value.map((_, idx: number) => sliceColor(idx)),
	tooltip: {
		trigger: 'item',
		formatter: (params: any) =>
			`${params.marker} ${params.name}<br/>${params.data.detail}`,
	},
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
			data: progressChartData.value,
		},
	],
}))

// Stream the progress report from the backend; the content-disposition response
// makes the browser download it without leaving the SPA. "xlsx" is the
// human-readable summary, "csv" the raw per-lesson dataset for AI analysis.
function exportProgress(fileFormat: 'xlsx' | 'csv') {
	const name = props.batch?.data?.name
	if (!name) return
	window.open(
		`/api/method/os_lms.os_lms.api.export_batch_progress?batch=${encodeURIComponent(
			name,
		)}&file_format=${fileFormat}`,
		'_blank',
	)
}

const exportMenu = computed(() => [
	{
		label: __('Excel (.xlsx)'),
		onClick: () => exportProgress('xlsx'),
	},
	{
		label: __('CSV (raw data)'),
		onClick: () => exportProgress('csv'),
	},
])

watch(searchFilter, () => {
	let filters: Record<string, any> = {
		batch: props.batch?.data?.name,
	}

	if (searchFilter.value) {
		filters.member_name = ['like', `%${searchFilter.value}%`]
	}

	students.update({ filters })
	students.reload()
})

// Toggle sorting on a students-list column. Clicking the active column flips its
// direction; clicking a different column starts ascending. `member_name` and
// `creation` sort server-side via `orderBy` (`update` merges only `orderBy`,
// leaving the search `filters` intact); `progress` is handled entirely by the
// `sortedStudents` computed, so it needs no server round-trip.
const toggleSort = (key: string) => {
	if (sortColumn.value === key) {
		sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
	} else {
		sortColumn.value = key
		sortOrder.value = 'asc'
	}
	if (key !== 'progress') {
		students.update({ orderBy: `${sortColumn.value} ${sortOrder.value}` })
		students.reload()
	}
}

const studentColumns = computed(() => {
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
			align: 'right',
		},
	]
})

const removeStudents = async (
	selections: string[],
	unselectAll: () => void,
) => {
	for (const student of selections) {
		await students.delete.submit(student)
	}
	unselectAll()
	toast.success(__('Students removed successfully'))
}

const showStudentsEmptyState = computed(
	() => !students.loading && !students.data?.length && !searchFilter.value,
)
</script>
