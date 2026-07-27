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
						<Button variant="solid" :disabled="!selectedForReport.length">
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
							{{ __('Clear') }}
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
					<MultiLink
						v-model="filterCourse"
						doctype="LMS Course"
						:label="__('Courses')"
						:placeholder="__('All courses')"
						variant="outline"
					/>
					<MultiLink
						v-model="filterBatch"
						doctype="LMS Batch"
						:label="__('Class')"
						:placeholder="__('All classes')"
						variant="outline"
					/>
					<MultiLink
						v-model="filterStudents"
						doctype="User"
						:label="__('Students')"
						:placeholder="__('All students')"
						variant="outline"
					/>
					<div class="grid grid-cols-2 gap-2">
						<FormControl
							v-model="activityFrom"
							:label="__('Activity from')"
							type="date"
							variant="outline"
						/>
						<FormControl
							v-model="activityTo"
							:label="__('Activity to')"
							type="date"
							variant="outline"
						/>
					</div>
				</div>
			</section>

			<!-- Export -->
			<section class="flex items-center justify-between"></section>
		</div>
	</div>
</template>

<script setup>
import {
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
import { computed, ref, watch } from 'vue'

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

// Default every column to selected the first time a report type is opened.
function ensureDefaults() {
	const cols = availableColumns.value
	if (!cols.length) return
	if (!Array.isArray(savedColumns.value[reportType.value])) {
		savedColumns.value = {
			...savedColumns.value,
			[reportType.value]: cols.map((c) => c.key),
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
const activityFrom = ref('')
const activityTo = ref('')

function buildFilters() {
	const f = {}
	if (filterCourse.value.length) f.course = filterCourse.value
	if (filterBatch.value.length) f.batch = filterBatch.value
	if (filterStudents.value.length) f.students = filterStudents.value
	if (activityFrom.value) f.activity_from = activityFrom.value
	if (activityTo.value) f.activity_to = activityTo.value
	return f
}

function exportStats(fileFormat) {
	const cols = selectedForReport.value
	if (!cols.length) {
		toast.error(__('Select at least one column'))
		return
	}
	const params = new URLSearchParams({
		report_type: reportType.value,
		file_format: fileFormat,
		columns: JSON.stringify(cols),
		filters: JSON.stringify(buildFilters()),
	})
	window.open(
		`/api/method/os_lms.os_lms.api.export_student_stats?${params.toString()}`,
		'_blank',
	)
}

const exportMenu = computed(() => [
	{ label: __('Excel (.xlsx)'), onClick: () => exportStats('xlsx') },
	{ label: __('CSV'), onClick: () => exportStats('csv') },
])
</script>
