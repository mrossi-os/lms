<template>
	<FormShell
		:title="isEdit ? __('Edit Live Class') : __('Create a Live Class')"
		size="xl"
		@close="close"
	>
		<template #default>
			<div v-if="loadingBatch" class="p-4 text-base text-ink-gray-6">
				{{ __('Loading...') }}
			</div>
			<div v-else-if="refusal" class="p-4 text-base text-ink-gray-6">
				{{ refusal }}
			</div>
			<div v-else data-testid="live-class-fields" class="flex flex-col gap-4">
				<!-- OSLMS-CUSTOM: edit mode notices, schedule frozen once the class has started / students notified on a reschedule -->
				<div
					v-if="isEdit && scheduleLocked"
					class="flex items-start gap-2 bg-surface-amber-1 px-3 py-2 rounded-lg text-ink-amber-6 text-sm"
				>
					<span class="lucide-alert-circle size-4 shrink-0 mt-0.5" />
					<span>
						{{
							__(
								'La lezione è già stata avviata: data, ora e durata non sono più modificabili.'
							)
						}}
					</span>
				</div>
				<div
					v-else-if="isEdit"
					class="flex items-start gap-2 bg-surface-blue-1 px-3 py-2 rounded-lg text-ink-blue-3 text-sm"
				>
					<span class="lucide-alert-circle size-4 shrink-0 mt-0.5" />
					<span>
						{{
							__(
								"Se cambi titolo, data, ora o durata, gli iscritti ricevono un'email con i dettagli aggiornati e i promemoria vengono riprogrammati."
							)
						}}
					</span>
				</div>
				<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
					<div class="space-y-4">
						<FormControl
							type="text"
							v-model="liveClass.title"
							:label="__('Title')"
							:required="true"
						/>
						<FormControl
							v-model="liveClass.date"
							type="date"
							:label="__('Date')"
							:required="true"
							:disabled="scheduleLocked"
						/>
						<FormControl
							type="number"
							v-model="liveClass.duration"
							:label="__('Duration (in minutes)')"
							:required="true"
							:disabled="scheduleLocked"
						/>
					</div>
					<div class="space-y-4">
						<Tooltip
							:text="
								__(
									'Time must be in 24 hour format (HH:mm). Example 11:30 or 22:00'
								)
							"
						>
							<!-- OSLMS-CUSTOM: 24-hour time picker (use12Hour false) -->
							<FormControl
								v-model="liveClass.time"
								type="time"
								:label="__('Time')"
								:required="true"
								:disabled="scheduleLocked"
								:use12Hour="false"
							/>
						</Tooltip>

						<Combobox
							:modelValue="liveClass.timezone"
							:options="getTimezoneOptions()"
							:label="__('Timezone')"
							:required="true"
							:disabled="scheduleLocked"
							@update:modelValue="(value) => (liveClass.timezone = value)"
						/>
						<!-- OSLMS-CUSTOM: auto recording chosen only at creation (not editable afterwards), translated placeholder -->
						<FormControl
							v-if="!isEdit && conferencingProvider === 'Zoom'"
							v-model="liveClass.auto_recording"
							type="select"
							:options="getRecordingOptions()"
							:label="__('Auto Recording')"
							:placeholder="__('Select option')"
						/>
					</div>
				</div>
				<FormControl
					v-model="liveClass.description"
					type="textarea"
					:label="__('Description')"
				/>
				<!-- OSLMS-CUSTOM: per-class reminders (offset + unit, min 15 minutes, sent status) -->
				<div class="border-t pt-4">
					<div class="flex items-center justify-between mb-2">
						<div>
							<div class="text-ink-gray-7 text-sm font-medium">
								{{ __('Reminders') }}
							</div>
							<span class="text-xs text-ink-gray-5">
								{{ __('Minimum 15 minutes before the class.') }}
							</span>
						</div>
						<Button @click="addReminder" variant="solid">
							<template #prefix>
								<span class="lucide-plus size-4" />
							</template>
							{{ __('Add Reminder') }}
						</Button>
					</div>
					<div
						v-if="!liveClass.reminders.length"
						class="text-ink-gray-5 text-sm leading-5"
					>
						{{
							__(
								'No reminders configured. Add one to notify students before the class.'
							)
						}}
					</div>
					<div
						v-for="(row, idx) in liveClass.reminders"
						:key="idx"
						class="flex items-end gap-2 mb-2"
					>
						<div class="flex-1">
							<FormControl
								v-model="row.offset_value"
								type="number"
								:min="1"
								:label="idx === 0 ? __('Value') : ''"
							/>
						</div>
						<div class="flex-1">
							<FormControl
								v-model="row.offset_unit"
								type="select"
								:options="reminderUnitOptions"
								:label="idx === 0 ? __('Unit') : ''"
							/>
						</div>
						<div class="flex-[1.5] text-xs text-ink-gray-5 leading-5 pb-2">
							<span v-if="row.sent_at">
								{{ __('Sent') }}
								{{ dayjs(row.sent_at).format('DD MMM HH:mm') }}
							</span>
							<span v-else class="text-ink-gray-4">
								{{ __('Not sent yet') }}
							</span>
						</div>
						<Button
							variant="ghost"
							:aria-label="__('Delete')"
							@click="removeReminder(idx)"
						>
							<template #icon>
								<span class="lucide-trash-2 size-4 text-ink-red-6" />
							</template>
						</Button>
					</div>
				</div>
			</div>
		</template>
		<template #actions>
			<div
				v-if="!refusal && !loadingBatch"
				class="flex items-center justify-end"
			>
				<HeaderButton
					data-testid="live-class-save"
					:label="__('Save')"
					variant="solid"
					:loading="
						saving ||
						createLiveClass.loading ||
						createGoogleMeetLiveClass.loading ||
						updateLiveClassResource.loading
					"
					@click="submitLiveClass()"
				/>
			</div>
		</template>
	</FormShell>
