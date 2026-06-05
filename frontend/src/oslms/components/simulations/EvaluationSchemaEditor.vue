<template>
	<form @submit.prevent="onSave" class="space-y-6">
		<div class="flex items-center justify-between">
			<h2 class="text-lg font-semibold text-ink-gray-9">
				{{ schemaName ? __('Modifica schema di valutazione') : __('Nuovo schema di valutazione') }}
			</h2>
			<Button variant="solid" :loading="saving" type="submit">
				{{ __('Salva') }}
			</Button>
		</div>

		<div class="grid grid-cols-2 gap-4">
			<FormControl v-model="model.schema_name" type="text" :label="__('Nome schema')" required />
			<FormControl
				v-model="model.scoring_scale"
				type="select"
				:options="['0-3', '0-5', '0-10']"
				:label="__('Scala')"
				required
			/>
			<FormControl
				v-model.number="model.passing_threshold"
				type="number"
				step="1"
				min="0"
				max="100"
				:label="__('Soglia di superamento (%)')"
			/>
			<FormControl
				v-model="model.is_shared"
				type="checkbox"
				:label="__('Condividi con altri docenti')"
			/>
		</div>

		<FormControl
			v-model="model.description"
			type="textarea"
			:rows="3"
			:label="__('Descrizione')"
		/>

		<!-- Criteria -->
		<div>
			<div class="flex items-center justify-between mb-2">
				<div>
					<div class="text-sm font-medium text-ink-gray-9">{{ __('Criteri') }}</div>
					<div
						class="text-xs"
						:class="weightSumOk ? 'text-ink-gray-5' : 'text-ink-red-5'"
					>
						{{ __('Somma pesi') }}: {{ weightSum.toFixed(2) }}
						<span v-if="!weightSumOk">— {{ __('deve essere 1.00') }}</span>
					</div>
				</div>
				<Button size="sm" variant="ghost" @click="addCriterion">+ {{ __('Aggiungi criterio') }}</Button>
			</div>
			<div class="space-y-2">
				<div
					v-for="(row, i) in model.criteria"
					:key="`crit-${i}`"
					class="border border-outline-gray-2 rounded-md p-3 space-y-2"
				>
					<div class="flex gap-2 items-start">
						<input
							v-model="row.criterion_name"
							type="text"
							class="flex-1 rounded-md border border-outline-gray-2 px-2 py-1 text-sm"
							:placeholder="__('Es. Ascolto attivo')"
						/>
						<input
							v-model.number="row.weight"
							type="number"
							step="0.05"
							min="0"
							max="1"
							class="w-24 rounded-md border border-outline-gray-2 px-2 py-1 text-sm"
							:placeholder="__('Peso')"
						/>
						<Button variant="ghost" size="sm" @click="removeCriterion(i)">×</Button>
					</div>
					<textarea
						v-model="row.description"
						:rows="3"
						class="w-full rounded-md border border-outline-gray-2 px-2 py-1 text-sm"
						:placeholder="__('Descrizione (cosa va osservato)')"
					></textarea>
					<textarea
						v-model="row.observable_behaviors"
						:rows="5"
						class="w-full rounded-md border border-outline-gray-2 px-2 py-1 text-sm"
						:placeholder="__('Comportamenti osservabili (per il prompt)')"
					></textarea>
				</div>
			</div>
			<div v-if="!model.criteria.length" class="text-xs text-ink-gray-5 mt-2">
				{{ __('Aggiungi almeno un criterio.') }}
			</div>
		</div>
	</form>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Button, FormControl, createResource, toast } from 'frappe-ui'

const props = defineProps({
	schemaName: { type: String, default: '' },
})
const emit = defineEmits(['saved'])

const saving = ref(false)

const model = reactive({
	name: props.schemaName || '',
	schema_name: '',
	description: '',
	scoring_scale: '0-10',
	passing_threshold: 70,
	is_shared: 0,
	criteria: [],
})

const weightSum = computed(() =>
	(model.criteria || []).reduce((s, r) => s + (Number(r.weight) || 0), 0),
)
const weightSumOk = computed(() => Math.abs(weightSum.value - 1.0) <= 0.001)

const loadRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.get_evaluation_schema',
	makeParams() {
		return { name: props.schemaName }
	},
	onSuccess(data) {
		if (!data) return
		Object.assign(model, data)
		model.criteria = data.criteria || []
	},
})
watch(
	() => props.schemaName,
	(n) => {
		if (n) loadRes.submit()
	},
	{ immediate: true },
)

const saveRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.save_evaluation_schema',
	method: 'POST',
})

function addCriterion() {
	model.criteria.push({
		criterion_name: '',
		description: '',
		weight: 0,
		observable_behaviors: '',
	})
}
function removeCriterion(i) {
	model.criteria.splice(i, 1)
}

async function onSave() {
	if (!model.criteria.length) {
		toast.error(__('Aggiungi almeno un criterio.'))
		return
	}
	if (!weightSumOk.value) {
		toast.error(__('I pesi dei criteri devono sommare a 1.00.'))
		return
	}
	saving.value = true
	try {
		const result = await saveRes.submit({ payload: { ...model } })
		toast.success(__('Schema salvato'))
		emit('saved', result)
	} catch (e) {
		toast.error(e.messages?.[0] || __('Salvataggio fallito'))
	} finally {
		saving.value = false
	}
}
</script>
