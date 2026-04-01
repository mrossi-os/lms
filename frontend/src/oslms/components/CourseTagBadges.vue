<template>
	<div v-if="tagObjects.length" class="flex items-center flex-wrap gap-1.5">
		<span
			v-for="tag in tagObjects"
			:key="tag.tag_name"
			class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold text-white leading-4"
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