</template>
<script setup>
import {
	Button,
	Combobox,
	createResource,
	getCachedListResource,
	Tooltip,
	FormControl,
	toast,
} from 'frappe-ui'
import { computed, reactive, ref, inject, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getTimezones, getUserTimezone } from '@/utils/'
import FormShell from '@/components/FormShell.vue'
import HeaderButton from '@/components/HeaderButton.vue'
import {
	batchRouteLocation,
	useBatchDetails,
} from '@/composables/useBatchForms'
import { useFormRoute } from '@/composables/useFormRoute'
import { submitResource } from '@/utils/resource'

const props = defineProps({
	batchName: {
		type: String,
		required: true,
	},
	// OSLMS-CUSTOM: set by the EditLiveClass route; absent on NewLiveClass
	liveClassName: {
		type: String,
		default: null,
	},
})

const user = inject('$user')
const dayjs = inject('$dayjs')
const route = useRoute()
const readOnlyMode = window.read_only_mode

// C2: close()'s pop branch restores the hash by itself; its deep-link branch
// replaces to this literal location, so the tab hash has to be carried here or
// a close lands on the bare path and silently resets the page to tab 0.
const { close } = useFormRoute(
	batchRouteLocation('BatchDetail', props.batchName, route.hash)
)

// Parent context a URL cannot carry: the conferencing provider and its account
// pick which endpoint a class is created through. Its own fetch, NOT the page's
// instance — see useBatchForms.ts for why sharing one is not available here.
const batch = useBatchDetails(() => props.batchName)

// OSLMS-CUSTOM: the same form edits an existing live class (EditLiveClass route)
const isEdit = computed(() => !!props.liveClassName)

// OSLMS-CUSTOM: edit mode loads the full class document (reminders included)
const liveClassDoc = createResource({
	url: 'frappe.client.get',
	makeParams() {
		return {
			doctype: 'LMS Live Class',
			name: props.liveClassName,
		}
	},
	auto: Boolean(props.liveClassName),
	onSuccess(doc) {
		prefillFromDoc(doc)
	},
})

