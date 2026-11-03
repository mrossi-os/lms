<template>
	<Dialog
		v-model="visible"
		:options="{ title: __('Trascrizione + Debrief'), size: '4xl' }"
	>
		<template #body-content>
			<div v-if="loading" class="text-ink-gray-5 text-sm">{{ __('Caricamento…') }}</div>
			<div v-else-if="payload" class="grid grid-cols-5 gap-4">
				<!-- Left: transcript (read-only chat) -->
				<div class="col-span-3 border rounded-md overflow-hidden flex flex-col h-[70vh]">
					<ChatSession
						class="flex-1"
						:scenarioName="payload.session.scenario"
						:persona="persona"
						:turns="payload.turns"
						:status="payload.session.status"
						readOnly
					/>
				</div>

				<!-- Right: debrief summary -->
				<div class="col-span-2 space-y-3 max-h-[70vh] overflow-y-auto pr-2">
					<div v-if="payload.debrief">
						<div class="text-xs uppercase text-ink-gray-5 mb-1">
							{{ __("Versione dell'AI") }}
						</div>
						<div class="text-3xl font-semibold text-ink-gray-9">
							{{ Math.round(payload.debrief.overall_score || 0) }}
							<span class="text-sm text-ink-gray-5">/100</span>
						</div>
						<div class="mt-1 text-xs text-ink-gray-5">
							{{ __("Punteggio indicativo dell'AI: non decide l'esito e non si modifica.") }}
						</div>

						<section v-if="payload.debrief.criterion_scores?.length" class="mt-4">
							<div class="text-sm font-semibold text-ink-gray-9 mb-2">
								{{ __('Criteri') }}
							</div>
							<ul class="space-y-2">
								<li
									v-for="c in payload.debrief.criterion_scores"
									:key="c.criterion_name"
									class="border border-outline-gray-2 rounded-md p-3"
								>
									<div class="flex items-baseline justify-between gap-3">
										<span class="text-sm font-medium text-ink-gray-9">
											{{ c.criterion_name }}
										</span>
										<span class="text-sm font-semibold text-ink-gray-9 tabular-nums whitespace-nowrap">
											{{ c.score }}<span class="font-normal text-ink-gray-5"> / {{ c.max_score || 10 }}</span>
										</span>
									</div>
									<div class="mt-2 h-1.5 bg-surface-gray-2 rounded-full overflow-hidden">
										<div
											class="h-full bg-surface-blue-3 transition-all"
											:style="{
												width: `${Math.max(0, Math.min(100, (Number(c.score) / Number(c.max_score || 10)) * 100))}%`,
											}"
										></div>
									</div>
								</li>
							</ul>
						</section>

						<section v-if="payload.debrief.improvements?.length" class="mt-4">
							<div class="text-xs font-semibold text-ink-gray-9 mb-1">
								{{ __('Aree di miglioramento') }}
							</div>
							<ul class="text-xs list-disc list-inside text-ink-gray-7">
								<li v-for="(imp, i) in payload.debrief.improvements" :key="i">
									{{ imp.title }}
								</li>
							</ul>
						</section>

						<!-- Teacher version: a copy of the AI version the teacher edits and
							publishes; students see it only once published. On simulations
							with an outcome the teacher decides passed / not passed here. -->
						<section class="mt-6 border-t border-outline-gray-2 pt-4">
							<div class="flex items-center justify-between gap-2 mb-2">
								<div class="text-sm font-semibold text-ink-gray-9">
									{{ __('Versione del docente') }}
								</div>
								<Badge
									v-if="teacherVersion"
									:label="isPublished ? __('Pubblicata') : __('Bozza')"
									:theme="isPublished ? 'green' : 'orange'"
								/>
							</div>

							<template v-if="!reviewForm">
								<p class="text-xs text-ink-gray-5 mb-2">
									{{ __("Parte dai suggerimenti dell'AI: puoi modificarli prima di pubblicarli allo studente.") }}
								</p>
								<p v-if="outcomeRequired" class="text-xs text-ink-gray-7 mb-2">
									{{ __('Questa simulazione ha un esito: decidi tu se lo studente l\'ha superata.') }}
								</p>
								<Button
									variant="solid"
									size="sm"
									:loading="reviewBusy === 'start'"
									@click="onStartReview"
								>
									{{ __('Crea la versione del docente') }}
								</Button>
							</template>

							<div v-else class="space-y-4">
								<div class="text-xs text-ink-gray-5 space-y-0.5">
									<div v-if="teacherVersion.edited_at">
										{{ __('Modificata da {0} il {1}').format(teacherVersion.edited_by_name, formatDateTime(teacherVersion.edited_at)) }}
									</div>
									<div v-if="isPublished">
										{{ __('Pubblicata da {0} il {1}: lo studente vede questa versione.').format(teacherVersion.published_by_name, formatDateTime(teacherVersion.published_at)) }}
									</div>
									<div v-else>{{ __('Lo studente non la vede finché non la pubblichi.') }}</div>
								</div>

								<FormControl
									v-model="reviewForm.overall_score"
									type="number"
									min="0"
									max="100"
									:label="__('Punteggio del docente (0-100)')"
								/>

								<div v-if="reviewForm.criterion_scores.length">
									<div class="text-xs font-semibold text-ink-gray-9 mb-1">{{ __('Criteri') }}</div>
									<div
										v-for="c in reviewForm.criterion_scores"
										:key="c.criterion_name"
										class="border border-outline-gray-2 rounded-md p-2 mb-2 space-y-2"
									>
										<div class="flex items-center justify-between gap-2">
											<span class="text-sm text-ink-gray-9">{{ c.criterion_name }}</span>
											<div class="flex items-center gap-1 w-28">
												<FormControl v-model="c.score" type="number" min="0" :max="c.max_score || 10" />
												<span class="text-xs text-ink-gray-5 whitespace-nowrap">/ {{ c.max_score || 10 }}</span>
											</div>
										</div>
										<FormControl v-model="c.note" type="textarea" :rows="2" :placeholder="__('Nota sul criterio')" />
									</div>
								</div>

								<div>
									<div class="flex items-center justify-between mb-1">
										<div class="text-xs font-semibold text-ink-gray-9">{{ __('Punti di forza') }}</div>
										<Button size="sm" variant="ghost" @click="addRow('strengths')">+ {{ __('Aggiungi') }}</Button>
									</div>
									<div
										v-for="(row, i) in reviewForm.strengths"
										:key="`s-${i}`"
										class="border border-outline-gray-2 rounded-md p-2 mb-2 space-y-2"
									>
										<div class="flex gap-2 items-start">
											<FormControl v-model="row.title" class="flex-1" :placeholder="__('Titolo')" />
											<Button size="sm" variant="ghost" :title="__('Rimuovi')" @click="removeRow('strengths', i)">✕</Button>
										</div>
										<FormControl v-model="row.detail" type="textarea" :rows="2" :placeholder="__('Dettaglio')" />
									</div>
								</div>

								<div>
									<div class="flex items-center justify-between mb-1">
										<div class="text-xs font-semibold text-ink-gray-9">{{ __('Aree di miglioramento') }}</div>
										<Button size="sm" variant="ghost" @click="addRow('improvements')">+ {{ __('Aggiungi') }}</Button>
									</div>
									<div
										v-for="(row, i) in reviewForm.improvements"
										:key="`m-${i}`"
										class="border border-outline-gray-2 rounded-md p-2 mb-2 space-y-2"
									>
										<div class="flex gap-2 items-start">
											<FormControl v-model="row.title" class="flex-1" :placeholder="__('Titolo')" />
											<Button size="sm" variant="ghost" :title="__('Rimuovi')" @click="removeRow('improvements', i)">✕</Button>
										</div>
										<FormControl v-model="row.detail" type="textarea" :rows="2" :placeholder="__('Dettaglio')" />
										<FormControl v-model="row.suggestion" type="textarea" :rows="2" :placeholder="__('Consiglio')" />
									</div>
								</div>

								<FormControl
									v-model="reviewForm.comment"
									type="textarea"
									:rows="4"
									:label="__('Commento per lo studente')"
								/>

								<div v-if="outcomeRequired" class="space-y-2">
									<FormControl
										v-model="reviewForm.outcome"
										type="select"
										class="lms-select"
										:label="__('Esito')"
										:options="[
											{ label: __('Da decidere'), value: '' },
											{ label: __('Superata'), value: 'Passed' },
											{ label: __('Non superata'), value: 'Not Passed' },
										]"
									/>
									<FormControl
										v-if="reviewForm.outcome"
										v-model="reviewForm.outcome_reason"
										type="textarea"
										:rows="3"
										:label="reviewForm.outcome === 'Not Passed' ? __('Motivazione (obbligatoria)') : __('Motivazione (facoltativa)')"
									/>
									<div v-if="teacherVersion.outcome_decided_at" class="text-xs text-ink-gray-5">
										{{ __('Esito deciso da {0} il {1}').format(teacherVersion.outcome_decided_by_name, formatDateTime(teacherVersion.outcome_decided_at)) }}
									</div>
								</div>

								<div class="flex flex-wrap justify-end gap-2">
									<Button
										v-if="!isPublished"
										variant="ghost"
										size="sm"
										:loading="reviewBusy === 'discard'"
										@click="onDiscardReview"
									>
										{{ __('Elimina bozza') }}
									</Button>
									<Button
										v-if="!isPublished"
										variant="outline"
										size="sm"
										:loading="reviewBusy === 'save'"
										@click="onSaveReview(false)"
									>
										{{ __('Salva bozza') }}
									</Button>
									<Button
										variant="solid"
										size="sm"
										:loading="reviewBusy === 'publish' || (isPublished && reviewBusy === 'save')"
										@click="onSaveReview(!isPublished)"
									>
										{{ isPublished ? __('Salva e aggiorna per lo studente') : __('Pubblica allo studente') }}
									</Button>
								</div>
							</div>
						</section>

						<div v-if="isTerminal" class="mt-4 flex justify-end">
							<Button variant="outline" size="sm" :loading="evaluating" @click="onEvaluate">
								{{ __('Valuta sessione') }}
							</Button>
						</div>

						<section v-if="evalHistory.length" class="mt-4">
							<div class="text-xs font-semibold text-ink-gray-9 mb-1">
								{{ __('Valutazioni precedenti') }}
							</div>
							<ul class="text-xs space-y-1">
								<li
									v-for="ev in evalHistory"
									:key="ev.eval_id"
									class="flex items-center justify-between cursor-pointer hover:bg-surface-gray-1 px-1 py-0.5 rounded"
									@click="openEvaluation(ev.eval_id)"
								>
									<span class="text-ink-gray-7">{{ ev.triggered_at }}</span>
									<Badge :label="evalStatusLabel(ev.status)" :theme="evalStatusTheme(ev.status)" />
								</li>
							</ul>
						</section>
					</div>
					<div v-else class="text-sm text-ink-gray-5">
						{{ __('Debrief non disponibile per questa sessione.') }}
					</div>
				</div>
			</div>
		</template>
	</Dialog>

	<EvaluationResultsDialog
		v-model="evalDialogOpen"
		:evalId="evalDialogId"
	/>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Badge, Button, Dialog, FormControl, createResource, toast } from 'frappe-ui'
