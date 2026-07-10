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
			<h1 class="text-2xl font-semibold text-ink-gray-9 mt-2">
				{{ __('Debrief della simulazione') }}
			</h1>
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
			<!-- Hero score -->
			<div
				class="border rounded-md p-5 mb-6"
				:class="debrief.passed ? 'card-success' : 'card-failure'"
			>
				<div class="flex items-center justify-between gap-4">
					<div>
						<p class="text-xs uppercase tracking-wide text-ink-gray-5 mb-1">
							{{ __('Punteggio complessivo') }}
						</p>
						<div class="text-4xl font-semibold text-ink-gray-9">
							{{ Math.round(debrief.overall_score || 0) }}
							<span class="text-base text-ink-gray-5">/100</span>
						</div>
					</div>
					<Badge
						:label="debrief.passed ? __('Superata') : __('Non superata')"
						:theme="debrief.passed ? 'green' : 'orange'"
					/>
				</div>
				<div
					v-if="status === 'needs_review'"
					class="mt-3 text-xs text-ink-orange-5"
				>
					{{ __('Il debrief richiede revisione manuale del docente.') }}
				</div>
			</div>

			<!-- Criterion scores -->
			<section v-if="debrief.criterion_scores?.length" class="mb-6">
				<h2 class="text-base font-semibold text-ink-gray-9 mb-3">
					{{ __('Punteggi per criterio') }}
				</h2>
				<div class="space-y-2">
					<div
						v-for="c in debrief.criterion_scores"
						:key="c.criterion_name"
						class="border border-outline-gray-2 rounded-md p-3 card"
					>
						<div
							class="flex items-center justify-between text-sm font-medium text-ink-gray-9"
						>
							<span>{{ c.criterion_name }}</span>
							<span>{{ c.score }} / {{ c.max_score || 10 }}</span>
						</div>
						<div
							v-if="c.evidence_quote"
							class="text-xs text-ink-gray-5 italic mt-1 border-l-2 border-outline-gray-2 pl-2"
						>
							"{{ c.evidence_quote }}"
						</div>
						<div v-if="c.note" class="text-xs text-ink-gray-5 mt-1">
							{{ c.note }}
						</div>
					</div>
				</div>
			</section>

			<!-- Strengths -->
			<section v-if="debrief.strengths?.length" class="mb-6">
				<h2 class="text-base font-semibold text-ink-gray-9 mb-3">
					{{ __('Punti di forza') }}
				</h2>
				<ul class="space-y-2">
					<li
						v-for="(s, i) in debrief.strengths"
						:key="i"
						class="border border-outline-green-2 bg-surface-green-1 rounded-md p-3 text-sm"
					>
						<div class="font-medium text-ink-gray-9">{{ s.title }}</div>
						<div v-if="s.detail" class="text-xs text-ink-gray-5 mt-1">
							{{ s.detail }}
						</div>
						<blockquote
							v-if="s.quote"
							class="text-xs italic mt-2 border-l-2 border-outline-green-3 pl-2"
						>
							"{{ s.quote }}"
						</blockquote>
					</li>
				</ul>
			</section>

			<!-- Improvements -->
			<section v-if="debrief.improvements?.length" class="mb-6">
				<h2 class="text-base font-semibold text-ink-gray-9 mb-3">
					{{ __('Aree di miglioramento') }}
				</h2>
				<ul class="space-y-2">
					<li
						v-for="(imp, i) in debrief.improvements"
						:key="i"
						class="card-failure text-sm"
					>
						<div class="font-medium text-ink-gray-9">{{ imp.title }}</div>
						<div v-if="imp.detail" class="text-xs text-ink-gray-5 mt-1">
							{{ imp.detail }}
						</div>
						<blockquote
							v-if="imp.quote"
							class="text-xs italic mt-2 border-l-2 border-outline-orange-3 pl-2"
						>
							"{{ imp.quote }}"
						</blockquote>
						<div v-if="imp.suggestion" class="text-xs text-ink-gray-9 mt-2">
							<span class="font-medium">{{ __('Suggerimento') }}:</span>
							{{ imp.suggestion }}
						</div>
					</li>
				</ul>
			</section>

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

			<!-- Instructor review -->
			<section v-if="debrief.instructor_review" class="mb-6">
				<h2 class="text-base font-semibold text-ink-gray-9 mb-3">
					{{ __('Nota del docente') }}
				</h2>
				<div
					class="text-sm border border-outline-gray-2 rounded-md p-3 bg-surface-gray-1 card text-ink-gray-9 whitespace-pre-wrap"
				>
					{{ debrief.instructor_review }}
				</div>
			</section>
		</template>
	</div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Badge } from 'frappe-ui'
import { useSimulationDebrief } from '@/oslms/composables/useSimulationDebrief.js'

const route = useRoute()
const sessionId = computed(() => route.params.sessionId)

const { debrief, status, timedOut } = useSimulationDebrief(sessionId)

const courseName = computed(() => debrief.value?.course || '')

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
