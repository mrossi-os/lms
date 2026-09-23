<template>
	<div class="border rounded-lg p-3 space-y-2 card">
		<!-- OSLMS-CUSTOM: "card" class on the root is the elite theme card style hook -->
		<div class="text-ink-gray-5">
			{{ __(title) }}
		</div>
		<div class="flex items-center gap-x-2">
			<slot name="prefix" />
			<div class="text-ink-gray-9 text-3xl-semibold">
				{{ value }}
			</div>
			<slot name="suffix" />
		</div>
	</div>
</template>
<script setup lang="ts">
const props = defineProps<{
	title: string
	value: number | string
}>()
</script>