import ChatSession from '@/oslms/components/simulations/ChatSession.vue'
import EvaluationResultsDialog from '@/oslms/components/simulations/eval/EvaluationResultsDialog.vue'
import { useEvaluation } from '@/oslms/composables/useEvaluation.js'

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	sessionId: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'review-saved'])

const visible = computed({
	get: () => props.modelValue,
	set: (v) => emit('update:modelValue', v),
})

const payload = ref(null)
const loading = ref(false)

const persona = computed(() => {
	const raw = payload.value?.session?.generated_persona
	if (!raw) return null
	try { return JSON.parse(raw) } catch { return null }
})

const loadRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.get_transcript',
	makeParams() {
		return { session_id: props.sessionId }
	},
	onSuccess(data) {
		payload.value = data
		reviewForm.value = formFromDebrief(data?.debrief)
	},
	onError(e) {
		toast.error(e.messages?.[0] || __('Caricamento trascrizione fallito'))
	},
})

watch(
	() => [props.sessionId, visible.value],
	([id, open]) => {
		if (open && id) {
			loading.value = true
			loadRes.submit().finally(() => { loading.value = false })
		}
	},
	{ immediate: true },
)

// ---- Teacher version of the debrief (ai/simulations/teacher_review.py) ----
const reviewForm = ref(null)
const reviewBusy = ref('')