const loadingBatch = computed(
	() =>
		(!batch.data && batch.loading) ||
		(isEdit.value && !liveClassDoc.data && liveClassDoc.loading)
)

const conferencingProvider = computed(
	() => batch.data?.conferencing_provider || null
)

// OSLMS-CUSTOM: same gate as LiveClass.vue's isAdmin() and the server
// (create_live_class / os_lms _ensure_live_class_admin): Moderator, Batch
// Evaluator and Docente; a batch Valutatore sees the classes read-only.
const isAdmin = computed(() =>
	Boolean(
		user.data?.is_moderator || user.data?.is_evaluator || user.data?.is_docente
	)
)

// Copied from LiveClass.vue's canCreateClass()/hasProviderAccount(), which gate
// the "Add" button. A URL does not go through a button.
//
// UX gate, not an authorization boundary — the server-side permission check in
// lms_batch.create_live_class is.
const hasProviderAccount = computed(() => {
	const data = batch.data
	if (data?.conferencing_provider === 'Zoom' && data?.zoom_account) return true
	if (
		data?.conferencing_provider === 'Google Meet' &&
		data?.google_meet_account
	)
		return true
	return false
})

const refusal = computed(() => {
	if (readOnlyMode) return __('This site is in read-only mode.')
	if (!isAdmin.value)
		return __('You are not permitted to create a live class for this batch.')
	// OSLMS-CUSTOM: editing an existing class needs no conferencing account on
	// the batch (update_live_class works on the class's own meeting)
	if (isEdit.value) {
		if (liveClassDoc.error) return __('Could not load the live class.')
		return null
	}
	if (!hasProviderAccount.value)
		return __(
			'Please select a conferencing provider and add an account to the batch to create live classes.'
		)
	return null
})

// OSLMS-CUSTOM: double-submit guard
// Guards against a second submit while the first is still running: two saves in
// flight on the same class make the loser fail with "Record has changed since
// last read".
const saving = ref(false)
// OSLMS-CUSTOM: schedule locked once the host has started the class
// Once the host has started the class its schedule is frozen, server-side too
// (see `_validate_schedule_change`): only title, description and reminders stay
// editable, because students are already being let in on the old slot.
const scheduleLocked = computed(
	() => isEdit.value && !!liveClassDoc.data?.started_at
)

const reminderUnitOptions = [
	{ label: __('Minutes'), value: 'Minutes' },
	{ label: __('Hours'), value: 'Hours' },
	{ label: __('Days'), value: 'Days' },
]

// OSLMS-CUSTOM: reminders must fire at least 15 minutes before the class (mirrored server-side)
const MIN_REMINDER_MINUTES = 15
const UNIT_TO_MINUTES = { Minutes: 1, Hours: 60, Days: 60 * 24 }
const offsetToMinutes = (value, unit) =>
	(parseInt(value, 10) || 0) * (UNIT_TO_MINUTES[unit] || 0)

const liveClass = reactive({
	title: '',
	description: '',
	date: '',
	time: '',
	duration: '',
	timezone: '',
	auto_recording: 'No Recording',
	batch: props.batchName,
	host: user.data?.name,
	reminders: [],
})

onMounted(() => {
	if (!isEdit.value) liveClass.timezone = getUserTimezone()
})

// OSLMS-CUSTOM: prefill the form from the class being edited
const prefillFromDoc = (doc) => {
	liveClass.title = doc.title || ''
	liveClass.description = doc.description || ''
	liveClass.date = doc.date || ''
	// Stored as HH:mm:ss, but the time field (and valideTime) work on HH:mm.
	liveClass.time = (doc.time || '').slice(0, 5)
	liveClass.duration = doc.duration || ''
	liveClass.timezone = doc.timezone || getUserTimezone()
	liveClass.auto_recording = doc.auto_recording || 'No Recording'
	liveClass.reminders = (doc.reminders || []).map((r) => ({
		offset_value: r.offset_value,
		offset_unit: r.offset_unit,
		sent_at: r.sent_at,
	}))
}

