<template>
	<div class="flex items-center gap-3">
		<div class="w-44 shrink-0 text-sm text-ink-gray-9">{{ label }}</div>
		<div class="flex-1 h-2 bg-surface-gray-2 rounded-full overflow-hidden">
			<div
				v-if="score !== null && score !== undefined"
				class="h-full transition-all"
				:class="barClass"
				:style="{ width: `${pct}%` }"
			/>
		</div>
		<div class="w-20 text-right text-sm font-semibold tabular-nums" :class="textClass">
			<template v-if="score === null || score === undefined">—</template>
			<template v-else>{{ Math.round(score * 100) }}</template>
		</div>
	</div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
	label: { type: String, required: true },
	score: { type: [Number, null], default: null },
})

const pct = computed(() =>
	props.score === null || props.score === undefined
		? 0
		: Math.max(0, Math.min(100, props.score * 100)),
)

const tier = computed(() => {
	if (props.score === null || props.score === undefined) return 'na'
	if (props.score >= 0.8) return 'good'
	if (props.score >= 0.6) return 'warn'
	return 'bad'
})

const barClass = computed(() => ({
	good: 'bg-surface-green-3',
	warn: 'bg-surface-amber-3',
	bad: 'bg-surface-red-3',
	na: 'bg-surface-gray-3',
}[tier.value]))

const textClass = computed(() => ({
	good: 'text-ink-green-7',
	warn: 'text-ink-amber-7',
	bad: 'text-ink-red-7',
	na: 'text-ink-gray-5',
}[tier.value]))
</script>
