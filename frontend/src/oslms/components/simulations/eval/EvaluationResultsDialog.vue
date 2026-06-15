<template>
	<Dialog
		v-model="visible"
		:options="{ title: __('Valutazione scenario'), size: '4xl' }"
	>
		<template #body-content>
			<div v-if="loading" class="text-sm text-ink-gray-5 py-8 text-center">
				{{ __('Caricamento risultati…') }}
			</div>
			<div v-else-if="result" class="space-y-4">
				<div class="flex items-center justify-between text-xs text-ink-gray-5">
					<span>
						{{ __('Mode') }}: <strong>{{ result.run_mode }}</strong>
					</span>
					<span>{{ __('Avviato') }}: {{ result.triggered_at }}</span>
					<Badge
						:label="statusLabel(result.status)"
						:theme="statusTheme(result.status)"
					/>
				</div>

				<div v-if="result.error_message" class="text-sm text-ink-red-5">
					{{ result.error_message }}
				</div>

				<section>
					<div class="text-sm font-semibold text-ink-gray-9 mb-2">
						{{ __('Aggregate scores') }}
					</div>
					<div class="space-y-2">
						<DimensionScoreBar
							:label="__('Persona consistency')"
							:score="result.aggregate_persona_score"
						/>
						<DimensionScoreBar
							:label="__('Coverage obiettivi')"
							:score="result.aggregate_coverage_score"
						/>
						<DimensionScoreBar
							:label="__('Accuratezza debrief')"
							:score="result.aggregate_debrief_score"
						/>
						<DimensionScoreBar
							:label="__('Calibrazione difficoltà')"
							:score="result.aggregate_difficulty_score"
						/>
					</div>
				</section>

				<section>
					<div class="text-sm font-semibold text-ink-gray-9 mb-2">
						{{ __('Traces') }} ({{ result.traces?.length || 0 }})
					</div>
					<div class="space-y-2">
						<EvaluationTraceCard
							v-for="(trace, i) in result.traces || []"
							:key="i"
							:trace="trace"
						/>
					</div>
				</section>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Badge, Dialog } from 'frappe-ui'
import DimensionScoreBar from './DimensionScoreBar.vue'
import EvaluationTraceCard from './EvaluationTraceCard.vue'
import { useEvaluation } from '@/oslms/composables/useEvaluation'

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	evalId: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue'])

const visible = computed({
	get: () => props.modelValue,
	set: (v) => emit('update:modelValue', v),
})

const { loadResult } = useEvaluation()
const result = ref(null)
const loading = ref(false)

watch(
	() => [visible.value, props.evalId],
	async ([open, id]) => {
		if (!open || !id) return
		loading.value = true
		try {
			result.value = await loadResult(id)
		} finally {
			loading.value = false
		}
	},
	{ immediate: true },
)

function statusLabel(s) {
	return {
		queued: __('In coda'),
		running: __('In esecuzione'),
		complete: __('Completata'),
		failed: __('Fallita'),
	}[s] || s
}
function statusTheme(s) {
	return { queued: 'gray', running: 'blue', complete: 'green', failed: 'red' }[s] || 'gray'
}
</script>
