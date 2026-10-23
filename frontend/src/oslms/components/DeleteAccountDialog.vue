<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Delete account'),
			size: 'lg',
			actions: [
				{
					label: __('Delete account'),
					variant: 'solid',
					theme: 'red',
					disabled: !method || !secret,
					loading: deleteAccount.loading,
					onClick: confirm,
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4 text-p-base text-ink-gray-8">
				<p class="font-medium text-ink-gray-9">
					{{
						__(
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
						{{ __('Badges already issued on TrueSkills stay on TrueSkills.') }}
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
// email when the account has none (social login). On success the server has
// already closed every session, so the page leaves for the site root.
import { computed, inject, ref, watch } from 'vue'
import { Dialog, FormControl, createResource } from 'frappe-ui'

const show = defineModel<boolean>({ default: false })
const $user = inject<any>('$user')

const method = ref<'password' | 'code' | null>(null)
const secret = ref('')

const isStaff = computed(() =>
	Boolean(
		$user?.data?.is_instructor ||
		$user?.data?.is_moderator ||
		$user?.data?.is_evaluator,
	),
)

const start = createResource({
	url: 'os_lms.os_lms.account_deletion.start_account_deletion',
	onSuccess(data: { method: 'password' | 'code' }) {
		method.value = data.method
	},
})

const deleteAccount = createResource({
	url: 'os_lms.os_lms.account_deletion.delete_my_account',
	makeParams() {
		return { secret: secret.value }
	},
	onSuccess() {
		window.location.href = '/'
	},
})

const errorMessage = computed(() => {
	const error = (deleteAccount.error || start.error) as any
	return error ? error.messages?.[0] || error.message : ''
})

// The pages mount the dialog only while it is open, so it starts open.
watch(
	show,
	(open) => {
		if (!open) return
		method.value = null
		secret.value = ''
		deleteAccount.reset()
		start.submit()
	},
	{ immediate: true },
)

const confirm = () => {
	if (!method.value || !secret.value || deleteAccount.loading) return
	deleteAccount.submit()
}
</script>
