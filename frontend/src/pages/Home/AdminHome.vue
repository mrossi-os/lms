<template>
	<div>
		<div class="mt-10 space-y-10">
			<div v-if="evals?.data?.length">
				<div class="text-lg-semibold text-ink-gray-9 mb-3">
					{{ __('Upcoming Evaluations') }}
				</div>
				<div class="grid grid-cols-1 md:grid-cols-4 gap-5">
					<component
						:is="user.data?.username ? 'router-link' : 'div'"
						v-for="evaluation in evals?.data"
						:key="evaluation.name"
						:to="profileRoute(user.data?.username, 'ProfileEvaluationSchedule')"
						class="border rounded-md p-3 flex flex-col h-full"
						:class="
							user.data?.username
								? 'cursor-pointer hover:border-outline-gray-3'
								: ''
						"
					>
						<div class="text-ink-gray-9 text-lg-semibold leading-5 mb-3">
							{{ evaluation.course_title }}
						</div>
						<div class="text-ink-gray-7">
							<div class="flex items-center mb-3">
								<Calendar class="w-4 h-4 stroke-1.5" />
								<span class="ms-2">
									{{ dayjs(evaluation.date).format('DD MMMM YYYY') }}
								</span>
							</div>
							<div class="flex items-center mb-3">
								<Clock class="w-4 h-4 stroke-1.5" />
								<span class="ms-2">
									{{ formatTime(evaluation.start_time) }}
								</span>
							</div>
							<div v-if="evaluation.timezone" class="flex items-center mb-3">
								<span class="lucide-globe size-4" />
								<span class="ms-2">
									{{ formatTimezone(evaluation.timezone, evaluation.date) }}
								</span>
							</div>
							<div class="flex items-center">
								<GraduationCap class="w-4 h-4 stroke-1.5" />
								<span class="ms-2">
									{{ evaluation.member_name }}
								</span>
							</div>
						</div>
					</component>
				</div>
			</div>
			<div v-if="liveClasses?.data?.length">
				<div class="text-lg-semibold text-ink-gray-9 mb-3">
					{{ __('Upcoming Live Classes') }}
				</div>
				<div class="grid grid-cols-1 md:grid-cols-4 gap-5">
					<!-- OSLMS-CUSTOM: shared LiveClassCard (gated internal join, host start, observer join for the Valutatore) replaces the upstream inline card -->
					<LiveClassCard
						v-for="cls in liveClasses?.data"
						:key="cls.name"
						:cls="cls"
						:isAdmin="user.data?.is_moderator || user.data?.is_evaluator"
						:observer="Boolean(cls.is_valutatore)"
						@started="liveClasses?.reload?.()"
					/>
				</div>
			</div>
		</div>

		<!-- OSLMS-CUSTOM: "Batches you evaluate" section for the Valutatore -->
		<div
			v-if="user.data?.is_valutatore && evaluationBatches.data?.length"
			class="mt-10"
		>
			<div class="flex items-center justify-between mb-3">
				<span class="font-semibold text-lg text-ink-gray-9">
					{{ __('Batches you evaluate') }}
				</span>
				<router-link :to="{ name: 'Batches' }">
					<span class="flex items-center gap-x-1 text-ink-gray-5 text-xs">
						<span>
							{{ __('See all') }}
						</span>
						<MoveRight class="size-3 stroke-1.5 rtl:rotate-180" />
					</span>
				</router-link>
			</div>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
				<router-link
					v-for="batch in evaluationBatches.data"
					:to="{ name: 'BatchDetail', params: { batchName: batch.name } }"
				>
					<BatchCard :batch="batch" />
				</router-link>
			</div>
		</div>

		<div v-if="createdCourses.data?.length" class="mt-10">
			<div class="flex items-center justify-between mb-3">
				<span class="text-lg-semibold text-ink-gray-9">
					{{ __('Courses Created') }}
				</span>
				<router-link
					:to="{
						name: 'Courses',
					}"
				>
					<span class="flex items-center gap-x-1 text-ink-gray-5 text-xs">
						<span>
							{{ __('See all') }}
						</span>
						<MoveRight class="size-3 stroke-1.5 rtl:rotate-180" />
					</span>
				</router-link>
			</div>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
				<router-link
					v-for="course in createdCourses.data"
					:key="course.name"
					:to="{ name: 'CourseDetail', params: { courseName: course.name } }"
				>
					<CourseCard :course="course" />
				</router-link>
			</div>
		</div>

		<div v-if="createdBatches.data?.length" class="mt-10">
			<div class="flex items-center justify-between mb-3">
				<span class="text-lg-semibold text-ink-gray-9">
					{{ __('Upcoming Batches') }}
				</span>
				<router-link
					:to="{
						name: 'Batches',
					}"
				>
					<span class="flex items-center gap-x-1 text-ink-gray-5 text-xs">
						<span>
							{{ __('See all') }}
						</span>
						<MoveRight class="size-3 stroke-1.5 rtl:rotate-180" />
					</span>
				</router-link>
			</div>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
				<router-link
					v-for="batch in createdBatches.data"
					:key="batch.name"
					:to="{ name: 'BatchDetail', params: { batchName: batch.name } }"
				>
					<BatchCard :batch="batch" />
				</router-link>
			</div>
		</div>

		<!-- OSLMS-CUSTOM: no "Create Course" empty state for the Valutatore -->
		<div
			v-if="
				!createdCourses.data?.length &&
				!createdBatches.data?.length &&
				!user.data?.is_valutatore
			"
			class="flex flex-col items-center justify-center mt-60"
		>
			<span class="lucide-graduation-cap size-10 mx-auto text-ink-gray-5" />
			<div class="text-lg-semibold text-ink-gray-7 mb-1.5">
				{{ __('No courses created') }}
			</div>
			<div
				class="leading-5 text-base w-full md:w-2/5 text-base text-center text-ink-gray-7"
			>
				{{
					__(
						'There are no courses currently. Create your first course to get started!',
					)
				}}
			</div>
			<router-link :to="{ name: 'NewCourse' }" class="mt-4">
				<Button>
					<template #prefix>
						<Plus class="size-4 stroke-1.5" />
					</template>
					{{ __('Create Course') }}
				</Button>
			</router-link>
		</div>
	</div>
</template>
<script setup lang="ts">
import { Button, createResource } from 'frappe-ui'
import { inject } from 'vue'
import {
	Calendar,
	Clock,
	GraduationCap,
	MoveRight,
	Plus,
} from 'lucide-vue-next'
import { formatTime } from '@/utils'
import { formatTimezone } from '@/utils/timezone'
import { profileRoute } from '@/utils/routes'
import CourseCard from '@/components/CourseCard.vue'
import BatchCard from '@/pages/Batches/components/BatchCard.vue'
// OSLMS-CUSTOM: shared live class card
import LiveClassCard from '@/components/LiveClassCard.vue'

const user = inject<any>('$user')
const dayjs = inject<any>('$dayjs')

const props = defineProps<{
	liveClasses?: { data?: any[] }
	evals?: { data?: any[] }
}>()

const createdCourses = createResource({
	url: 'lms.lms.api.get_created_courses',
	auto: true,
})

const createdBatches = createResource({
	url: 'lms.lms.api.get_created_batches',
	auto: true,
})

// OSLMS-CUSTOM: Valutatore's evaluated batches
// Batches the current user evaluates — shown only to a "Valutatore" so their
// (otherwise instructor-centric) admin home is not empty.
const evaluationBatches = createResource({
	url: 'os_lms.os_lms.api.get_evaluation_batches',
	auto: user.data?.is_valutatore ? true : false,
})
</script>
