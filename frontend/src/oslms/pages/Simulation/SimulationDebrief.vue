<template>
	<div class="max-w-3xl mx-auto p-6">
		<!-- Header -->
		<div class="mb-6">
			<div class="flex items-center gap-4">
				<router-link
					:to="{ name: 'SimulationPlay', params: { sessionId } }"
					class="text-sm text-ink-gray-5 hover:underline"
				>
					← {{ __('Trascrizione') }}
				</router-link>
				<router-link
					v-if="courseName"
					:to="{ name: 'CourseDetail', params: { courseName } }"
					class="text-sm text-ink-gray-5 hover:underline"
				>
					← {{ __('Torna al corso') }}
				</router-link>
			</div>
			<div class="flex flex-wrap items-center justify-between gap-3 mt-2">
				<h1 class="text-2xl font-semibold text-ink-gray-9">
					{{ __('Debrief della simulazione') }}
				</h1>
				<Button
					v-if="debrief?.can_retry"
					:loading="cloneRes.loading"
					@click="onRetry"
				>
					<template #prefix><RotateCcw class="size-4" /></template>
					{{ __('Rifai la simulazione') }}
				</Button>
			</div>
		</div>

		<!-- Status states -->
		<div
			v-if="status === 'not_started'"
			class="border border-outline-gray-2 rounded-md p-4 text-sm text-ink-gray-5"
		>
			{{
				__(
					'La sessione è ancora in corso. Termina la simulazione per generare il debrief.',
				)
			}}
		</div>

		<div
			v-else-if="status === 'pending'"
			class="border border-outline-gray-2 rounded-md p-6 text-center card"
		>
			<div class="text-base font-medium text-ink-gray-9 mb-1">
				{{ __('Stiamo preparando il tuo debrief…') }}
			</div>
			<div class="text-xs text-ink-gray-5">
				{{ __('Di solito richiede meno di 30 secondi.') }}
			</div>
			<div v-if="timedOut" class="mt-3 text-xs text-ink-orange-5">
				{{
					__(
						'Sta impiegando più tempo del previsto. Aggiorna la pagina tra un minuto.',
					)
				}}
			</div>
		</div>

		<div
			v-else-if="status === 'failed'"
			class="border border-outline-red-2 bg-surface-red-1 rounded-md p-4 text-sm text-ink-red-5"
		>
			{{
				__(
					'La generazione del debrief è fallita. Il docente potrà rivedere manualmente questa sessione.',
				)
			}}
		</div>

		<template v-else-if="debrief">
			<!-- Where the teacher's review stands: published (with the outcome on
			     simulations that have one), awaiting the outcome, or not reviewed. -->
			<div
				v-if="debrief.review_state === 'published' && teacherVersion?.outcome"
				class="rounded-md p-4 mb-6 text-sm border"
				:class="
					teacherVersion.outcome === 'Passed'
						? 'border-outline-green-2 bg-surface-green-1'
						: 'border-outline-red-2 bg-surface-red-1'
				"
			>
				<div class="font-semibold text-ink-gray-9">
					{{
						teacherVersion.outcome === 'Passed'
							? __('Simulazione superata')
							: __('Simulazione non superata')
					}}
				</div>
				<div
					v-if="teacherVersion.outcome_reason"
					class="mt-1 text-ink-gray-7 whitespace-pre-wrap"
				>
					{{ teacherVersion.outcome_reason }}
				</div>
				<div
					v-if="teacherVersion.outcome_decided_by_name"
					class="mt-2 text-xs text-ink-gray-5"
				>
					{{
						__('Deciso da {0} il {1}').format(
							teacherVersion.outcome_decided_by_name,
							formatDate(teacherVersion.outcome_decided_at),
						)
					}}
				</div>
			</div>
			<div
				v-else-if="debrief.review_state === 'awaiting_outcome'"
				class="border border-outline-orange-2 bg-surface-orange-1 rounded-md p-4 mb-6 text-sm text-ink-gray-9"
			>
				{{
					__(
						'In attesa di valutazione: un docente deciderà se hai superato la simulazione.',
					)
				}}
			</div>
			<div
				v-else-if="debrief.review_state === 'not_reviewed'"
				class="border border-outline-gray-2 rounded-md p-4 mb-6 text-sm text-ink-gray-5"
			>
				{{ __('Non ancora rivista da un docente.') }}
			</div>

			<TabButtons
				v-if="teacherVersion"
				v-model="activeTab"
				:buttons="tabs"
				class="w-fit mb-6"
			/>

			<!-- Teacher version, once published -->
			<template v-if="teacherVersion && activeTab === 'teacher'">
				<DebriefVersion
					:version="teacherVersion"
					:score-note="__('Punteggio del docente.')"
				/>
				<p
					v-if="teacherVersion.published_by_name"
					class="text-xs text-ink-gray-5"
				>
					{{
						__('Pubblicata da {0} il {1}').format(
							teacherVersion.published_by_name,
							formatDate(teacherVersion.published_at),
						)
					}}
				</p>
			</template>

			<!-- AI version: never edited by a person -->
			<template v-else>
				<div class="border border-outline-gray-2 rounded-md p-5 mb-6 card">
					<p class="text-sm text-ink-gray-7">
						{{
							__(
								'Ecco i consigli del coach per aiutarti a migliorare. Qui trovi i tuoi punti di forza, le aree su cui lavorare e alcune indicazioni pratiche.',
							)
						}}
					</p>
					<!-- AI disclosure (AI Act art. 50). -->
					<p class="mt-2 text-xs text-ink-gray-5">
						{{
							__(
								"Questo report è generato da un'intelligenza artificiale: il punteggio è indicativo e non decide l'esito. Il tuo docente può rivederlo.",
							)
						}}
					</p>
					<div
						v-if="status === 'needs_review'"
						class="mt-3 text-xs text-ink-orange-5"
					>
						{{ __('Il debrief richiede revisione manuale del docente.') }}
					</div>
				</div>

				<DebriefVersion
					:version="debrief"
					:score-note="__('Punteggio indicativo dell\'AI.')"
				/>

				<!-- Behavioral analysis -->
				<section v-if="debrief.behavioral_analysis" class="mb-6">
					<h2 class="text-base font-semibold text-ink-gray-9 mb-3">
						{{ __('Pattern comportamentali') }}
					</h2>
					<div
						class="text-sm text-ink-gray-7 whitespace-pre-wrap border border-outline-gray-2 rounded-md p-3 card"
					>
						{{ debrief.behavioral_analysis }}
					</div>
				</section>

				<!-- Recommendations -->
				<section v-if="debrief.recommended_content?.length" class="mb-6">
					<h2 class="text-base font-semibold text-ink-gray-9 mb-3">
						{{ __('Lezioni consigliate da rivedere') }}
					</h2>
					<div class="space-y-2">
						<router-link
							v-for="(r, i) in debrief.recommended_content"
							:key="i"
							:to="lessonRoute(r.lesson)"
							class="block rounded-md p-3 text-sm card"
						>
							<div class="font-medium text-ink-gray-9">
								{{ r.title || r.lesson }}
							</div>
							<div v-if="r.why" class="text-xs text-ink-gray-5 mt-1">
								{{ r.why }}
							</div>
						</router-link>
					</div>
				</section>
			</template>
		</template>

		<!-- "Rifai la simulazione": a new attempt of the same scenario
		     (clone_session, same start limits), opened on its briefing. -->
		<Dialog
			v-model="briefingOpen"
			:options="{ title: __('Preparati alla simulazione'), size: 'lg' }"
		>
			<template #body-content>
				<SimulationBriefing
					:brief="retry.brief"
					:modality="retry.modality"
					:starting="beginning"
					@begin="onBegin"
				/>
			</template>
		</Dialog>
		<Dialog
			v-if="voiceSessionId"
			v-model="voiceDialogOpen"
			:options="{ title: __('Simulazione vocale'), size: 'lg' }"
		>
			<template #body-content>
				<VoiceSession :session-id="voiceSessionId" @ended="clearVoice" />
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Button, Dialog, TabButtons, createResource, toast } from 'frappe-ui'
import { RotateCcw } from 'lucide-vue-next'
import { useSimulationDebrief } from '@/oslms/composables/useSimulationDebrief.js'
import { useSimulationBegin } from '@/oslms/composables/useSimulationBegin'
import DebriefVersion from '@/oslms/components/simulations/DebriefVersion.vue'
import SimulationBriefing from '@/oslms/components/simulations/SimulationBriefing.vue'
import VoiceSession from '@/oslms/components/simulations/VoiceSession.vue'

