<template>
	<div>
		<header
			class="sticky top-0 z-10 bg-surface-gray-1 flex items-center justify-between border-b bg-surface-base px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
		</header>

		<div
			v-if="schema.loading && !schema.data"
			class="flex flex-1 items-center justify-center p-10"
		>
			<LoadingIndicator class="size-5 text-ink-gray-5" />
		</div>

		<div v-else-if="schema.error" class="p-10 text-center text-ink-gray-6">
			{{ __('You are not authorized to export student statistics.') }}
		</div>

		<div v-else-if="schema.data" class="mx-auto max-w-4xl space-y-6 p-5">
			<!-- Report type -->
			<section class="space-y-2">
				<h2 class="text-base font-semibold text-ink-gray-9">
					{{ __('Report type') }}
				</h2>
				<div class="flex justify-between">
					<TabButtons
						:buttons="reportTabs"
						v-model="reportType"
						class="w-fit"
					/>

					<Dropdown :options="exportMenu" placement="left">
						<Button
							variant="solid"
							:loading="startResource.loading"
							:disabled="!selectedForReport.length"
						>
							<template #prefix>
								<span class="lucide-download size-4" />
							</template>
							{{ __('Export') }}
						</Button>
					</Dropdown>
				</div>
			</section>

			<!-- Columns -->
			<section class="space-y-3 rounded-md border card">
				<div class="flex items-center justify-between">
					<h2 class="text-base font-semibold text-ink-gray-9">
						{{ __('Columns') }}
					</h2>
					<div class="flex items-center gap-3 text-sm">
						<button
							class="text-ink-gray-6 hover:text-ink-gray-9"
							@click="selectAll"
						>
							{{ __('Select all') }}
						</button>
						<span class="text-ink-gray-3">|</span>
						<button
							class="text-ink-gray-6 hover:text-ink-gray-9"
							@click="selectNone"
						>
							{{ __('Deselect All') }}
						</button>
					</div>
				</div>
				<div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
					<Checkbox
						v-for="col in availableColumns"
						:key="col.key"
						:modelValue="isSelected(col.key)"
						:label="col.label"
						@update:modelValue="(v) => setColumn(col.key, v)"
					/>
				</div>
			</section>

			<!-- Filters -->
			<section class="space-y-4 rounded-md border card">
				<h2 class="text-base font-semibold text-ink-gray-9">
					{{ __('Filters') }}
				</h2>
				<p class="text-sm text-ink-gray-6">
					{{
						__(
							'Leave empty to include all available data for the selected report.',
						)
					}}
				</p>
				<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
					<div class="flex items-end gap-1">
						<MultiLink
							class="flex-1"
							v-model="filterCourse"
							doctype="LMS Course"
							:label="__('Courses')"
							:placeholder="__('All courses')"
							variant="outline"
						/>
						<Button
							v-if="filterCourse.length"
							variant="ghost"
							class="shrink-0"
							:aria-label="__('Clear filter')"
							@click="filterCourse = []"
						>
							<span class="lucide-x size-4" />
						</Button>
					</div>
					<div class="flex items-end gap-1">
						<MultiLink
							class="flex-1"
							v-model="filterBatch"
							doctype="LMS Batch"
							:label="__('Class')"
							:placeholder="__('All classes')"
							variant="outline"
						/>
						<Button
							v-if="filterBatch.length"
							variant="ghost"
							class="shrink-0"
							:aria-label="__('Clear filter')"
							@click="filterBatch = []"
						>
							<span class="lucide-x size-4" />
						</Button>
					</div>
					<div class="flex items-end gap-1">
						<MultiLink
							class="flex-1"
							v-model="filterStudents"
							doctype="User"
							:label="__('Students')"
							:placeholder="__('All students')"
							variant="outline"
						/>
						<Button
							v-if="filterStudents.length"
							variant="ghost"
							class="shrink-0"
							:aria-label="__('Clear filter')"
							@click="filterStudents = []"
						>
							<span class="lucide-x size-4" />
						</Button>
					</div>
					<div
						v-for="df in dateFilters"
						:key="df.key"
						class="grid grid-cols-2 gap-2 sm:col-span-2"
					>
						<div class="flex items-end gap-1">
							<FormControl
								class="flex-1"
								v-model="dates[df.key + '_from']"
								:label="df.from_label"
								:placeholder="__('Select date')"
								type="date"
								variant="outline"
							/>
							<Button
								v-if="dates[df.key + '_from']"
								variant="ghost"
								class="shrink-0"
								:aria-label="__('Clear filter')"
								@click="dates[df.key + '_from'] = ''"
							>
								<span class="lucide-x size-4" />
							</Button>
						</div>
						<div class="flex items-end gap-1">
							<FormControl
								class="flex-1"
								v-model="dates[df.key + '_to']"
								:label="df.to_label"
								:placeholder="__('Select date')"
								type="date"
								variant="outline"
							/>
							<Button
								v-if="dates[df.key + '_to']"
								variant="ghost"
								class="shrink-0"
								:aria-label="__('Clear filter')"
								@click="dates[df.key + '_to'] = ''"
							>
								<span class="lucide-x size-4" />
							</Button>
						</div>
					</div>
				</div>
			</section>

			<!-- Generated reports -->
			<section class="space-y-3 rounded-md border card">
				<div class="flex items-center justify-between">
					<h2 class="text-base font-semibold text-ink-gray-9">
						{{ __('Generated reports') }}
					</h2>
					<button
						class="text-sm text-ink-gray-6 hover:text-ink-gray-9 disabled:opacity-50"
						:disabled="exportsList.loading"
						@click="refreshExports"
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
								<th class="py-2 font-medium">{{ __('Report') }}</th>
								<th class="py-2 font-medium">{{ __('Format') }}</th>
								<th class="py-2 font-medium">{{ __('Date') }}</th>
								<th class="py-2 font-medium">{{ __('Status') }}</th>
								<th class="py-2 text-right font-medium">
									{{ __('Actions') }}
								</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="row in exportsList.data"
								:key="row.name"
								class="border-t border-outline-gray-1"
							>
								<td class="py-2 text-ink-gray-8">
									{{ row.report_label }}
								</td>
								<td class="py-2 uppercase text-ink-gray-6">
									{{ row.file_format }}
								</td>
								<td class="py-2 text-ink-gray-6">
									{{ formatDate(row.creation) }}
								</td>
								<td class="py-2">
									<Badge
										:theme="statusTheme(row.status)"
										:label="statusLabel(row.status)"
										:title="row.error || ''"
									/>
								</td>
								<td class="py-2">
									<div class="flex items-center justify-end gap-1">
										<Button
											v-if="row.status === 'Ready'"
											variant="subtle"
											@click="downloadExport(row)"
										>
											{{ __('Download') }}
										</Button>
										<Button
											variant="ghost"
											theme="red"
											@click="removeExport(row)"
										>
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
	</div>
