<template>
	<!-- OSLMS-CUSTOM: push the card down when the video is hidden (hero shows it).
	Hide the whole card when it would be empty — on mobile the outline and the
	"Continue Learning" CTA are moved out (hideOutline/hideContinueCta), which can
	leave nothing to show (see hasCardContent). -->
	<div
		v-if="hasCardContent"
		class="border-2 rounded-md w-full md:min-w-80 max-w-sm card !p-0"
		:class="{ 'md:mt-16': hideVideo }"
	>
		<!-- OSLMS-CUSTOM: hide the preview video when a hero banner already shows it -->
		<iframe
			v-if="course.data?.video_link && !hideVideo"
			:src="video_link"
			class="rounded-t-md min-h-56 w-full"
		/>
		<div class="p-5">
			<!-- <div class="text-2xl font-semibold text-ink-gray-9 mb-4">
				{{ priceLabel }}
			</div> -->
			<div v-if="!readOnlyMode">
				<div v-if="course.data?.membership" class="space-y-2 mb-8">
					<router-link
						v-if="!hideContinueCta"
						:to="{
							name: 'Lesson',
							params: {
								courseName: course.data?.name,
								chapterNumber: course?.data?.current_lesson
									? course?.data?.current_lesson.split('-')[0]
									: 1,
								lessonNumber: course?.data?.current_lesson
									? course?.data?.current_lesson.split('-')[1]
									: 1,
							},
						}"
					>
						<Button variant="solid" size="md" class="w-full">
							<template #prefix>
								<span class="lucide-book-text size-4" />
							</template>
							<span>
								{{ __('Continue Learning') }}
							</span>
						</Button>
					</router-link>
					<CertificationLinks :courseName="course.data.name" class="w-full" />
				</div>
				<router-link
					v-else-if="course.data?.paid_course && canEnroll"
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
							<span class="lucide-credit-card size-4" />
						</template>
						<span>
							{{ __('Buy this course') }}
						</span>
					</Button>
				</router-link>
				<Badge
					v-else-if="course.data?.disable_self_learning && canEnroll"
					theme="blue"
					size="lg"
					class="mb-4"
				>
					{{ __('Contact the Administrator to enroll for this course') }}
				</Badge>
				<Button
					v-else-if="canEnroll"
					@click="enrollStudent()"
					variant="solid"
					class="w-full mb-8"
					size="md"
				>
					<template #prefix>
						<span class="lucide-book-text size-4" />
					</template>
					<span>
						{{ __('Enroll Now') }}
					</span>
				</Button>
				<Button
					v-if="canGetCertificate"
					@click="fetchCertificate()"
					:loading="opening"
					variant="subtle"
					class="w-full mt-2"
					size="md"
				>
					<template #prefix>
						<span class="lucide-graduation-cap size-4" />
					</template>
					{{ __('Get Certificate') }}
				</Button>
			</div>
			<!-- OSLMS-CUSTOM: navigable course outline (replaces the stats block below).
			On mobile it is hidden here and re-rendered at the page bottom (see
			CourseOverview), so pass `hideOutline` from the mobile mount. -->
			<div v-if="!hideOutline" :class="readOnlyMode ? 'mt-4' : 'mt-0'">
				<CourseOutline
					:title="__('Course Outline')"
					:courseName="course.data?.name ?? ''"
					:showOutline="false"
					:getProgress="course.data?.membership ? true : false"
				/>
			</div>
			<!--
				OSLMS-CUSTOM: "This course includes" stats block disabled in favour of the
				CourseOutline above. Kept here for easy restore.
			<section v-if="hasCourseStats" class="space-y-3">
				<div class="text-base text-ink-gray-9 mb-1">
					{{ __('This course includes:') }}
				</div>
				<div
					v-if="enrolledLabel"
					class="flex items-center gap-3 text-ink-gray-8"
				>
					<span class="lucide-users size-4 shrink-0 text-ink-gray-7" />
					<span>{{ enrolledLabel }} {{ __('enrolled') }}</span>
				</div>
				<div
					v-if="course.data?.video_link"
					class="flex items-center gap-3 text-ink-gray-8"
				>
					<span class="lucide-monitor-play size-4 shrink-0 text-ink-gray-7" />
					<span>{{ __('On demand course video') }}</span>
				</div>
				<div
					v-if="course.data?.lessons"
					class="flex items-center gap-3 text-ink-gray-8"
				>
					<span class="lucide-book-open size-4 shrink-0 text-ink-gray-7" />
					<span>
						{{ course.data?.lessons }}
						{{ course.data?.lessons === 1 ? __('Lesson') : __('Lessons') }}
					</span>
				</div>
				<div
					v-if="(course.data?.quiz_count || 0) > 0"
					class="flex items-center gap-3 text-ink-gray-8"
				>
					<span class="lucide-help-circle size-4 shrink-0 text-ink-gray-7" />
					<span>
						{{ course.data?.quiz_count }}
						{{
							course.data?.quiz_count === 1
								? __('Quiz topic')
								: __('Quiz topics')
						}}
					</span>
				</div>
				<div
					v-if="course.data?.enable_certification"
					class="flex items-center gap-3 text-ink-gray-8"
				>
					<span class="lucide-award size-4 shrink-0 text-ink-gray-7" />
					<span>{{ __('Certificate of completion') }}</span>
				</div>
			</section>
			-->
		</div>
	</div>
