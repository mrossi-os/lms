<template>
	<div class="max-w-3xl mx-auto p-6 space-y-6">
		<div>
			<h1 class="text-2xl font-semibold text-ink-gray-9">
				{{ __('TrueSkills API Test') }}
			</h1>
			<p class="text-ink-gray-6 mt-1">
				{{
					__(
						'Use this page to verify the TrueSkills integration and trigger manual operations.',
					)
				}}
			</p>
		</div>

		<!-- Status -->
		<div class="rounded-lg border border-outline-gray-2 p-4 space-y-2">
			<div class="flex items-center justify-between">
				<h2 class="text-lg font-medium text-ink-gray-9">
					{{ __('Status') }}
				</h2>
				<Button
					:loading="status.loading"
					@click="status.reload()"
					variant="subtle"
				>
					{{ __('Refresh') }}
				</Button>
			</div>
			<div v-if="status.data" class="text-sm text-ink-gray-7 space-y-1">
				<div>
					{{ __('Enabled') }}:
					<Badge
						:label="status.data.enabled ? __('Yes') : __('No')"
						:theme="status.data.enabled ? 'green' : 'gray'"
					/>
				</div>
				<div>
					{{ __('API Key configured') }}:
					<Badge
						:label="status.data.has_api_key ? __('Yes') : __('No')"
						:theme="status.data.has_api_key ? 'green' : 'orange'"
					/>
				</div>
				<div>
					{{ __('Endpoint') }}:
					<span class="font-mono">{{
						status.data.endpoint || __('not set')
					}}</span>
				</div>
				<div>
					{{ __('Certificate Template') }}:
					<span class="font-mono">{{
						status.data.certificate_template || __('not set')
					}}</span>
				</div>
				<div>
					{{ __('Ready') }}:
					<Badge
						:label="status.data.ready ? __('Yes') : __('No')"
						:theme="status.data.ready ? 'green' : 'orange'"
					/>
				</div>
			</div>
			<div v-else-if="status.error" class="text-sm text-ink-red-5">
				{{ status.error.message || status.error }}
			</div>
		</div>

		<!-- Test connection -->
		<div class="rounded-lg border border-outline-gray-2 p-4 space-y-3">
			<div class="flex items-center justify-between">
				<h2 class="text-lg font-medium text-ink-gray-9">
					{{ __('Test Connection') }}
				</h2>
				<Button
					variant="solid"
					:loading="testConnection.loading"
					@click="testConnection.submit()"
				>
					{{ __('Run') }}
				</Button>
			</div>
			<p class="text-sm text-ink-gray-6">
				{{
					__(
						'Issues a ping request to the configured TrueSkills endpoint.',
					)
				}}
			</p>
			<pre
				v-if="testConnection.data"
				class="text-xs bg-surface-gray-2 p-3 rounded overflow-x-auto"
				>{{ JSON.stringify(testConnection.data, null, 2) }}</pre
			>
		</div>

		<!-- Issue certificate -->
		<div class="rounded-lg border border-outline-gray-2 p-4 space-y-3">
			<h2 class="text-lg font-medium text-ink-gray-9">
				{{ __('Issue Certificate') }}
			</h2>
			<p class="text-sm text-ink-gray-6">
				{{
					__(
						'Manually mirror an existing LMS Certificate on TrueSkills.',
					)
				}}
			</p>
			<FormControl
				v-model="certificateName"
				:label="__('LMS Certificate ID')"
				placeholder="LMS-CERT-..."
			/>
			<Button
				variant="solid"
				:loading="issueCertificate.loading"
				:disabled="!certificateName"
				@click="onIssueCertificate"
			>
				{{ __('Issue') }}
			</Button>
			<pre
				v-if="issueCertificate.data"
				class="text-xs bg-surface-gray-2 p-3 rounded overflow-x-auto"
				>{{ JSON.stringify(issueCertificate.data, null, 2) }}</pre
			>
		</div>
	</div>
</template>

<script setup>
import { ref } from 'vue'
import { Badge, Button, FormControl, createResource, toast } from 'frappe-ui'

const certificateName = ref('')

const status = createResource({
	url: 'os_lms.os_lms.trueskills.api.get_status',
	auto: true,
})

const testConnection = createResource({
	url: 'os_lms.os_lms.trueskills.api.test_connection',
	onSuccess(data) {
		if (data?.ok) {
			toast.success(__('Connection successful'))
		} else {
			toast.error(data?.error || __('Connection failed'))
		}
	},
	onError(err) {
		toast.error(err.message || __('Connection failed'))
	},
})

const issueCertificate = createResource({
	url: 'os_lms.os_lms.trueskills.api.issue_certificate',
	makeParams() {
		return { certificate: certificateName.value }
	},
	onSuccess(data) {
		if (data?.ok) {
			toast.success(__('Certificate issued on TrueSkills'))
		} else {
			toast.error(data?.error || __('Failed to issue certificate'))
		}
	},
	onError(err) {
		toast.error(err.message || __('Failed to issue certificate'))
	},
})

const onIssueCertificate = () => {
	if (!certificateName.value) return
	issueCertificate.submit()
}
</script>
