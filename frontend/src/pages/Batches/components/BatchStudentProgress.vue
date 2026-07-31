<template>
	<Dialog
		v-model:open="show"
		size="xl"
		:title="studentDetails.data?.full_name || __('Student Details')"
	>
		<template #body>
			<div
				v-if="studentDetails.loading && !studentDetails.data"
				class="flex items-center justify-center py-12"
			>
				<LoadingIndicator class="size-4" />
			</div>
			<div v-else-if="studentDetails.data" class="p-5 space-y-10 text-sm">
				<div class="flex items-center gap-x-2">
					<Avatar :image="studentDetails.data.user_image" size="3xl" />
					<div class="space-y-1">
						<div class="flex items-center gap-x-2">
							<div class="text-3xl-semibold text-ink-gray-9">
								{{ studentDetails.data.full_name }}
							</div>
							<Badge
								v-if="
									Object.keys(studentDetails.data.assessments).length ||
									Object.keys(studentDetails.data.courses).length
								"
								:theme="studentDetails.data.progress === 100 ? 'green' : 'red'"
							>
								{{ studentDetails.data.progress }}% {{ __('Completato') }}
							</Badge>
						</div>
						<div class="text-sm text-ink-gray-7">
							{{ studentDetails.data.email }}
						</div>
					</div>
				</div>

				<div class="space-y-8">
					<!-- Assessments -->
					<ListView
						v-if="canViewAssessments"
						:columns="assessmentColumns"
						:rows="studentDetails.data.assessments"
						row-key="title"
						class="border border-outline-elevation-2 rounded-lg"
						:options="{
							selectable: false,
							showTooltip: false,
							onRowClick: (row: any) => {
								redirectToAssessment(row)
							},
						}"
					>
						<ListHeader
							class="mb-2 grid items-center gap-x-4 rounded-t-lg bg-surface-gray-2 p-2"
						>
						</ListHeader>
						<ListRows v-for="row in studentDetails.data.assessments">
							<ListRow :row="row" class="!rounded-none last:!rounded-b-lg">
								<template #default="{ column, item }">
									<ListRowItem
										:item="row[column.key]"
										:align="column.align"
										class="w-full"
									>
										<div
											v-if="column.key == 'status' && isAssignment(row.status)"
										>
											<Badge :theme="getStatusTheme(row[column.key])">
												{{ __(row[column.key]) }}
											</Badge>
										</div>
										<div v-else>
											{{ row[column.key] }}
										</div>
									</ListRowItem>
								</template>
							</ListRow>
						</ListRows>
					</ListView>

					<!-- Courses -->
					<div class="space-y-3">
						<div class="flex items-center justify-between gap-x-2">
							<div class="text-ink-gray-5">
								{{ __('Courses') }}
							</div>
							<Select
								v-model="selectedCourse"
								:options="courseSelectOptions"
								class="!w-48"
							/>
						</div>

						<!-- All courses selected: per-course average progress -->
						<ListView
							v-if="!selectedCourse"
							:columns="courseColumns"
							:rows="studentDetails.data.courses"
							row-key="title"
							class="border border-outline-elevation-2 rounded-lg"
							:options="{
								selectable: false,
								showTooltip: false,
								onRowClick: (row: any) => {
									redirectToCourse(row)
								},
							}"
						>
							<ListHeader
								class="mb-2 grid items-center gap-x-4 rounded-t-lg bg-surface-gray-2 p-2"
							>
							</ListHeader>
							<ListRows v-for="row in studentDetails.data.courses">
								<ListRow :row="row" class="!rounded-none last:!rounded-b-lg">
									<template #default="{ column, item }">
										<ListRowItem
											:item="row[column.key]"
											:align="column.align"
											class="w-full"
										>
											<template #prefix>
												<ProgressBar
													v-if="column.key == 'progress'"
													:progress="Math.ceil(row[column.key])"
													class="!mx-0 !me-4 max-w-32"
												/>
											</template>
											<div
												v-if="column.key == 'progress'"
												class="text-xs !ms-0 !me-3 w-5"
											>
												{{ Math.ceil(row[column.key]) }}%
											</div>
											<div v-else>
												{{ row[column.key] }}
											</div>
										</ListRowItem>
									</template>
								</ListRow>
							</ListRows>
						</ListView>

						<!-- A specific course selected: this student's per-lesson detail -->
						<div
							v-else
							class="border border-outline-elevation-2 rounded-lg px-3 py-1 max-h-[50vh] overflow-y-auto"
						>
							<div
								v-if="courseLessonProgress.loading"
								class="flex items-center justify-center py-8"
							>
								<LoadingIndicator class="size-4" />
							</div>
							<template v-else-if="courseLessonProgress.data?.lessons?.length">
								<div
									v-for="lesson in courseLessonProgress.data.lessons"
									:key="lesson.lesson_name"
									class="flex items-center justify-between text-sm py-2 my-1"
								>
									<div>
										<span class="me-3 text-xs text-ink-gray-5">
											{{ lesson.chapter_idx }}.{{ lesson.idx }}
										</span>
										<span class="text-ink-gray-8">{{ lesson.title }}</span>
									</div>
									<Tooltip
										:text="lesson.completed ? __('Complete') : __('Pending')"
									>
										<span
											v-if="lesson.completed"
											class="lucide-check text-ink-green-6 size-4"
										/>
										<span v-else class="lucide-minus text-ink-amber-5 size-4" />
									</Tooltip>
								</div>
							</template>
							<div v-else class="text-ink-gray-5 py-8 text-center">
								{{ __('No lessons in this course') }}
							</div>
						</div>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import {
	Avatar,
	Badge,
	createResource,
	Dialog,
	ListView,
	ListHeader,
	ListRows,
	ListRow,
	ListRowItem,
	LoadingIndicator,
	Tooltip,
} from 'frappe-ui'
import { useRouter } from 'vue-router'
import { computed, inject, ref, watch } from 'vue'
import ProgressBar from '@/components/ProgressBar.vue'
import Select from '@/components/Controls/Select.vue'

