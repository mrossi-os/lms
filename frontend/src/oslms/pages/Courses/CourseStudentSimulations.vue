<!-- frontend/src/oslms/pages/Courses/CourseStudentSimulations.vue -->
<template>
	<div class="p-5 space-y-8 overflow-y-auto">
		<!-- New simulation -->
		<section>
			<div class="flex items-center justify-between mb-3">
				<h2 class="text-lg font-semibold text-ink-gray-9">
					{{ __('Avvia una nuova simulazione') }}
				</h2>
				<Button
					variant="solid"
					:disabled="!scenariosRes.data?.length"
					@click="launcherOpen = true"
				>
					<template #prefix><span class="lucide-bot size-4" /></template>
					{{ __('Nuova simulazione') }}
				</Button>
			</div>
			<div v-if="!scenariosRes.data?.length" class="text-sm text-ink-gray-5">
				{{ __('Nessuno scenario disponibile per questo corso.') }}
			</div>
		</section>

		<!-- History -->
		<section>
			<h2 class="text-lg font-semibold text-ink-gray-9 mb-3">
				{{ __('Le tue simulazioni') }}
			</h2>
			<div v-if="!sessionsRes.data?.length" class="text-sm text-ink-gray-5">
				{{ __('Non hai ancora svolto simulazioni per questo corso.') }}
			</div>
			<table v-else class="w-full text-sm">
				<thead class="text-left text-ink-gray-5">
					<tr>
						<th class="py-2">{{ __('Scenario') }}</th>
						<th>{{ __('Modalità') }}</th>
						<th>{{ __('Stato') }}</th>
						<th>{{ __('Data') }}</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="s in sessionsRes.data"
						:key="s.name"
						class="border-t border-outline-gray-1"
					>
						<td class="py-2">{{ s.scenario_name }}</td>
						<td class="capitalize">{{ s.modality }}</td>
						<td><Badge :label="s.status" :theme="statusTheme(s.status)" /></td>
						<td>{{ formatDate(s.started_at) }}</td>
						<td class="text-right">
							<div class="flex gap-2 justify-end">
								<Button
									v-if="isTerminal(s.status)"
									variant="subtle"
									size="sm"
									@click="goDebrief(s.name)"
								>
									{{ __('Rivedi') }}
								</Button>
								<Button
									v-if="isTerminal(s.status)"
									variant="outline"
									size="sm"
									:loading="busyId === s.name"
									@click="onRestart(s.name)"
								>
									{{ __('Riavvia') }}
								</Button>
								<Button
									v-else-if="s.status === 'Ready'"
									variant="solid"
									size="sm"
									:loading="busyId === s.name"
									@click="onContinueReady(s)"
								>
									{{ __('Continua') }}
								</Button>
								<Button
									v-else-if="
										s.status === 'In Progress' && s.modality === 'chat'
									"
									variant="solid"
									size="sm"
									@click="goPlay(s.name)"
								>
									{{ __('Riprendi') }}
								</Button>
								<Button
									v-else-if="
										s.status === 'In Progress' && s.modality === 'voice'
									"
									variant="subtle"
									size="sm"
									@click="goPlay(s.name)"
								>
									{{ __('Rivedi trascrizione') }}
								</Button>
							</div>
						</td>
					</tr>
				</tbody>
			</table>
		</section>

		<!-- Launcher for new sessions (own briefing flow inside) -->
		<SimulationLauncher
			v-model="launcherOpen"
			:scenarios="scenariosRes.data || []"
			@started="onLauncherStarted"
		/>

		<!-- Briefing dialog for restart / continue-ready -->
		<Dialog
			v-model="briefingOpen"
			:options="{ title: __('Preparati alla simulazione'), size: 'lg' }"
		>
			<template #body-content>
				<SimulationBriefing
					:brief="briefing.brief"
					:modality="briefing.modality"
					:starting="beginning"
					@begin="onBriefBegin"
				/>
			</template>
		</Dialog>

		<!-- Voice runtime overlay -->
		<Dialog
			v-if="voiceSessionId"
			v-model="voiceDialogOpen"
			:options="{ title: __('Simulazione vocale'), size: 'lg' }"
		>
			<template #body-content>
				<VoiceSession :session-id="voiceSessionId" @ended="onVoiceEnded" />
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Badge, Button, Dialog, createResource, toast } from 'frappe-ui'
import SimulationLauncher from '@/oslms/components/simulations/SimulationLauncher.vue'
import SimulationBriefing from '@/oslms/components/simulations/SimulationBriefing.vue'
import VoiceSession from '@/oslms/components/simulations/VoiceSession.vue'
import { useSimulationBegin } from '@/oslms/composables/useSimulationBegin'