</template>
<script setup lang="ts">
import { BookText, CreditCard, GraduationCap } from 'lucide-vue-next'
// OSLMS-CUSTOM: Award, BookOpen, HelpCircle, MonitorPlay, Users were used by the
// disabled "This course includes" stats block — restore them with that block.
import { computed, inject, watch } from 'vue'
import { Badge, Button, call, createResource, toast } from 'frappe-ui'
import { useRouter } from 'vue-router'
import CertificationLinks from '@/components/CertificationLinks.vue'
import CourseOutline from '@/components/CourseOutline.vue'
// OSLMS-CUSTOM: route certificate opening through TrueSkills when enabled.
import { useCertificateViewer } from '@/oslms/composables/useCertificateViewer'
import { getVideoEmbedURL } from '@/utils/'
import { useTelemetry } from 'frappe-ui/frappe'
import type {
	CertificationInfo,
	CourseDetails,
	CourseInstructorInfo,
	Resource,
	SessionUser,
} from '@/types/api'

const router = useRouter()
const user = inject<SessionUser>('$user')!
const readOnlyMode = (window as Window & { read_only_mode?: boolean })
	.read_only_mode
const { capture } = useTelemetry()

const props = withDefaults(
	defineProps<{
		course: Resource<CourseDetails | null>
		// OSLMS-CUSTOM: suppress the preview video iframe (e.g. when a hero shows it)
		hideVideo?: boolean
		// OSLMS-CUSTOM: suppress the embedded course outline (moved to the page
		// bottom on mobile — see CourseOverview).
		hideOutline?: boolean
		// OSLMS-CUSTOM: suppress the "Continue Learning" button (replaced by a fixed
		// bottom bar on mobile — see CourseOverview).
		hideContinueCta?: boolean
	}>(),
	{ hideVideo: false, hideOutline: false, hideContinueCta: false },
)

const video_link = computed<string | undefined>(() => {
	const link = props.course.data?.video_link
	// Supports YouTube and Vimeo (and legacy bare YouTube ids).
	return link ? getVideoEmbedURL(link) : undefined
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
			const msg = typeof err === 'string' ? err : (err.messages?.[0] ?? 'Error')
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

/* OSLMS-CUSTOM: computeds for the disabled "This course includes" stats block.
   Restore together with the stats <section> in the template.
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
*/

// OSLMS-CUSTOM: once the certificate has been issued we only want to show
// CertificationLinks' "View Certificate", not a second "Get Certificate" button.
// LMS Enrollment.certificate is not set on issuance, so query the authoritative
// LMS Certificate via get_certification_details (same signal CertificationLinks uses).
const certification = createResource({
	url: 'lms.lms.api.get_certification_details',
	makeParams() {
		return { course: props.course.data?.name }
	},
}) as Resource<CertificationInfo | null>

watch(
	() => props.course.data?.name,
	(name) => {
		if (name && user.data) certification.reload()
	},
	{ immediate: true },
)

const canGetCertificate = computed<boolean>(() => {
	// TrueSkills issuance is exclusive with the internal completion certificate,
	// so a TrueSkills-only course has enable_certification off — gate on either.
	return Boolean(
		(props.course.data?.enable_certification ||
			props.course.data?.trueskills_certificate_enabled) &&
		(props.course.data?.membership?.progress ?? 0) >= 100 &&
		// Hide once the certificate exists (CertificationLinks shows "View
		// Certificate"). Wait for the resource to load to avoid a flash.
		certification.data &&
		!certification.data.certificate,
	)
})

// OSLMS-CUSTOM: for TrueSkills-enabled courses the completion certificate is the
// TrueSkills openbadge image (opened inline), not the internal Print Format PDF.
// useCertificateViewer ensures the LMS Certificate exists and picks the artifact.
const { opening, openCourseCertificate } = useCertificateViewer()

const fetchCertificate = () => {
	openCourseCertificate(props.course.data?.name)
}

const isAdmin = computed<boolean>(() => {
	return (
		Boolean(user.data?.is_moderator) ||
		Boolean(user.data?.is_docente) ||
		is_instructor()
	)
})

// OSLMS-CUSTOM: a "Valutatore" of a batch holding this course reviews it read-only
// and is never a student (the session forces is_student = false). They reach the
// lessons without an enrolment, so offering them an enrolment CTA is a trap: one
// click creates a real LMS Enrollment and lists them among the course students.
const isValutatore = computed<boolean>(() =>
	Boolean(props.course.data?.is_valutatore),
)

// Only a prospective student is offered an enrol / buy / contact-the-admin CTA.
// Enrolled members never reach these branches (the template checks `membership`
// first), so a valutatore who is also enrolled keeps the full student view.
const canEnroll = computed<boolean>(() => !isAdmin.value && !isValutatore.value)

// OSLMS-CUSTOM: mirrors CertificationLinks' own visibility (using the same
// certification resource), so the card can tell whether that child will render
// anything before deciding to hide itself.
const certLinksVisible = computed<boolean>(() => {
	const d = certification.data
	if (!d) return false
	if (d.certificate) return true
	if (d.membership && d.paid_certificate && user.data?.is_student) {
		return !d.membership.purchased_certificate || !d.membership.certificate
	}
	return false
})

// OSLMS-CUSTOM: whether the card has anything worth a border. On mobile the outline
// and Continue CTA are moved out (hideOutline/hideContinueCta), which can leave the
// card empty — hide it in that case rather than render an empty box.
const hasCardContent = computed<boolean>(() => {
	// Non-stripped mounts (desktop sidebar / 640–767 inline) always show the outline.
	if (!props.hideOutline) return true
	// Preview video.
	if (props.course.data?.video_link && !props.hideVideo) return true
	// Enrolled member: certificate actions (issue, or view/get-certified).
	if (props.course.data?.membership) {
		return canGetCertificate.value || certLinksVisible.value
	}
	// Non-member student: an enroll/buy/contact CTA always renders. Admins and
	// valutatori get no CTA, so for them the stripped card would be empty.
	return canEnroll.value
})
</script>
