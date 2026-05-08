<template>
	<div class="w-[90%] lg:w-[75%] mx-auto mt-5">
		<div class="flex items-center justify-between mb-5">
			<div class="text-ink-gray-9 font-semibold text-lg">
				{{ __('Announcements') }}
			</div>
			<Button
				v-if="canMakeAnnouncement"
				variant="solid"
				@click="showAnnouncementModal = true"
			>
				<template #prefix>
					<Plus class="w-4 h-4" />
				</template>
				{{ __('Make an Announcement') }}
			</Button>
		</div>
		<div v-if="announcements.length">
			<div v-for="comm in announcements">
				<div class="mb-8">
					<div class="flex items-center justify-between mb-2">
						<div class="flex items-center">
							<Avatar :label="comm.sender_full_name" size="lg" />
							<div class="ms-2 text-ink-gray-7">
								{{ comm.sender_full_name }}
							</div>
						</div>

						<div class="text-sm text-white">
							{{ timeAgo(comm.communication_date) }}
						</div>
					</div>
					<div class="ml-3 font-bold text-white prose">
						{{ comm.subject }}
					</div>
					<div
						class="prose prose-sm bg-surface-menu-bar !min-w-full px-4 py-2 rounded-md"
						v-html="comm.content"
					></div>
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
import { createResource, Avatar, Button } from 'frappe-ui'
import { Plus, ChevronLeft, ChevronRight } from 'lucide-vue-next'
import { computed, inject, ref, watch } from 'vue'
import { timeAgo } from '@/utils'
import AnnouncementModal from '@/pages/Batches/components/AnnouncementModal.vue'

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
</script>
<style>
.prose-sm p {
	margin: 0 0 0.5rem;
}
</style>
