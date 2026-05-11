<template>
	<div class="flex flex-col min-h-0 text-base">
		<div class="flex items-center justify-between mb-5">
			<div class="flex flex-col space-y-2">
				<div class="text-xl font-semibold text-ink-gray-9">
					{{ label }}
				</div>
				<div class="text-ink-gray-6 leading-5">
					{{ __(description) }}
				</div>
			</div>
			<div v-if="oauthConfigured.data" class="flex items-center space-x-5">
				<Button @click="openForm('new')">
					<template #prefix>
						<Plus class="h-3 w-3 stroke-1.5" />
					</template>
					{{ __('New') }}
				</Button>
			</div>
		</div>

		<div
			v-if="oauthConfigured.loading"
			class="text-ink-gray-6 text-sm"
		>
			{{ __('Checking Google OAuth configuration...') }}
		</div>

		<div
			v-else-if="!oauthConfigured.data"
			class="flex items-start gap-3 bg-surface-amber-2 text-ink-amber-3 text-sm p-4 rounded-md"
		>
			<CircleAlert class="h-5 w-5 stroke-1.5 shrink-0 mt-0.5" />
			<div class="space-y-2">
				<div class="font-semibold">
					{{ __('Google OAuth credentials are not configured.') }}
				</div>
				<div>
					{{
						__(
							'Configure client ID and secret in Google Settings before creating calendars.',
						)
					}}
				</div>
				<a
					href="/app/google-settings"
					target="_blank"
					class="underline font-medium"
				>
					{{ __('Open Google Settings') }}
				</a>
			</div>
		</div>

		<div v-else-if="googleCalendars.data?.length" class="overflow-y-auto">
			<ListView
				:columns="columns"
				:rows="googleCalendars.data"
				row-key="name"
				:options="{
					showTooltip: false,
					onRowClick: (row) => {
						openForm(row.name)
					},
				}"
			>
				<ListHeader
					class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
				>
					<ListHeaderItem :item="item" v-for="item in columns">
						<template #prefix="{ item }">
							<FeatherIcon
								v-if="item.icon"
								:name="item.icon"
								class="h-4 w-4 stroke-1.5"
							/>
						</template>
					</ListHeaderItem>
				</ListHeader>

				<ListRows>
					<ListRow :row="row" v-for="row in googleCalendars.data">
						<template #default="{ column }">
							<ListRowItem :item="row[column.key]" :align="column.align">
								<div v-if="column.key == 'enable'">
									<Badge v-if="row[column.key]" theme="green">
										{{ __('Enabled') }}
									</Badge>
									<Badge v-else theme="gray">
										{{ __('Disabled') }}
									</Badge>
								</div>
								<div v-else-if="column.key == 'authorization_code'">
									<Badge v-if="row[column.key]" theme="green">
										<Check class="h-3 w-3 stroke-1.5 mr-1" />
										{{ __('Authorized') }}
									</Badge>
									<Badge v-else theme="orange">
										<CircleAlert class="h-3 w-3 stroke-1.5 mr-1" />
										{{ __('Not authorized') }}
									</Badge>
								</div>
								<div v-else class="leading-5 text-sm">
									{{ row[column.key] }}
								</div>
							</ListRowItem>
						</template>
					</ListRow>
				</ListRows>

				<ListSelectBanner>
					<template #actions="{ unselectAll, selections }">
						<div class="flex gap-2">
							<Button
								variant="ghost"
								@click="removeCalendars(selections, unselectAll)"
							>
								<Trash2 class="h-4 w-4 stroke-1.5" />
							</Button>
						</div>
					</template>
				</ListSelectBanner>
			</ListView>
		</div>

		<div
			v-else-if="oauthConfigured.data"
			class="text-ink-gray-6 text-sm py-8 text-center"
		>
			{{ __('No Google Calendars yet. Click "New" to create one.') }}
		</div>
	</div>

	<GoogleCalendarModal
		v-model="showForm"
		v-model:googleCalendars="googleCalendars"
		:calendarID="currentCalendar"
	/>
</template>

<script setup lang="ts">
import {
	Badge,
	Button,
	call,
	createListResource,
	createResource,
	FeatherIcon,
	ListHeader,
	ListHeaderItem,
	ListRow,
	ListRowItem,
	ListRows,
	ListSelectBanner,
	ListView,
	toast,
} from 'frappe-ui'
import { computed, inject, onMounted, ref } from 'vue'
import { Check, CircleAlert, Plus, Trash2 } from 'lucide-vue-next'
import { cleanError } from '@/utils'
import { User } from '@/components/Settings/types'
import GoogleCalendarModal from '@/components/Settings/GoogleCalendarModal.vue'

const user = inject<User | null>('$user')
const showForm = ref(false)
const currentCalendar = ref<string | null>(null)

const props = defineProps({
	label: String,
	description: String,
})

const oauthConfigured = createResource({
	url: 'os_lms.os_lms.google_calendar.is_google_oauth_configured',
	auto: true,
	onSuccess(isConfigured: boolean) {
		if (isConfigured) {
			fetchGoogleCalendars()
		}
	},
})

const googleCalendars = createListResource({
	doctype: 'Google Calendar',
	fields: [
		'name',
		'calendar_name',
		'user',
		'google_calendar_id',
		'authorization_code',
		'enable',
		'owner',
	],
	cache: ['googleCalendars'],
})

onMounted(() => {
	// If OAuth is already cached as configured, kick off the list fetch.
	if (oauthConfigured.data) fetchGoogleCalendars()
})

const fetchGoogleCalendars = () => {
	if (!user?.data?.is_system_manager) {
		googleCalendars.update({
			filters: { owner: user?.data?.email },
		})
	}
	googleCalendars.reload()
}

const openForm = (calendarID: string) => {
	currentCalendar.value = calendarID
	showForm.value = true
}

const removeCalendars = (selections: Set<string>, unselectAll: () => void) => {
	call('lms.lms.api.delete_documents', {
		doctype: 'Google Calendar',
		documents: Array.from(selections),
	})
		.then(() => {
			googleCalendars.reload()
			toast.success(__('Google Calendar deleted successfully'))
			unselectAll()
		})
		.catch((err: any) => {
			toast.error(
				cleanError(err.messages?.[0]) ||
					__('Error deleting Google Calendar'),
			)
		})
}

const columns = computed(() => {
	return [
		{
			label: __('Calendar Name'),
			key: 'calendar_name',
			icon: 'calendar',
		},
		{
			label: __('User'),
			key: 'user',
			icon: 'user',
		},
		{
			label: __('Status'),
			key: 'enable',
			align: 'center',
			icon: 'check-square',
		},
		{
			label: __('Authorization'),
			key: 'authorization_code',
			align: 'center',
			icon: 'shield',
		},
	]
})
</script>
