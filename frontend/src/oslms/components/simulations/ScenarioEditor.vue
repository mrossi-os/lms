<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b main-page-header px-3 py-2.5 sm:px-5">
			<div class="flex items-center gap-2">
				<Breadcrumbs class="h-7" :items="breadcrumbs" />
				<Badge v-if="runningEvalId" theme="blue" :label="__('Test in corso')" />
			</div>
			<div class="flex items-center gap-x-2">
				<Button
					v-if="scenarioName"
					:title="__('Test simulazione (scegli profilo e n. conversazioni)')"
					:disabled="!!runningEvalId"
					@click="simTestDialogOpen = true"
				>
					{{ __('Test simulazione') }}
				</Button>
				<Button  :title="__('Esporta scenario in JSON')" @click="onExportScenario">
					<template #icon>
						<Download class="size-4 stroke-1.5" />
					</template>
				</Button>
				<Button  :title="__('Importa scenario da JSON')" @click="onImportScenarioClick">
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
				<Button

					:title="__('Compila i campi dello scenario con AI, usando il materiale del corso/lezione selezionato')"
					:disabled="!model.lms_course || aiGenerating"
					@click="aiDialogOpen = true"
				>
					<template #prefix>
						<Sparkles class="size-4 stroke-1.5" />
					</template>
					{{ __('Compila con IA') }}
				</Button>
				<Button v-if="scenarioName" @click="onTestRun" :loading="testing">
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
							:options="[
								{ label: __('Bozza'), value: 'Draft' },
								{ label: __('Pubblicato'), value: 'Published' },
								{ label: __('Archiviato'), value: 'Archived' },
							]" required />
						<Autocomplete class="lms-auto-complete" v-model="model.lms_course" :options="courseOptions"
							:label="__('Corso')" :placeholder="__('Cerca un corso')" required />
						<!-- Lesson field hidden by request; binding kept so the rest of the logic still works -->
						<Autocomplete v-if="false" class="lms-auto-complete" v-model="model.course_lesson"
							:options="lessonOptions" :label="__('Lezione (opzionale)')"
							:placeholder="__('Cerca una lezione')" :disabled="!model.lms_course" />
						<FormControl v-model="model.difficulty" type="select" class="lms-select "
							:label="__('Difficoltà')" :options="[
								{ label: __('Facile'), value: 'easy' },
								{ label: __('Media'), value: 'medium' },
								{ label: __('Difficile'), value: 'hard' },
							]" required />
						<!-- Modality select hidden by request; binding kept so the rest of
							the logic still works. New scenarios are locked to chat (see onSave). -->
						<FormControl v-if="false" v-model="model.modality" type="select" class="lms-select " :label="__('Modalità')"
							:options="[
								{ label: __('Chat'), value: 'chat' },
								{ label: __('Voce'), value: 'voice' },
								{ label: __('Entrambi'), value: 'both' },
							]" required />
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
						
						<Button  @click="openSchemaManagement">
							{{ __('Gestisci') }}
						</Button>

					</div>

					<!-- Limits: chat sessions are time-bounded only. `max_turns` is
						hidden from the form (kept bound + defaulted so the automated
						eval loop, which still reads it, is unaffected). -->
					<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
						<FormControl v-if="false" v-model.number="model.max_turns" type="number"
							:label="__('Turni max')" />
						<FormControl v-model.number="model.time_limit_minutes" type="number"
							:label="__('Tempo max (min)')"
							:description="__('0 = nessun limite. Allo scadere il personaggio chiude la conversazione entro pochi messaggi.')" />
					</div>


					<!-- Persona & situation -->
					<div class="">
						<div class="mb-4">
							<FormControl v-model="model.roleplay_persona" type="textarea" :rows="15"
								:label="__('Descrizione del personaggio')" :description="__('Età, ruolo, contesto, stato emotivo iniziale del personaggio AI (cliente, esaminatore, paziente, ecc.).')
									" required />
						</div>
						<FormControl v-model="model.situation_template" type="textarea" :rows="15"
							:label="__('Template situazione')" :description="__('Variabili randomizzate vengono sostituite al runtime. Per inserire una variabile nel testo usa la sintassi {nome_variabile}: il nome deve corrispondere esattamente a una variabile definita nella sezione \'Variabili scenario\'.')
								" required />

						<!-- Student brief (the "compito" the student reads before starting) -->
						<div class="mt-4">
							<div class="flex items-center justify-between mb-1.5">
								<label class="block text-xs text-ink-gray-5">
									{{ __('Compito dello studente') }}
								</label>
								<Button
									size="sm"
									:loading="briefGenerating"
									:disabled="!model.roleplay_persona || !model.situation_template"
									:title="__('Genera il compito con l\'IA a partire da persona, situazione e obiettivi')"
									@click="onGenerateBrief"
								>
									<template #prefix>
										<Sparkles class="size-3.5 stroke-1.5" />
									</template>
									{{ __('Genera con IA') }}
								</Button>
							</div>
							<FormControl v-model="model.student_brief" type="textarea" :rows="8"
								:description="__('Ciò che lo studente legge prima di iniziare, per capire la situazione e l\'obiettivo. Puoi usare le variabili {nome_variabile}. Se lasciato vuoto, viene generato dall\'IA a ogni sessione.')" />
						</div>
					</div>
				</div>

				<!-- Sidebar (1/3): objectives + variations -->
				<aside class="lg:col-span-1 space-y-6">
					<!-- Learning objectives -->
					<section>
						<div class="flex items-center justify-between mb-2">
							<div class="text-md font-medium text-ink-gray-9">
								{{ __('Obiettivi formativi') }}
							</div>
							<Button size="sm" @click="addObjective">
								+ {{ __('Aggiungi') }}
							</Button>
						</div>
						<div class="space-y-2">
							<div v-for="(row, i) in model.learning_objectives" :key="`obj-${i}`"
								class="flex gap-2 items-start border border-outline-gray-2 rounded-md card p-2">
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
								<Button variant="outline" size="sm" @click="removeObjective(i)">
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
							<div class="text-md font-medium text-ink-gray-9">
								{{ __('Variabili scenario') }}
							</div>
							<Button size="sm" @click="addVariation">
								+ {{ __('Aggiungi') }}
							</Button>
						</div>
						<div class="space-y-2">
							<div v-for="(row, i) in model.seed_variations" :key="`seed-${i}`"
								class="border border-outline-gray-2 rounded-md card !p-2">
								<!-- Accordion header: always visible -->
								<div
									class="flex items-center gap-2 p-3 cursor-pointer hover:bg-surface-gray-1 rounded-md"
									@click="toggleVariation(i)"
								>
									<ChevronDown
										class="size-4 stroke-1.5 text-ink-gray-5 transition-transform"
										:class="{ '-rotate-90': !expandedVariations[i] }"
									/>
									<div class="flex-1 text-sm font-semibold text-ink-gray-9 truncate">
										{{ row.variable_name || __('Nuova variabile') }}
									</div>
									<Button
										variant="outline"
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
							:remainingSeconds="simulationRemainingSeconds"
							:inputLocked="simulationInputLocked"
							@send="simulationOnSend"
							@send-audio="simulationOnSendAudio"
							@end="simulationEnd"
						/>
					</div>
				</template>
			</Dialog>

			<EvaluationResultsDialog
				v-model="evalDialogOpen"
				:evalId="evalDialogId"
			/>

			<SimulationTestDialog
				v-if="scenarioName"
				v-model="simTestDialogOpen"
				:scenario="scenarioName"
				@started="onSimTestStarted"
			/>

			<Dialog v-model="aiDialogOpen" :options="{
				title: __('Compila scenario con IA'),
				size: 'lg',
			}">
				<template #body-content>
					<div class="space-y-3">
						<p class="text-sm text-ink-gray-7">
							{{ __('Il modello leggerà gli estratti del corso/lezione selezionato (via RAG) e produrrà uno scenario completo. Tutti i campi del form verranno sostituiti — il salvataggio rimane manuale.') }}
						</p>
						<FormControl
							v-model="aiHint"
							type="textarea"
							:rows="4"
							:label="__('Hint (opzionale)')"
							:placeholder="__('Es: scenario incentrato sulla gestione delle obiezioni privacy in vendita B2B...')"
						/>
						<div class="flex justify-end gap-2 pt-2">
							<Button @click="aiDialogOpen = false" :disabled="aiGenerating">
								{{ __('Annulla') }}
							</Button>
							<Button variant="solid" :loading="aiGenerating" @click="onAiGenerate">
								{{ __('Genera') }}
							</Button>
						</div>
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
	Badge,
	Breadcrumbs,
	Button,
	Dialog,
	FormControl,
	createResource,
	toast,
	usePageMeta,
} from 'frappe-ui'
import { useRouter } from 'vue-router'
import { ChevronDown, Download, Sparkles, Trash2, Upload } from 'lucide-vue-next'
import EvaluationSchemaEditor from '@/oslms/components/simulations/EvaluationSchemaEditor.vue'
import ChatSession from '@/oslms/components/simulations/ChatSession.vue'
import EvaluationResultsDialog from '@/oslms/components/simulations/eval/EvaluationResultsDialog.vue'
import SimulationTestDialog from '@/oslms/components/simulations/eval/SimulationTestDialog.vue'
import { useSimulationSession } from '@/oslms/composables/useSimulationSession.js'
import { useEvaluation } from '@/oslms/composables/useEvaluation.js'

