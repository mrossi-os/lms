<template>
	<div class="flex flex-col gap-4" :class="{ 'md:mt-16': hideVideo }">
		<div class="border-2 rounded-md w-full md:min-w-80 max-w-sm card">
			<iframe
				v-if="course.data.video_link && !hideVideo"
				:src="video_link"
				class="rounded-t-md min-h-56 w-full"
			/>
			<div class="p-5 flex flex-col gap-4">
				<div v-if="course.data.paid_course" class="text-2xl font-semibold mb-3">
					{{ course.data.price }}
				</div>
				<div v-if="!readOnlyMode">
					<div v-if="course.data.membership" class="space-y-2">
						<router-link
							:to="{
								name: 'Lesson',
								params: {
									courseName: course.name,
									chapterNumber: course.data.current_lesson
										? course.data.current_lesson.split('-')[0]
										: 1,
									lessonNumber: course.data.current_lesson
										? course.data.current_lesson.split('-')[1]
										: 1,
								},
							}"
						>
							<Button variant="solid" size="md" class="w-full">
								<template #prefix>
									<BookText class="size-4 stroke-1.5" />
								</template>
								<span>
									{{ __('Continue Learning') }}
								</span>
							</Button>
						</router-link>
						<CertificationLinks :courseName="course.data.name" class="w-full" />
					</div>
					<router-link
						v-else-if="course.data.paid_course && !isAdmin"
						:to="{
							name: 'Billing',
							params: {
								type: 'course',
								name: course.data.name,
							},
						}"
					>
						<Button variant="solid" size="md" class="w-full mb-8">
							<template #prefix>
								<CreditCard class="size-4 stroke-1.5" />
							</template>
							<span>
								{{ __('Buy this course') }}
							</span>
						</Button>
					</router-link>
					<Badge
						v-else-if="course.data.disable_self_learning && !isAdmin"
						theme="blue"
						size="lg"
						class="mb-4"
					>
						{{ __('Contact the Administrator to enroll for this course') }}
					</Badge>
					<Button
						v-else-if="!isAdmin"
						@click="enrollStudent()"
						variant="solid"
						class="w-full mb-8"
						size="md"
					>
						<template #prefix>
							<BookText class="size-4 stroke-1.5" />
						</template>
						<span>
							{{ __('Start Learning') }}
						</span>
					</Button>
					<Button
						v-if="canGetCertificate"
						@click="fetchCertificate()"
						variant="subtle"
						class="w-full mt-2"
						size="md"
					>
						<template #prefix>
							<GraduationCap class="size-4 stroke-1.5" />
						</template>
						{{ __('Get Certificate') }}
					</Button>
				</div>
				<div :class="readOnlyMode ? 'mt-4' : 'mt-0'">
					<CourseOutline
						:title="__('Course Outline')"
						:courseName="course.data.name"
						:showOutline="false"
						:getProgress="course.data.membership ? true : false"
					/>
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
import { BookText, CreditCard, GraduationCap } from 'lucide-vue-next'
import { computed, inject } from 'vue'
import { Badge, Button, call, createResource, toast } from 'frappe-ui'
import { useRouter } from 'vue-router'
import CertificationLinks from '@/components/CertificationLinks.vue'
import { useTelemetry } from 'frappe-ui/frappe'
import CourseOutline from '@/components/CourseOutline.vue'

const router = useRouter()
const user = inject('$user')
const readOnlyMode = window.read_only_mode
const { capture } = useTelemetry()

const props = defineProps({
	course: {
		type: Object,
		default: null,
	},
	hideVideo: {
		type: Boolean,
		default: false,
	},
})

const video_link = computed(() => {
	if (props.course.data.video_link) {
		return 'https://www.youtube.com/embed/' + props.course.data.video_link
	}
	return null
})

function enrollStudent() {
	if (!user.data) {
		toast.warning(__('You need to login first to enroll for this course'))
		setTimeout(() => {
			window.location.href = `/login?redirect-to=${window.location.pathname}`
		}, 500)
	} else {
		call('frappe.client.insert', {
			doc: {
				doctype: 'LMS Enrollment',
				course: props.course.data.name,
				member: user.data.name,
			},
		})
			.then(() => {
				capture('enrolled_in_course', {
					course: props.course.data.name,
				})
				toast.success(__('You have been enrolled in this course'))
				setTimeout(() => {
					router.push({
						name: 'Lesson',
						params: {
							courseName: props.course.data.name,
							chapterNumber: 1,
							lessonNumber: 1,
						},
					})
				}, 1000)
			})
			.catch((err) => {
				toast.warning(__(err.messages?.[0] || err))
				console.error(err)
			})
	}
}

const is_instructor = () => {
	let user_is_instructor = false
	props.course.data.instructors.forEach((instructor) => {
		if (!user_is_instructor && instructor.name == user.data?.name) {
			user_is_instructor = true
		}
	})
	return user_is_instructor
}

const canGetCertificate = computed(() => {
	if (
		props.course.data?.enable_certification &&
		props.course.data?.membership?.progress == 100
	) {
		return true
	}
	return false
})

const certificate = createResource({
	url: 'lms.lms.doctype.lms_certificate.lms_certificate.create_certificate',
	makeParams(values) {
		return {
			course: values.course,
		}
	},
	onSuccess(data) {
		window.open(
			`/api/method/frappe.utils.print_format.download_pdf?doctype=LMS+Certificate&name=${data.name}&format=${encodeURIComponent(data.template)}`,
			'_blank',
		)
	},
})

const fetchCertificate = () => {
	certificate.submit({
		course: props.course.data?.name,
		member: user.data?.name,
	})
}

const isAdmin = computed(() => {
	return user.data?.is_moderator || is_instructor()
})
</script>
