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
						<div class="text-xs uppercase text-ink-gray-5 mb-1">{{ __('Punteggio') }}</div>
						<div class="text-3xl font-semibold text-ink-gray-9">
							{{ Math.round(payload.debrief.overall_score || 0) }}
							<span class="text-sm text-ink-gray-5">/100</span>
							<Badge
								class="ml-2 align-middle"
								:label="payload.debrief.passed ? __('Superata') : __('Non superata')"
								:theme="payload.debrief.passed ? 'green' : 'orange'"
							/>
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

						<!-- Instructor review -->
						<section class="mt-4">
							<div class="text-xs font-semibold text-ink-gray-9 mb-1">
								{{ __('Nota docente') }}
							</div>
							<FormControl
								v-model="reviewDraft"
								type="textarea"
								:rows="4"
								:placeholder="__('Aggiungi un commento privato per lo studente.')"
							/>
							<div class="flex justify-end gap-2 mt-2">
								<Button
									v-if="isTerminal"
									variant="outline"
									size="sm"
									:loading="evaluating"
									@click="onEvaluate"
								>
									{{ __('Valuta sessione') }}
								</Button>
								<Button
									variant="solid"
									size="sm"
									:loading="savingReview"
									:disabled="!reviewDraft.trim()"
									@click="onSaveReview"
								>
									{{ __('Salva nota') }}
								</Button>
							</div>
						</section>

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
const reviewDraft = ref('')
const savingReview = ref(false)

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
		reviewDraft.value = data?.debrief?.instructor_review || ''
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

const reviewRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.instructor_review_debrief',
	method: 'POST',
})

async function onSaveReview() {
	if (!reviewDraft.value.trim()) return
	savingReview.value = true
	try {
		await reviewRes.submit({ session_id: props.sessionId, review: reviewDraft.value })
		toast.success(__('Nota salvata.'))
		emit('review-saved')
	} catch (e) {
		toast.error(e.messages?.[0] || __('Salvataggio fallito'))
	} finally {
		savingReview.value = false
	}
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
