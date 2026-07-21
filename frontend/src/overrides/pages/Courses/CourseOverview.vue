<template>
	<SkeletonLoader v-if="!course.data" variant="course-page" />
	<div v-else class="p-5">
		<div
			class="flex flex-col md:flex-row items-start justify-between w-full gap-x-8 gap-y-8"
		>
			<div class="w-full md:w-2/3 space-y-10 min-w-0">
				<section class="space-y-4">
					<h1 class="text-3xl font-semibold text-ink-gray-9">
						{{ course.data.title }}
					</h1>
					<div
						class="flex flex-wrap items-center gap-x-3 gap-y-2 text-ink-gray-7"
					>
						<!-- OSLMS-CUSTOM: hide the course instructors from students;
						only moderators/course instructors see them. -->
						<div
							v-if="isCourseAdmin && course.data.instructors?.length"
							class="flex items-center"
						>
							<span
								class="h-6 me-1"
								:class="{
									'avatar-group overlap': course.data.instructors.length > 1,
								}"
							>
								<UserAvatar
									v-for="instructor in course.data.instructors"
									:key="instructor.name"
									:user="instructor"
								/>
							</span>
							<CourseInstructors :instructors="course.data.instructors" />
						</div>
					</div>
					<CourseTagBadges
						v-if="course.data.tags"
						:tags="course.data.tags"
						class="my-4"
					/>
					<p
						v-if="course.data.short_introduction"
						class="text-ink-gray-7 leading-6"
					>
						{{ course.data.short_introduction }}
					</p>
					<div class="md:hidden">
						<CourseCardOverlay :course="course" :hideVideo="hasHero" />
					</div>
				</section>

				<!-- OSLMS-CUSTOM: "Course content" section removed (commented out)
				<section>
					<div class="flex items-baseline justify-between gap-4 mb-4">
						<h2 class="text-2xl font-semibold text-ink-gray-9">
							{{ __('Course content') }}
						</h2>
						<div class="text-base text-ink-gray-5">
							{{ outlineStats }}
						</div>
					</div>
					<div class="border rounded-md p-2">
						<SkeletonLoader
							v-if="outline.loading && !outline.data"
							variant="list"
							:count="6"
						/>
						<CourseOutline
							v-else
							:courseName="course.data.name"
							:getProgress="course.data.membership ? true : false"
							:editorLinks="isCourseAdmin"
						/>
					</div>
				</section>
				-->

				<!-- OSLMS-CUSTOM: hero media as a standalone section between the
				short introduction and the "About this course" section. -->
				<CourseHero
					v-if="hasHero"
					:hero="heroData"
					:title="course.data.title"
				/>

				<section v-if="course.data.description" class="space-y-3">
					<h2 class="text-2xl font-semibold text-ink-gray-9">
						{{ __('About this course') }}
					</h2>
					<!-- OSLMS-CUSTOM: collapsible description (show more/less) -->
					<CourseDescription :description="course.data.description" />
				</section>

				<!-- OSLMS-CUSTOM: course feature sections -->
				<FeaturedSectionView
					v-if="featureSections"
					:sections="featureSections"
					:isEnrolled="!!course.data.membership"
				/>

				<!-- OSLMS-CUSTOM: CourseReviews removed (commented out)
				<CourseReviews
					:courseName="course.data.name"
					:avg_rating="course.data.rating"
					:membership="course.data.membership || null"
				/>
				-->
			</div>

			<aside
				class="hidden md:flex w-80 shrink-0 flex-col space-y-6 self-start sticky top-5"
			>
				<CourseCardOverlay :course="course" :hideVideo="hasHero" />
				<!-- OSLMS-CUSTOM: CourseCreatorCard removed (commented out)
				<CourseCreatorCard :instructors="course.data.instructors || []" />
				-->
			</aside>
		</div>

		<RelatedCourses :courseName="course.data.name" class="mt-12" />
	</div>
</template>

