<template>
	<div class="p-5">
		<section
			v-if="hasHero"
			class="relative -mx-5 -mt-5 mb-8 h-[50vh] max-h-[50vh] bg-black overflow-hidden"
		>
			<template v-if="course.data.hero?.media_type === 'Video'">
				<video
					v-if="isDirectVideoFile(course.data.hero?.media_url)"
					:src="course.data.hero?.media_url"
					controls
					class="absolute inset-0 w-full h-full object-cover"
				/>
				<iframe
					v-else
					:src="course.data.hero?.media_url"
					class="absolute inset-0 w-full h-full"
					frameborder="0"
					allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
					allowfullscreen
				/>
			</template>
			<img
				v-else-if="course.data.hero?.media_type === 'Image'"
				:src="course.data.hero?.media_url"
				:alt="course.data.title"
				class="absolute inset-0 w-full h-full object-cover"
			/>
			<div
				class="absolute inset-x-0 bottom-0 p-6 md:p-8 bg-gradient-to-t from-black/80 via-black/50 to-transparent text-white pointer-events-none"
			>
				<h1 class="text-2xl md:text-4xl font-semibold">
					{{ course.data.title }}
				</h1>
				<p
					v-if="course.data.short_introduction"
					class="mt-2 max-w-3xl text-sm md:text-base text-white/85 leading-6"
				>
					{{ course.data.short_introduction }}
				</p>
			</div>
		</section>
		<div class="flex justify-between w-full space-x-5">
			<div class="md:w-2/3">
				<template v-if="!hasHero">
					<div class="text-3xl font-semibold text-ink-gray-9">
						{{ course.data.title }}
					</div>
					<div class="my-3 leading-6 text-ink-gray-7">
						{{ course.data.short_introduction }}
					</div>
				</template>
				<div class="flex items-center">
					<Tooltip
						v-if="parseInt(course.data.rating) > 0"
						:text="__('Average Rating')"
						class="flex items-center"
					>
						<Star class="size-4 text-transparent fill-yellow-500" />
						<span class="ml-1 text-ink-gray-7">
							{{ course.data.rating }}
						</span>
					</Tooltip>
					<span v-if="parseInt(course.data.rating) > 0" class="mx-3"
						>&middot;</span
					>
					<Tooltip
						v-if="course.data.enrollment_count"
						:text="__('Enrolled Students')"
						class="flex items-center"
					>
						<Users class="h-4 w-4 text-ink-gray-7" />
						<span class="ml-1">
							{{ course.data.enrollment_count_formatted }}
						</span>
					</Tooltip>
					<span v-if="course.data.enrollment_count" class="mx-3">&middot;</span>
					<div
						v-if="
							user?.data?.is_moderator ||
							user?.data?.is_evaluator ||
							user?.data?.is_instructor
						"
						class="flex items-center"
					>
						<span
							class="h-6 mr-1"
							:class="{
								'avatar-group overlap': course.data.instructors?.length > 1,
							}"
						>
							<UserAvatar
								v-for="instructor in course.data.instructors"
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
				<div class="md:hidden my-4">
					<CourseCardOverlay :course="course" :hideVideo="hasHero" />
				</div>

				<div class="mt-10">
					<div
						ref="descriptionRef"
						v-html="unescapeDescription(course.data.description)"
						class="card p-3 ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal overflow-hidden transition-all duration-300"
						:style="
							!isExpanded && showToggle
								? `max-height: ${collapsedHeight}px`
								: ''
						"
					></div>
					<div
						v-if="showToggle"
						class="relative flex justify-center"
						:class="!isExpanded ? '-mt-10 pt-12' : 'mt-2'"
					>
						<Button
							variant="outline"
							size="sm"
							@click="isExpanded = !isExpanded"
						>
							<template #prefix>
								<ChevronDown
									class="h-4 w-4 transition-transform duration-300"
									:class="isExpanded ? 'rotate-180' : ''"
								/>
							</template>
							{{ isExpanded ? __('Mostra meno') : __('Mostra altro') }}
						</Button>
					</div>
				</div>
				<FeaturedSectionView
					v-if="course.data.feature_sections"
					:sections="course.data.feature_sections"
					:is-enrolled="!!course.data.membership"
				/>
			</div>
			<div class="hidden md:block">
				<CourseCardOverlay :course="course" :hideVideo="hasHero" />
			</div>
		</div>
		<RelatedCourses :courseName="course.data.name" />
	</div>
</template>
<script setup lang="ts">
import { Star, Users, ChevronDown } from 'lucide-vue-next'
import { Tooltip, Button } from 'frappe-ui'
import CourseCardOverlay from '@/components/CourseCardOverlay.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import CourseInstructors from '@/components/CourseInstructors.vue'
import RelatedCourses from '@/components/RelatedCourses.vue'
import FeaturedSectionView from '@/oslms/components/FeaturedSectionView.vue'
import CourseTagBadges from '@/oslms/components/CourseTagBadges.vue'
import { inject, ref, computed, onMounted, nextTick } from 'vue'

const props = defineProps<{
	course: any
}>()

const user = inject<any>('$user')

const hasHero = computed<boolean>(() => {
	const hero = props.course.data?.hero
	return !!(hero?.enabled && hero?.media_url)
})

const DIRECT_VIDEO_EXTENSIONS = /\.(mp4|webm|ogg|ogv|mov|m4v)(\?.*)?$/i
const isDirectVideoFile = (url: string | undefined) => {
	if (!url) return false
	return DIRECT_VIDEO_EXTENSIONS.test(url)
}

const isExpanded = ref(false)
const showToggle = ref(false)
const descriptionRef = ref<HTMLElement | null>(null)
const collapsedHeight = 156
const charLimit = 400

onMounted(async () => {
	await nextTick()
	const descriptionText =
		props.course.data.description?.replace(/<[^>]*>/g, '') || ''
	if (descriptionText.length > charLimit) {
		showToggle.value = true
	}
})

const unescapeDescription = (html: string) => {
	if (!html) return ''
	const textarea = document.createElement('textarea')
	textarea.innerHTML = html
	return textarea.value
}
</script>
