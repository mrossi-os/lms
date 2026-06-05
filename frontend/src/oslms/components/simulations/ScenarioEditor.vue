<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b main-page-header px-3 py-2.5 sm:px-5">
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			<div class="flex items-center gap-x-2">
				<Button variant="ghost" :title="__('Esporta scenario in JSON')" @click="onExportScenario">
					<template #icon>
						<Download class="size-4 stroke-1.5" />
					</template>
				</Button>
				<Button variant="ghost" :title="__('Importa scenario da JSON')" @click="onImportScenarioClick">
					<template #icon>
						<Upload class="size-4 stroke-1.5" />
					</template>
				</Button>
				<input
					ref="importFileInput"
					type="file"
					accept="application/json,.json"
					class="hidden"
					@change="onImportScenarioFileSelected"
				/>
				<Button v-if="scenarioName" variant="ghost" @click="onTestRun" :loading="testing">
					{{ __('Prova come studente') }}
				</Button>
				<Button variant="solid" :loading="saving" @click="onSave">
					{{ __('Salva') }}
				</Button>
			</div>
		</header>

		<div class="p-5 sm:p-7">
			<div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
				<!-- Main column (2/3): scenario data in 2 sub-columns -->
				<div class="lg:col-span-2 space-y-6">
					<!-- Identity -->
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
						<FormControl v-model="model.scenario_name" type="text" :label="__('Nome scenario')" required />
						<FormControl v-model="model.status" type="select" class="lms-select " :label="__('Stato')"
							:options="['Draft', 'Published', 'Archived']" required />
						<Autocomplete class="lms-auto-complete" v-model="model.lms_course" :options="courseOptions"
							:label="__('Corso')" :placeholder="__('Cerca un corso')" required />
						<Autocomplete class="lms-auto-complete" v-model="model.course_lesson" :options="lessonOptions"
							:label="__('Lezione (opzionale)')" :placeholder="__('Cerca una lezione')"
							:disabled="!model.lms_course" />
						<FormControl v-model="model.difficulty" type="select" class="lms-select "
							:label="__('Difficoltà')" :options="['easy', 'medium', 'hard']" required />
						<FormControl v-model="model.modality" type="select" class="lms-select " :label="__('Modalità')"
							:options="['chat', 'voice', 'both']" required />
					</div>

					<!-- Evaluation schema link -->
					<div class="flex items-end gap-2">
						<div class="flex-1">
							<Autocomplete v-model="model.evaluation_schema" :options="schemaOptions"
								:label="__('Schema di valutazione')" required class="lms-auto-complete" />
						</div>

						<Button @click="schemaEditorOpen = true"">
							+ {{ __('Nuovo') }}
						</Button>
						
								<Button variant=" ghost" @click="openSchemaManagement">
							{{ __('Gestisci') }}
						</Button>

					</div>

					<!-- Limits -->
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
						<FormControl v-model.number="model.max_turns" type="number" :label="__('Turni max')" />
						<FormControl v-model.number="model.time_limit_minutes" type="number"
							:label="__('Tempo max (min)')" />
					</div>


					<!-- Persona & situation -->
					<div class="">
						<div class="mb-4">
							<FormControl v-model="model.customer_persona" type="textarea" :rows="15"
								:label="__('Persona base')" :description="__('Età, ruolo, contesto, stato emotivo iniziale.')
									" required />
						</div>
						<FormControl v-model="model.situation_template" type="textarea" :rows="15"
							:label="__('Template situazione')" :description="__('Variabili randomizzate vengono sostituite al runtime. Per inserire una variabile nel testo usa la sintassi {nome_variabile}: il nome deve corrispondere esattamente a una variabile definita nella sezione \'Variabili scenario\'.')
								" required />
					</div>
				</div>

				<!-- Sidebar (1/3): objectives + variations -->
				<aside class="lg:col-span-1 space-y-6">
					<!-- Learning objectives -->
					<section>
						<div class="flex items-center justify-between mb-2">
							<div class="text-sm font-medium text-ink-gray-9">
								{{ __('Obiettivi formativi') }}
							</div>
							<Button size="sm" variant="ghost" @click="addObjective">
								+ {{ __('Aggiungi') }}
							</Button>
						</div>
						<div class="space-y-2">
							<div v-for="(row, i) in model.learning_objectives" :key="`obj-${i}`"
								class="flex gap-2 items-start border border-outline-gray-2 rounded-md p-2">
								<FormControl
									v-model="row.objective_text"
									type="textarea"
									:rows="5"
									class="flex-1"
									:placeholder="__('Descrizione obiettivo')"
								/>
								<FormControl
									v-model.number="row.weight"
									type="number"
									step="0.05"
									min="0"
									max="1"
									class="w-20"
									:placeholder="__('Peso')"
								/>
								<Button variant="ghost" size="sm" @click="removeObjective(i)">
									<template #icon>
										<Trash2 class="size-4 stroke-1.5" />
									</template>
								</Button>
							</div>
						</div>
					</section>

					<!-- Seed variations -->
					<section>
						<div class="flex items-center justify-between mb-2">
							<div class="text-sm font-medium text-ink-gray-9">
								{{ __('Variabili scenario') }}
							</div>
							<Button size="sm" variant="ghost" @click="addVariation">
								+ {{ __('Aggiungi') }}
							</Button>
						</div>
						<div class="space-y-2">
							<div v-for="(row, i) in model.seed_variations" :key="`seed-${i}`"
								class="border border-outline-gray-2 rounded-md">
								<!-- Accordion header: always visible -->
								<div
									class="flex items-center gap-2 p-3 cursor-pointer hover:bg-surface-gray-1 rounded-md"
									@click="toggleVariation(i)"
								>
									<ChevronDown
										class="size-4 stroke-1.5 text-ink-gray-5 transition-transform"
										:class="{ '-rotate-90': !expandedVariations[i] }"
									/>
									<div class="flex-1 text-sm font-medium text-ink-gray-9 truncate">
										{{ row.variable_name || __('Nuova variabile') }}
									</div>
									<Button
										variant="ghost"
										size="sm"
										@click.stop="removeVariation(i)"
									>
										<template #icon>
											<Trash2 class="size-4 stroke-1.5" />
										</template>
									</Button>
								</div>

								<!-- Accordion body: only when expanded -->
								<div
									v-if="expandedVariations[i]"
									class="p-3 border-t border-outline-gray-2 space-y-2"
								>
									<FormControl
										v-model="row.variable_name"
										type="text"
										:placeholder="__('Nome variabile')"
									/>
									<FormControl
										v-model="row.possible_values"
										type="textarea"
										:rows="5"
										:placeholder="__('Un valore per riga')"
									/>
								</div>
							</div>
						</div>
					</section>
				</aside>
			</div>

			<Dialog v-model="schemaEditorOpen" :options="{
				title: __('Nuovo schema di valutazione'),
				size: '3xl',
			}">
				<template #body-content>
					<EvaluationSchemaEditor schemaName="" @saved="onSchemaCreated" />
				</template>
			</Dialog>

			<!--
				Test-as-student simulation. The default body-header slot is
				overridden so the X close button is not rendered: the only way to
				close this dialog is via the "Termina" button inside ChatSession,
				which moves the session to a terminal status and triggers the
				auto-close watcher on `simulationIsTerminal`.

				ESC + backdrop are still attempted by Radix; they are silently
				rejected by `simulationDialogModel` and `disableOutsideClickToClose`.
			-->
			<Dialog
				v-model="simulationDialogModel"
				:disableOutsideClickToClose="true"
				:options="{
					title: __('Simulazione di prova'),
					size: '4xl',
				}"
			>
				<template #body-header>
					<div class="mb-6 flex items-center">
						<h3 class="text-2xl font-semibold leading-6 text-ink-gray-9">
							{{ __('Simulazione di prova') }}
						</h3>
					</div>
				</template>
				<template #body-content>
					<div
						v-if="simulationSessionId"
						class="h-[70vh] flex flex-col"
					>
						<ChatSession
							class="flex-1"
							:scenarioName="model.scenario_name"
							:persona="simulationPersona"
							:turns="simulationTurns"
							:status="simulationSession?.status || 'In Progress'"
							:sending="simulationSending"
							:ending="simulationEnding"
							@send="simulationSend"
							@end="simulationEnd"
						/>
					</div>
				</template>
			</Dialog>
		</div>
	</div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import {
	Autocomplete,
	Breadcrumbs,
	Button,
	Dialog,
	FormControl,
	createResource,
	toast,
	usePageMeta,
} from 'frappe-ui'
import { useRouter } from 'vue-router'
import { ChevronDown, Download, Trash2, Upload } from 'lucide-vue-next'
import EvaluationSchemaEditor from '@/oslms/components/simulations/EvaluationSchemaEditor.vue'
import ChatSession from '@/oslms/components/simulations/ChatSession.vue'
import { useSimulationSession } from '@/oslms/composables/useSimulationSession.js'

