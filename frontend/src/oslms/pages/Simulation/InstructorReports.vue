<template>
	<LayoutHeader>
		<template #left-header>
			<Breadcrumbs :items="breadcrumbs" />
		</template>
		<template #right-header>
			<div class="flex gap-2">
				<Button @click="router.push({ name: 'EvaluationSchemas' })">
					{{ __('Schemi di valutazione') }}
				</Button>
				<Button variant="solid" @click="newScenario"
					>+ {{ __('Scenario') }}</Button
				>
			</div>
		</template>
	</LayoutHeader>
	<div class="p-5 pb-10">
		<Tabs v-model="activeTab" :tabs="tabs">
			<template #tab-panel="{ tab }">
				<!-- REPORT -->
				<div v-if="tab.name === 'report'" class="space-y-6">
					<!-- Filters -->
					<div class="grid grid-cols-4 gap-3 items-end">
						<FormControl
							v-model="filters.course"
							type="select"
							:label="__('Corso')"
							:options="courseFilterOptions"
						/>
						<FormControl
							v-model.number="filters.period_days"
							type="select"
							:label="__('Periodo')"
							:options="[
								{ label: __('Ultimi 7 giorni'), value: 7 },
								{ label: __('Ultimi 30 giorni'), value: 30 },
								{ label: __('Ultimi 90 giorni'), value: 90 },
								{ label: __('Ultimi 365 giorni'), value: 365 },
							]"
						/>
						<FormControl
							v-model="filters.student"
							type="text"
							:label="__('Studente (email)')"
						/>
						<Button @click="report.submit()">{{ __('Aggiorna') }}</Button>
					</div>

					<!-- KPIs -->
					<div v-if="report.data" class="grid grid-cols-4 gap-3">
						<div
							v-for="card in kpiCards"
							:key="card.label"
							class="border rounded-md p-4 bg-surface-sidebar"
						>
							<div class="text-xs text-ink-gray-5">{{ card.label }}</div>
							<div class="text-4xl-semibold text-ink-gray-9 mt-1">
								{{ card.value }}
							</div>
						</div>
					</div>

					<!-- Distribution -->
					<div v-if="distribution.length" class="border rounded-md card">
						<div class="text-sm-medium text-ink-gray-9 mb-3">
							{{ __('Distribuzione punteggi') }}
						</div>
						<div class="flex items-end gap-3 h-32">
							<div
								v-for="b in distribution"
								:key="b.label"
								class="flex-1 flex flex-col items-center"
							>
								<div class="text-xs text-ink-gray-5">{{ b.count }}</div>
								<div
									class="w-full bg-surface-blue-3 rounded-t"
									:style="{ height: `${distributionHeight(b)}%` }"
								></div>
								<div class="text-xs text-ink-gray-5 mt-1">{{ b.label }}</div>
							</div>
						</div>
					</div>

					<!-- Top improvements -->
					<div v-if="topImprovements.length" class="border rounded-md p-4">
						<div class="text-sm-medium text-ink-gray-9 mb-3">
							{{ __('Aree di miglioramento più frequenti') }}
						</div>
						<ul class="text-sm space-y-1">
							<li
								v-for="row in topImprovements"
								:key="row.title"
								class="flex justify-between"
							>
								<span>{{ row.title }}</span>
								<span class="text-ink-gray-5">{{ row.occurrences }}×</span>
							</li>
						</ul>
					</div>

					<!-- Sessions table -->
					<div class="border rounded-md overflow-hidden">
						<table class="w-full text-sm os-table-view">
							<thead class="bg-surface-gray-2 text-xs text-ink-gray-7">
								<tr>
									<th class="text-left px-3 py-2">{{ __('Studente') }}</th>
									<th class="text-left px-3 py-2">{{ __('Scenario') }}</th>
									<th class="text-left px-3 py-2">{{ __('Inizio') }}</th>
									<th class="text-left px-3 py-2">{{ __('Stato') }}</th>
									<th class="text-right px-3 py-2">{{ __('Punteggio') }}</th>
									<th></th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="s in sessions"
									:key="s.name"
									class="border-t hover:bg-surface-gray-1"
								>
									<td class="px-3 py-2">{{ s.student }}</td>
									<td class="px-3 py-2">{{ s.scenario }}</td>
									<td class="px-3 py-2 text-ink-gray-5">
										{{ formatDate(s.started_at) }}
									</td>
									<td class="px-3 py-2">
										<Badge :label="s.status" :theme="statusTheme(s.status)" />
									</td>
									<td class="px-3 py-2 text-right">
										<span v-if="s.overall_score !== null">
											{{ Math.round(s.overall_score) }}
										</span>
										<span v-else class="text-ink-gray-5">—</span>
									</td>
									<td class="px-3 py-2">
										<Button
											size="sm"
											variant="ghost"
											@click="openTranscript(s.name)"
										>
											{{ __('Apri') }}
										</Button>
									</td>
								</tr>
								<tr v-if="!sessions.length">
									<td colspan="6" class="px-3 py-6 text-center text-ink-gray-5">
										{{ __('Nessuna sessione nel periodo selezionato.') }}
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>

				<!-- SCENARIOS -->
				<div v-else-if="tab.name === 'scenarios'" class="space-y-3">
					<div class="flex items-center justify-between">
						<FormControl
							v-model="scenarioCourseFilter"
							type="select"
							:options="courseFilterOptions"
							:label="__('Corso')"
						/>
						<Button variant="solid" @click="newScenario"
							>+ {{ __('Nuovo scenario') }}</Button
						>
					</div>
					<div class="border rounded-md overflow-hidden">
						<table class="w-full text-sm os-table-view">
							<thead class="bg-surface-gray-2 text-xs text-ink-gray-7">
								<tr>
									<th class="text-left px-3 py-2">{{ __('Nome') }}</th>
									<th class="text-left px-3 py-2">{{ __('Corso') }}</th>
									<th class="text-left px-3 py-2">{{ __('Difficoltà') }}</th>
									<th class="text-left px-3 py-2">{{ __('Stato') }}</th>
									<th></th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="s in scenarios"
									:key="s.name"
									class="border-t hover:bg-surface-gray-1"
								>
									<td class="px-3 py-2">{{ s.scenario_name }}</td>
									<td class="px-3 py-2 text-ink-gray-5">{{ s.lms_course }}</td>
									<td class="px-3 py-2">
										<Badge
											:label="s.difficulty"
											:theme="difficultyTheme(s.difficulty)"
										/>
									</td>
									<td class="px-3 py-2">
										<Badge
											:label="s.status"
											:theme="scenarioStatusTheme(s.status)"
										/>
									</td>
									<td class="px-3 py-2 text-right">
										<Button
											size="sm"
											variant="outline"
											@click="editScenario(s.name)"
										>
											{{ __('Modifica') }}
										</Button>
									</td>
								</tr>
								<tr v-if="!scenarios.length">
									<td colspan="5" class="px-3 py-6 text-center text-ink-gray-5">
										{{ __('Nessuno scenario.') }}
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</template>
		</Tabs>

		<TranscriptDrawer
			v-model="transcriptOpen"
			:sessionId="transcriptSession"
			@review-saved="report.submit()"
		/>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
	Badge,
	Breadcrumbs,
	Button,
	FormControl,
	Tabs,
	createResource,
} from 'frappe-ui'
import LayoutHeader from '@/components/Layouts/LayoutHeader.vue'
import TranscriptDrawer from '@/oslms/components/simulations/TranscriptDrawer.vue'