</template>

<script setup>
import {
	Badge,
	Breadcrumbs,
	Button,
	Checkbox,
	Dropdown,
	FormControl,
	LoadingIndicator,
	TabButtons,
	createResource,
	toast,
} from 'frappe-ui'
import MultiLink from '@/components/Controls/MultiLink.vue'
import { useLocalStorage } from '@/utils/composables'
import dayjs from '@/utils/dayjs'
import { computed, onUnmounted, reactive, ref, watch } from 'vue'

const breadcrumbs = computed(() => [
	{
		label: __('Export Statistics'),
		route: { name: 'StudentStatsExport' },
	},
])

const schema = createResource({
	url: 'os_lms.os_lms.api.get_student_stats_schema',
	auto: true,
})

// --- Generated reports (async export jobs) ---
function isPending(r) {
	return r.status === 'Queued' || r.status === 'Processing'
}

let pollTimer = null

function stopPolling() {
	if (pollTimer) {
		clearInterval(pollTimer)
		pollTimer = null
	}
}

function ensurePolling() {
	if (pollTimer) return
	pollTimer = setInterval(() => exportsList.reload(), 4000)
}

onUnmounted(stopPolling)

const exportsList = createResource({
	url: 'os_lms.os_lms.api.list_student_stats_exports',
	auto: true,
	onSuccess(data) {
		if ((data || []).some(isPending)) ensurePolling()
		else stopPolling()
	},
})

const startResource = createResource({
	url: 'os_lms.os_lms.api.start_student_stats_export',
})

const deleteResource = createResource({
	url: 'os_lms.os_lms.api.delete_student_stats_export',
})

function statusTheme(s) {
	return { Ready: 'green', Processing: 'orange', Queued: 'gray', Failed: 'red' }[s] || 'gray'
}

function statusLabel(s) {
	return (
		{
			Queued: __('Queued'),
			Processing: __('Processing'),
			Ready: __('Ready'),
			Failed: __('Export failed'),
		}[s] || s
	)
}

