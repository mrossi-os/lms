<template>
	<div class="w-[90%] lg:w-[75%] mx-auto mt-5">
		<div class="text-ink-gray-9 text-xl-semibold mb-5">
			{{ __('Announcements') }}
		</div>
		<div v-if="announcements.length">
			<div v-for="(comm, idx) in announcements" :key="idx">
				<div class="mb-8">
					<div class="flex items-center justify-between mb-2">
						<div class="flex items-center">
							<Avatar :label="comm.sender_full_name" size="lg" />
							<div class="ms-2 text-ink-gray-7">
								{{ comm.sender_full_name }}
							</div>
						</div>

						<div class="text-sm text-ink-gray-9">
							{{ timeAgo(comm.communication_date) }}
						</div>
					</div>
					<div class="ml-3 font-bold text-ink-gray-9 prose">
						{{ comm.subject }}
					</div>
					<!-- Rich email/template HTML mirrors the email in an isolated
					     iframe; a plain notification keeps the app's themed card. -->
					<div
						v-if="isPlainNotification(comm.content)"
						class="prose prose-sm bg-surface-sidebar !min-w-full px-4 py-2 rounded-md"
						v-html="sanitizeRichHTML(comm.content)"
					></div>
					<AnnouncementContent v-else :content="comm.content" />
				</div>
			</div>
			<div
				v-if="totalPages > 1"
				class="flex items-center justify-between border-t pt-3 mt-2"
			>
				<div class="text-sm text-ink-gray-5">
					{{ __('Page {0} of {1}').format(currentPage, totalPages) }}
				</div>
				<div class="flex items-center space-x-2">
					<Button :disabled="currentPage <= 1" @click="currentPage--">
						<template #prefix>
							<ChevronLeft class="w-4 h-4" />
						</template>
						{{ __('Previous') }}
					</Button>
					<Button :disabled="currentPage >= totalPages" @click="currentPage++">
						<template #suffix>
							<ChevronRight class="w-4 h-4" />
						</template>
						{{ __('Next') }}
					</Button>
				</div>
			</div>
		</div>
		<div v-else class="text-ink-gray-7 leading-5">
			{{ __('No announcements have been made yet for this batch') }}
		</div>
		<AnnouncementModal
			v-if="showAnnouncementModal"
			v-model="showAnnouncementModal"
			:batch="props.batch.data.name"
			:students="props.batch.data.students"
		/>
	</div>
</template>
<script setup>
import { computed, inject, ref, watch } from 'vue'
import { sanitizeRichHTML } from '@/utils/sanitizeRichHTML'
import { createResource, Avatar } from 'frappe-ui'
import { timeAgo } from '@/utils'
import AnnouncementModal from '@/pages/Batches/components/AnnouncementModal.vue'
import AnnouncementContent from '@/pages/Batches/components/AnnouncementContent.vue'

const user = inject('$user')
const readOnlyMode = window.read_only_mode
const showAnnouncementModal = ref(false)
const currentPage = ref(1)
const pageSize = 10

const props = defineProps({
	batch: {
		type: Object,
		required: true,
	},
})

const canMakeAnnouncement = computed(() => {
	if (readOnlyMode) return false
	if (!props.batch.data?.students?.length) return false
	return user.data?.is_moderator || user.data?.is_evaluator
})

/*
 * Plain notification announcements (written in the editor, no email template)
 * have no document/layout/background markup, so they render on the app's themed
 * card. Richer email-template HTML is detected here and rendered in the isolated
 * iframe instead, mirroring the email the recipient receives.
 */
const isPlainNotification = (html) => {
	const s = String(html || '').trim()
	if (!s) return true
	if (
		/<(?:!doctype|html|head|body|style|table|center|tbody|td|tr)[\s>]/i.test(s)
	)
		return false
	if (/(?:background(?:-color)?|max-width|width)\s*:/i.test(s)) return false
	return true
}

const communications = createResource({
	url: 'lms.lms.api.get_announcements',
	makeParams() {
		return {
			batch: props.batch.data?.name,
			start: (currentPage.value - 1) * pageSize,
			page_length: pageSize,
		}
	},
	auto: true,
})

watch(currentPage, () => {
	communications.reload()
})

watch(
	() => showAnnouncementModal.value,
	(isOpen, wasOpen) => {
		if (wasOpen && !isOpen) {
			currentPage.value = 1
			communications.reload()
		}
	},
)

const announcements = computed(() => communications.data?.data || [])
const totalAnnouncements = computed(() => communications.data?.total || 0)
const totalPages = computed(() =>
	Math.max(1, Math.ceil(totalAnnouncements.value / pageSize)),
)

// Opened from the batch header's "Make Announcement" button via the tab's
// childRef (see BatchDetail).
const openAnnouncementModal = () => {
	showAnnouncementModal.value = true
}
defineExpose({ openAnnouncementModal })
</script>
<style>
.prose-sm p {
	margin: 0 0 0.5rem;
}

/*
 * Plain notification card sits on the dark theme, so map the editor's named
 * colors to the dark-mode shades (lighter) for readable contrast on the dark
 * background. Covers content stored as `color: var(--prose-color-<name>)`.
 */
.announcement-card {
	--prose-color-red: #e43838;
	--prose-color-blue: #3294e3;
	--prose-color-green: #1ba964;
	--prose-color-yellow: #c69c12;
	--prose-color-orange: #c45a0e;
	--prose-color-purple: #984bd8;
	--prose-color-pink: #cb4394;
	--prose-color-gray: #717171;
	--prose-color-teal: #219c8f;
	--prose-color-cyan: #2b8dab;
}
</style>
