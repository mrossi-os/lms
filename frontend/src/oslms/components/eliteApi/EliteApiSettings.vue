<template>
	<SettingsLayout :title="label" :description="description">
		<template #header-actions>
			<Button variant="solid" @click="openCreate">
				<template #prefix>
					<span class="lucide-plus h-4 w-4" />
				</template>
				{{ __('New key') }}
			</Button>
		</template>

		<div
			v-if="!keysResource.data?.length"
			class="rounded border border-dashed border-outline-gray-2 p-6 text-center text-p-base text-ink-gray-5"
		>
			{{
				keysResource.loading
					? __('Loading...')
					: __(
							'No API keys yet. Create one to let an external system, such as TrueSkill, read courses, batches and students.',
						)
			}}
		</div>

		<div
			v-else
			class="divide-y divide-outline-gray-1 rounded border border-outline-gray-2"
		>
			<div
				v-for="key in keysResource.data"
				:key="key.name"
				class="flex items-start justify-between gap-4 p-4"
			>
				<div class="min-w-0 space-y-1">
					<div class="flex items-center gap-2">
						<span class="truncate text-base font-medium text-ink-gray-9">
							{{ key.key_name }}
						</span>
						<Badge
							:theme="STATE_THEMES[key.state]"
							:label="stateLabel(key.state)"
						/>
					</div>
					<code class="block text-sm text-ink-gray-6"
						>{{ key.key_preview }}…</code
					>
					<p class="text-sm text-ink-gray-6">
						{{
							__('Key created on {0} by {1}').format(
								formatDateTime(key.created_on),
								key.created_by,
							)
						}}
					</p>
					<p class="text-sm text-ink-gray-6">
						{{
							key.last_used_on
								? __('Last used on {0} from {1}').format(
										formatDateTime(key.last_used_on),
										key.last_used_ip,
									)
								: __('This key has never been used')
						}}
					</p>
					<p v-if="key.expires_on" class="text-sm text-ink-gray-6">
						{{
							(key.state === 'expired'
								? __('Key expired on {0}')
								: __('Expires on {0}')
							).format(formatDate(key.expires_on))
						}}
					</p>
					<p v-if="key.state === 'revoked'" class="text-sm text-ink-gray-6">
						{{
							__('Key revoked on {0} by {1}').format(
								formatDateTime(key.revoked_on),
								key.revoked_by,
							)
						}}
					</p>
				</div>
				<Button
					v-if="key.state === 'active'"
					variant="subtle"
					theme="red"
					@click="askRevoke(key)"
				>
					{{ __('Revoke') }}
				</Button>
			</div>
		</div>
	</SettingsLayout>

	<Dialog
		v-model="createDialog.show"
		:title="__('New API key')"
		:actions="[
			{ label: __('Cancel'), onClick: ({ close }) => close() },
			{ label: __('Create key'), variant: 'solid', onClick: submitCreate },
		]"
	>
		<div class="space-y-4">
			<TextInput
				v-model="createDialog.keyName"
				:label="__('Name')"
				:placeholder="__('e.g. TrueSkill production')"
				:maxlength="140"
			/>
			<div class="space-y-1.5">
				<TextInput
					v-model="createDialog.expiresOn"
					type="date"
					:label="__('Expiry date (optional)')"
					:min="today"
				/>
				<p class="text-p-sm text-ink-gray-5">
					{{
						__(
							'Leave empty for a key that never expires. An expired key cannot be extended: create a new one.',
						)
					}}
				</p>
			</div>
		</div>
	</Dialog>

	<Dialog
		v-model="createdDialog.show"
		:title="__('Copy the API key now')"
		:dismissible="false"
		size="xl"
		:actions="[
			{
				label: __('I have copied the key'),
				variant: 'solid',
				onClick: ({ close }) => close(),
			},
		]"
		@after-leave="forgetCreatedKey"
	>
		<div class="space-y-4">
			<p class="text-p-base text-ink-gray-7">
				{{
					__(
						'This is the only time the full key is shown. Store it safely and give it to the system that will call the Elite API.',
					)
				}}
			</p>
			<div class="flex items-center gap-2">
				<input
					ref="keyInput"
					:value="createdDialog.key"
					readonly
					class="w-full rounded border border-outline-gray-2 bg-surface-gray-2 px-2 py-1.5 font-mono text-sm text-ink-gray-9"
					@focus="$event.target.select()"
				/>
				<Button @click="copyKey">
					<template #prefix>
						<span class="lucide-copy h-4 w-4" />
					</template>
					{{ __('Copy') }}
				</Button>
			</div>
			<div class="space-y-1.5">
				<p class="text-p-sm text-ink-gray-6">{{ __('Example request') }}</p>
				<pre
					class="overflow-x-auto whitespace-pre rounded bg-surface-gray-2 p-2 text-xs text-ink-gray-8"
					>{{ exampleRequest }}</pre
				>
			</div>
		</div>
	</Dialog>

	<Dialog
		v-model="revokeDialog.show"
		:title="__('Revoke API key?')"
		:actions="[
			{ label: __('Cancel'), onClick: ({ close }) => close() },
			{
				label: __('Revoke'),
				variant: 'solid',
				theme: 'red',
				onClick: submitRevoke,
			},
		]"
	>
		<p class="text-p-base text-ink-gray-7">
			{{
				__(
					'The key "{0}" stops working immediately and cannot be re-enabled. Systems still using it will be refused.',
				).format(revokeDialog.key?.key_name)
			}}
		</p>
	</Dialog>