const getTimezoneOptions = () => {
	return getTimezones().map((timezone) => {
		return {
			label: timezone,
			value: timezone,
		}
	})
}

const getRecordingOptions = () => {
	return [
		// OSLMS-CUSTOM: recording option labels translated via __() (values stay English)
		{ label: __('No Recording'), value: 'No Recording' },
		{ label: __('Local'), value: 'Local' },
		{ label: __('Cloud'), value: 'Cloud' },
	]
}

const addReminder = () => {
	liveClass.reminders.push({
		offset_value: 1,
		offset_unit: 'Hours',
		sent_at: null,
	})
}

const removeReminder = (idx) => {
	liveClass.reminders.splice(idx, 1)
}

const createLiveClass = createResource({
	url: 'lms.lms.doctype.lms_batch.lms_batch.create_live_class',
	makeParams(values) {
		return {
			doctype: 'LMS Live Class',
			batch_name: values.batch,
			zoom_account: batch.data?.zoom_account,
			...values,
		}
	},
})

const createGoogleMeetLiveClass = createResource({
	url: 'lms.lms.doctype.lms_batch.lms_batch.create_google_meet_live_class',
	makeParams(values) {
		return {
			batch_name: values.batch,
			google_meet_account: batch.data?.google_meet_account,
			...values,
		}
	},
})

// OSLMS-CUSTOM: edits and post-create reminders go through the os_lms update_live_class endpoint
const updateLiveClassResource = createResource({
	url: 'os_lms.os_lms.api.update_live_class',
})

// C4: the `reloadLiveClasses` defineModel is gone with the modal, so the tab's
// list is refreshed by name instead. A lookup, NOT createListResource — a
// constructor here would win the cache and hand LiveClass.vue an instance with
// this file's (absent) filters/fields, because createListResource discards the
// second caller's options. Null when the tab is not mounted (deep link), which
// is correct: it fetches on mount anyway. Mirrors stores/notifications.js:35.
// OSLMS-CUSTOM: our paginated LiveClass.vue list is not a cached list resource,
// so this lookup finds nothing there; the tab reloads itself (back to page 1)
// when the route returns from this form.
const reloadLiveClassList = () => {
	getCachedListResource(['liveClasses', props.batchName])?.reload()
}

const reportError = (err) => {
	toast.error(err.messages?.[0] || err)
	console.error(err)
}

const submitLiveClass = () => {
	if (refusal.value) return
	// OSLMS-CUSTOM: ignore a second click while a save is in flight, then route to create or update
	if (saving.value) {
		return
	}
	if (isEdit.value) {
		return submitUpdate()
	}
	return submitCreate()
}

const submitCreate = () => {
	const resource =
		conferencingProvider.value === 'Google Meet'
			? createGoogleMeetLiveClass
			: createLiveClass
	saving.value = true
	return submitResource(resource, liveClass, {
		// OSLMS-CUSTOM: validation really blocks the submit (upstream discarded
		// validateFormFields()'s message); submitResource toasts it via onError
		validate: () => validateFormFields(),
		onSuccess(created) {
			return persistRemindersAfterCreate(created)
		},
		onError: reportError,
	}).finally(() => {
		saving.value = false
	})
}

// OSLMS-CUSTOM: reminders are saved on the new class right after the upstream create call
const persistRemindersAfterCreate = (created) => {
	const finish = () => {
		reloadLiveClassList()
		close()
	}
	if (!liveClass.reminders.length) {
		finish()
		return
	}
	return submitResource(
		updateLiveClassResource,
		{
			name: created?.name || created,
			payload: {
				reminders: liveClass.reminders.map((r) => ({
					offset_value: r.offset_value,
					offset_unit: r.offset_unit,
				})),
			},
		},
		{
			onSuccess: finish,
			onError: reportError,
		}
	)
}

