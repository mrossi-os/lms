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
					onClick: ({ close }) => submitLiveClass(close),
				},
			],
		}"
	>
		<template #body-content>
			<div class="flex flex-col gap-4">
				<div
					v-if="isEdit"
					class="flex items-start gap-2 bg-surface-amber-1 px-3 py-2 rounded-lg text-ink-amber-3 text-sm"
				>
					<AlertCircle class="size-4 shrink-0 stroke-1.5 mt-0.5" />
					<span>
						{{
							__(
								"Per cambiare data, ora o durata della lezione, eliminala e ricreala.",
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
							:disabled="isEdit"
						/>
						<FormControl
							type="number"
							v-model="liveClass.duration"
							:label="__('Duration (in minutes)')"
							:required="true"
							:disabled="isEdit"
						/>
					</div>
					<div class="space-y-4">
						<Tooltip
							:text="
								__(
									'Time must be in 24 hour format (HH:mm). Example 11:30 or 22:00',
								)
							"
						>
							<FormControl
								v-model="liveClass.time"
								type="time"
								:label="__('Time')"
								:required="true"
								:disabled="isEdit"
							/>
						</Tooltip>

						<div class="space-y-1.5">
							<label class="block text-ink-gray-5 text-xs" for="batchTimezone">
								{{ __('Timezone') }}
								<span class="text-ink-red-3">*</span>
							</label>
							<Autocomplete
								@update:modelValue="(opt) => (liveClass.timezone = opt.value)"
								:modelValue="liveClass.timezone"
								:options="getTimezoneOptions()"
								:required="true"
								:disabled="isEdit"
							/>
						</div>
						<FormControl
							v-if="
								!isEdit && props.conferencingProvider === 'Zoom'
							"
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
				<div class="border-t pt-4">
					<div class="flex items-center justify-between mb-2">
						<label class="text-ink-gray-7 text-sm font-medium">
							{{ __('Reminders') }}
						</label>
						<Button @click="addReminder" :variant="'subtle'">
							<template #prefix>
								<Plus class="w-4 h-4" />
							</template>
							{{ __('Add Reminder') }}
						</Button>
					</div>
					<div
						v-if="!liveClass.reminders.length"
						class="text-ink-gray-5 text-sm leading-5"
					>
						{{ __('No reminders configured. Add one to notify students before the class.') }}
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
								{{ __('Sent') }} {{ dayjs(row.sent_at).format('DD MMM HH:mm') }}
							</span>
							<span v-else class="text-ink-gray-4">
								{{ __('Not sent yet') }}
							</span>
						</div>
						<Button @click="removeReminder(idx)" :variant="'ghost'">
							<template #icon>
								<Trash2 class="w-4 h-4 text-ink-red-3" />
							</template>
						</Button>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, createResource, Tooltip, FormControl, Button, toast } from 'frappe-ui'
import { Plus, Trash2, AlertCircle } from 'lucide-vue-next'
import { reactive, computed, inject, onMounted } from 'vue'
import { getTimezones, getUserTimezone } from '@/utils/'
import Autocomplete from '@/components/Controls/Autocomplete.vue'

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

const isEdit = computed(() => !!props.liveClass)

const reminderUnitOptions = [
	{ label: __('Minutes'), value: 'Minutes' },
	{ label: __('Hours'), value: 'Hours' },
	{ label: __('Days'), value: 'Days' },
]

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
		liveClass.time = props.liveClass.time || ''
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

const updateLiveClassResource = createResource({
	url: 'os_lms.os_lms.api.update_live_class',
})

const submitLiveClass = (close) => {
	if (isEdit.value) {
		return submitUpdate(close)
	}
	return submitCreate(close)
}

const submitCreate = (close) => {
	const resource =
		props.conferencingProvider === 'Google Meet'
			? createGoogleMeetLiveClass
			: createLiveClass
	return resource.submit(liveClass, {
		validate() {
			return validateFormFields()
		},
		onSuccess(data) {
			persistRemindersAfterCreate(data, close)
		},
		onError(err) {
			toast.error(err.messages?.[0] || err)
			console.error(err)
		},
	})
}

const persistRemindersAfterCreate = (created, close) => {
	if (!liveClass.reminders.length) {
		liveClasses.value.reload()
		refreshForm()
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
				close()
			},
			onError(err) {
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
	updateLiveClassResource.submit(
		{
			name: props.liveClass.name,
			payload: {
				title: liveClass.title,
				description: liveClass.description,
				reminders: liveClass.reminders.map((r) => ({
					offset_value: r.offset_value,
					offset_unit: r.offset_unit,
					sent_at: r.sent_at || null,
				})),
			},
		},
		{
			onSuccess() {
				toast.success(__('Live class updated'))
				liveClasses.value.reload()
				close()
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		},
	)
}

const validateEditFields = () => {
	if (!liveClass.title) {
		return __('Please enter a title.')
	}
	for (const r of liveClass.reminders) {
		if (!r.offset_value || r.offset_value < 1) {
			return __('Reminders must have a positive offset value.')
		}
	}
}

const validateFormFields = () => {
	if (!liveClass.title) {
		return __('Please enter a title.')
	}
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
	if (!liveClass.duration) {
		return __('Please select a duration.')
	}
	for (const r of liveClass.reminders) {
		if (!r.offset_value || r.offset_value < 1) {
			return __('Reminders must have a positive offset value.')
		}
	}
}

const valideTime = () => {
	let time = liveClass.time.split(':')
	if (time.length != 2) {
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
