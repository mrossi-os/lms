<template>
	<Dialog
		v-model="show"
		:options="{
			title: isEdit ? __('Edit Live Class') : __('Create a Live Class'),
			size: 'xl',
			actions: [
				{
					label: __('Submit'),
					variant: 'solid',
					loading: saving,
					onClick: ({ close }) => submitLiveClass(close),
				},
			],
		}"
	>
		<template #default>
			<div class="flex flex-col gap-4">
				<!-- OSLMS-CUSTOM: edit mode notices, schedule frozen once the class has started / students notified on a reschedule -->
				<div
					v-if="isEdit && scheduleLocked"
					class="flex items-start gap-2 bg-surface-amber-1 px-3 py-2 rounded-lg text-ink-amber-6 text-sm"
				>
					<AlertCircle class="size-4 shrink-0 stroke-1.5 mt-0.5" />
					<span>
						{{
							__(
								'La lezione è già stata avviata: data, ora e durata non sono più modificabili.',
							)
						}}
					</span>
				</div>
				<div
					v-else-if="isEdit"
					class="flex items-start gap-2 bg-surface-blue-1 px-3 py-2 rounded-lg text-ink-blue-3 text-sm"
				>
					<AlertCircle class="size-4 shrink-0 stroke-1.5 mt-0.5" />
					<span>
						{{
							__(
								'Se cambi titolo, data, ora o durata, gli iscritti ricevono un\'email con i dettagli aggiornati e i promemoria vengono riprogrammati.',
							)
						}}
					</span>
				</div>
				<div class="grid grid-cols-2 gap-4">
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
						<!-- OSLMS-CUSTOM: explicit required Time label and 24-hour time picker (use12Hour false) -->
						<Tooltip
							:text="
								__(
									'Time must be in 24 hour format (HH:mm). Example 11:30 or 22:00',
								)
							"
						>
							<label
								class="block text-p-sm-medium text-ink-gray-7"
								for="batchTimezone"
							>
								{{ __('Time') }}
								<span class="text-ink-red-6">*</span>
							</label>
							<FormControl
								v-model="liveClass.time"
								type="time"
								:label="__('Time')"
								:required="true"
								:disabled="scheduleLocked"
								:use12Hour="false"
							/>
						</Tooltip>

						<div class="space-y-1.5">
							<label
								class="block text-p-sm-medium text-ink-gray-7"
								for="batchTimezone"
							>
								{{ __('Timezone') }}
								<span class="text-ink-red-6">*</span>
							</label>
							<Combobox
								:modelValue="liveClass.timezone"
								:options="getTimezoneOptions()"
								:disabled="scheduleLocked"
								@update:modelValue="(value) => (liveClass.timezone = value)"
							/>
						</div>
						<!-- OSLMS-CUSTOM: auto recording chosen only at creation (not editable afterwards), translated placeholder -->
						<FormControl
							v-if="!isEdit && props.conferencingProvider === 'Zoom'"
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
							<label class="text-ink-gray-7 text-sm font-medium block">
								{{ __('Reminders') }}
							</label>
							<span class="text-xs text-ink-gray-5">
								{{ __('Minimum 15 minutes before the class.') }}
							</span>
						</div>
						<Button
							@click="addReminder"
							theme="blue"
							:variant="'solid'"
							class="!text-white"
						>
							<template #prefix>
								<Plus class="w-4 h-4 !text-white" />
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
								'No reminders configured. Add one to notify students before the class.',
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
								class="small-form"
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
								{{ __('Sent') }} {{ dayjs(row.sent_at).format('DD MMM HH:mm') }}
							</span>
							<span v-else class="text-ink-gray-4">
								{{ __('Not sent yet') }}
							</span>
						</div>
						<Button @click="removeReminder(idx)" :variant="'ghost'">
							<template #icon>
								<Trash2 class="w-4 h-4 text-ink-red-6" />
							</template>
						</Button>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import {
	Button,
	Combobox,
	Dialog,
	createResource,
	Tooltip,
	FormControl,
	toast,
} from 'frappe-ui'
import { computed, reactive, ref, inject, onMounted } from 'vue'
import { Plus, Trash2, AlertCircle } from 'lucide-vue-next'
import { getTimezones, getUserTimezone } from '@/utils/'

const liveClasses = defineModel('reloadLiveClasses')
const show = defineModel()
const user = inject('$user')
const dayjs = inject('$dayjs')

const props = defineProps({
	batch: {
		type: String,
		required: true,
	},
	zoomAccount: String,
	googleMeetAccount: String,
	conferencingProvider: String,
	liveClass: {
		type: Object,
		default: null,
	},
})

// OSLMS-CUSTOM: the same modal edits an existing live class when LiveClass.vue passes it in
const isEdit = computed(() => !!props.liveClass)
// OSLMS-CUSTOM: double-submit guard
// Guards against a second submit while the first is still running: two saves in
// flight on the same class make the loser fail with "Record has changed since
// last read".
const saving = ref(false)
// OSLMS-CUSTOM: schedule locked once the host has started the class
// Once the host has started the class its schedule is frozen, server-side too
// (see `_validate_schedule_change`): only title, description and reminders stay
// editable, because students are already being let in on the old slot.
const scheduleLocked = computed(() => isEdit.value && !!props.liveClass?.started_at)

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

