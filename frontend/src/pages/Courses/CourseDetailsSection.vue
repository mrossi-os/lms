<template>
	<section v-if="doc" class="space-y-5">
		<div class="text-base font-semibold text-ink-gray-9">
			{{ __('Course details') }}
		</div>
		<div class="grid grid-cols-2 gap-5">
			<FormControl
				v-model="doc.title"
				:label="__('Title')"
				:required="true"
				variant="outline"
				@input="markDirty()"
			/>
			<Link
				v-model="doc.category"
				doctype="LMS Category"
				:label="__('Category')"
				:placeholder="__('Select category')"
				:inlineCreate="true"
				:inlineCreatePlaceholder="__('Category name')"
				:onCreate="createCategory"
				variant="outline"
				@update:modelValue="markDirty()"
			/>
			<CourseInstructorsField />
			<div class="space-y-1.5">
				<TagPicker v-model="doc.tags" @dirty="markDirty()" />
			</div>
			<FormControl
				v-model="doc.short_introduction"
				type="textarea"
				:rows="3"
				:label="__('Short description')"
				:placeholder="__('Type something')"
				:required="true"
				variant="outline"
				class="col-span-2"
				@change="markDirty()"
			/>
		</div>
		<div class="grid gap-5 grid-cols-1 xl:grid-cols-2">
			<CourseThumbnailField />
			<VideoPreviewField
				:modelValue="doc.video_link"
				:label="__('Preview video')"
				@update:modelValue="setVideoLink"
			/>
		</div>
	</section>
</template>

<script setup lang="ts">
import TagPicker from '@/oslms/components/TagPicker.vue'
import { FormControl } from 'frappe-ui'
import { computed, inject } from 'vue'
import { createLMSCategory } from '@/utils'
import Link from '@/oslms/components/Controls/Link.vue'
import CourseInstructorsField from '@/pages/Courses/CourseInstructorsField.vue'
import CourseThumbnailField from '@/pages/Courses/CourseThumbnailField.vue'
import VideoPreviewField from '@/components/Controls/VideoPreviewField.vue'
import type { CourseFormContext } from '@/types/api'

const { resource, markDirty } = inject<CourseFormContext>('courseForm')!

const doc = computed(() => resource.doc)

function setVideoLink(value: string) {
	if (!resource.doc) return
	resource.doc.video_link = value
	markDirty()
}

function createCategory(name: string | null, done?: () => void) {
	if (!name) return
	createLMSCategory(name).then((categoryName: string | undefined) => {
		if (!categoryName || !resource.doc) return
		resource.doc.category = categoryName
		done?.()
		markDirty()
	})
}
</script>
