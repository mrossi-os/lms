<template>
	<Dialog
		v-model:open="show"
		size="xl"
		:title="studentDetails.data?.full_name || __('Student Details')"
		bare
	>
		<template #default>
			<div
				v-if="studentDetails.loading && !studentDetails.data"
				class="flex items-center justify-center py-12"
			>
				<LoadingIndicator class="size-4" />
			</div>
			<div v-else-if="studentDetails.data" class="p-5 space-y-10 text-sm">
				<div class="flex items-center gap-x-4">
					<Avatar :image="studentDetails.data.user_image" size="3xl" />
					<div class="space-y-1">
						<div class="flex items-center gap-x-2">
							<div class="text-2xl-semibold text-ink-gray-9">
								{{ studentDetails.data.full_name }}
							</div>
							<!-- OSLMS-CUSTOM: Italian label for the completion badge -->
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
					<ResponsiveListView
						:columns="assessmentColumns"
						:rows="studentDetails.data.assessments"
						row-key="title"
						class="sm:border sm:border-outline-elevation-2 sm:rounded-lg"
						:options="assessmentListOptions"
					>
						<template #cell="{ column, value }">
							<Badge
								v-if="column.key == 'status' && isAssignment(value)"
								:theme="getStatusTheme(value as string)"
							>
								<!-- OSLMS-CUSTOM: translated assignment status -->
								{{ __(value as string) }}
							</Badge>
							<span v-else>{{ value }}</span>
						</template>
					</ResponsiveListView>

					<!-- Courses -->
					<!-- OSLMS-CUSTOM: course selector with per-lesson drill-down for this student -->
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
						<ResponsiveListView
							v-if="!selectedCourse"
							:columns="courseColumns"
							:rows="studentDetails.data.courses"
							row-key="title"
							class="sm:border sm:border-outline-elevation-2 sm:rounded-lg"
							:options="courseListOptions"
						>
							<template #cell="{ column, value }">
								<span
									v-if="column.key == 'progress'"
									class="flex items-center gap-2"
								>
									<ProgressBar
										:progress="Math.ceil(Number(value))"
										class="!mx-0 min-w-0 max-w-32 flex-1"
									/>
									<span class="text-xs shrink-0">
										{{ Math.ceil(Number(value)) }}%
									</span>
								</span>
								<span v-else>{{ value }}</span>
							</template>
						</ResponsiveListView>

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
	LoadingIndicator,
	Tooltip,
} from 'frappe-ui'
import { useRouter } from 'vue-router'
import { computed, ref, watch } from 'vue'
import ProgressBar from '@/components/ProgressBar.vue'
import Select from '@/components/Controls/Select.vue'
import ResponsiveListView from '@/components/ResponsiveListView.vue'
import type { ListColumn, ListRow, ListViewOptions } from '@/types'

const show = defineModel()
const router = useRouter()
const props = defineProps<{
	student: string
	batch: string
}>()

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

// OSLMS-CUSTOM: per-course lesson drill-down
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
	// OSLMS-CUSTOM: batch-authorized endpoint so a Valutatore can see it too
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

const assessmentColumns: ListColumn[] = [
	{ key: 'title', label: __('Assessment'), align: 'left', width: '60%' },
	{ key: 'status', label: __('Percentage/Status'), align: 'left' },
]

const courseColumns: ListColumn[] = [
	{ key: 'title', label: __('Course'), align: 'left', width: '70%' },
	{ key: 'progress', label: __('Progress'), align: 'left' },
]

const assessmentListOptions: ListViewOptions = {
	selectable: false,
	showTooltip: false,
	onRowClick: (row: ListRow) => redirectToAssessment(row),
}

const courseListOptions: ListViewOptions = {
	selectable: false,
	showTooltip: false,
	onRowClick: (row: ListRow) => redirectToCourse(row),
}

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
