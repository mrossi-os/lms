<template>
	<Dialog
		v-model:open="show"
		:title="__('Privacy policy')"
		size="md"
		:dismissible="false"
		:show-close-button="false"
		:actions="actions"
	>
		<div class="space-y-4 text-p-base text-ink-gray-8">
			<p>
				{{
					__(
						'To keep using the platform, read the privacy policy and confirm you accept it.',
					)
				}}
			</p>
			<label class="flex cursor-pointer items-start gap-2">
				<input
					v-model="accepted"
					type="checkbox"
					class="mt-1 shrink-0 rounded-sm border-outline-gray-2 text-ink-gray-9"
				/>
				<span>
					{{ labelParts[0]
					}}<a
						:href="safeUrl(policyUrl)"
						v-external
						class="font-medium underline"
						>{{ __('privacy policy') }}</a
					>{{ labelParts[1] }}
				</span>
			</label>
			<p v-if="errorMessage" class="text-p-sm text-ink-red-6" role="alert">
				{{ errorMessage }}
			</p>
		</div>
	</Dialog>
</template>

<script setup lang="ts">
// Privacy policy acceptance after login (ESG, os_lms privacy_consent.py).
// Shown, without a way to close it, to every logged-in user get_user_info
// flags with privacy_consent_required: no acceptance recorded yet while
// LMS Settings has a policy URL. Accepting records it on the User; the
// alternative is logging out.
import { computed, ref } from 'vue'
import { Dialog, createResource } from 'frappe-ui'
import { sessionStore } from '@/stores/session'
import { usersStore } from '@/stores/user'
import { safeUrl } from '@/utils/safeUrl'
import { translationsLoaded } from '@/translation'

// Not inject('$user'): main.js provides it after app.mount, so a component
// set up with App (this one) would get undefined. The store is the same resource.
const { userResource: $user } = usersStore()
const { logout } = sessionStore()
const accepted = ref(false)

// Without a safe link there is nothing to accept, so the dialog stays closed.
const policyUrl = computed(
	() => safeUrl(String($user.data?.privacy_policy_url || '').trim()) || '',
)

const show = computed({
	get: () => Boolean($user.data?.privacy_consent_required && policyUrl.value),
	set: () => {},
})

// The sentence is translated whole, the link sits where {0} is. __() returns
// a { format } object for a message with placeholders, so {0} is put back and
// split on. Reading translationsLoaded recomputes it once the messages land.
const labelParts = computed(() => {
	translationsLoaded.value
	const [before, after = ''] = __('I have read and accept the {0}')
		.format('{0}')
		.split('{0}')
	return [before, after]
})

const accept = createResource({
	url: 'os_lms.os_lms.privacy_consent.accept_privacy_policy',
	onSuccess() {
		if ($user.data) $user.data.privacy_consent_required = false
	},
})

const actions = computed(() => {
	translationsLoaded.value
	return [
		{
			label: __('Accept'),
			variant: 'solid' as const,
			disabled: !accepted.value,
			loading: accept.loading,
			onClick: () => accept.submit(),
		},
		{
			label: __('Log out'),
			loading: logout.loading,
			onClick: () => logout.submit(),
		},
	]
})

const errorMessage = computed(() => {
	const error = accept.error as any
	return error ? error.messages?.[0] || error.message : ''
})
</script>