const props = defineProps({
	scenarioName: { type: String, default: '' },
	initialCourse: { type: String, default: '' },
})
const emit = defineEmits(['saved'])

const router = useRouter()
const saving = ref(false)
const testing = ref(false)
const schemaEditorOpen = ref(false)

// ---- "Compila con IA" state ----
const aiDialogOpen = ref(false)
const aiHint = ref('')
const aiGenerating = ref(false)
const aiGenerateRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.ai_generate_scenario',
	method: 'POST',
})

async function onAiGenerate() {
	if (!model.lms_course) {
		toast.error(__('Seleziona prima un corso.'))
		return
	}
	aiGenerating.value = true
	try {
		const result = await aiGenerateRes.submit({
			course: model.lms_course,
			lesson: model.course_lesson || null,
			hint: aiHint.value || '',
		})
		const payload = result?.payload
		if (!payload) {
			throw new Error(__('Risposta vuota dal generatore.'))
		}
		// Replace generated fields; lms_course / course_lesson /
		// evaluation_schema / status / provider_override stay as the user set
		// them (the AI payload doesn't include those).
		const REPLACE_FIELDS = [
			'scenario_name',
			'difficulty',
			'modality',
			'roleplay_persona',
			'situation_template',
			'max_turns',
			'time_limit_minutes',
		]
		for (const field of REPLACE_FIELDS) {
			if (payload[field] !== undefined) {
				model[field] = payload[field]
			}
		}
		model.learning_objectives = Array.isArray(payload.learning_objectives)
			? payload.learning_objectives
			: []
		model.seed_variations = Array.isArray(payload.seed_variations)
			? payload.seed_variations
			: []
		aiDialogOpen.value = false
		aiHint.value = ''
		toast.success(__('Scenario precompilato. Rivedi e salva.'))
	} catch (e) {
		toast.error(e.messages?.[0] || e.message || __('Generazione fallita'))
	} finally {
		aiGenerating.value = false
	}
}

