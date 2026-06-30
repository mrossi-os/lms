<template>
	<div>
		<div class="mt-10 space-y-10">
			<div v-if="evals?.data?.length">
				<div class="text-xl-semibold text-ink-gray-9 mb-3">
					{{ __('Upcoming Evaluations') }}
				</div>
				<div class="grid grid-cols-1 md:grid-cols-4 gap-5">
					<div
						v-for="evaluation in evals?.data"
						class="border hover:border-outline-gray-3 rounded-md p-3 flex flex-col h-full cursor-pointer"
						@click="redirectToProfile()"
					>
						<div class="text-ink-gray-9 text-xl-semibold leading-5 mb-3">
							{{ evaluation.course_title }}
						</div>
						<div class="text-ink-gray-7">
							<div class="flex items-center mb-3">
								<span class="lucide-calendar size-4" />
								<span class="ms-2">
									{{ dayjs(evaluation.date).format('DD MMMM YYYY') }}
								</span>
							</div>
							<div class="flex items-center mb-3">
								<span class="lucide-clock size-4" />
								<span class="ms-2">
									{{ formatTime(evaluation.start_time) }}
								</span>
							</div>
							<div class="flex items-center">
								<span class="lucide-graduation-cap size-4" />
								<span class="ms-2">
									{{ evaluation.member_name }}
								</span>
							</div>
						</div>
					</div>
				</div>
			</div>
			<div v-if="liveClasses?.data?.length">
				<div class="text-xl-semibold text-ink-gray-9 mb-3">
					{{ __('Upcoming Live Classes') }}
				</div>
				<div class="grid grid-cols-1 md:grid-cols-4 gap-5">
					<LiveClassCard
						v-for="cls in liveClasses?.data"
						class="border hover:border-outline-gray-3 rounded-md p-3"
					>
						<div class="text-ink-gray-9 text-xl-semibold leading-5 mb-1">
							{{ cls.title }}
						</div>
						<div class="text-ink-gray-7 leading-5 mb-4">
							{{ cls.description }}
						</div>
						<div class="mt-auto space-y-3 text-ink-gray-7">
							<div class="flex items-center gap-x-2">
								<span class="lucide-calendar size-4" />
								<span>
									{{ dayjs(cls.date).format('DD MMMM YYYY') }}
								</span>
							</div>
							<div class="flex items-center gap-x-2">
								<span class="lucide-clock size-4" />
								<span>
									{{ formatTime(cls.time) }} -
									{{ dayjs(getClassEnd(cls)).format('HH:mm A') }}
								</span>
							</div>
							<div
								v-if="canAccessClass(cls)"
								class="flex items-center gap-x-2 text-ink-gray-9 mt-auto"
							>
								<a
									v-if="user.data?.is_moderator || user.data?.is_evaluator"
									:href="cls.start_url"
									target="_blank"
									class="cursor-pointer inline-flex items-center justify-center gap-2 transition-colors focus:outline-none text-ink-gray-8 bg-surface-gray-2 hover:bg-surface-gray-3 active:bg-surface-gray-4 focus-visible:ring focus-visible:ring-outline-gray-3 h-7 text-base px-2 rounded"
									:class="cls.join_url ? 'w-full' : 'w-1/2'"
								>
									<span class="lucide-monitor size-4" />
									{{ __('Start') }}
								</a>
								<a
									:href="cls.join_url"
									target="_blank"
									class="w-full cursor-pointer inline-flex items-center justify-center gap-2 transition-colors focus:outline-none text-ink-gray-8 bg-surface-gray-2 hover:bg-surface-gray-3 active:bg-surface-gray-4 focus-visible:ring focus-visible:ring-outline-gray-3 h-7 text-base px-2 rounded"
								>
									<span class="lucide-video size-4" />
									{{ __('Join') }}
								</a>
							</div>
							<Tooltip
								v-else-if="hasClassEnded(cls)"
								:text="__('This class has ended')"
								placement="right"
							>
								<div class="flex items-center gap-x-2 text-ink-amber-6 w-fit">
									<span class="lucide-info size-4" />
									<span>
										{{ __('Ended') }}
									</span>
								</div>
							</Tooltip>
						</div>
					</div>
				</div>
			</div>
		</div>

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
				<span class="text-xl-semibold text-ink-gray-9">
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
						<span class="lucide-move-right size-3 rtl:rotate-180" />
					</span>
				</router-link>
			</div>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
				<router-link
					v-for="course in createdCourses.data"
					:to="{ name: 'CourseDetail', params: { courseName: course.name } }"
				>
					<CourseCard :course="course" />
				</router-link>
			</div>
		</div>

		<div v-if="createdBatches.data?.length" class="mt-10">
			<div class="flex items-center justify-between mb-3">
				<span class="text-xl-semibold text-ink-gray-9">
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
						<span class="lucide-move-right size-3 rtl:rotate-180" />
					</span>
				</router-link>
			</div>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
				<router-link
					v-for="batch in createdBatches.data"
					:to="{ name: 'BatchDetail', params: { batchName: batch.name } }"
				>
					<BatchCard :batch="batch" />
				</router-link>
			</div>
		</div>

		<div
			v-if="
				!createdCourses.data?.length &&
				!createdBatches.data?.length &&
				!user.data?.is_valutatore
			"
			class="flex flex-col items-center justify-center mt-60"
		>
			<span class="lucide-graduation-cap size-10 mx-auto text-ink-gray-5" />
			<div class="text-xl-semibold text-ink-gray-7 mb-1.5">
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
			<router-link
				:to="{ name: 'Courses', query: { newCourse: '1' } }"
				class="mt-4"
			>
				<Button>
					<template #prefix>
						<span class="lucide-plus size-4" />
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
import { useRouter } from 'vue-router'
import { formatTime } from '@/utils'
import CourseCard from '@/components/CourseCard.vue'
import BatchCard from '@/pages/Batches/components/BatchCard.vue'
import LiveClassCard from '@/components/LiveClassCard.vue'

const user = inject<any>('$user')
const dayjs = inject<any>('$dayjs')
const router = useRouter()

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

// Batches the current user evaluates — shown only to a "Valutatore" so their
// (otherwise instructor-centric) admin home is not empty.
const evaluationBatches = createResource({
	url: 'os_lms.os_lms.api.get_evaluation_batches',
	auto: user.data?.is_valutatore ? true : false,
})

const redirectToProfile = () => {
	router.push({
		name: 'ProfileEvaluationSchedule',
		params: { username: user.data?.username },
	})
}
</script>