const route = useRoute()
const router = useRouter()
const activeTab = ref('report')
const tabs = [
	{ name: 'report', label: __('Report') },
	{ name: 'scenarios', label: __('Scenari') },
]

const breadcrumbs = computed(() => [
	{
		label: __('Pannello simulazioni'),
		route: { name: 'InstructorReports' },
	},
])

onMounted(() => {
	const requestedTab = route.query.tab
	if (requestedTab && tabs.some((t) => t.name === requestedTab)) {
		activeTab.value = requestedTab
	}
	const requestedCourse = route.query.course
	if (requestedCourse) {
		filters.value.course = requestedCourse
		scenarioCourseFilter.value = requestedCourse
	}
})

// ---- shared course list ----
const coursesRes = createResource({
	url: 'frappe.client.get_list',
	auto: true,
	makeParams() {
		return {
			doctype: 'LMS Course',
			fields: ['name', 'title'],
			limit_page_length: 500,
		}
	},
})
const courseFilterOptions = computed(() => [
	{ label: __('Tutti'), value: '' },
	...(coursesRes.data || []).map((c) => ({
		label: c.title || c.name,
		value: c.name,
	})),
])

// ---- REPORT ----
const filters = ref({ course: '', period_days: 30, student: '' })

const report = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.instructor_report',
	auto: true,
	makeParams() {
		return {
			course: filters.value.course || null,
			student: filters.value.student || null,
			period_days: filters.value.period_days || 30,
		}
	},
})