const props = defineProps({
	scenarioName: { type: String, default: '' },
	initialCourse: { type: String, default: '' },
})
const emit = defineEmits(['saved'])

const router = useRouter()
const saving = ref(false)
const testing = ref(false)
const schemaEditorOpen = ref(false)
// Accordion open/closed state for seed variations, one boolean per row.
// New variations added via UI start expanded; variations loaded from backend
// start collapsed.
const expandedVariations = ref([])

// ---- Simulation dialog state (Prova come studente) ----
const simulationDialogOpen = ref(false)
const simulationSessionId = ref('')
const {
	session: simulationSession,
	turns: simulationTurns,
	sending: simulationSending,
	ending: simulationEnding,
	isTerminal: simulationIsTerminal,
	send: simulationSend,
	end: simulationEnd,
} = useSimulationSession(simulationSessionId)

const simulationPersona = computed(() => {
	const raw = simulationSession.value?.generated_persona
	if (!raw) return null
	try {
		return JSON.parse(raw)
	} catch {
		return null
	}
})

// Closing is blocked until the session is terminal (i.e. the user clicked
// "Termina" inside ChatSession or the backend marked it as finished). This
// computed intercepts every close attempt — backdrop click, ESC, X — and
// silently ignores them while the simulation is still running.
const simulationDialogModel = computed({
	get: () => simulationDialogOpen.value,
	set: (value) => {
		if (!value && !simulationIsTerminal.value) return
		simulationDialogOpen.value = value
	},
})

