<template>
	<Dialog
		v-model="show"
		:options="{
			title: pending
				? __('Account deletion request')
				: mode === 'request'
					? __('Request account deletion')
					: __('Delete account'),
			size: 'lg',
			actions,
		}"
	>
		<template #body-content>
			<div class="space-y-4 text-p-base text-ink-gray-8">
				<template v-if="pending">
					<p class="font-medium text-ink-gray-9">
						{{
							__(
								'You asked to delete your account on {0}. A platform manager will decide by {1}.',
							).format(
								formatDate(pending.requested_on),
								formatDate(pending.due_on),
							)
						}}
					</p>
					<p>
						{{
							__(
								'Until then your account stays active. If you changed your mind, withdraw the request.',
							)
						}}
					</p>
				</template>
				<template v-else>
					<p class="font-medium text-ink-gray-9">
						{{
							mode === 'request'
								? __(
										'A platform manager reviews your request within 60 days. Once approved, your account and your personal data are deleted for good.',
									)
								: __(
										'This deletes your account and your personal data for good. It cannot be undone.',
									)
						}}
					</p>
					<ul class="list-disc space-y-1 ps-5">
						<li>
							{{
								__(
									'Deleted: your profile, enrollments, progress, quiz and assignment results, certificates, notes, discussions and conversations with the AI assistants.',
								)
							}}
						</li>
						<li v-if="isStaff">
							{{
								__(
									'Courses, lessons and live classes you created stay on the platform without your name.',
								)
							}}
						</li>
						<li>
							{{
								__('Badges already issued on TrueSkills stay on TrueSkills.')
							}}
						</li>
						<li v-if="mode === 'request'">
							{{
								__(
									'Until the decision your account stays active and you can withdraw the request.',
								)
							}}
						</li>
					</ul>
					<p v-if="start.loading" class="text-ink-gray-6">
						{{ __('Loading...') }}
					</p>
					<FormControl
						v-else-if="method"
						v-model="secret"
						:type="method === 'password' ? 'password' : 'text'"
						:label="method === 'password' ? __('Password') : __('Code')"
						:description="
							method === 'code'
								? __('Enter the code we sent to your email.')
								: undefined
						"
						autocomplete="off"
						@keydown.enter="confirm"
					/>
				</template>
				<p v-if="errorMessage" class="text-p-sm text-ink-red-6" role="alert">
					{{ errorMessage }}
				</p>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
// Self-service account deletion (ESG point 3).
// The user proves it is them with their password, or with a code sent by
// email when the account has none (social login). In "direct" mode the server
// has then already closed every session, so the page leaves for the site root.
// In "request" mode (LMS Settings review on, user neither Gestore nor admin)
// the same check files a request a Gestore decides on; the account stays
// active and the dialog shows the pending request, which can be withdrawn.
import { computed, inject, ref, watch } from 'vue'
import { Dialog, FormControl, createResource, toast } from 'frappe-ui'
import dayjs from '@/utils/dayjs'

type PendingRequest = { name: string; requested_on: string; due_on: string }

const show = defineModel<boolean>({ default: false })
const $user = inject<any>('$user')

const method = ref<'password' | 'code' | null>(null)
const mode = ref<'direct' | 'request'>('direct')
const pending = ref<PendingRequest | null>(null)
const secret = ref('')

const isStaff = computed(() =>
	Boolean(
		$user?.data?.is_instructor ||
		$user?.data?.is_moderator ||
		$user?.data?.is_evaluator,
	),
)

const formatDate = (value: string) => dayjs(value).format('DD/MM/YYYY')

const start = createResource({
	url: 'os_lms.os_lms.account_deletion.start_account_deletion',
	onSuccess(data: {
		method?: 'password' | 'code'
		mode?: 'direct' | 'request'
		pending?: PendingRequest
	}) {
		method.value = data.method || null
		mode.value = data.mode || 'direct'
		pending.value = data.pending || null
	},
})

const deleteAccount = createResource({
	url: 'os_lms.os_lms.account_deletion.delete_my_account',
	makeParams() {
		return { secret: secret.value }
	},
	onSuccess(data: { requested?: boolean; pending?: PendingRequest }) {
		if (data?.requested) {
			pending.value = data.pending || null
			secret.value = ''
			toast.success(__('Your request has been sent.'))
			return
		}
		window.location.href = '/'
	},
})

const withdraw = createResource({
	url: 'os_lms.os_lms.account_deletion_requests.withdraw_my_request',
	onSuccess() {
		toast.success(__('Your request has been withdrawn.'))
		show.value = false
	},
})

const actions = computed(() => {
	if (pending.value) {
		return [
			{
				label: __('Withdraw request'),
				variant: 'solid' as const,
				loading: withdraw.loading,
				onClick: () => withdraw.submit(),
			},
		]
	}
	return [
		{
			label:
				mode.value === 'request' ? __('Send request') : __('Delete account'),
			variant: 'solid' as const,
			theme: 'red' as const,
			disabled: !method.value || !secret.value,
			loading: deleteAccount.loading,
			onClick: confirm,
		},
	]
})

const errorMessage = computed(() => {
	const error = (deleteAccount.error || start.error || withdraw.error) as any
	return error ? error.messages?.[0] || error.message : ''
})

// The pages mount the dialog only while it is open, so it starts open.
watch(
	show,
	(open) => {
		if (!open) return
		method.value = null
		mode.value = 'direct'
		pending.value = null
		secret.value = ''
		deleteAccount.reset()
		withdraw.reset()
		start.submit()
	},
	{ immediate: true },
)

function confirm() {
	if (!method.value || !secret.value || deleteAccount.loading) return
	deleteAccount.submit()
}
</script>
