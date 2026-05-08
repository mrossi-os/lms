<template>
	<div class="flex flex-col h-full text-base overflow-y-hidden">
		<div>
			<div class="flex items-center justify-between mb-2">
				<div class="flex items-center space-x-2">
					<div class="text-xl font-semibold leading-none text-ink-gray-9">
						{{ __(label) }}
					</div>
					<Badge
						v-if="lmsData.isDirty"
						:label="__('Not Saved')"
						variant="subtle"
						theme="orange"
					/>
				</div>
				<div class="flex items-center space-x-2">
					<Button
						:loading="testConnection.loading"
						@click="testConnection.submit()"
					>
						{{ __('Test Connection') }}
					</Button>
					<Button
						variant="solid"
						:loading="lmsData.save.loading"
						@click="update"
					>
						{{ __('Update') }}
					</Button>
				</div>
			</div>
			<div class="text-ink-gray-6 leading-5">
				{{ __(description) }}
			</div>
		</div>

		<div class="flex-1 min-h-0 overflow-y-auto">
			<SettingFields
				v-if="lmsData.doc"
				:sections="sections"
				:data="lmsData.doc"
			/>
		</div>

		<div
			v-if="lastTestResult"
			class="mt-4 shrink-0 rounded-lg border p-3 text-sm"
			:class="
				lastTestResult.ok
					? 'border-outline-green-2 bg-surface-green-1 text-ink-green-5'
					: 'border-outline-red-2 bg-surface-red-1 text-ink-red-5'
			"
		>
			<div class="flex items-start justify-between gap-2 mb-1">
				<div class="font-medium">
					{{
						lastTestResult.ok
							? __('Connection successful')
							: __('Connection failed')
					}}
				</div>
				<button
					type="button"
					class="text-xs opacity-70 hover:opacity-100"
					@click="lastTestResult = null"
				>
					{{ __('Dismiss') }}
				</button>
			</div>
			<div v-if="lastTestResult.url" class="text-xs mb-2 opacity-80">
				<span class="font-medium">{{ __('Called URL') }}:</span>
				<code class="ml-1 break-all">{{ lastTestResult.url }}</code>
			</div>
			<pre
				class="text-xs max-h-40 overflow-auto whitespace-pre-wrap break-all"
				>{{
					JSON.stringify(
						lastTestResult.ok
							? lastTestResult.response
							: lastTestResult.error,
						null,
						2,
					)
				}}</pre
			>
		</div>
	</div>
</template>

<script setup>
import { ref } from 'vue'
import {
	Badge,
	Button,
	createDocumentResource,
	createResource,
	toast,
} from 'frappe-ui'
import SettingFields from '@/components/Settings/SettingFields.vue'

defineProps({
	label: { type: String, required: true },
	description: { type: String },
	sections: { type: Array, required: true },
})

const lastTestResult = ref(null)

const lmsData = createDocumentResource({
	doctype: 'LMS Settings',
	name: 'LMS Settings',
	fields: ['*'],
	cache: 'LMS Settings',
	auto: true,
})

const update = () => {
	lmsData.save.submit(
		{},
		{
			onSuccess() {
				toast.success(__('Settings updated'))
			},
			onError(err) {
				toast.error(err.messages?.[0] || err.message || err)
			},
		},
	)
}

const testConnection = createResource({
	url: 'os_lms.os_lms.trueskills.api.test_connection',
	onSuccess(data) {
		lastTestResult.value = data
		if (data?.ok) {
			toast.success(__('Connection successful'))
		} else {
			toast.error(data?.error || __('Connection failed'))
		}
	},
	onError(err) {
		lastTestResult.value = { ok: false, error: err.message || String(err) }
		toast.error(err.message || __('Connection failed'))
	},
})
</script>