// ---- "Genera con IA" state for the student brief (compito) ----
const briefGenerating = ref(false)
const aiBriefRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.ai_generate_student_brief',
	method: 'POST',
})

async function onGenerateBrief() {
	if (!model.roleplay_persona || !model.situation_template) {
		toast.error(__('Compila prima persona e situazione.'))
		return
	}
	briefGenerating.value = true
	try {
		const result = await aiBriefRes.submit({
			payload: {
				scenario_name: model.scenario_name,
				lms_course: unwrapAutocomplete(model.lms_course),
				difficulty: model.difficulty,
				roleplay_persona: model.roleplay_persona,
				situation_template: model.situation_template,
				learning_objectives: model.learning_objectives,
				seed_variations: model.seed_variations,
				provider_override: model.provider_override,
				model_override: model.model_override,
			},
		})
		if (!result?.student_brief) {
			throw new Error(__('Risposta vuota dal generatore.'))
		}
		model.student_brief = result.student_brief
		toast.success(__('Compito generato. Rivedi e salva.'))
	} catch (e) {
		toast.error(e.messages?.[0] || e.message || __('Generazione fallita'))
	} finally {
		briefGenerating.value = false
	}
}

// ---- Evaluation state (Test simulazione) ----
const evaluation = useEvaluation()
const evalDialogOpen = ref(false)
const evalDialogId = ref('')
const simTestDialogOpen = ref(false)
const runningEvalId = ref('')   // non-empty while a test is in flight

async function onSimTestStarted({ eval_id, num_variants }) {
	if (!eval_id) return
	runningEvalId.value = eval_id
	// For a single-variant run we poll inline (typically <60s); larger runs
	// rely on the realtime listener below to auto-open the dialog.
	if (num_variants === 1) {
		try {
			await evaluation.pollUntilComplete(eval_id, {
				intervalMs: 2000,
				timeoutMs: 90_000,
			})
			runningEvalId.value = ''
			evalDialogId.value = eval_id
			evalDialogOpen.value = true
		} catch (e) {
			if (e?.message === 'poll_timeout') {
				toast.success(
					__('Sta richiedendo più del previsto, ti notificheremo a fine test.'),
				)
			} else {
				toast.error(e?.message || __('Polling fallito'))
			}
		}
	} else {
		toast.success(__('Test avviato, ti notificheremo a fine job.'))
	}
}