// When the simulation terminates, auto-close the dialog and clear the session
// id so the composable unsubscribes from realtime events.
watch(simulationIsTerminal, (terminal) => {
	if (!terminal) return
	toast.success(__('Simulazione conclusa.'))
	simulationDialogOpen.value = false
})

watch(simulationDialogOpen, (open) => {
	if (!open) simulationSessionId.value = ''
})

const model = reactive({
	name: props.scenarioName || '',
	scenario_name: '',
	lms_course: props.initialCourse || '',
	course_lesson: '',
	difficulty: 'medium',
	modality: 'chat',
	status: 'Draft',
	customer_persona: '',
	situation_template: '',
	evaluation_schema: '',
	max_turns: 20,
	time_limit_minutes: 15,
	provider_override: 'auto',
	model_override: '',
	learning_objectives: [],
	seed_variations: [],
})

// ---- Resource loaders ----

const courseRes = createResource({
	url: 'frappe.client.get_list',
	auto: true,
	makeParams() {
		return { doctype: 'LMS Course', fields: ['name', 'title'], limit_page_length: 500 }
	},
})
const courseOptions = computed(() =>
	(courseRes.data || []).map((c) => ({ label: c.title || c.name, value: c.name })),
)

const lessonRes = createResource({
	url: 'frappe.client.get_list',
	makeParams() {
		return {
			doctype: 'Course Lesson',
			filters: { course: model.lms_course },
			fields: ['name', 'title'],
			limit_page_length: 500,
		}
	},
	auto: false,
})
const lessonOptions = computed(() =>
	(lessonRes.data || []).map((l) => ({ label: l.title || l.name, value: l.name })),
)
watch(
	() => model.lms_course,
	(c) => {
		if (c) lessonRes.submit()
	},
	{ immediate: true },
)

const schemaRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.list_my_evaluation_schemas',
	auto: true,
})
const schemaOptions = computed(() =>
	(schemaRes.data || []).map((r) => ({ label: r.schema_name, value: r.name })),
)

const loadRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.get_scenario',
	makeParams() {
		return { name: props.scenarioName }
	},
	onSuccess(data) {
		if (!data) return
		Object.assign(model, data)
		model.learning_objectives = data.learning_objectives || []
		model.seed_variations = data.seed_variations || []
		expandedVariations.value = model.seed_variations.map(() => false)
	},
})
watch(
	() => props.scenarioName,
	(n) => {
		if (n) loadRes.submit()
	},
	{ immediate: true },
)

const saveRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.save_scenario',
	method: 'POST',
})

// ---- Page meta ----

usePageMeta(() => ({
	title: props.scenarioName
		? model.scenario_name || __('Scenario')
		: __('Nuovo scenario'),
}))

// ---- Breadcrumbs ----

const breadcrumbs = computed(() => {
	const items = [{ label: __('Courses'), route: { name: 'Courses' } }]
	if (model.lms_course) {
		const opt = courseOptions.value.find((o) => o.value === model.lms_course)
		const courseLabel = opt?.label || model.lms_course
		items.push({
			label: courseLabel,
			route: {
				name: 'CourseDetail',
				params: { courseName: model.lms_course },
			},
		})
	}
	items.push({
		label: props.scenarioName
			? model.scenario_name || __('Scenario')
			: __('Nuovo scenario'),
	})
	return items
})

// ---- Child-row helpers ----

function addObjective() {
	model.learning_objectives.push({ objective_text: '', weight: 0 })
}
function removeObjective(i) {
	model.learning_objectives.splice(i, 1)
}
function addVariation() {
	model.seed_variations.push({ variable_name: '', possible_values: '' })
	expandedVariations.value.push(true)
}
function removeVariation(i) {
	model.seed_variations.splice(i, 1)
	expandedVariations.value.splice(i, 1)
}
function toggleVariation(i) {
	expandedVariations.value[i] = !expandedVariations.value[i]
}