let liveClass = reactive({
	title: '',
	description: '',
	date: '',
	time: '',
	duration: '',
	timezone: '',
	auto_recording: 'No Recording',
	batch: props.batch,
	host: user.data.name,
	reminders: [],
})

onMounted(() => {
	if (props.liveClass) {
		liveClass.title = props.liveClass.title || ''
		liveClass.description = props.liveClass.description || ''
		liveClass.date = props.liveClass.date || ''
		// OSLMS-CUSTOM: prefill the form from the class being edited
		// Stored as HH:mm:ss, but the time field (and valideTime) work on HH:mm.
		liveClass.time = (props.liveClass.time || '').slice(0, 5)
		liveClass.duration = props.liveClass.duration || ''
		liveClass.timezone = props.liveClass.timezone || getUserTimezone()
		liveClass.auto_recording = props.liveClass.auto_recording || 'No Recording'
		liveClass.reminders = (props.liveClass.reminders || []).map((r) => ({
			offset_value: r.offset_value,
			offset_unit: r.offset_unit,
			sent_at: r.sent_at,
		}))
	} else {
		liveClass.timezone = getUserTimezone()
	}
})

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
			zoom_account: props.zoomAccount,
			...values,
		}
	},
})

const createGoogleMeetLiveClass = createResource({
	url: 'lms.lms.doctype.lms_batch.lms_batch.create_google_meet_live_class',
	makeParams(values) {
		return {
			batch_name: values.batch,
			google_meet_account: props.googleMeetAccount,
			...values,
		}
	},
})

// OSLMS-CUSTOM: edits and post-create reminders go through the os_lms update_live_class endpoint
const updateLiveClassResource = createResource({
	url: 'os_lms.os_lms.api.update_live_class',
})

const submitLiveClass = (close) => {
	// OSLMS-CUSTOM: ignore a second click while a save is in flight, then route to create or update
	if (saving.value) {
		return
	}
	if (isEdit.value) {
		return submitUpdate(close)
	}
	return submitCreate(close)
}

const submitCreate = (close) => {
	// OSLMS-CUSTOM: validation really blocks the submit (upstream validate() dropped the message)
	const validation = validateFormFields()
	if (validation) {
		toast.error(validation)
		return
	}
	const resource =
		props.conferencingProvider === 'Google Meet'
			? createGoogleMeetLiveClass
			: createLiveClass
	saving.value = true
	return resource.submit(liveClass, {
		onSuccess(data) {
			persistRemindersAfterCreate(data, close)
		},
		onError(err) {
			saving.value = false
			toast.error(err.messages?.[0] || err)
			console.error(err)
		},
	})
}

// OSLMS-CUSTOM: reminders are saved on the new class right after the upstream create call
const persistRemindersAfterCreate = (created, close) => {
	if (!liveClass.reminders.length) {
		liveClasses.value.reload()
		refreshForm()
		saving.value = false
		close()
		return
	}
	updateLiveClassResource.submit(
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
			onSuccess() {
				liveClasses.value.reload()
				refreshForm()
				saving.value = false
				close()
			},
			onError(err) {
				saving.value = false
				toast.error(err.messages?.[0] || err)
			},
		},
	)
}

const submitUpdate = (close) => {
	const validation = validateEditFields()
	if (validation) {
		toast.error(validation)
		return
	}
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
	updateLiveClassResource.submit(
		{
			name: props.liveClass.name,
			payload,
		},
		{
			onSuccess() {
				toast.success(__('Live class updated'))
				liveClasses.value.reload()
				saving.value = false
				close()
			},
			onError(err) {
				saving.value = false
				toast.error(err.messages?.[0] || err)
			},
		},
	)
}

// OSLMS-CUSTOM: only a real reschedule must land in the future when editing
const scheduleChanged = () => {
	if (!props.liveClass) return true
	// The stored time comes back as HH:mm:ss, the form holds HH:mm.
	const sameTime =
		String(liveClass.time || '').slice(0, 5) ===
		String(props.liveClass.time || '').slice(0, 5)
	return !(
		liveClass.date === props.liveClass.date &&
		sameTime &&
		Number(liveClass.duration) === Number(props.liveClass.duration) &&
		liveClass.timezone === props.liveClass.timezone
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
			true,
		)
		if (
			liveClassDateTime.isSameOrBefore(
				dayjs().tz(liveClass.timezone, false),
				'minute',
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

const refreshForm = () => {
	liveClass.title = ''
	liveClass.description = ''
	liveClass.date = ''
	liveClass.time = ''
	liveClass.duration = ''
	liveClass.timezone = getUserTimezone()
	liveClass.auto_recording = 'No Recording'
	liveClass.reminders = []
}
</script>