<script setup lang="ts">
import { computed, inject, provide } from 'vue'
import { createResource, Badge } from 'frappe-ui'
import { Star, UsersRound } from 'lucide-vue-next'
import { formatAmount, formatRating } from '@/utils/'
import type { SessionUser } from '@/types/api'
import CourseCardOverlay from '@/components/CourseCardOverlay.vue'
import CourseOutline from '@/components/CourseOutline.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import CourseReviews from '@/components/CourseReviews.vue'
import CourseInstructors from '@/components/CourseInstructors.vue'
import CourseCreatorCard from '@/components/CourseCreatorCard.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import RelatedCourses from '@/components/RelatedCourses.vue'
import CourseHero from '@/oslms/components/CourseHero.vue'
import CourseDescription from '@/oslms/components/CourseDescription.vue'
import CourseTagBadges from '@/oslms/components/CourseTagBadges.vue'
import FeaturedSectionView from '@/oslms/components/FeaturedSectionView.vue'
import type { CourseDetails, OutlineChapter, Resource } from '@/types/api'

const props = defineProps<{
	course: Resource<CourseDetails | null>
}>()

const user = inject<SessionUser>('$user')

// OSLMS-CUSTOM: tag colours are provided by Courses.vue on the listing page, but
// not in the CourseDetail tab tree. Re-fetch the LMS OS Tag colour map here and
// provide it so <CourseTagBadges> renders on the course overview too.
const tagResource = createResource({
	url: 'frappe.client.get_list',
	method: 'POST',
	params: {
		doctype: 'LMS OS Tag',
		fields: ['tag_name', 'color'],
		limit_page_length: 0,
	},
	auto: true,
})

const tagColorMap = computed<Map<string, string>>(() => {
	if (!tagResource.data) return new Map()
	return new Map(
		(tagResource.data as Array<{ tag_name: string; color: string }>).map(
			(t) => [t.tag_name, t.color],
		),
	)
})

provide('tagColorMap', tagColorMap)

const isCourseInstructor = computed<boolean>(() =>
	(props.course.data?.instructors || []).some(
		(i) => i.name === user?.data?.name,
	),
)

const isCourseAdmin = computed<boolean>(
	() => Boolean(user?.data?.is_moderator) || isCourseInstructor.value,
)

// OSLMS-CUSTOM: hero banner — `hero` is nested by the os_lms get_course_details
// override (override_utils.py); not part of the upstream CourseDetails type.
const heroData = computed<any>(() => (props.course.data as any)?.hero ?? null)
const hasHero = computed<boolean>(() =>
	Boolean(heroData.value?.enabled && heroData.value?.media_url),
)

// OSLMS-CUSTOM: feature sections — also nested by the os_lms get_course_details
// override (override_utils.py); not part of the upstream CourseDetails type.
const featureSections = computed<any>(
	() => (props.course.data as any)?.feature_sections ?? null,
)

// OSLMS-CUSTOM: outline resource/stats removed with the "Course content" section
// (commented out to avoid a wasted get_course_outline API call).
/*
const outline = createResource({
	url: 'lms.lms.utils.get_course_outline',
	cache: ['course_outline', props.course.data?.name],
	makeParams() {
		return { course: props.course.data?.name, progress: false }
	},
	auto: true,
}) as Resource<OutlineChapter[]>

const outlineStats = computed(() => {
	const chapters = outline.data || []
	const lessonCount = chapters.reduce(
		(acc, c) => acc + (c.lessons?.length || 0),
		0,
	)
	const parts: string[] = []
	if (chapters.length) {
		parts.push(
			`${chapters.length} ${
				chapters.length === 1 ? __('section') : __('sections')
			}`,
		)
	}
	if (lessonCount) {
		parts.push(
			`${lessonCount} ${lessonCount === 1 ? __('lesson') : __('lessons')}`,
		)
	}
	return parts.join(' · ')
})
*/
</script>
