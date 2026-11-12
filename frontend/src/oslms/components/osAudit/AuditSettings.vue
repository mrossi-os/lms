<template>
	<div class="space-y-5">
		<!-- General -->
		<section class="space-y-4 rounded-md border card">
			<h2 class="text-base font-semibold text-ink-gray-9">
				{{ __('General') }}
			</h2>
			<div class="flex items-start justify-between gap-4">
				<div class="space-y-1">
					<div class="text-base font-medium text-ink-gray-9">
						{{ __('Audit active') }}
					</div>
					<p class="text-p-sm text-ink-gray-6">
						{{
							hasRetention
								? __(
										'While the audit is active, the activity of the students of the courses in scope is recorded.',
									)
								: __(
										'Set how many days the data is kept before turning the audit on: without it the audit cannot start.',
									)
						}}
					</p>
				</div>
				<Switch
					v-model="form.enabled"
					:disabled="!hasRetention && !form.enabled"
				/>
			</div>
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
				<FormControl
					v-model="form.retention_days"
					type="number"
					:label="__('Retention (days)')"
					:description="
						__(
							'Events and lesson visits older than this are deleted every night. Required.',
						)
					"
					variant="outline"
					min="1"
				/>
				<FormControl
					v-model="form.inactivity_minutes"
					type="number"
					:label="__('Inactivity threshold (minutes)')"
					:description="
						__(
							'Without mouse, keyboard, scroll or touch for this long, the student counts as present but not active.',
						)
					"
					variant="outline"
					min="1"
				/>
				<FormControl
					v-model="form.counted_time"
					type="select"
					:options="countedTimeOptions"
					:label="__('Time that counts')"
					:description="
						__(
							'Used for totals and attendance %. The other measure is always shown next to it.',
						)
					"
					variant="outline"
				/>
			</div>
		</section>

		<!-- Scope -->
		<section class="space-y-4 rounded-md border card">
			<h2 class="text-base font-semibold text-ink-gray-9">
				{{ __('Courses') }}
			</h2>
			<FormControl
				v-model="form.scope"
				type="select"
				:options="scopeOptions"
				:label="__('Courses in scope')"
				variant="outline"
				class="sm:w-1/2"
			/>
			<p class="text-p-sm text-ink-gray-6">
				{{
					form.scope === 'All Courses'
						? __(
								'Every course is in scope. The table only sets planned hours and minimum attendance, used by the Attendance tab.',
							)
						: __(
								'Only the courses listed here are recorded. Planned hours and minimum attendance are optional.',
							)
				}}
			</p>
			<div
				v-if="form.courses.length"
				class="divide-y divide-outline-gray-1 rounded border border-outline-gray-2"
			>
				<div
					v-for="(row, index) in form.courses"
					:key="index"
					class="grid grid-cols-1 items-end gap-3 p-3 sm:grid-cols-[minmax(0,1fr)_7rem_7rem_auto]"
				>
					<Link
						v-model="row.course"
						doctype="LMS Course"
						:label="__('Course')"
						variant="outline"
					/>
					<FormControl
						v-model="row.planned_hours"
						type="number"
						:label="__('Planned hours')"
						variant="outline"
						min="0"
					/>
					<FormControl
						v-model="row.min_attendance_percent"
						type="number"
						:label="__('Minimum attendance %')"
						variant="outline"
						min="0"
						max="100"
					/>
					<Button
						variant="ghost"
						:aria-label="__('Remove course')"
						@click="form.courses.splice(index, 1)"
					>
						<span class="lucide-trash-2 size-4" />
					</Button>
				</div>
			</div>
			<Button @click="addCourse">
				<template #prefix>
					<span class="lucide-plus size-4" />
				</template>
				{{ __('Add course') }}
			</Button>
		</section>

		<!-- What to record -->
		<section class="space-y-4 rounded-md border card">
			<h2 class="text-base font-semibold text-ink-gray-9">
				{{ __('What to record') }}
			</h2>
			<div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
				<label
					v-for="toggle in toggles"
					:key="toggle.field"
					class="flex items-center justify-between gap-3 rounded border border-outline-gray-1 px-3 py-2"
				>
					<span class="text-base text-ink-gray-8">{{ toggle.label }}</span>
					<Switch v-model="form[toggle.field]" />
				</label>
			</div>
		</section>

		<!-- Technical data, deletion, seal -->
		<section class="space-y-4 rounded-md border card">
			<h2 class="text-base font-semibold text-ink-gray-9">
				{{ __('Technical data and privacy') }}
			</h2>
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
				<label
					class="flex items-center justify-between gap-3 rounded border border-outline-gray-1 px-3 py-2"
				>
					<span class="text-base text-ink-gray-8">{{
						__('Record the device type')
					}}</span>
					<Switch v-model="form.store_device" />
				</label>
				<FormControl
					v-model="form.store_ip"
					type="select"
					:options="ipOptions"
					:label="__('IP address')"
					variant="outline"
				/>
				<FormControl
					v-model="form.on_account_deletion"
					type="select"
					:options="deletionOptions"
					:label="__('When an account is deleted')"
					:description="
						__(
							'Keeping the data until expiry needs a legal basis assessed by the data protection officer.',
						)
					"
					variant="outline"
				/>
				<FormControl
					v-model="form.seal_email"
					type="email"
					:label="__('Send the daily seal to')"
					:description="
						__(
							'Optional. A copy of each daily seal outside the platform proves later that the data was not altered.',
						)
					"
					variant="outline"
				/>
			</div>
		</section>

		<div class="flex justify-end gap-2">
			<Button :disabled="!dirty || saving" @click="reset">
				{{ __('Discard changes') }}
			</Button>
			<Button
				variant="solid"
				:loading="saving"
				:disabled="!dirty"
				@click="requestSave"
			>
				{{ __('Save') }}
			</Button>
		</div>

		<!-- History -->
		<section class="space-y-3 rounded-md border card">
			<h2 class="text-base font-semibold text-ink-gray-9">
				{{ __('Change history') }}
			</h2>
			<div
				v-if="!page.history?.length"
				class="py-4 text-center text-sm text-ink-gray-5"
			>
				{{ __('No changes yet') }}
			</div>
			<ul v-else class="divide-y divide-outline-gray-1 text-sm">
				<li
					v-for="(entry, index) in page.history"
					:key="index"
					class="space-y-1 py-2"
				>
					<div class="text-ink-gray-6">
						{{ formatDateTime(entry.at) }} · {{ entry.full_name }}
					</div>
					<div class="text-ink-gray-8">
						<span
							v-for="(change, i) in entry.changes"
							:key="change.field"
						>
							{{ change.label
							}}<template v-if="change.field !== 'courses'"
								>: {{ showValue(change.field, change.old) }} →
								{{ showValue(change.field, change.new) }}</template
							><template v-if="i < entry.changes.length - 1">; </template>
						</span>
					</div>
				</li>
			</ul>
		</section>

		<Dialog
			v-model="confirm.show"
			:title="__('Shorter retention')"
			:actions="[
				{ label: __('Cancel'), onClick: ({ close }) => close() },
				{
					label: __('Save'),
					variant: 'solid',
					theme: 'red',
					onClick: ({ close }) => {
						close()
						save()
					},
				},
			]"
		>
			<p class="text-p-base text-ink-gray-7">
				{{
					__(
						'Tonight {0} events and {1} lesson visits older than {2} days will be deleted. Deleted data cannot be recovered.',
					).format(confirm.events, confirm.sessions, form.retention_days)
				}}
			</p>
		</Dialog>
	</div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import {
	Button,
	Dialog,
	FormControl,
	call,
	toast,
} from 'frappe-ui'
import Switch from '@/components/Controls/BooleanSwitch.vue'
import Link from '@/oslms/components/Controls/Link.vue'
import { AUDIT_API, formatDateTime } from './format'

