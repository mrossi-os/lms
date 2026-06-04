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
				inlineCreatePlaceholder="Category name"
				:onCreate="createCategory"
				variant="outline"
				@update:modelValue="markDirty()"
			/>
			<CourseInstructorsField />
			<div class="space-y-1.5">
				<TagPicker
					v-model="doc.tags"
					@dirty="markDirty()"
							/>
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
		<CourseThumbnailField />
	</section>
</template>

<script setup lang="ts">
import TagPicker from '@/oslms/components/TagPicker.vue'
import { FormControl } from 'frappe-ui'
import { computed, inject, ref } from 'vue'
import { createLMSCategory } from '@/utils'
import Link from '@/components/Controls/Link.vue'
import CourseInstructorsField from '@/pages/Courses/CourseInstructorsField.vue'
import CourseThumbnailField from '@/pages/Courses/CourseThumbnailField.vue'
import type { CourseFormContext } from '@/types/api'

interface TagOption {
	label: string
	value: string
}

const { resource, markDirty } = inject<CourseFormContext>('courseForm')!

const doc = computed(() => resource.doc)

const parsedTags = computed<string[]>(() => {
	const tags = resource.doc?.tags
	return tags ? tags.split(', ').filter(Boolean) : []
})

const tagsArray = computed<string[]>({
	get: () => parsedTags.value,
	set: (vals: string[]) => {
		if (!resource.doc) return
		resource.doc.tags = vals.join(', ')
		markDirty()
	},
})

const tagQuery = ref<string>('')
const tagOptions = computed<TagOption[]>(() => {
	const selected: TagOption[] = parsedTags.value.map((t) => ({
		label: t,
		value: t,
	}))
	const q = tagQuery.value.trim()
	if (q && !parsedTags.value.includes(q)) {
		return [...selected, { label: `${__('Create')} "${q}"`, value: q }]
	}
	return selected
})

const tagsSelectedLabels = computed<string>(() => tagsArray.value.join(', '))

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
