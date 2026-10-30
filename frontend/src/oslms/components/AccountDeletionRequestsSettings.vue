<template>
	<SettingsLayout :title="label" :description="description">
		<div
			v-if="requests.loading && !requests.data"
			class="flex flex-1 items-center justify-center p-10"
		>
			<LoadingIndicator class="size-5 text-ink-gray-5" />
		</div>

		<div v-else-if="requests.error" class="p-10 text-center text-ink-gray-6">
			{{ __('You are not authorized to review account deletion requests.') }}
		</div>

		<div v-else-if="requests.data" class="space-y-8">
			<section class="space-y-3">
				<div class="space-y-1">
					<h2 class="text-base font-semibold text-ink-gray-9">
						{{ __('Pending requests') }} ({{ pendingRows.length }})
					</h2>
					<p class="text-p-sm text-ink-gray-6">
						{{
							__(
								'Approve to delete the account and its personal data for good, or reject with a reason the user receives by email. Decide within {0} days of the request.',
							).format(requests.data.review_days)
						}}
					</p>
				</div>

				<p
					v-if="!pendingRows.length"
					class="rounded-md border p-4 text-p-base text-ink-gray-6"
				>
					{{ __('No pending requests.') }}
				</p>

				<div
					v-for="request in pendingRows"
					:key="request.name"
					class="flex flex-col gap-3 rounded-md border p-4 sm:flex-row sm:items-center"
				>
					<div class="min-w-0 flex-1 space-y-1">
						<div class="flex flex-wrap items-center gap-2">
							<span class="truncate font-medium text-ink-gray-9">
								{{ request.full_name || request.user }}
							</span>
							<Badge :theme="dueTheme(request.days_left)">
								{{ dueLabel(request.days_left) }}
							</Badge>
						</div>
						<div class="truncate text-p-sm text-ink-gray-6">
							{{ request.user }}
						</div>
						<div class="text-p-sm text-ink-gray-6">
							{{
								__('Requested on {0}, decide by {1}').format(
									formatDate(request.requested_on),
									formatDate(request.due_on),
								)
							}}
						</div>
					</div>
					<div class="flex shrink-0 gap-2">
						<Button @click="openReject(request)">
							{{ __('Reject') }}
						</Button>
						<Button theme="red" variant="solid" @click="openApprove(request)">
							{{ __('Approve and delete') }}
						</Button>
					</div>
				</div>
			</section>

			<section v-if="decidedRows.length" class="space-y-3">
				<h2 class="text-base font-semibold text-ink-gray-9">
					{{ __('Recent decisions') }}
				</h2>
				<div class="divide-y rounded-md border">
					<div
						v-for="request in decidedRows"
						:key="request.name"
						class="space-y-1 p-4"
					>
						<div class="flex flex-wrap items-center gap-2">
							<span class="font-medium text-ink-gray-9">
								{{
									request.user
										? request.full_name || request.user
										: __('Deleted account')
								}}
							</span>
							<Badge :theme="statusTheme(request.status)">
								{{ statusLabel(request.status) }}
							</Badge>
						</div>
						<div class="text-p-sm text-ink-gray-6">
							{{ decisionLine(request) }}
						</div>
						<div
							v-if="request.rejection_reason"
							class="whitespace-pre-line text-p-sm text-ink-gray-7"
						>
							{{ request.rejection_reason }}
						</div>
					</div>
				</div>
			</section>
		</div>

		<Dialog
			v-model:open="showApprove"
			:title="__('Delete this account?')"
			size="md"
			:actions="[
				{
					label: __('Approve and delete'),
					variant: 'solid',
					theme: 'red',
					loading: approve.loading,
					onClick: () => approve.submit(),
				},
			]"
		>
			<div class="space-y-3 text-p-base text-ink-gray-8">
				<p>
					{{
						__(
							'The account of {0} and their personal data are deleted for good. It cannot be undone.',
						).format(selected?.full_name || selected?.user || '')
					}}
				</p>
				<p v-if="dialogError" class="text-p-sm text-ink-red-6" role="alert">
					{{ dialogError }}
				</p>
			</div>
		</Dialog>

		<Dialog
			v-model:open="showReject"
			:title="__('Reject the request')"
			size="md"
			:actions="[
				{
					label: __('Reject'),
					variant: 'solid',
					disabled: !reason.trim(),
					loading: reject.loading,
					onClick: () => reject.submit(),
				},
			]"
		>
			<div class="space-y-3 text-p-base text-ink-gray-8">
				<FormControl
					v-model="reason"
					type="textarea"
					:label="__('Reason')"
					:description="__('The user receives it by email.')"
					:maxlength="1000"
					:rows="4"
				/>
				<p v-if="dialogError" class="text-p-sm text-ink-red-6" role="alert">
					{{ dialogError }}
				</p>
			</div>
		</Dialog>
	</SettingsLayout>
