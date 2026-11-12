<template>
	<div class="space-y-5">
		<section class="space-y-4 rounded-md border card">
			<h2 class="text-base font-semibold text-ink-gray-9">
				{{ __('New export') }}
			</h2>
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
				<FormControl
					v-model="form.report"
					type="select"
					:options="reportOptions"
					:label="__('Report')"
					:description="reportDescription"
					variant="outline"
				/>
				<FormControl
					v-model="form.file_format"
					type="select"
					:options="formatOptions"
					:label="__('Format')"
					variant="outline"
				/>
				<Link
					v-model="form.course"
					doctype="LMS Course"
					:label="needsCourse ? __('Course (required)') : __('Course')"
					:placeholder="needsCourse ? '' : __('All courses')"
					variant="outline"
				/>
				<Link
					v-if="!needsCourse"
					v-model="form.user"
					doctype="User"
					:label="__('Student')"
					:placeholder="__('All students')"
					variant="outline"
				/>
				<FormControl
					v-model="form.from_date"
					type="date"
					:placeholder="__('Select date')"
					:label="__('From')"
					variant="outline"
				/>
				<FormControl
					v-model="form.to_date"
					type="date"
					:placeholder="__('Select date')"
					:label="__('To')"
					variant="outline"
				/>
			</div>
			<p class="text-p-sm text-ink-gray-6">
				{{
					__(
						'Every export is recorded in the audit with who generated it and the fingerprint of the file. The file ends with the last daily seal it falls under.',
					)
				}}
			</p>
			<div class="flex justify-end">
				<Button
					variant="solid"
					:loading="starting"
					:disabled="needsCourse && !form.course"
					@click="start"
				>
					<template #prefix>
						<span class="lucide-download size-4" />
					</template>
					{{ __('Generate') }}
				</Button>
			</div>
		</section>

		<section class="space-y-3 rounded-md border card">
			<div class="flex items-center justify-between">
				<h2 class="text-base font-semibold text-ink-gray-9">
					{{ __('Generated reports') }}
				</h2>
				<button
					class="text-sm text-ink-gray-6 hover:text-ink-gray-9 disabled:opacity-50"
					:disabled="exportsList.loading"
					@click="exportsList.reload()"
				>
					{{ exportsList.loading ? __('Refreshing…') : __('Refresh') }}
				</button>
			</div>
			<div
				v-if="!exportsList.data?.length"
				class="py-6 text-center text-sm text-ink-gray-5"
			>
				{{ __('No reports yet') }}
			</div>
			<div v-else class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="text-left text-ink-gray-5">
							<th class="py-2 pr-3 font-medium">{{ __('Report') }}</th>
							<th class="py-2 pr-3 font-medium">{{ __('Format') }}</th>
							<th class="py-2 pr-3 font-medium">{{ __('Date') }}</th>
							<th class="py-2 pr-3 font-medium">{{ __('Rows') }}</th>
							<th class="py-2 pr-3 font-medium">{{ __('Status') }}</th>
							<th class="py-2 text-right font-medium">{{ __('Actions') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="row in exportsList.data"
							:key="row.name"
							class="border-t border-outline-gray-1"
						>
							<td class="py-2 pr-3 text-ink-gray-8">
								{{ exportLabel(row.report_type) }}
							</td>
							<td class="py-2 pr-3 uppercase text-ink-gray-6">{{ row.file_format }}</td>
							<td class="py-2 pr-3 text-ink-gray-6">{{ formatDateTime(row.creation) }}</td>
							<td class="py-2 pr-3 text-ink-gray-6">
								{{ row.status === 'Ready' ? row.row_count : '' }}
							</td>
							<td class="py-2 pr-3">
								<Badge
									:theme="statusTheme(row.status)"
									:label="statusLabel(row.status)"
								/>
							</td>
							<td class="py-2">
								<div class="flex items-center justify-end gap-1">
									<Button
										v-if="row.status === 'Ready'"
										variant="subtle"
										@click="openExternal(row.file)"
									>
										{{ __('Download') }}
									</Button>
									<Button variant="ghost" theme="red" @click="remove(row)">
										{{ __('Delete') }}
									</Button>
								</div>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</section>
	</div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, reactive, ref } from 'vue'
import {
	Badge,
	Button,
	FormControl,
	call,
	createResource,
	toast,
} from 'frappe-ui'
import Link from '@/oslms/components/Controls/Link.vue'
import { openExternal } from '@/utils/openExternal'
import { EXPORT_API, exportLabel, formatDateTime } from './format'

const COURSE_REPORTS = ['os_audit_register', 'os_audit_live']

const form = reactive({
	report: 'os_audit_register',
	file_format: 'xlsx',
	course: '',
	user: '',
	from_date: '',
	to_date: '',
})
const starting = ref(false)

const needsCourse = computed(() => COURSE_REPORTS.includes(form.report))

const reportOptions = computed(() =>
	['os_audit_register', 'os_audit_live', 'os_audit_sessions', 'os_audit_events'].map(
		(value) => ({ value, label: exportLabel(value) }),
	),
)
const formatOptions = computed(() => [
	{ label: __('Excel (.xlsx)'), value: 'xlsx' },
	{ label: __('CSV'), value: 'csv' },
])
const reportDescription = computed(
	() =>
		({
			os_audit_register: __(
				'For each student of the course: every lesson visit with entry, exit and time, then the total with the % of the planned hours.',
			),
			os_audit_live: __(
				'For each live class of the course: teacher and participants with entry, exit and duration.',
			),
			os_audit_sessions: __('Every lesson visit with presence and active time.'),
			os_audit_events: __('Every audit event with its fingerprint in the chain.'),
		})[form.report],
)

let pollTimer: ReturnType<typeof setInterval> | null = null
function stopPolling() {
	if (pollTimer) clearInterval(pollTimer)
	pollTimer = null
}
onUnmounted(stopPolling)

const exportsList = createResource({
	url: `${EXPORT_API}.list_audit_exports`,
	auto: true,
	onSuccess(rows: any[]) {
		const pending = (rows || []).some((row) =>
			['Queued', 'Processing'].includes(row.status),
		)
		if (pending && !pollTimer)
			pollTimer = setInterval(() => exportsList.reload(), 4000)
		if (!pending) stopPolling()
	},
})

function statusTheme(status: string) {
	return (
		{ Ready: 'green', Processing: 'orange', Queued: 'gray', Failed: 'red' } as Record<
			string,
			string
		>
	)[status] || 'gray'
}

function statusLabel(status: string) {
	return (
		(
			{
				Queued: __('Queued'),
				Processing: __('Processing'),
				Ready: __('Ready'),
				Failed: __('Export failed'),
			} as Record<string, string>
		)[status] || status
	)
}

async function start() {
	starting.value = true
	try {
		await call(`${EXPORT_API}.start_audit_export`, {
			report: form.report,
			file_format: form.file_format,
			course: form.course || undefined,
			user: needsCourse.value ? undefined : form.user || undefined,
			from_date: form.from_date || undefined,
			to_date: form.to_date || undefined,
		})
		toast.success(__('Export queued'))
		exportsList.reload()
	} catch (error: any) {
		toast.error(error?.messages?.[0] || __('Could not start the export'))
	} finally {
		starting.value = false
	}
}

async function remove(row: any) {
	try {
		await call(`${EXPORT_API}.delete_audit_export`, { name: row.name })
		exportsList.reload()
	} catch (error: any) {
		toast.error(error?.messages?.[0] || __('Could not delete the report'))
	}
}
</script>
