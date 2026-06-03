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
import { getVideoEmbedURL } from '@/utils'

const router = useRouter()
const user = inject<SessionUser>('$user')!
const readOnlyMode = (window as Window & { read_only_mode?: boolean })
	.read_only_mode
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
		return getVideoEmbedURL(props.course.data.video_link)
	}
	return null
})

function enrollStudent() {
	if (!user.data) {
		toast.warning(__('You need to login first to enroll for this course'))
		setTimeout(() => {
			window.location.href = `/login?redirect-to=${window.location.pathname}`
		}, 500)
		return
	}
	const courseName = props.course.data?.name
	if (!courseName) return
	call('frappe.client.insert', {
		doc: {
			doctype: 'LMS Enrollment',
			course: courseName,
			member: user.data.name,
		},
	})
		.then(() => {
			capture('enrolled_in_course', { course: courseName })
			toast.success(__('You have been enrolled in this course'))
			setTimeout(() => {
				router.push({
					name: 'Lesson',
					params: {
						courseName,
						chapterNumber: 1,
						lessonNumber: 1,
					},
				})
			}, 1000)
		})
		.catch((err: { messages?: string[] } | string) => {
			const msg = typeof err === 'string' ? err : err.messages?.[0] ?? 'Error'
			toast.warning(__(msg))
			console.error(err)
		})
}

const is_instructor = (): boolean => {
	let user_is_instructor = false
	props.course.data?.instructors.forEach((instructor: CourseInstructorInfo) => {
		if (!user_is_instructor && instructor.name == user.data?.name) {
			user_is_instructor = true
		}
	})
	return user_is_instructor
}

const priceLabel = computed<string>(() => {
	if (props.course.data?.paid_course) return props.course.data?.price || ''
	return __('Free')
})

const enrolledLabel = computed<string>(() => {
	const n = props.course.data?.enrollments ?? 0
	if (!n) return ''
	if (n < 50) return String(n)
	const tier = n < 1000 ? 50 : 100
	return `${Math.floor(n / tier) * tier}+`
})

const hasCourseStats = computed<boolean>(() =>
	Boolean(
		enrolledLabel.value ||
			props.course.data?.video_link ||
			props.course.data?.lessons ||
			(props.course.data?.quiz_count ?? 0) > 0 ||
			props.course.data?.enable_certification
	)
)

const canGetCertificate = computed<boolean>(() => {
	return Boolean(
		props.course.data?.enable_certification &&
			(props.course.data?.membership?.progress ?? 0) >= 100
	)
})

const certificate = createResource({
	url: 'lms.lms.doctype.lms_certificate.lms_certificate.create_certificate',
	makeParams(values: { course?: string }) {
		return {
			course: values.course,
		}
	},
	onSuccess(data: { name: string; template: string }) {
		window.open(
			`/api/method/frappe.utils.print_format.download_pdf?doctype=LMS+Certificate&name=${data.name}&format=${encodeURIComponent(data.template)}`,
			'_blank',
		)
	},
}) as Resource<{ name: string; template: string } | null>

const fetchCertificate = () => {
	certificate.submit({
		course: props.course.data?.name,
		member: user.data?.name,
	})
}

const isAdmin = computed(() => {
	return user.data?.is_moderator || user.data?.is_docente || is_instructor()
})
</script>
