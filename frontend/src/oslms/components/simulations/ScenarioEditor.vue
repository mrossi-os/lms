<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b main-page-header px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			<div class="flex items-center gap-x-2">
				<Button
					v-if="scenarioName"
					variant="ghost"
					@click="onTestRun"
					:loading="testing"
				>
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
						<FormControl
							v-model="model.scenario_name"
							type="text"
							:label="__('Nome scenario')"
							required
						/>
						<FormControl
							v-model="model.status"
							type="select"
							:label="__('Stato')"
							:options="['Draft', 'Published', 'Archived']"
							required
						/>
						<Autocomplete
							v-model="model.lms_course"
							:options="courseOptions"
							:label="__('Corso')"
							:placeholder="__('Cerca un corso')"
							required
						/>
						<Autocomplete
							v-model="model.course_lesson"
							:options="lessonOptions"
							:label="__('Lezione (opzionale)')"
							:placeholder="__('Cerca una lezione')"
							:disabled="!model.lms_course"
						/>
						<FormControl
							v-model="model.difficulty"
							type="select"
							:label="__('Difficoltà')"
							:options="['easy', 'medium', 'hard']"
							required
						/>
						<FormControl
							v-model="model.modality"
							type="select"
							:label="__('Modalità')"
							:options="['chat', 'voice', 'both']"
							required
						/>
					</div>

					<!-- Evaluation schema link -->
					<div class="flex items-end gap-2">
						<div class="flex-1">
							<Autocomplete
								v-model="model.evaluation_schema"
								:options="schemaOptions"
								:label="__('Schema di valutazione')"
								required
							/>
						</div>
						<Button @click="schemaEditorOpen = true">
							+ {{ __('Nuovo') }}
						</Button>
						<Button variant="ghost" @click="openSchemaManagement">
							{{ __('Gestisci') }}
						</Button>
					</div>

					<!-- Limits -->
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
						<FormControl
							v-model.number="model.max_turns"
							type="number"
							:label="__('Turni max')"
						/>
						<FormControl
							v-model.number="model.time_limit_minutes"
							type="number"
							:label="__('Tempo max (min)')"
						/>
					</div>

	
					<!-- Persona & situation -->
					<div class="">
						<div class="mb-4">
							<FormControl
								v-model="model.customer_persona"
								type="textarea"
								:rows="15"
								:label="__('Persona base')"
								:description="
									__('Età, ruolo, contesto, stato emotivo iniziale.')
								"
								required
							/>
						</div>
						<FormControl
							v-model="model.situation_template"
							type="textarea"
							:rows="15"
							:label="__('Template situazione')"
							:description="
								__('Variabili randomizzate vengono sostituite al runtime.')
							"
							required
						/>
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
							<div
								v-for="(row, i) in model.learning_objectives"
								:key="`obj-${i}`"
								class="flex gap-2 items-start border border-outline-gray-2 rounded-md p-2"
							>
								<textarea
									v-model="row.objective_text"
									:rows="5"
									class="flex-1 rounded-md border border-outline-gray-2 px-2 py-1 text-sm"
									:placeholder="__('Descrizione obiettivo')"
								></textarea>
								<input
									v-model.number="row.weight"
									type="number"
									step="0.05"
									min="0"
									max="1"
									class="w-20 rounded-md border border-outline-gray-2 px-2 py-1 text-sm"
									:placeholder="__('Peso')"
								/>
								<Button variant="ghost" size="sm" @click="removeObjective(i)">
									×
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
							<div
								v-for="(row, i) in model.seed_variations"
								:key="`seed-${i}`"
								class="flex flex-col gap-2 border border-outline-gray-2 rounded-md p-2"
							>
								<div class="flex gap-2 items-center">
									<input
										v-model="row.variable_name"
										type="text"
										class="flex-1 rounded-md border border-outline-gray-2 px-2 py-1 text-sm"
										:placeholder="__('Nome variabile')"
									/>
									<Button
										variant="ghost"
										size="sm"
										@click="removeVariation(i)"
									>
										×
									</Button>
								</div>
								<textarea
									v-model="row.possible_values"
									:rows="5"
									class="rounded-md border border-outline-gray-2 px-2 py-1 text-sm"
									:placeholder="__('Un valore per riga')"
								></textarea>
							</div>
						</div>
					</section>
				</aside>
			</div>

			<Dialog
				v-model="schemaEditorOpen"
				:options="{
					title: __('Nuovo schema di valutazione'),
					size: '3xl',
				}"
			>
				<template #body-content>
					<EvaluationSchemaEditor schemaName="" @saved="onSchemaCreated" />
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
} from 'frappe-ui'
import { useRouter } from 'vue-router'
import EvaluationSchemaEditor from '@/oslms/components/simulations/EvaluationSchemaEditor.vue'

const props = defineProps({
	scenarioName: { type: String, default: '' },
	initialCourse: { type: String, default: '' },
})
const emit = defineEmits(['saved'])

const router = useRouter()
const saving = ref(false)
const testing = ref(false)
const schemaEditorOpen = ref(false)

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
}
function removeVariation(i) {
	model.seed_variations.splice(i, 1)
}

// ---- Save / preview ----

async function onSave() {
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
		router.push({ name: 'SimulationPlay', params: { sessionId: result.session } })
	} catch (e) {
		toast.error(e.messages?.[0] || __('Avvio sessione fallito'))
	} finally {
		testing.value = false
	}
}

function openSchemaManagement() {
	router.push({
		name: 'InstructorReports',
		query: { tab: 'schemas' },
	})
}

async function onSchemaCreated(result) {
	schemaEditorOpen.value = false
	await schemaRes.reload()
	if (result?.name) {
		model.evaluation_schema = result.name
	}
}
</script>
