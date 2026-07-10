<template>
	<section v-if="lesson">
		<!-- Lesson settings card (native disclosure), styled like the
		     instructor-notes card in LessonForm. -->
		<details class="lesson-settings rounded-lg border border-outline-gray-2">
			<summary
				class="flex w-full cursor-pointer items-center gap-2 px-4 py-3 text-start"
			>
				<Settings class="size-4 stroke-2 text-ink-gray-7" />
				<span class="text-p-base font-medium text-ink-gray-8">
					{{ __('Lesson Settings') }}
				</span>
				<ChevronRight
					class="lesson-settings-chevron ms-auto size-4 stroke-2 text-ink-gray-5"
				/>
			</summary>
			<div class="border-t border-outline-gray-2 px-4 py-3">
				<div class="grid grid-cols-1 md:grid-cols-2 gap-5">
					<Switch
						v-model="lesson.include_in_preview"
						:label="__('Include in Preview')"
						:description="
							__(
								'If enabled, the lesson will also be accessible to users who are not enrolled in the course.',
							)
						"
						class="card p-4"
						@update:modelValue="markDirty"
					/>
					<FormControl
						v-model="lesson.duration"
						:label="__('Duration (minutes)')"
						type="number"
						class="mb-4"
						autocomplete="off"
						:description="__('Estimated time to complete this lesson')"
						@input="markDirty"
					/>
				</div>
				<div class="card p-4 md:col-span-2 mt-2">
					<TagPicker v-model="lesson.tags" @dirty="markDirty" />
				</div>
				<div class="border-t mt-4">
					<LessonAIIngestion :lesson="lesson" />
				</div>
			</div>
		</details>
	</section>
</template>

<script setup lang="ts">
import { ChevronRight, Settings } from 'lucide-vue-next'

import LessonAIIngestion from '@/oslms/components/ai/Course/LessonAIIngestion.vue'
import TagPicker from '@/oslms/components/TagPicker.vue'

import { FormControl, Switch } from 'frappe-ui'

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

<style scoped>
/* Native <details> disclosure styled as a card, mirroring the instructor-notes
   card in LessonForm: drop the default marker triangle and drive the chevron
   rotation off the [open] state instead of a JS toggle. */
.lesson-settings > summary {
	list-style: none;
}
.lesson-settings > summary::-webkit-details-marker {
	display: none;
}
.lesson-settings-chevron {
	transition: transform 200ms;
}
.lesson-settings[open] .lesson-settings-chevron {
	transform: rotate(90deg);
}
[dir='rtl'] .lesson-settings:not([open]) .lesson-settings-chevron {
	transform: rotate(180deg);
}
</style>
