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
			<!-- Per-dimension accordion: header is always visible (name + score
			     bar), body holds summary + evidence quotes + warnings + extras. -->
			<div
				v-for="dim in dims"
				:key="dim.dimension"
				class="border border-outline-gray-2 rounded-md"
			>
				<div
					class="flex items-center gap-2 p-3 cursor-pointer hover:bg-surface-gray-1 rounded-md"
					@click="toggleDim(dim.dimension)"
				>
					<ChevronDown
						class="size-4 stroke-1.5 text-ink-gray-5 transition-transform shrink-0"
						:class="{ '-rotate-90': !expandedDims[dim.dimension] }"
					/>
					<div class="flex-1 min-w-0">
						<DimensionScoreBar
							:label="dimLabel(dim.dimension)"
							:score="dim.score"
						/>
					</div>
				</div>
				<div
					v-if="expandedDims[dim.dimension]"
					class="px-3 pb-3 pt-0 space-y-3 border-t border-outline-gray-2"
				>
					<!-- Summary -->
					<div v-if="dim.summary" class="text-sm text-ink-gray-7 whitespace-pre-wrap pt-3">
						{{ dim.summary }}
					</div>

					<!-- Evidence quotes -->
					<div v-if="dim.evidence_quotes?.length" class="space-y-2">
						<div class="text-xs font-medium uppercase tracking-wide text-ink-gray-5">
							{{ __('Evidence') }}
						</div>
						<ul class="space-y-2">
							<li
								v-for="(q, i) in dim.evidence_quotes"
								:key="i"
								class="text-xs border-l-2 border-outline-gray-2 pl-2"
							>
								<div class="text-ink-gray-9">
									<span
										v-if="q.turn_index !== undefined && q.turn_index !== null"
										class="font-semibold mr-1"
									>
										[turn {{ q.turn_index }}]
									</span>
									<span class="italic">"{{ q.quote }}"</span>
								</div>
								<div v-if="q.comment" class="text-ink-gray-5 mt-1">
									{{ q.comment }}
								</div>
							</li>
						</ul>
					</div>

					<!-- Warnings -->
					<div v-if="dim.warnings?.length" class="space-y-1">
						<div class="text-xs font-medium uppercase tracking-wide text-ink-orange-5">
							{{ __('Warnings') }}
						</div>
						<ul class="text-xs text-ink-orange-5 list-disc list-inside space-y-1">
							<li v-for="(w, i) in dim.warnings" :key="i">{{ w }}</li>
						</ul>
					</div>

					<!-- Extras (dimension-specific) -->
					<div v-if="hasExtras(dim)" class="space-y-2">
						<div class="text-xs font-medium uppercase tracking-wide text-ink-gray-5">
							{{ __('Dettagli') }}
						</div>

						<!-- coverage.by_objective -->
						<ul
							v-if="dim.extras?.by_objective?.length"
							class="space-y-2"
						>
							<li
								v-for="(o, i) in dim.extras.by_objective"
								:key="i"
								class="text-xs border border-outline-gray-2 rounded p-2"
							>
								<div class="flex items-start justify-between gap-2">
									<div class="font-medium text-ink-gray-9 flex-1">
										{{ o.objective }}
									</div>
									<div class="flex items-center gap-2 shrink-0">
										<span
											:class="o.covered ? 'text-ink-green-6' : 'text-ink-orange-5'"
										>
											{{ o.covered ? __('coperto') : __('non coperto') }}
										</span>
										<span
											v-if="o.score !== undefined && o.score !== null"
											class="tabular-nums text-ink-gray-7"
										>
											{{ o.score }}
										</span>
									</div>
								</div>
								<div v-if="o.reason" class="text-ink-gray-5 mt-1">{{ o.reason }}</div>
							</li>
						</ul>

						<!-- difficulty extras -->
						<div
							v-if="dim.dimension === 'difficulty'"
							class="text-xs text-ink-gray-7 space-y-1"
						>
							<div v-if="dim.extras?.expected_difficulty">
								<span class="text-ink-gray-5">{{ __('Difficoltà attesa') }}:</span>
								{{ dim.extras.expected_difficulty }}
							</div>
							<div v-if="dim.extras?.perceived_difficulty">
								<span class="text-ink-gray-5">{{ __('Difficoltà percepita') }}:</span>
								{{ dim.extras.perceived_difficulty }}
							</div>
							<div
								v-if="dim.extras?.calibration_offset !== undefined &&
								      dim.extras?.calibration_offset !== null"
							>
								<span class="text-ink-gray-5">{{ __('Offset di calibrazione') }}:</span>
								{{ dim.extras.calibration_offset }}
							</div>
						</div>

						<!-- debrief extras -->
						<template v-if="dim.dimension === 'debrief'">
							<div
								v-if="dim.extras?.hallucinated_quotes?.length"
								class="text-xs space-y-1"
							>
								<div class="text-ink-gray-5">{{ __('Citazioni allucinate') }}:</div>
								<ul class="list-disc list-inside text-ink-red-5">
									<li v-for="(h, i) in dim.extras.hallucinated_quotes" :key="i">{{ h }}</li>
								</ul>
							</div>
							<div
								v-if="dim.extras?.score_inconsistencies?.length"
								class="text-xs space-y-1"
							>
								<div class="text-ink-gray-5">{{ __('Incoerenze di score') }}:</div>
								<ul class="space-y-1">
									<li
										v-for="(s, i) in dim.extras.score_inconsistencies"
										:key="i"
										class="border-l-2 border-outline-orange-3 pl-2"
									>
										<span class="font-medium">{{ s.criterion }}:</span> {{ s.issue }}
									</li>
								</ul>
							</div>
							<div
								v-if="dim.extras?.overall_consistency_delta !== null &&
								      dim.extras?.overall_consistency_delta !== undefined"
								class="text-xs text-ink-gray-7"
							>
								<span class="text-ink-gray-5">{{ __('Delta consistenza overall') }}:</span>
								{{ dim.extras.overall_consistency_delta }}
							</div>
						</template>
					</div>

					<!-- Empty state: skipped dimensions or no payload -->
					<div
						v-if="!dim.summary && !dim.evidence_quotes?.length &&
						      !dim.warnings?.length && !hasExtras(dim)"
						class="text-xs italic text-ink-gray-5"
					>
						{{ __('Nessun dettaglio disponibile.') }}
					</div>
				</div>
			</div>

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
							[{{ t.turn_index }}] {{ t.role === 'user' ? __('STUDENTE') : __('PERSONAGGIO') }}:
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
const expandedDims = ref({})

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

function toggleDim(d) {
	expandedDims.value[d] = !expandedDims.value[d]
}

// Whether a dimension carries any non-empty extras. Keeps the "Dettagli"
// section hidden when there's nothing to show (e.g. persona, which always
// emits extras={}).
function hasExtras(dim) {
	const e = dim.extras
	if (!e || typeof e !== 'object') return false
	if (Array.isArray(e.by_objective) && e.by_objective.length) return true
	if (Array.isArray(e.hallucinated_quotes) && e.hallucinated_quotes.length) return true
	if (Array.isArray(e.score_inconsistencies) && e.score_inconsistencies.length) return true
	if (e.expected_difficulty || e.perceived_difficulty) return true
	if (e.calibration_offset !== undefined && e.calibration_offset !== null) return true
	if (e.overall_consistency_delta !== undefined && e.overall_consistency_delta !== null) return true
	return false
}
</script>