const props = defineProps<{ page: any }>()
const emit = defineEmits<{ saved: [data: any] }>()

const TOGGLE_FIELDS = [
	'track_logins',
	'track_course_lesson',
	'track_lesson_time',
	'track_quizzes',
	'track_assignments',
	'track_live_classes',
	'track_scorm',
	'track_certificates',
]

const form = reactive<Record<string, any>>({ courses: [] })
const saving = ref(false)
const confirm = reactive({ show: false, events: 0, sessions: 0 })

function snapshot(settings: any) {
	return JSON.parse(JSON.stringify(settings || {}))
}

function reset() {
	const settings = snapshot(props.page.settings)
	Object.keys(form).forEach((key) => delete form[key])
	Object.assign(form, settings, { courses: settings.courses || [] })
}

watch(() => props.page.settings, reset, { immediate: true })

function normalized(values: any) {
	return JSON.stringify({
		...values,
		retention_days: Number(values.retention_days) || null,
		inactivity_minutes: Number(values.inactivity_minutes) || null,
		courses: (values.courses || []).map((row: any) => ({
			course: row.course || '',
			planned_hours: Number(row.planned_hours) || 0,
			min_attendance_percent: Number(row.min_attendance_percent) || 0,
		})),
	})
}

const dirty = computed(
	() => normalized(form) !== normalized(props.page.settings),
)
const hasRetention = computed(() => Number(form.retention_days) > 0)

