<template>
	<SkeletonLoader v-if="!course.data" variant="course-page" />
	<!-- OSLMS-CUSTOM: extra bottom padding on mobile so the fixed "Continue Learning"
	bar (rendered below) never covers the last section. -->
	<div v-else class="p-5" :class="{ 'pb-36': showMobileCta }">
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
					<!-- OSLMS-CUSTOM: 640–767px keeps the desktop shell (with sidebar),
					so the new mobile treatment (fixed bottom CTA + outline-at-bottom)
					is confined to the phone shell (<640px, MobileLayout, no sidebar).
					In the 640–767px gap the page is single-column but the desktop
					sidebar card is hidden, so render the original full card inline. -->
					<div v-if="isNarrow && !isMobile" class="md:hidden">
						<CourseCardOverlay :course="course" :hideVideo="hasHero" />
					</div>
					<!-- Phone (<640px): the outline moves to the page bottom and the
					"Continue Learning" CTA becomes a fixed bar, so the card keeps only
					the preview/enroll + certificate actions. It hides itself when that
					would leave it empty (see hasCardContent in CourseCardOverlay). -->
					<div v-else-if="isMobile">
						<CourseCardOverlay
							:course="course"
							:hideVideo="hasHero"
							hideOutline
							hideContinueCta
						/>
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

				<!-- OSLMS-CUSTOM: on the phone shell (<640px) the course outline
				("Programma del Corso") moves to the bottom, below the content
				sections. In every wider layout it stays in the card (inline 640–767px,
				sidebar ≥768px), so this is mount-gated to avoid a duplicate outline. -->
				<section v-if="isMobile">
					<CourseOutline
						:title="__('Course Outline')"
						:courseName="course.data.name"
						:showOutline="false"
						:getProgress="course.data.membership ? true : false"
					/>
				</section>
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

		<!-- OSLMS-CUSTOM: phone-only (<640px) floating "Continue Learning" CTA — a
		full-width bar pinned above the MobileLayout bottom nav (~48px = bottom-12).
		Confined to the phone shell so it never overlaps the desktop sidebar. The
		course outline moved to the page bottom so this stays the single primary
		action. AiFixedButtons lifts above it via the shared mobile-cta store. -->
		<div
			v-if="showMobileCta"
			class="fixed inset-x-0 bottom-12 standalone:bottom-16 z-30 p-3"
		>
			<router-link :to="continueRoute" class="flex w-full justify-center">
				<Button variant="solid" size="md" class="w-2/3">
					<template #prefix>
						<span class="lucide-book-text size-4" />
					</template>
					<span>
						{{ __('Continue Learning') }}
					</span>
				</Button>
			</router-link>
		</div>
	</div>
</template>

<script setup lang="ts">
import { computed, inject, provide, watch, onUnmounted } from 'vue'
import { createResource, Badge, Button } from 'frappe-ui'
import { Star, UsersRound } from 'lucide-vue-next'
import { formatAmount, formatRating } from '@/utils/'
import { useScreenSize } from '@/utils/composables'
import { useMobileCta } from '@/stores/mobileCta'
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

// OSLMS-CUSTOM: mobile treatment for the course page. `isNarrow` matches the
// page's own `md:` split (single column below 768px); `isMobile` matches the app
// shell breakpoint (MobileLayout + its bottom nav render below 640px), used to
// park the floating CTA above that nav.
const { size } = useScreenSize()
const isNarrow = computed<boolean>(() => size.width < 768)
const isMobile = computed<boolean>(() => size.width < 640)

// The floating "Continue Learning" bar shows on the phone shell (<640px, where the
// MobileLayout bottom nav lives and there is no sidebar) for enrolled members.
const showMobileCta = computed<boolean>(
	() => isMobile.value && Boolean(props.course.data?.membership),
)

// Same target as CourseCardOverlay's "Continue Learning" button: resume at the
// stored current lesson, or the very first lesson when none is recorded yet.
const continueRoute = computed(() => {
	const current = props.course.data?.current_lesson
	return {
		name: 'Lesson',
		params: {
			courseName: props.course.data?.name ?? '',
			chapterNumber: current ? current.split('-')[0] : 1,
			lessonNumber: current ? current.split('-')[1] : 1,
		},
	}
})

// Publish the bar's presence so global floating UI (AiFixedButtons) can lift above
// it instead of overlapping. Cleared on unmount so it never leaks to other pages.
const mobileCta = useMobileCta()
watch(showMobileCta, (visible) => mobileCta.setBar(visible), {
	immediate: true,
})
onUnmounted(() => mobileCta.setBar(false))

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
