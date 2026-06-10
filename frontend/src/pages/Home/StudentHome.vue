<template>
	<div>
		<div class="mt-10 space-y-10">
			<UpcomingEvaluations :forHome="true" />
			<WelcomeWithOverallProgress />
			<div v-if="myLiveClasses.data?.length">
				<div class="font-semibold text-lg mb-3 text-ink-gray-9">
					{{ __('Upcoming Live Classes') }}
				</div>
				<div class="grid grid-cols-1 md:grid-cols-4 gap-5">
					<LiveClassCard
						v-for="cls in myLiveClasses.data"
						:key="cls.name"
						:cls="cls"
						:isAdmin="user.data?.is_moderator || user.data?.is_evaluator"
						@started="myLiveClasses.reload()"
					/>
				</div>
			</div>
		</div>

		<div v-if="myCourses.data?.length" class="mt-10">
			<div class="flex items-center justify-between mb-3">
				<span class="font-semibold text-lg text-ink-gray-9">
					{{
						myCourses.data[0].membership
							? __('My Courses')
							: __('Our Popular Courses')
					}}
				</span>
				<router-link
					:to="{
						name: 'Courses',
					}"
				>
					<span
						class="flex items-center gap-x-1 text-ink-gray-5 text-xs"
					>
						<span>
							{{ __('See all') }}
						</span>
						<MoveRight class="size-3 stroke-1.5 rtl:rotate-180" />
					</span>
				</router-link>
			</div>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5" :class="courseGridClass">
				<router-link
					v-for="course in myCourses.data"
					:to="{ name: 'CourseDetail', params: { courseName: course.name } }"
				>
					<CourseCard :course="course" />
				</router-link>
			</div>
		</div>

		<div v-if="newCourses.data?.length" class="mt-10">
			<div class="flex items-center justify-between mb-3">
				<span class="font-semibold text-lg text-ink-gray-9">
					{{ __('New Arrivals') }}
				</span>
				<router-link :to="{ name: 'Courses' }">
					<span
						class="flex items-center space-x-1 text-ink-gray-5 text-xs card p-1.5"
					>
						<span>
							{{ __('See all') }}
						</span>
						<MoveRight class="size-3 stroke-1.5" />
					</span>
				</router-link>
			</div>
			<div class="grid gap-5" :class="courseGridClass">
				<router-link
					v-for="course in newCourses.data"
					:to="{ name: 'CourseDetail', params: { courseName: course.name } }"
				>
					<CourseCard :course="course" />
				</router-link>
			</div>
		</div>

		<div v-if="mostFollowed.data?.length" class="mt-10">
			<div class="flex items-center justify-between mb-3">
				<span class="font-semibold text-lg text-ink-gray-9">
					{{ __('Most Popular') }}
				</span>
				<router-link :to="{ name: 'Courses' }">
					<span
						class="flex items-center space-x-1 text-ink-gray-5 text-xs card p-1.5"
					>
						<span>
							{{ __('See all') }}
						</span>
						<MoveRight class="size-3 stroke-1.5" />
					</span>
				</router-link>
			</div>
			<div class="grid gap-5" :class="courseGridClass">
				<router-link
					v-for="course in mostFollowed.data"
					:to="{ name: 'CourseDetail', params: { courseName: course.name } }"
				>
					<CourseCard :course="course" />
				</router-link>
			</div>
		</div>

		<div v-if="myBatches.data?.length" class="mt-10">
			<div class="flex items-center justify-between mb-3">
				<span class="font-semibold text-lg text-ink-gray-9">
					{{
						myBatches.data?.[0].students?.includes(user.data?.name)
							? __('My Batches')
							: __('Our Upcoming Batches')
					}}
				</span>
				<router-link
					:to="{
						name: 'Batches',
					}"
				>
					<span
						class="flex items-center gap-x-1 text-ink-gray-5 text-xs"
					>
						<span>
							{{ __('See all') }}
						</span>
						<MoveRight class="size-3 stroke-1.5 rtl:rotate-180" />
					</span>
				</router-link>
			</div>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
				<router-link
					v-for="batch in myBatches.data"
					:to="{ name: 'BatchDetail', params: { batchName: batch.name } }"
				>
					<BatchCard :batch="batch" />
				</router-link>
			</div>
		</div>
	</div>
</template>
<script setup lang="ts">
import { inject } from 'vue'
import { createResource } from 'frappe-ui'
import { MoveRight } from 'lucide-vue-next'
import CourseCard from '@/components/CourseCard.vue'
import BatchCard from '@/pages/Batches/components/BatchCard.vue'
import UpcomingEvaluations from '@/components/UpcomingEvaluations.vue'
import WelcomeWithOverallProgress from '@/oslms/components/Home/WelcomeWithOverallProgress.vue'
import LiveClassCard from '@/components/LiveClassCard.vue'

const user = inject<any>('$user')

const HOME_COURSE_COLS = 5

const courseGridClass =
	{
		1: 'grid-cols-1',
		2: 'grid-cols-1 sm:grid-cols-2',
		3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
		4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
		5: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5',
		6: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6',
	}[HOME_COURSE_COLS] || 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3'

const props = defineProps<{
	myLiveClasses: any
}>()

const myCourses = createResource({
	url: 'lms.lms.api.get_my_courses',
	auto: true,
})

const newCourses = createResource({
	url: 'os_lms.os_lms.override_api.get_new_courses',
	auto: true,
})

const mostFollowed = createResource({
	url: 'os_lms.os_lms.override_api.get_most_followed_courses',
	auto: true,
})

const myBatches = createResource({
	url: 'lms.lms.api.get_my_batches',
	auto: true,
})
</script>