evaluation.subscribeToCompletion({
	filter: (payload) => payload?.scenario === props.scenarioName,
	onComplete: (payload) => {
		if (payload.eval_id === runningEvalId.value) {
			runningEvalId.value = ''
		}
		evalDialogId.value = payload.eval_id
		evalDialogOpen.value = true
	},
})

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
	remainingSeconds: simulationRemainingSeconds,
	inputLocked: simulationInputLocked,
} = useSimulationSession(simulationSessionId)

// ChatSession emits a plain string on `send` (typed text) and a Blob on
// `send-audio` (recorded voice), but the composable's `send` takes a
// { text, audioBlob } object. These adapters bridge the two — mirroring
// SimulationPlay.vue, the page reached from the floating simulation button.
function simulationOnSend(text) {
	return simulationSend({ text })
}
function simulationOnSendAudio(blob) {
	return simulationSend({ audioBlob: blob })
}

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
	roleplay_persona: '',
	situation_template: '',
	student_brief: '',
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
			__('Variabili usate nel testo ma non definite: {0}').format(
				missing.join(', '),
			),
		)
		return
	}
	// Block on empty required fields with a clear message instead of waiting
	// for the backend MandatoryError (the server message hits the toast as
	// raw `Errore: Campo ... mancante` and disorients the user).
	const REQUIRED_FIELDS = [
		['scenario_name', __('Nome scenario')],
		['lms_course', __('Corso')],
		['roleplay_persona', __('Descrizione del personaggio')],
		['situation_template', __('Template situazione')],
	]
	for (const [field, label] of REQUIRED_FIELDS) {
		if (!String(model[field] ?? '').trim()) {
			toast.error(__('Campo obbligatorio mancante: {0}').format(label))
			return
		}
	}
	// frappe-ui Autocomplete writes {label, value} into v-model when the user
	// picks from the dropdown, but a plain string when populated
	// programmatically (get_scenario response, onSchemaCreated). Normalize
	// every Autocomplete-backed field to a plain string so the payload that
	// hits the backend never contains a {label, value} object.
	model.lms_course = unwrapAutocomplete(model.lms_course)
	model.course_lesson = unwrapAutocomplete(model.course_lesson)
	model.evaluation_schema = unwrapAutocomplete(model.evaluation_schema)
	const validSchemas = new Set(schemaOptions.value.map((o) => o.value))
	if (!model.evaluation_schema || !validSchemas.has(model.evaluation_schema)) {
		toast.error(
			__('Seleziona uno schema di valutazione dalla lista (oppure creane uno nuovo).'),
		)
		return
	}
	// New scenarios are locked to chat modality (the select is hidden at
	// creation); guarantee the saved value regardless of AI-fill / JSON import.
	if (!props.scenarioName) {
		model.modality = 'chat'
	}
	saving.value = true
	try {
		const result = await saveRes.submit({ payload: { ...model } })
		toast.success(__('Scenario salvato'))
		// Stay on the editor page on save. For a freshly-created scenario,
		// update `model.name` and `router.replace` to the edit URL so
		// (a) a subsequent save goes through as an UPDATE (the backend
		//     branches on payload.name and would otherwise re-create), and
		// (b) the URL becomes refresh-safe (currently it would be
		//     `ScenarioCreate?course=...` with no record id).
		if (result?.name) {
			model.name = result.name
			if (!props.scenarioName) {
				router.replace({
					name: 'ScenarioEdit',
					params: { name: result.name },
				})
			}
		}
	} catch (e) {
		toast.error(formatBackendError(e) || __('Salvataggio fallito'))
	} finally {
		saving.value = false
	}
}

// Returns the plain-string value of an Autocomplete-bound field. Accepts a
// string (returned as-is) or a {label, value} object (returns `value`).
function unwrapAutocomplete(v) {
	if (v && typeof v === 'object') {
		return v.value ?? ''
	}
	return v ?? ''
}

// Some Frappe handlers return server_messages whose entries are objects
// `{message, indicator, title}` instead of plain strings — passing the object
// straight to toast.error renders as "[object Object]". Extract the human-
// readable message safely.
function formatBackendError(e) {
	const first = e?.messages?.[0]
	if (typeof first === 'string') return first
	if (first && typeof first === 'object') {
		return first.message || JSON.stringify(first)
	}
	if (e?.message) return String(e.message)
	return ''
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
	'roleplay_persona',
	'situation_template',
	'student_brief',
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
			__('Importazione fallita: {0}').format(e.message || String(e)),
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