const route = useRoute()
const sessionId = computed(() => route.params.sessionId)

const { debrief, status, timedOut } = useSimulationDebrief(sessionId)

const courseName = computed(() => debrief.value?.course || '')

// This page shows the teacher version only once published, as its student
// sees it, even to a reviewer (who edits drafts in the transcript drawer).
const teacherVersion = computed(() =>
	debrief.value?.review_state === 'published'
		? debrief.value?.teacher_version || null
		: null,
)

const activeTab = ref('teacher')
// Getters: __() must run at render time, after translations load.
const tabs = [
	{
		value: 'teacher',
		get label() {
			return __('Docente')
		},
	},
	{
		value: 'ai',
		get label() {
			return __('AI')
		},
	},
]
watch(sessionId, () => {
	activeTab.value = 'teacher'
})

const cloneRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.clone_session',
	method: 'POST',
})
const briefingOpen = ref(false)
const retry = reactive({ sessionId: null, brief: '', modality: 'chat' })
const { beginning, voiceSessionId, begin, clearVoice } = useSimulationBegin()
const voiceDialogOpen = computed({
	get: () => Boolean(voiceSessionId.value),
	set: (v) => {
		if (!v) clearVoice()
	},
})

async function onRetry() {
	try {
		const res = await cloneRes.submit({ session_id: sessionId.value })
		retry.sessionId = res.session_id
		retry.brief = res.brief
		retry.modality = res.modality
		briefingOpen.value = true
	} catch (e) {
		toast.error(e.messages?.[0] || e.message || String(e))
	}
}

async function onBegin(mode) {
	briefingOpen.value = false
	await begin({ sessionId: retry.sessionId, mode })
}

function formatDate(dt) {
	if (!dt) return '—'
	const d = new Date(dt)
	const pad = (n) => String(n).padStart(2, '0')
	return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`
}

function lessonRoute(lessonName) {
	if (!lessonName) return { name: 'Courses' }
	// `lessonName` is a Course Lesson docname; the LMS lesson URL is built
	// from the course + chapter/lesson index. We don't know those here without
	// extra lookups, so we fall back to the Lessons list of the course. The
	// instructor-side review can deep-link to the lesson directly via the
	// LMSA-aware overrides later (phase 2 niceties).
	return { name: 'Courses' }
}
</script>
