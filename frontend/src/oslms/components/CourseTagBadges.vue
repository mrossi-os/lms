<template>
	<div
		v-if="tagObjects.length"
		class="flex items-center flex-wrap"
		:class="size === 'xs' ? 'gap-1' : 'gap-3'"
	>
		<span
			v-for="tag in tagObjects"
			:key="tag.tag_name"
			class="inline-flex items-center rounded-full font-semibold text-ink-gray-9 leading-4"
			:class="
				size === 'xs'
					? 'px-1.5 py-0.5 text-[10px]'
					: 'px-2 py-1 text-sm'
			"
			:style="{ backgroundColor: tag.color }"
		>
			{{ tag.tag_name }}
		</span>
	</div>
</template>

<script setup>
import { computed, inject } from 'vue'

const props = defineProps({
	tags: {
		type: String,
		default: '',
	},
	size: {
		type: String,
		default: 'md',
	},
})

const tagColorMap = inject('tagColorMap', null)

const tagNames = computed(() => {
	if (!props.tags) return []
	return props.tags
		.split(', ')
		.map((t) => t.trim())
		.filter(Boolean)
})

const tagObjects = computed(() => {
	if (!tagNames.value.length || !tagColorMap?.value) return []
	return tagNames.value
		.map((name) => ({
			tag_name: name,
			color: tagColorMap.value.get(name) || '#6B7280',
		}))
		.filter(Boolean)
})
</script>
