<template>
	<div class="p-5 sm:p-7 space-y-5">
		<!-- Header -->
		<div class="flex items-center justify-between">
			<div>
				<h2 class="text-lg font-semibold text-ink-gray-9">
					{{ __('Simulazioni AI') }}
				</h2>
				<p class="text-sm ">
					{{ __('Gestisci gli scenari di simulazione per questo corso.') }}
				</p>
			</div>
			<div class="flex items-center gap-2">
				<Button
					variant="ghost"
					@click="
						router.push({
							name: 'InstructorReports',
							query: { course: courseName },
						})
					"
				>
					{{ __('Apri report completo') }}
				</Button>
				<Button variant="solid" @click="openCreate">
					+ {{ __('Nuovo scenario') }}
				</Button>
			</div>
		</div>

		<!-- KPI -->
		<div class="grid grid-cols-3 gap-3">
			<div
				v-for="card in kpiCards"
				:key="card.label"
				class="border rounded-md p-4 bg-surface-menu-bar"
			>
				<div class="text-xs ">{{ card.label }}</div>
				<div class="text-2xl font-semibold text-ink-gray-9 mt-1">
					{{ card.value }}
				</div>
			</div>
		</div>

		<!-- Scenario list -->
		<div class="text-sm font-medium text-ink-gray-9">
			{{ __('Scenari') }}
		</div>
		<div class="border rounded-md overflow-hidden">
			<table class="w-full text-sm">
				<thead class="bg-surface-gray-2 text-xs text-ink-gray-7">
					<tr>
						<th class="text-left px-3 py-2">{{ __('Nome') }}</th>
						<th class="text-left px-3 py-2">{{ __('Lezione') }}</th>
						<th class="text-left px-3 py-2">{{ __('Difficoltà') }}</th>
						<th class="text-left px-3 py-2">{{ __('Modalità') }}</th>
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
						<td class="px-3 py-2 ">{{ s.scenario_name }}</td>
						<td class="px-3 py-2 ">
							{{ s.course_lesson || '—' }}
						</td>
						<td class="px-3 py-2">
							<Badge
								:label="s.difficulty"
								:theme="difficultyTheme(s.difficulty)"
							/>
						</td>
						<td class="px-3 py-2 capitalize ">{{ s.modality }}</td>
						<td class="px-3 py-2">
							<Badge :label="s.status" :theme="statusTheme(s.status)" />
						</td>
						<td class="px-3 py-2 text-right whitespace-nowrap">
							<Button size="sm" variant="ghost" @click="openEdit(s.name)">
								{{ __('Modifica') }}
							</Button>
							<Button
								size="sm"
								variant="ghost"
								@click="confirmDelete(s)"
								:disabled="s.status === 'Published'"
							>
								{{ __('Elimina') }}
							</Button>
						</td>
					</tr>
					<tr v-if="!scenarios.length">
						<td
							colspan="6"
							class="px-3 py-8 text-center "
						>
							{{ __('Nessuno scenario configurato per questo corso.') }}
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- Sessions report -->
		<div class="flex items-center justify-between pt-3">
			<div class="text-sm font-medium text-ink-gray-9">
				{{ __('Report sessioni') }}
			</div>
			<FormControl
				v-model.number="reportPeriodDays"
				type="select"
				:options="[
					{ label: __('Ultimi 7 giorni'), value: 7 },
					{ label: __('Ultimi 30 giorni'), value: 30 },
					{ label: __('Ultimi 90 giorni'), value: 90 },
					{ label: __('Ultimi 365 giorni'), value: 365 },
				]"
			/>
		</div>
		<div class="border rounded-md overflow-hidden">
			<table class="w-full text-sm">
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
						<td class="px-3 py-2 ">{{ s.student }}</td>
						<td class="px-3 py-2 ">{{ s.scenario }}</td>
						<td class="px-3 py-2 ">
							{{ formatDate(s.started_at) }}
						</td>
						<td class="px-3 py-2">
							<Badge
								:label="s.status"
								:theme="sessionStatusTheme(s.status)"
							/>
						</td>
						<td class="px-3 py-2 text-right ">
							<span v-if="s.overall_score !== null && s.overall_score !== undefined">
								{{ Math.round(s.overall_score) }}
							</span>
							<span v-else class="">—</span>
						</td>
						<td class="px-3 py-2 text-right whitespace-nowrap">
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
						<td
							colspan="6"
							class="px-3 py-8 text-center "
						>
							{{ __('Nessuna sessione nel periodo selezionato.') }}
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<TranscriptDrawer
			v-model="transcriptOpen"
			:sessionId="transcriptSession"
			@review-saved="reportRes.submit()"
		/>
	</div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Button, FormControl, createResource, toast } from 'frappe-ui'
import TranscriptDrawer from '@/oslms/components/simulations/TranscriptDrawer.vue'

const props = defineProps({
	course: { type: Object, required: true },
})

const router = useRouter()
const courseName = computed(() => props.course?.data?.name)

const scenariosRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.list_my_scenarios',
	auto: true,
	makeParams() {
		return { course: courseName.value }
	},
})
const scenarios = computed(() => scenariosRes.data || [])

const kpiCards = computed(() => {
	const byStatus = (s) => scenarios.value.filter((x) => x.status === s).length
	return [
		{ label: __('Pubblicati'), value: byStatus('Published') },
		{ label: __('Bozze'), value: byStatus('Draft') },
		{ label: __('Archiviati'), value: byStatus('Archived') },
	]
})

function openCreate() {
	router.push({
		name: 'ScenarioCreate',
		query: { course: courseName.value },
	})
}
function openEdit(name) {
	router.push({
		name: 'ScenarioEdit',
		params: { name },
		query: { course: courseName.value },
	})
}

const deleteRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.delete_scenario',
	method: 'POST',
})

async function confirmDelete(scenario) {
	if (
		!window.confirm(
			__('Eliminare lo scenario "{0}"?', [scenario.scenario_name]),
		)
	)
		return
	try {
		await deleteRes.submit({ name: scenario.name })
		toast.success(__('Scenario eliminato'))
		scenariosRes.submit()
	} catch (e) {
		toast.error(e.messages?.[0] || __('Eliminazione fallita'))
	}
}

function difficultyTheme(d) {
	return { easy: 'green', medium: 'blue', hard: 'orange' }[d] || 'gray'
}

function statusTheme(s) {
	return (
		{ Draft: 'gray', Published: 'green', Archived: 'orange' }[s] || 'gray'
	)
}

// ---- Sessions report ----

const reportPeriodDays = ref(30)
const transcriptOpen = ref(false)
const transcriptSession = ref('')

const reportRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.instructor_report',
	makeParams() {
		return {
			course: courseName.value,
			period_days: reportPeriodDays.value,
		}
	},
})
const sessions = computed(() => reportRes.data?.sessions || [])

watch(
	[courseName, reportPeriodDays],
	() => {
		if (courseName.value) reportRes.submit()
	},
	{ immediate: true },
)

function openTranscript(sessionId) {
	transcriptSession.value = sessionId
	transcriptOpen.value = true
}

function sessionStatusTheme(s) {
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
</script>