const teacherVersion = computed(() => payload.value?.debrief?.teacher_version || null)
const isPublished = computed(() => teacherVersion.value?.status === 'published')
const outcomeRequired = computed(() => !!payload.value?.debrief?.outcome_required)

function formFromDebrief(debrief) {
	const v = debrief?.teacher_version
	if (!v) return null
	return {
		overall_score: v.overall_score ?? '',
		criterion_scores: (v.criterion_scores || []).map((c) => ({ ...c })),
		strengths: (v.strengths || []).map((r) => ({ ...r })),
		improvements: (v.improvements || []).map((r) => ({ ...r })),
		comment: v.comment || '',
		outcome: v.outcome || '',
		outcome_reason: v.outcome_reason || '',
	}
}

function addRow(field) {
	reviewForm.value[field].push({ title: '', detail: '', quote: '', suggestion: '' })
}

function removeRow(field, index) {
	reviewForm.value[field].splice(index, 1)
}

// Mirrors the server checks, so the teacher gets the message before the call.
function reviewProblem(publishing) {
	const f = reviewForm.value
	const score = Number(f.overall_score)
	if (f.overall_score === '' || !Number.isFinite(score) || score < 0 || score > 100) {
		return __('Il punteggio deve essere un numero tra 0 e 100.')
	}
	for (const c of f.criterion_scores) {
		const value = Number(c.score)
		const max = Number(c.max_score || 10)
		if (c.score === '' || !Number.isFinite(value) || value < 0 || value > max) {
			return __('Il voto di {0} deve essere un numero tra 0 e {1}.').format(c.criterion_name, max)
		}
	}
	if (publishing && outcomeRequired.value && !f.outcome) {
		return __('Decidi se la simulazione è superata prima di pubblicare.')
	}
	if (publishing && f.outcome === 'Not Passed' && !f.outcome_reason.trim()) {
		return __('Scrivi la motivazione: la simulazione non è superata.')
	}
	return ''
}

const startReviewRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.instructor_start_review',
	method: 'POST',
})
const saveReviewRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.instructor_save_review',
	method: 'POST',
})
const discardReviewRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.instructor_discard_review',
	method: 'POST',
})

async function runReview(kind, call) {
	reviewBusy.value = kind
	try {
		const debrief = await call()
		payload.value.debrief = debrief
		reviewForm.value = formFromDebrief(debrief)
		emit('review-saved')
		return true
	} catch (e) {
		toast.error(e.messages?.[0] || __('Salvataggio fallito'))
		return false
	} finally {
		reviewBusy.value = ''
	}
}

function onStartReview() {
	return runReview('start', () => startReviewRes.submit({ session_id: props.sessionId }))
}

async function onSaveReview(publish) {
	const wasPublished = isPublished.value
	const problem = reviewProblem(publish || wasPublished)
	if (problem) {
		toast.error(problem)
		return
	}
	const f = reviewForm.value
	const review = {
		...f,
		overall_score: Number(f.overall_score),
		criterion_scores: f.criterion_scores.map((c) => ({
			criterion_name: c.criterion_name,
			score: Number(c.score),
			note: c.note || '',
		})),
	}
	const ok = await runReview(publish ? 'publish' : 'save', () =>
		saveReviewRes.submit({ session_id: props.sessionId, review, publish }),
	)
	if (!ok) return
	if (publish) toast.success(__('Versione del docente pubblicata: lo studente la vede.'))
	else if (wasPublished) toast.success(__('Modifiche salvate: lo studente vede la versione aggiornata.'))
	else toast.success(__('Bozza salvata.'))
}

async function onDiscardReview() {
	if (!window.confirm(__('Eliminare la bozza della versione del docente?'))) return
	const ok = await runReview('discard', () =>
		discardReviewRes.submit({ session_id: props.sessionId }),
	)
	if (ok) toast.success(__('Bozza eliminata.'))
}

function formatDateTime(value) {
	if (!value) return ''
	const d = new Date(value.replace(' ', 'T'))
	return Number.isNaN(d.getTime()) ? value : d.toLocaleString()
}

// ---- Production evaluation ----
const evaluation = useEvaluation()
const evalDialogOpen = ref(false)
const evalDialogId = ref('')
const evaluating = ref(false)

const historyRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.eval.api.list_evaluations_for_session',
	makeParams() {
		return { session_id: props.sessionId }
	},
})
const evalHistory = computed(() => historyRes.data || [])

watch(
	() => [visible.value, props.sessionId],
	([open, id]) => {
		if (open && id) historyRes.submit()
	},
	{ immediate: true },
)

const isTerminal = computed(() => {
	const s = payload.value?.session?.status
	return ['Completed', 'Needs Review', 'Abandoned', 'Error'].includes(s)
})

async function onEvaluate() {
	if (!props.sessionId) return
	evaluating.value = true
	try {
		const evalId = await evaluation.runProductionEvaluation(props.sessionId)
		if (!evalId) return
		try {
			await evaluation.pollUntilComplete(evalId, {
				intervalMs: 2000,
				timeoutMs: 90_000,
			})
			evalDialogId.value = evalId
			evalDialogOpen.value = true
			historyRes.submit()
		} catch (e) {
			if (e?.message === 'poll_timeout') {
				toast.success(__('Sta richiedendo più del previsto, ti notificheremo.'))
			} else {
				toast.error(e?.message || __('Polling fallito'))
			}
		}
	} finally {
		evaluating.value = false
	}
}

function openEvaluation(evalId) {
	evalDialogId.value = evalId
	evalDialogOpen.value = true
}

function evalStatusTheme(s) {
	return { queued: 'gray', running: 'blue', complete: 'green', failed: 'red' }[s] || 'gray'
}

// Backend evaluation status enum → Italian display label.
function evalStatusLabel(s) {
	return {
		queued: __('In coda'),
		running: __('In corso'),
		complete: __('Completata'),
		failed: __('Fallita'),
	}[s] || s
}

evaluation.subscribeToCompletion({
	filter: (p) => p?.source_session === props.sessionId,
	onComplete: (p) => {
		evalDialogId.value = p.eval_id
		evalDialogOpen.value = true
		historyRes.submit()
	},
})
</script>