const show = defineModel()
const router = useRouter()
const user = inject<{ data?: Record<string, any> }>('$user')
const props = defineProps<{
	student: string
	batch: string
}>()

// A scoped "Valutatore" reads the batch dashboard but must not reach the quiz
// and assignment results from it (each row links to the submission). The backend
// strips them from the payload too, see os_lms override_utils.
const canViewAssessments = computed(
	() =>
		!user?.data?.is_valutatore ||
		user?.data?.is_moderator ||
		user?.data?.is_evaluator ||
		user?.data?.is_docente,
)

const studentDetails = createResource({
	url: 'lms.lms.utils.get_batch_student_progress',
	makeParams() {
		return {
			member: props.student,
			batch: props.batch,
		}
	},
	auto: true,
})

// Course drill-down. Empty value = "All courses" (the per-course summary list);
// a course value switches to this student's per-lesson detail for that course.
const selectedCourse = ref('')

const courseSelectOptions = computed(() => [
	{ label: __('All Courses'), value: '' },
	...(studentDetails.data?.courses || []).map((course: any) => ({
		label: course.title,
		value: course.course,
	})),
])

// Per-lesson progress of this student in the selected course. Goes through the
// batch-authorized endpoint so valutatori can see it too. Fetched on demand only
// when a specific course is selected (no `auto`).
const courseLessonProgress = createResource({
	url: 'os_lms.os_lms.api.get_batch_student_course_progress',
	makeParams() {
		return {
			batch: props.batch,
			course: selectedCourse.value,
			member: props.student,
		}
	},
})

watch(selectedCourse, (course) => {
	if (course) courseLessonProgress.reload()
})

const redirectToAssessment = (row: any) => {
	console.log(row)
	if (!row.submission) return
	if (row.type == 'LMS Assignment') {
		router.push({
			name: 'AssignmentSubmission',
			params: {
				assignmentID: row.assessment,
				submissionName: row.submission,
			},
		})
	} else if (row.type == 'LMS Programming Exercise') {
		router.push({
			name: 'ProgrammingExerciseSubmission',
			params: {
				exerciseID: row.assessment,
				submissionID: row.submission,
			},
		})
	} else if (row.type == 'LMS Quiz') {
		router.push({
			name: 'QuizSubmission',
			params: {
				submission: row.submission,
			},
		})
	}
}

const redirectToCourse = (row: any) => {
	router.push({
		name: 'CourseDetail',
		params: {
			courseName: row.course,
		},
	})
}

const assessmentColumns = [
	{ key: 'title', label: __('Assessment'), align: 'left', width: '60%' },
	{ key: 'status', label: __('Percentage/Status'), align: 'right' },
]

const courseColumns = [
	{ key: 'title', label: __('Course'), align: 'left', width: '70%' },
	{ key: 'progress', label: __('Progress'), align: 'right' },
]

const isAssignment = (value: any) => {
	return isNaN(value)
}

const getStatusTheme = (status: string) => {
	if (status === 'Pass') {
		return 'green'
	} else if (status == 'Not Graded') {
		return 'orange'
	} else {
		return 'red'
	}
}
</script>
