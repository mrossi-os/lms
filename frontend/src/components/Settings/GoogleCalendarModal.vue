<template>
	<Dialog
		v-model="show"
		:options="{
			title:
				calendarID === 'new'
					? __('New Google Calendar')
					: __('Edit Google Calendar'),
			size: 'xl',
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					onClick: ({ close }) => {
						saveCalendar(close)
					},
				},
			],
		}"
	>
		<template #body-content>
			<div class="mb-4">
				<Switch
					size="sm"
					v-model="calendar.enable"
					:label="__('Enabled')"
					:description="
						__('Activate this calendar for syncing events with Google.')
					"
				/>
			</div>
			<div class="grid grid-cols-2 gap-5">
				<FormControl
					v-model="calendar.calendar_name"
					:label="__('Calendar Name')"
					type="text"
					:required="true"
				/>
				<Link
					v-model="calendar.user"
					:label="__('User')"
					doctype="User"
					:required="true"
				/>
			</div>

			<div
				v-if="calendarID !== 'new'"
				class="mt-6 pt-5 border-t border-outline-gray-1"
			>
				<div class="text-sm font-semibold text-ink-gray-9 mb-2">
					{{ __('Google Authorization') }}
				</div>
				<div class="flex items-center justify-between gap-4">
					<div class="text-sm">
						<Badge v-if="calendar.authorization_code" theme="green">
							<Check class="h-3 w-3 stroke-1.5 mr-1" />
							{{ __('Calendar is authorized') }}
						</Badge>
						<Badge v-else theme="orange">
							<CircleAlert class="h-3 w-3 stroke-1.5 mr-1" />
							{{ __('Not authorized yet') }}
						</Badge>
					</div>
					<Button @click="authorize">
						{{
							calendar.authorization_code
								? __('Re-authorize Google Calendar')
								: __('Authorize Google Calendar Access')
						}}
					</Button>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { Badge, Button, call, Dialog, FormControl, toast } from 'frappe-ui'
import { Check, CircleAlert } from 'lucide-vue-next'
import Switch from '@/oslms/components/Form/Switch.vue'
import { inject, reactive, watch } from 'vue'
import { User } from '@/components/Settings/types'
import { cleanError } from '@/utils'
import Link from '@/components/Controls/Link.vue'

interface GoogleCalendar {
	name: string
	calendar_name: string
	user: string
	enable: boolean
	authorization_code?: string
}

interface GoogleCalendars {
	data: GoogleCalendar[]
	reload: () => void
	insert: {
		submit: (
			data: Partial<GoogleCalendar>,
			options: { onSuccess: () => void; onError: (err: any) => void },
		) => void
	}
	setValue: {
		submit: (
			data: Partial<GoogleCalendar> & { name: string },
			options: { onSuccess: () => void; onError: (err: any) => void },
		) => void
	}
}

const show = defineModel('show')
const user = inject<User | null>('$user')
const googleCalendars = defineModel<GoogleCalendars>('googleCalendars')

const calendar = reactive<Partial<GoogleCalendar>>({
	calendar_name: '',
	user: user?.data?.email || '',
	enable: true,
})

const props = defineProps({
	calendarID: {
		type: String,
		default: 'new',
	},
})

watch(
	() => props.calendarID,
	(id) => {
		if (id === 'new') {
			calendar.calendar_name = ''
			calendar.user = user?.data?.email || ''
			calendar.enable = true
			calendar.authorization_code = ''
		} else if (id) {
			const found = googleCalendars.value?.data.find((c) => c.name === id)
			if (found) {
				calendar.calendar_name = found.calendar_name
				calendar.user = found.user
				calendar.enable = found.enable ?? true
				calendar.authorization_code = found.authorization_code || ''
			}
		}
	},
)

const saveCalendar = (close: () => void) => {
	if (props.calendarID === 'new') {
		createCalendar(close)
	} else {
		updateCalendar(close)
	}
}

const createCalendar = (close: () => void) => {
	googleCalendars.value?.insert.submit(
		{
			calendar_name: calendar.calendar_name,
			user: calendar.user,
			enable: calendar.enable,
		},
		{
			onSuccess() {
				googleCalendars.value?.reload()
				close()
				toast.success(__('Google Calendar created successfully'))
			},
			onError(err: any) {
				console.error(err)
				toast.error(
					cleanError(err.messages?.[0]) || __('Error creating Google Calendar'),
				)
			},
		},
	)
}

const updateCalendar = (close: () => void) => {
	googleCalendars.value?.setValue.submit(
		{
			name: props.calendarID,
			calendar_name: calendar.calendar_name,
			user: calendar.user,
			enable: calendar.enable,
		},
		{
			onSuccess() {
				googleCalendars.value?.reload()
				close()
				toast.success(__('Google Calendar updated successfully'))
			},
			onError(err: any) {
				console.error(err)
				toast.error(
					cleanError(err.messages?.[0]) || __('Error updating Google Calendar'),
				)
			},
		},
	)
}

const authorize = () => {
	if (!props.calendarID || props.calendarID === 'new') return
	const reauthorize = calendar.authorization_code ? 1 : 0
	call(
		'frappe.integrations.doctype.google_calendar.google_calendar.authorize_access',
		{
			g_calendar: props.calendarID,
			reauthorize,
		},
	)
		.then((message: any) => {
			googleCalendars.value?.setValue.submit(
				{
					name: props.calendarID,
					calendar_name: calendar.calendar_name,
					user: calendar.user,
					enable: calendar.enable,
				},
				{
					onSuccess() {
						googleCalendars.value?.reload()
					},
					onError(err: any) {
						console.error(err)
					},
				},
			)
			if (message?.url) {
				window.open(message.url)
			}
		})
		.catch((err: any) => {
			console.error(err)
			toast.error(
				cleanError(err.messages?.[0]) ||
					__('Error authorizing Google Calendar'),
			)
		})
}
</script>