function formatDate(value) {
	return value ? dayjs(value).format('DD/MM/YYYY HH:mm') : ''
}

function downloadExport(row) {
	if (row.file) window.open(row.file, '_blank')
}

function removeExport(row) {
	deleteResource.submit(
		{ name: row.name },
		{
			onSuccess: () => exportsList.reload(),
			onError: (err) =>
				toast.error(err?.messages?.[0] || __('Could not delete the report')),
		},
	)
}

function refreshExports() {
	exportsList.reload().then(
		() => toast.success(__('List updated')),
		() => toast.error(__('Could not refresh the list')),
	)
}

const reportType = ref('users')

const reportTabs = computed(() => {
	const reports = schema.data?.reports || {}
	return Object.keys(reports).map((key) => ({
		label: reports[key].label,
		value: key,
	}))
})

const availableColumns = computed(
	() => schema.data?.reports?.[reportType.value]?.columns || [],
)

// Persisted per report type: { [reportType]: [columnKey, ...] }.
const savedColumns = useLocalStorage('lms_stats_export_columns', {})

const selectedForReport = computed(
	() => savedColumns.value[reportType.value] || [],
)

// Default the first time a report type is opened: select every column except
// those flagged default:false (e.g. the lesson columns that switch the report
// to one row per lesson — the user opts into those explicitly).
function ensureDefaults() {
	const cols = availableColumns.value
	if (!cols.length) return
	if (!Array.isArray(savedColumns.value[reportType.value])) {
		savedColumns.value = {
			...savedColumns.value,
			[reportType.value]: cols
				.filter((c) => c.default !== false)
				.map((c) => c.key),
		}
	}
}

watch([reportType, availableColumns], ensureDefaults, { immediate: true })

function isSelected(key) {
	return selectedForReport.value.includes(key)
}

// Keep the declared column order regardless of toggle order.
function setColumn(key, checked) {
	const current = new Set(selectedForReport.value)
	if (checked) current.add(key)
	else current.delete(key)
	savedColumns.value = {
		...savedColumns.value,
		[reportType.value]: availableColumns.value
			.map((c) => c.key)
			.filter((k) => current.has(k)),
	}
}

function selectAll() {
	savedColumns.value = {
		...savedColumns.value,
		[reportType.value]: availableColumns.value.map((c) => c.key),
	}
}

function selectNone() {
	savedColumns.value = { ...savedColumns.value, [reportType.value]: [] }
}

// Filters
const filterCourse = ref([])
const filterBatch = ref([])
const filterStudents = ref([])

// Date-range filters are per-report (see each report's `date_filters` in the
// schema): each entry renders a from/to pair keyed `${key}_from` / `${key}_to`.
const dateFilters = computed(
	() => schema.data?.reports?.[reportType.value]?.date_filters || [],
)

// Values for the date pairs, keyed by `${key}_from` / `${key}_to`.
const dates = reactive({})

// Reset the date values when switching report so keys from one report don't
// leak into another's export payload.
watch(reportType, () => {
	Object.keys(dates).forEach((k) => delete dates[k])
})

function buildFilters() {
	const f = {}
	if (filterCourse.value.length) f.course = filterCourse.value
	if (filterBatch.value.length) f.batch = filterBatch.value
	if (filterStudents.value.length) f.students = filterStudents.value
	for (const df of dateFilters.value) {
		if (dates[df.key + '_from']) f[df.key + '_from'] = dates[df.key + '_from']
		if (dates[df.key + '_to']) f[df.key + '_to'] = dates[df.key + '_to']
	}
	return f
}

function exportStats(fileFormat) {
	const cols = selectedForReport.value
	if (!cols.length) {
		toast.error(__('Select at least one column'))
		return
	}
	startResource.submit(
		{
			report_type: reportType.value,
			columns: JSON.stringify(cols),
			file_format: fileFormat,
			filters: JSON.stringify(buildFilters()),
		},
		{
			onSuccess() {
				toast.success(__('Export queued'))
				exportsList.reload()
				ensurePolling()
			},
			onError(err) {
				toast.error(err?.messages?.[0] || __('Could not start the export'))
			},
		},
	)
}

const exportMenu = computed(() => [
	{ label: __('Excel (.xlsx)'), onClick: () => exportStats('xlsx') },
	{ label: __('CSV'), onClick: () => exportStats('csv') },
])
</script>