const kpi = computed(() => report.data?.kpi || {})
const kpiCards = computed(() => {
	const k = kpi.value
	return [
		{ label: __('Sessioni'), value: k.total_sessions ?? 0 },
		{ label: __('Completate'), value: k.completed_sessions ?? 0 },
		{
			label: __('Punteggio medio'),
			value:
				k.avg_score !== null && k.avg_score !== undefined ? k.avg_score : '—',
		},
		{
			label: __('Pass rate'),
			value:
				k.pass_rate !== null && k.pass_rate !== undefined
					? `${k.pass_rate}%`
					: '—',
		},
	]
})
const distribution = computed(() => report.data?.score_distribution || [])
const topImprovements = computed(
	() => report.data?.top_improvement_titles || [],
)
const sessions = computed(() => report.data?.sessions || [])

const distributionMax = computed(() =>
	Math.max(1, ...distribution.value.map((b) => b.count)),
)

function distributionHeight(bucket) {
	return Math.max(2, (bucket.count / distributionMax.value) * 100)
}

// ---- SCENARIOS ----
const scenarioCourseFilter = ref('')
const scenariosRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.list_my_scenarios',
	auto: true,
	makeParams() {
		return { course: scenarioCourseFilter.value || null }
	},
})
const scenarios = computed(() => scenariosRes.data || [])

function newScenario() {
	const query = { from: 'admin' }
	if (scenarioCourseFilter.value) query.course = scenarioCourseFilter.value
	router.push({ name: 'ScenarioCreate', query })
}
function editScenario(name) {
	const query = { from: 'admin' }
	if (scenarioCourseFilter.value) query.course = scenarioCourseFilter.value
	router.push({ name: 'ScenarioEdit', params: { name }, query })
}

// ---- DRILL-DOWN ----
const transcriptOpen = ref(false)
const transcriptSession = ref('')

function openTranscript(sessionId) {
	transcriptSession.value = sessionId
	transcriptOpen.value = true
}

// ---- formatters ----
function formatDate(dt) {
	if (!dt) return ''
	const d = new Date(dt)
	return d.toLocaleString(undefined, {
		month: 'short',
		day: 'numeric',
		hour: '2-digit',
		minute: '2-digit',
	})
}

function statusTheme(s) {
	return (
		{
			'In Progress': 'blue',
			Completed: 'green',
			Abandoned: 'gray',
			Error: 'red',
			'Needs Review': 'orange',
		}[s] || 'gray'
	)
}

function difficultyTheme(d) {
	return { easy: 'green', medium: 'blue', hard: 'orange' }[d] || 'gray'
}

function scenarioStatusTheme(s) {
	return { Draft: 'gray', Published: 'green', Archived: 'orange' }[s] || 'gray'
}
</script>