</template>

<script setup lang="ts">
// Review of the account deletion requests (ESG, os_lms
// account_deletion_requests.py), a Settings tab: Gestore and administrators
// only, which the server checks on every call; the tab follows
// show_account_deletion_requests from get_user_info.
import { computed, ref } from 'vue'
import {
	Badge,
	Button,
	Dialog,
	FormControl,
	LoadingIndicator,
	createResource,
	toast,
} from 'frappe-ui'
import SettingsLayout from '@/components/Layouts/SettingsLayout.vue'
import dayjs from '@/utils/dayjs'

defineProps<{ label: string; description?: string }>()

type Request = {
	name: string
	user: string | null
	full_name: string | null
	status: 'Pending' | 'Approved' | 'Rejected' | 'Withdrawn'
	requested_on: string
	due_on: string
	days_left?: number
	decided_on: string | null
	decided_by_name?: string | null
	rejection_reason: string | null
}

const requests = createResource({
	url: 'os_lms.os_lms.account_deletion_requests.get_requests',
	method: 'GET',
	auto: true,
})

const pendingRows = computed<Request[]>(() => requests.data?.pending || [])
const decidedRows = computed<Request[]>(() => requests.data?.decided || [])

const selected = ref<Request | null>(null)
const showApprove = ref(false)
const showReject = ref(false)
const reason = ref('')

const formatDate = (value: string | null) =>
	value ? dayjs(value).format('DD/MM/YYYY') : ''

const dueTheme = (daysLeft = 0) =>
	daysLeft < 0 ? 'red' : daysLeft <= 7 ? 'orange' : 'gray'

const dueLabel = (daysLeft = 0) => {
	if (daysLeft > 0) return __('{0} days left').format(daysLeft)
	if (daysLeft === 0) return __('Due today')
	return __('Overdue by {0} days').format(-daysLeft)
}

// "Approved" alone is already translated in the masculine elsewhere.
const statusLabel = (status: Request['status']) =>
	({
		Pending: __('Pending'),
		Approved: __('Approved and deleted'),
		Rejected: __('Rejected'),
		Withdrawn: __('Withdrawn'),
	})[status]

const statusTheme = (status: Request['status']) =>
	status === 'Approved' ? 'red' : status === 'Rejected' ? 'orange' : 'gray'

const decisionLine = (request: Request) => {
	const requested = __('Requested on {0}').format(
		formatDate(request.requested_on),
	)
	if (request.status === 'Withdrawn') {
		return `${requested} · ${__('withdrawn by the user on {0}').format(formatDate(request.decided_on))}`
	}
	const decided = request.decided_by_name
		? __('decided by {0} on {1}').format(
				request.decided_by_name,
				formatDate(request.decided_on),
			)
		: __('decided on {0}').format(formatDate(request.decided_on))
	return `${requested} · ${decided}`
}

const openApprove = (request: Request) => {
	selected.value = request
	approve.reset()
	showApprove.value = true
}

const openReject = (request: Request) => {
	selected.value = request
	reason.value = ''
	reject.reset()
	showReject.value = true
}

const approve = createResource({
	url: 'os_lms.os_lms.account_deletion_requests.approve_request',
	makeParams: () => ({ name: selected.value?.name }),
	onSuccess() {
		showApprove.value = false
		toast.success(__('Request approved: the account is being deleted.'))
		requests.reload()
	},
})

const reject = createResource({
	url: 'os_lms.os_lms.account_deletion_requests.reject_request',
	makeParams: () => ({ name: selected.value?.name, reason: reason.value }),
	onSuccess() {
		showReject.value = false
		toast.success(__('Request rejected: the user has been notified.'))
		requests.reload()
	},
})

const dialogError = computed(() => {
	const error = (showApprove.value ? approve.error : reject.error) as any
	return error ? error.messages?.[0] || error.message : ''
})
</script>
