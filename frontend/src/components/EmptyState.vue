<template>
	<div class="flex flex-col items-center justify-center mt-60">
		<GraduationCap class="size-10 mx-auto stroke-1 text-ink-gray-5" />
		<div class="text-lg font-semibold text-ink-gray-7 mb-2.5">
			{{ title }}
		</div>
		<div
			v-if="description"
			class="text-p-base w-full md:w-2/5 text-center text-ink-gray-7"
		>
			{{ description }}
		</div>
	</div>
</template>
<script setup lang="ts">
import { GraduationCap } from 'lucide-vue-next'

defineProps({
	title: { type: String, required: true },
	description: { type: String, default: '' },
})
</script>
