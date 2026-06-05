<template>
	<form @submit.prevent="onSave" class="space-y-6">
		<div class="flex items-center justify-between">
			<h2 class="text-lg font-semibold text-ink-gray-9">
				{{ schemaName ? __('Modifica schema di valutazione') : __('Nuovo schema di valutazione') }}
			</h2>
			<div class="flex items-center gap-2">
				<Button
					variant="ghost"
					type="button"
					:title="__('Esporta schema in JSON')"
					@click="onExportSchema"
				>
					<template #icon>
						<Download class="size-4 stroke-1.5" />
					</template>
				</Button>
				<Button
					variant="ghost"
					type="button"
					:title="__('Importa schema da JSON')"
					@click="onImportSchemaClick"
				>
					<template #icon>
						<Upload class="size-4 stroke-1.5" />
					</template>
				</Button>
				<input
					ref="importFileInput"
					type="file"
					accept="application/json,.json"
					class="hidden"
					@change="onImportSchemaFileSelected"
				/>
				<Button variant="solid" :loading="saving" type="submit">
					{{ __('Salva') }}
				</Button>
			</div>
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
				<CriterionEditor
					v-for="(row, i) in model.criteria"
					:key="`crit-${i}`"
					:criterion="row"
					v-model:expanded="expandedCriteria[i]"
					@remove="removeCriterion(i)"
				/>
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
import { Download, Upload } from 'lucide-vue-next'
import CriterionEditor from '@/oslms/components/simulations/CriterionEditor.vue'

const props = defineProps({
	schemaName: { type: String, default: '' },
})
const emit = defineEmits(['saved'])

const saving = ref(false)
// Parallel array of accordion open/closed state, one boolean per criterion.
// New criteria added via UI start expanded; criteria loaded from backend
// start collapsed.
const expandedCriteria = ref([])

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
		expandedCriteria.value = model.criteria.map(() => false)
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
	expandedCriteria.value.push(true)
}
function removeCriterion(i) {
	model.criteria.splice(i, 1)
	expandedCriteria.value.splice(i, 1)
}

// ---- JSON import / export ----

// `name` (the doctype id) is intentionally NOT exported: importing should
// never silently overwrite a different document — the payload populates the
// editor and gets persisted under the current schema id on Save.
const SCHEMA_EXPORT_FIELDS = [
	'schema_name',
	'description',
	'scoring_scale',
	'passing_threshold',
	'is_shared',
]

const importFileInput = ref(null)

function onExportSchema() {
	const data = {}
	for (const field of SCHEMA_EXPORT_FIELDS) {
		data[field] = model[field]
	}
	data.criteria = model.criteria
	const json = JSON.stringify(data, null, 2)
	const blob = new Blob([json], { type: 'application/json' })
	const url = URL.createObjectURL(blob)
	const slug = (model.schema_name || 'evaluation-schema')
		.replace(/[^a-z0-9_-]+/gi, '_')
		.replace(/^_+|_+$/g, '')
		.toLowerCase() || 'evaluation-schema'
	const link = document.createElement('a')
	link.href = url
	link.download = `${slug}.json`
	document.body.appendChild(link)
	link.click()
	document.body.removeChild(link)
	URL.revokeObjectURL(url)
}

function onImportSchemaClick() {
	importFileInput.value?.click()
}

async function onImportSchemaFileSelected(event) {
	const file = event.target.files?.[0]
	if (!file) return
	try {
		const text = await file.text()
		const data = JSON.parse(text)
		if (!data || typeof data !== 'object' || Array.isArray(data)) {
			throw new Error(__('Formato JSON non valido'))
		}
		for (const field of SCHEMA_EXPORT_FIELDS) {
			if (data[field] !== undefined) {
				model[field] = data[field]
			}
		}
		model.criteria = Array.isArray(data.criteria) ? data.criteria : []
		expandedCriteria.value = model.criteria.map(() => false)
		toast.success(__('Schema importato'))
	} catch (e) {
		toast.error(
			__('Importazione fallita: {0}', [e.message || String(e)]),
		)
	} finally {
		event.target.value = ''
	}
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
