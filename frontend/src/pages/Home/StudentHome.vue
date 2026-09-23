<template>
	<div>
		<div class="mt-10 space-y-10">
			<UpcomingEvaluations :forHome="true" />
			<WelcomeWithOverallProgress />
			<div v-if="myLiveClasses.data?.length">
				<h2 class="font-semibold text-md mb-3 text-ink-gray-9">
					{{ __('Upcoming Live Classes') }}
				</h2>
				<div class="grid grid-cols-1 md:grid-cols-4 gap-5">
					<LiveClassCard
						v-for="cls in myLiveClasses.data"
						:key="cls.name"
						:cls="cls"
						:isAdmin="user.data?.is_moderator || user.data?.is_evaluator"
						:observer="Boolean(cls.is_valutatore)"
						@started="myLiveClasses.reload()"
					/>
				</div>
			</div>
		</div>

		<div v-if="myCourses.data?.length" class="mt-10">
			<div class="flex items-center justify-between mb-3">
				<h2 class="font-semibold text-md text-ink-gray-9">
					{{
						myCourses.data[0].membership
							? __('My Courses')
							: __('Our Popular Courses')
					}}
				</h2>
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
			<div class="grid gap-5" :class="courseGridClass">
				<router-link
					v-for="course in myCourses.data"
					:key="course.name"
					:to="{ name: 'CourseDetail', params: { courseName: course.name } }"
				>
					<CourseCard :course="course" />
				</router-link>
			</div>
		</div>

		<!-- OSLMS-CUSTOM: the learner's programs; published ones as a fallback
		     when they are enrolled in none (same pattern as the batches row). -->
		<div v-if="homePrograms.length" class="mt-10">
			<div class="flex items-center justify-between mb-3">
				<span class="font-semibold text-lg text-ink-gray-9">
					{{
						hasEnrolledPrograms ? __('My Programs') : __('Available Programs')
					}}
				</span>
				<router-link :to="{ name: 'Programs' }">
					<span class="flex items-center gap-x-1 text-ink-gray-5 text-xs">
						<span>
							{{ __('See all') }}
						</span>
						<MoveRight class="size-3 stroke-1.5 rtl:rotate-180" />
					</span>
				</router-link>
			</div>
			<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
				<div
					v-for="program in homePrograms"
					:key="program.name"
					class="border rounded-md p-3 hover:border-outline-gray-3 cursor-pointer card"
					@click="openProgram(program.name)"
				>
					<div class="text-xl-semibold text-ink-gray-9 mb-2">
						{{ program.name }}
					</div>
					<div class="flex items-center gap-x-5 text-sm text-ink-gray-7">
						<div class="flex items-center gap-x-1">
							<span class="lucide-book-open size-3" />
							<span>
								{{ program.course_count }}
								{{ program.course_count == 1 ? __('course') : __('courses') }}
							</span>
						</div>
					</div>
					<div v-if="hasEnrolledPrograms" class="mt-5">
						<ProgressBar :progress="program.progress" />
						<div class="text-sm text-ink-gray-7 mt-1">
							{{ Math.ceil(program.progress || 0) }}% {{ __('completed') }}
						</div>
					</div>
				</div>
			</div>
			<ProgramEnrollment
				v-model="showProgramEnrollment"
				:programName="enrollmentProgram"
			/>
		</div>

		<div v-if="newCourses.data?.length" class="mt-10">
			<div class="flex items-center justify-between mb-3">
				<span class="font-semibold text-lg text-ink-gray-9">
					{{ __('New Arrivals') }}
				</span>
				<router-link :to="{ name: 'Courses' }">
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
						class="flex items-center gap-x-1 text-ink-gray-5 text-xs"
					>
						<span>
							{{ __('See all') }}
						</span>
						<MoveRight class="size-3 stroke-1.5 rtl:rotate-180" />
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
				<h2 class="font-semibold text-md text-ink-gray-9">
					{{
						myBatches.data?.[0].students?.includes(user.data?.name)
							? __('My Batches')
							: __('Our Upcoming Batches')
					}}
				</h2>
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
					:key="batch.name"
					:to="{ name: 'BatchDetail', params: { batchName: batch.name } }"
				>
					<BatchCard :batch="batch" />
				</router-link>
			</div>
		</div>
	</div>
</template>
<script setup lang="ts">
import { computed, inject, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { createResource } from 'frappe-ui'
import { MoveRight } from 'lucide-vue-next'
import CourseCard from '@/components/CourseCard.vue'
import BatchCard from '@/pages/Batches/components/BatchCard.vue'
import UpcomingEvaluations from '@/components/UpcomingEvaluations.vue'
import WelcomeWithOverallProgress from '@/oslms/components/Home/WelcomeWithOverallProgress.vue'
import LiveClassCard from '@/components/LiveClassCard.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import ProgramEnrollment from '@/pages/Programs/ProgramEnrollment.vue'
import { useSettings } from '@/stores/settings'

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
// OSLMS-CUSTOM: programs row. Reuses the settings-store resource the sidebar
// already loads (get_programs) instead of a second request; fetched here only
// when nothing has loaded it yet (e.g. the mobile layout has no sidebar).
const router = useRouter()
const { programs } = useSettings()
const showProgramEnrollment = ref(false)
const enrollmentProgram = ref<string | null>(null)

onMounted(() => {
	if (!programs.data && !programs.loading) programs.reload()
})

const hasEnrolledPrograms = computed(
	() => (programs.data?.enrolled?.length ?? 0) > 0,
)

const homePrograms = computed<any[]>(() =>
	hasEnrolledPrograms.value
		? programs.data.enrolled
		: (programs.data?.published ?? []),
)

const openProgram = (programName: string) => {
	if (hasEnrolledPrograms.value) {
		router.push({ name: 'ProgramDetail', params: { programName } })
	} else {
		enrollmentProgram.value = programName
		showProgramEnrollment.value = true
	}
}
</script>
