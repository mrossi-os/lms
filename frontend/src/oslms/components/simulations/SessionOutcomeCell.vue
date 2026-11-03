<template>
	<!-- The outcome a person decided and published, or "Da valutare" while a
	     simulation with an outcome waits for it. -->
	<Badge
		v-if="session.outcome"
		:label="session.outcome === 'Passed' ? __('Superata') : __('Non superata')"
		:theme="session.outcome === 'Passed' ? 'green' : 'red'"
	/>
	<Badge v-else-if="session.to_evaluate" :label="__('Da valutare')" theme="orange" />
	<span v-else class="text-ink-gray-5">—</span>
</template>

<script setup>
import { Badge } from 'frappe-ui'

defineProps({
	session: { type: Object, required: true },
})
</script>