// Without a retention period the audit cannot stay on (PIANO D9).
watch(hasRetention, (value) => {
	if (!value && form.enabled && !props.page.settings.enabled) form.enabled = 0
})

const countedTimeOptions = computed(() => [
	{ label: __('Presence'), value: 'Presence' },
	{ label: __('Active Time'), value: 'Active Time' },
])
const scopeOptions = computed(() => [
	{ label: __('Selected Courses'), value: 'Selected Courses' },
	{ label: __('All Courses'), value: 'All Courses' },
])
const ipOptions = computed(() => [
	{ label: __('Not Stored'), value: 'Not Stored' },
	{ label: __('Truncated'), value: 'Truncated' },
	{ label: __('Full Address'), value: 'Full Address' },
])
const deletionOptions = computed(() => [
	{ label: __('Delete Audit Data'), value: 'Delete Audit Data' },
	{ label: __('Keep Until Expiry'), value: 'Keep Until Expiry' },
])
const toggles = computed(() => {
	const labels: Record<string, string> = {
		track_logins: __('Logins and logouts'),
		track_course_lesson: __('Course and lesson opening, lesson completion'),
		track_lesson_time: __('Time in lessons'),
		track_quizzes: __('Quizzes, with their duration'),
		track_assignments: __('Assignments'),
		track_live_classes: __('Live classes'),
		track_scorm: __('SCORM packages'),
		track_certificates: __('Certificates'),
	}
	return TOGGLE_FIELDS.map((field) => ({ field, label: labels[field] }))
})

function addCourse() {
	form.courses.push({ course: '', planned_hours: 0, min_attendance_percent: 0 })
}

function showValue(field: string, value: any) {
	if (value === null || value === undefined || value === '') return '—'
	if (TOGGLE_FIELDS.includes(field) || ['enabled', 'store_device'].includes(field))
		return Number(value) ? __('Yes') : __('No')
	return typeof value === 'string' ? __(value) : String(value)
}

async function requestSave() {
	const before = Number(props.page.settings.retention_days) || 0
	const after = Number(form.retention_days) || 0
	if (after > 0 && (before === 0 || after < before)) {
		try {
			const impact = await call(`${AUDIT_API}.retention_impact`, {
				retention_days: after,
			})
			if (impact.events || impact.sessions) {
				Object.assign(confirm, { show: true, ...impact })
				return
			}
		} catch (error: any) {
			toast.error(error?.messages?.[0] || __('Could not save the settings'))
			return
		}
	}
	save()
}

async function save() {
	saving.value = true
	try {
		const values = JSON.parse(normalized(form))
		const data = await call(`${AUDIT_API}.save_settings`, { values })
		emit('saved', data)
		toast.success(__('Settings saved'))
	} catch (error: any) {
		toast.error(error?.messages?.[0] || __('Could not save the settings'))
	} finally {
		saving.value = false
	}
}
</script>