const submitUpdate = () => {
	const payload = {
		title: liveClass.title,
		description: liveClass.description,
		// `sent_at` is intentionally left out: the server matches each reminder
		// against the stored ones, so an edited offset fires again on its own.
		reminders: liveClass.reminders.map((r) => ({
			offset_value: r.offset_value,
			offset_unit: r.offset_unit,
		})),
	}
	if (!scheduleLocked.value) {
		payload.date = liveClass.date
		payload.time = liveClass.time
		payload.duration = liveClass.duration
		payload.timezone = liveClass.timezone
	}
	saving.value = true
	return submitResource(
		updateLiveClassResource,
		{
			name: props.liveClassName,
			payload,
		},
		{
			validate: () => validateEditFields(),
			onSuccess() {
				toast.success(__('Live class updated'))
				reloadLiveClassList()
				close()
			},
			onError: reportError,
		}
	).finally(() => {
		saving.value = false
	})
}

// OSLMS-CUSTOM: only a real reschedule must land in the future when editing
const scheduleChanged = () => {
	const original = liveClassDoc.data
	if (!original) return true
	// The stored time comes back as HH:mm:ss, the form holds HH:mm.
	const sameTime =
		String(liveClass.time || '').slice(0, 5) ===
		String(original.time || '').slice(0, 5)
	return !(
		liveClass.date === original.date &&
		sameTime &&
		Number(liveClass.duration) === Number(original.duration) &&
		liveClass.timezone === original.timezone
	)
}

const validateSchedule = (requireFuture) => {
	if (!liveClass.date) {
		return __('Please select a date.')
	}
	if (!liveClass.time) {
		return __('Please select a time.')
	}
	if (!liveClass.timezone) {
		return __('Please select a timezone.')
	}
	if (!valideTime()) {
		return __('Please enter a valid time in the format HH:mm.')
	}
	if (requireFuture) {
		const liveClassDateTime = dayjs(`${liveClass.date}T${liveClass.time}`).tz(
			liveClass.timezone,
			true
		)
		if (
			liveClassDateTime.isSameOrBefore(
				dayjs().tz(liveClass.timezone, false),
				'minute'
			)
		) {
			return __('Please select a future date and time.')
		}
	}
	if (!liveClass.duration) {
		return __('Please select a duration.')
	}
}

// OSLMS-CUSTOM: reminder validation (positive offset, minimum 15 minutes)
const validateReminders = () => {
	for (const r of liveClass.reminders) {
		if (!r.offset_value || r.offset_value < 1) {
			return __('Reminders must have a positive offset value.')
		}
		if (offsetToMinutes(r.offset_value, r.offset_unit) < MIN_REMINDER_MINUTES) {
			return __('Each reminder must be at least 15 minutes before the class.')
		}
	}
}

const validateEditFields = () => {
	if (!liveClass.title) {
		return __('Please enter a title.')
	}
	if (!scheduleLocked.value) {
		// A class left on its original slot may well be in the past already:
		// only a real reschedule has to land in the future.
		const scheduleError = validateSchedule(scheduleChanged())
		if (scheduleError) {
			return scheduleError
		}
	}
	return validateReminders()
}

const validateFormFields = () => {
	if (!liveClass.title) {
		return __('Please enter a title.')
	}
	const scheduleError = validateSchedule(true)
	if (scheduleError) {
		return scheduleError
	}
	return validateReminders()
}

const valideTime = () => {
	// OSLMS-CUSTOM: accept the stored HH:mm:ss format too
	// Accept both HH:mm from the picker and HH:mm:ss as stored on the document.
	let time = String(liveClass.time || '').split(':')
	if (time.length < 2 || time.length > 3) {
		return false
	}
	if (time[0] < 0 || time[0] > 23) {
		return false
	}
	if (time[1] < 0 || time[1] > 59) {
		return false
	}
	return true
}
</script>