</template>

<script setup>
import { computed, nextTick, reactive, ref } from 'vue'
import {
	Badge,
	Button,
	Dialog,
	TextInput,
	createResource,
	toast,
} from 'frappe-ui'
import SettingsLayout from '@/components/Layouts/SettingsLayout.vue'
import dayjs from '@/utils/dayjs'

defineProps({
	label: { type: String, required: true },
	description: { type: String },
})

const ADMIN_API = 'os_lms.os_lms.elite_api.admin'
const STATE_THEMES = { active: 'green', expired: 'orange', revoked: 'gray' }

const today = dayjs().format('YYYY-MM-DD')
const keyInput = ref(null)
const createDialog = reactive({ show: false, keyName: '', expiresOn: '' })
const createdDialog = reactive({ show: false, key: '' })
const revokeDialog = reactive({ show: false, key: null })

const keysResource = createResource({
	url: `${ADMIN_API}.list_keys`,
	method: 'GET',
	auto: true,
	onError: showError,
})

// frappe-ui resources never reject: failures go to onError and submit()
// resolves without data, which is what the handlers below check.
const createResourceCall = createResource({
	url: `${ADMIN_API}.create_key`,
	onError: showError,
})
const revokeResourceCall = createResource({
	url: `${ADMIN_API}.revoke_key`,
	onError: showError,
})

const exampleRequest = computed(
	() =>
		`curl -H "X-Elite-Api-Key: ${createdDialog.key}" \\\n  ${window.location.origin}/api/method/os_lms.os_lms.elite_api.v1.ping`,
)

function stateLabel(state) {
	// Key-specific msgids: generic ones ("Active"...) would get a gendered
	// Italian translation app-wide.
	return {
		active: __('Active key'),
		expired: __('Expired key'),
		revoked: __('Revoked key'),
	}[state]
}

function formatDate(value) {
	return value ? dayjs(value).format('DD/MM/YYYY') : ''
}

function formatDateTime(value) {
	return value ? dayjs(value).format('DD/MM/YYYY HH:mm') : ''
}

function showError(err) {
	toast.error(err?.messages?.[0] || err?.message || __('Something went wrong'))
}

function openCreate() {
	Object.assign(createDialog, { show: true, keyName: '', expiresOn: '' })
}

async function submitCreate({ close }) {
	if (!createDialog.keyName.trim()) {
		toast.error(__('The API key name is required.'))
		return
	}
	const created = await createResourceCall.submit({
		key_name: createDialog.keyName.trim(),
		expires_on: createDialog.expiresOn || null,
	})
	if (!created?.key) return
	close()
	Object.assign(createdDialog, { show: true, key: created.key })
	keysResource.reload()
}

async function copyKey() {
	try {
		await navigator.clipboard.writeText(createdDialog.key)
		toast.success(__('Key copied'))
	} catch {
		// Clipboard API needs HTTPS (or localhost): leave the key selected instead.
		await nextTick()
		keyInput.value?.select()
		toast.warning(
			__('Copy is not available here: the key is selected, copy it manually.'),
		)
	}
}

function forgetCreatedKey() {
	createdDialog.key = ''
	// The resource keeps the last response (with the full key) until reset.
	createResourceCall.reset()
}

function askRevoke(key) {
	Object.assign(revokeDialog, { show: true, key })
}

async function submitRevoke({ close }) {
	const revoked = await revokeResourceCall.submit({
		key: revokeDialog.key.name,
	})
	if (!revoked) return
	close()
	toast.success(__('API key revoked'))
	keysResource.reload()
}
</script>
