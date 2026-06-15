<template>
	<section v-if="lesson">
		<div class="mt-0">
			<div class="w-5/6 mx-auto">
				<div class="flex justify-between cursor-pointer" @click="
					() => {
						openSettingsEditor = !openSettingsEditor
					}
				">
					<label class="block font-medium text-ink-gray-5 mb-1">
						{{ __('Lesson Settings') }}
					</label>
					<ChevronRight class="stroke-2 h-5 w-5 text-ink-gray-5 transform duration-200" :class="{
						'rotate-90': openSettingsEditor,
						'rtl:rotate-180': !openSettingsEditor,
					}" />
				</div>
				<div v-show="openSettingsEditor"
					class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal py-3">
					<div class="grid grid-cols-1 md:grid-cols-2 gap-5 mx-auto">
						<Switch v-model="lesson.include_in_preview" :label="__('Include in Preview')" :description="__(
							'If enabled, the lesson will also be accessible to users who are not enrolled in the course.',
						)
							" class="card p-4" @update:modelValue="markDirty" />
						<FormControl v-model="lesson.duration" :label="__('Duration (minutes)')" type="number"
							class="mb-4" autocomplete="off" :description="__('Estimated time to complete this lesson')"
							@input="markDirty" />
					</div>
					<div class="card p-4 md:col-span-2 mt-2">
						<TagPicker v-model="lesson.tags" @dirty="markDirty"/>
					</div>
					<div class="border-t mt-4">
						<LessonAIIngestion :lesson="lesson" />
					</div>
				</div>
			</div>
		</div>
		<div class="border-t mt-4"></div>
	</section>
</template>

<script setup lang="ts">
import { ChevronRight } from 'lucide-vue-next'
import LessonAIIngestion from '@/oslms/components/ai/Course/LessonAIIngestion.vue'
import TagPicker from '@/oslms/components/TagPicker.vue'

import {
	FormControl,
	Switch,
} from 'frappe-ui'
import { ref } from 'vue'

export interface OsLessonData {
	title?: string
	include_in_preview?: boolean
	body?: string
	instructor_notes?: string
	content?: string
	instructor_content?: string
	tags: string
	[key: string]: unknown
}

const openSettingsEditor = ref(false)

const props = defineProps<{
	lesson: OsLessonData
}>()

const emit = defineEmits<{
	(e: 'dirty'): void
}>()

function markDirty(): void {
	emit('dirty')
}

defineExpose({ markDirty })
</script>