// ---- Save / preview ----

// Matches {variable_name} placeholders in the situation_template (single-brace
// convention, matching what the backend pipeline expects).
// Identifier rules: ASCII letter/underscore start, alphanumeric/underscore tail —
// matches what we accept as a variable name in the Variazioni section.
const VAR_REF_RE = /\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}/g

function findUndefinedVariables() {
	const referenced = new Set()
	const text = model.situation_template || ''
	for (const m of text.matchAll(VAR_REF_RE)) {
		referenced.add(m[1])
	}
	const defined = new Set(
		(model.seed_variations || [])
			.map((v) => (v.variable_name || '').trim())
			.filter(Boolean),
	)
	return [...referenced].filter((v) => !defined.has(v))
}

async function onSave() {
	const missing = findUndefinedVariables()
	if (missing.length) {
		toast.error(
			__('Variabili usate nel testo ma non definite: {0}', [
				missing.join(', '),
			]),
		)
		return
	}
	saving.value = true
	try {
		const result = await saveRes.submit({ payload: { ...model } })
		toast.success(__('Scenario salvato'))
		emit('saved', result)
	} catch (e) {
		toast.error(e.messages?.[0] || __('Salvataggio fallito'))
	} finally {
		saving.value = false
	}
}

const startRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.start_session',
	method: 'POST',
})

async function onTestRun() {
	if (!props.scenarioName) return
	testing.value = true
	try {
		const result = await startRes.submit({
			scenario_id: props.scenarioName,
			modality: model.modality || 'chat',
		})
		simulationSessionId.value = result.session
		simulationDialogOpen.value = true
	} catch (e) {
		toast.error(e.messages?.[0] || __('Avvio sessione fallito'))
	} finally {
		testing.value = false
	}
}

function openSchemaManagement() {
	router.push({ name: 'EvaluationSchemas' })
}

// ---- JSON import / export ----

// Fields that travel with the scenario across instances. `name` (the doctype
// id) is intentionally NOT exported: importing should never silently overwrite
// a different document — the imported payload populates the editor and is
// persisted under the current scenario id on Save.
const SCENARIO_EXPORT_FIELDS = [
	'scenario_name',
	'lms_course',
	'course_lesson',
	'difficulty',
	'modality',
	'status',
	'customer_persona',
	'situation_template',
	'evaluation_schema',
	'max_turns',
	'time_limit_minutes',
	'provider_override',
	'model_override',
]

const importFileInput = ref(null)

function onExportScenario() {
	const data = {}
	for (const field of SCENARIO_EXPORT_FIELDS) {
		data[field] = model[field]
	}
	data.learning_objectives = model.learning_objectives
	data.seed_variations = model.seed_variations
	const json = JSON.stringify(data, null, 2)
	const blob = new Blob([json], { type: 'application/json' })
	const url = URL.createObjectURL(blob)
	const slug = (model.scenario_name || 'scenario')
		.replace(/[^a-z0-9_-]+/gi, '_')
		.replace(/^_+|_+$/g, '')
		.toLowerCase() || 'scenario'
	const link = document.createElement('a')
	link.href = url
	link.download = `${slug}.json`
	document.body.appendChild(link)
	link.click()
	document.body.removeChild(link)
	URL.revokeObjectURL(url)
}

function onImportScenarioClick() {
	importFileInput.value?.click()
}

async function onImportScenarioFileSelected(event) {
	const file = event.target.files?.[0]
	if (!file) return
	try {
		const text = await file.text()
		const data = JSON.parse(text)
		if (!data || typeof data !== 'object' || Array.isArray(data)) {
			throw new Error(__('Formato JSON non valido'))
		}
		for (const field of SCENARIO_EXPORT_FIELDS) {
			if (data[field] !== undefined) {
				model[field] = data[field]
			}
		}
		model.learning_objectives = Array.isArray(data.learning_objectives)
			? data.learning_objectives
			: []
		model.seed_variations = Array.isArray(data.seed_variations)
			? data.seed_variations
			: []
		expandedVariations.value = model.seed_variations.map(() => false)
		toast.success(__('Scenario importato'))
	} catch (e) {
		toast.error(
			__('Importazione fallita: {0}', [e.message || String(e)]),
		)
	} finally {
		// Reset so re-importing the same file fires `change` again.
		event.target.value = ''
	}
}

async function onSchemaCreated(result) {
	schemaEditorOpen.value = false
	await schemaRes.reload()
	if (result?.name) {
		model.evaluation_schema = result.name
	}
}
</script>
