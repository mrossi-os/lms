<template>
	<div class="p-5">
		<div class="flex justify-between w-full space-x-5">
			<div class="md:w-2/3">
				<div class="text-3xl font-semibold text-ink-gray-9">
					{{ course.data.title }}
				</div>
				<div class="my-3 leading-6 text-ink-gray-7">
					{{ course.data.short_introduction }}
				</div>
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
				<div v-if="course.data.tags" class="flex my-4 w-fit">
					<Badge
						theme="gray"
						size="lg"
						class="mr-2 text-ink-gray-9"
						v-for="tag in course.data.tags.split(', ')"
					>
						{{ tag }}
					</Badge>
				</div>
				<div class="md:hidden my-4">
					<CourseCardOverlay :course="course" />
				</div>
				<!-- <div
					v-html="course.data.description"
					class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal mt-10"
				></div> -->
				<div
					v-html="unescapeDescription(course.data.description)"
					class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal mt-10"
				></div>
				<CourseFeaturedSections
					v-if="course.data.feature_sections"
					:sections="course.data.feature_sections"
				/>
			</div>
			<div class="hidden md:block">
				<CourseCardOverlay :course="course" />
			</div>
		</div>
		<RelatedCourses :courseName="course.data.name" />
	</div>
</template>
<script setup lang="ts">
import { Star, Users } from 'lucide-vue-next'
import { Badge, Tooltip } from 'frappe-ui'
import CourseCardOverlay from '@/components/CourseCardOverlay.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import CourseInstructors from '@/components/CourseInstructors.vue'
import RelatedCourses from '@/components/RelatedCourses.vue'
import CourseFeaturedSections from '@/oslms/components/CourseFeaturedSections.vue'
import { inject } from 'vue'

const props = defineProps<{
	course: any
}>()

const user = inject<any>('$user') // aggiungi questa riga

const unescapeDescription = (html: string) => {
	if (!html) return ''
	const textarea = document.createElement('textarea')
	textarea.innerHTML = html
	return textarea.value
}
</script>