const props = defineProps({
	// CourseDetail passes the `course` Resource object.
	course: { type: Object, required: true },
})

const router = useRouter()
const courseName = computed(() => props.course?.data?.name)

const launcherOpen = ref(false)
const briefingOpen = ref(false)
const briefing = reactive({ sessionId: null, brief: '', modality: 'chat' })
const busyId = ref(null)

const { beginning, voiceSessionId, begin, clearVoice } = useSimulationBegin()
const voiceDialogOpen = computed({
	get: () => Boolean(voiceSessionId.value),
	set: (v) => {
		if (!v) clearVoice()
	},
})

const scenariosRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.list_scenarios',
	method: 'GET',
	makeParams: () => ({ course: courseName.value }),
	auto: true,
})

const sessionsRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.list_my_sessions',
	method: 'GET',
	makeParams: () => ({ course: courseName.value }),
	auto: true,
})

const cloneRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.clone_session',
	method: 'POST',
})
const getSessionRes = createResource({
	// POST (not GET) so .submit({session_id}) reliably transmits the param;
	// get_session is an unrestricted @frappe.whitelist() that reads form_dict.
	url: 'os_lms.os_lms.ai.simulations.api.get_session',
	method: 'POST',
})

const TERMINAL = ['Completed', 'Abandoned', 'Error', 'Needs Review']
function isTerminal(status) {
	return TERMINAL.includes(status)
}
function statusTheme(status) {
	return (
		{
			Ready: 'gray',
			'In Progress': 'blue',
			Completed: 'green',
			Abandoned: 'orange',
			Error: 'red',
			'Needs Review': 'orange',
		}[status] || 'gray'
	)
}
function formatDate(dt) {
	return dt ? new Date(dt).toLocaleString() : '—'
}

function goPlay(sessionId) {
	router.push({ name: 'SimulationPlay', params: { sessionId } })
}
function goDebrief(sessionId) {
	router.push({ name: 'SimulationDebrief', params: { sessionId } })
}

async function onRestart(sessionId) {
	busyId.value = sessionId
	try {
		const res = await cloneRes.submit({ session_id: sessionId })
		openBriefing(res.session_id, res.brief, res.modality)
	} catch (e) {
		toast.error(e.messages?.[0] || e.message || String(e))
	} finally {
		busyId.value = null
	}
}

async function onContinueReady(session) {
	busyId.value = session.name
	try {
		const res = await getSessionRes.submit({ session_id: session.name })
		openBriefing(
			session.name,
			res?.session?.student_brief || '',
			session.modality,
		)
	} catch (e) {
		toast.error(e.messages?.[0] || e.message || String(e))
	} finally {
		busyId.value = null
	}
}

function openBriefing(sessionId, brief, modality) {
	briefing.sessionId = sessionId
	briefing.brief = brief
	briefing.modality = modality
	briefingOpen.value = true
}

async function onBriefBegin(mode) {
	briefingOpen.value = false
	await begin({ sessionId: briefing.sessionId, mode })
}

function onLauncherStarted() {
	sessionsRes.reload()
}
function onVoiceEnded() {
	clearVoice()
	sessionsRes.reload()
}
</script>
