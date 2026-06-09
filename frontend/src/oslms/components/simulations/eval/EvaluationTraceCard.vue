<template>
	<div class="border border-outline-gray-2 rounded-md">
		<div
			class="flex items-center gap-2 p-3 cursor-pointer hover:bg-surface-gray-1 rounded-md"
			@click="expanded = !expanded"
		>
			<ChevronDown
				class="size-4 stroke-1.5 text-ink-gray-5 transition-transform"
				:class="{ '-rotate-90': !expanded }"
			/>
			<div class="flex-1 text-sm font-medium text-ink-gray-9 truncate">
				{{ headline }}
			</div>
			<div class="text-sm font-semibold text-ink-gray-9 tabular-nums whitespace-nowrap">
				{{ traceAggregate === null ? '—' : Math.round(traceAggregate * 100) }}
			</div>
		</div>
		<div v-if="expanded" class="p-3 border-t border-outline-gray-2 space-y-3">
			<DimensionScoreBar
				v-for="dim in dims"
				:key="dim.dimension"
				:label="dimLabel(dim.dimension)"
				:score="dim.score"
			/>
			<details v-if="trace.transcript?.length" class="text-sm">
				<summary class="cursor-pointer text-ink-gray-7">
					{{ __('Vedi transcript completo') }}
				</summary>
				<div class="mt-2 space-y-2 max-h-72 overflow-y-auto">
					<div
						v-for="t in trace.transcript"
						:key="t.turn_index"
						class="text-xs"
					>
						<span class="font-medium text-ink-gray-9">
							[{{ t.turn_index }}] {{ t.role === 'user' ? 'STUDENTE' : 'CLIENTE' }}:
						</span>
						<span class="text-ink-gray-7 whitespace-pre-wrap">{{ t.text }}</span>
					</div>
				</div>
			</details>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import DimensionScoreBar from './DimensionScoreBar.vue'

const props = defineProps({
	trace: { type: Object, required: true },
})

const expanded = ref(false)
const dims = computed(() => props.trace.dimension_scores || [])

const traceAggregate = computed(() => {
	const numeric = dims.value
		.map((d) => d.score)
		.filter((s) => s !== null && s !== undefined)
	if (!numeric.length) return null
	return numeric.reduce((acc, x) => acc + x, 0) / numeric.length
})

const headline = computed(() => {
	const kind = props.trace.trace_kind
	if (kind === 'llm_student') {
		return `${__('LLM-student')} · ${props.trace.student_profile || ''}`
	}
	return `${__('Sessione reale')} · ${props.trace.source_session || ''}`
})

const DIM_LABELS = {
	persona: __('Persona consistency'),
	coverage: __('Coverage obiettivi'),
	debrief: __('Accuratezza debrief'),
	difficulty: __('Calibrazione difficoltà'),
}
function dimLabel(d) {
	return DIM_LABELS[d] || d
}
</script>
