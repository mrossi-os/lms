<template>
	<div class="space-y-5">
		<section class="space-y-4 rounded-md border card">
			<div class="flex flex-wrap items-start justify-between gap-4">
				<div class="space-y-1">
					<h2 class="text-base font-semibold text-ink-gray-9">
						{{ __('Integrity check') }}
					</h2>
					<p class="max-w-2xl text-p-sm text-ink-gray-6">
						{{
							__(
								'Each event is linked to the previous one by a fingerprint. The check recomputes the whole chain: any changed or removed event shows up.',
							)
						}}
					</p>
				</div>
				<Button variant="solid" :loading="verifying" @click="verify">
					<template #prefix>
						<span class="lucide-shield-check size-4" />
					</template>
					{{ __('Verify integrity') }}
				</Button>
			</div>

			<div
				v-if="result"
				class="rounded border p-3 text-sm"
				:class="
					result.ok
						? 'border-outline-green-2 bg-surface-green-1 text-ink-green-7'
						: 'border-outline-red-2 bg-surface-red-1 text-ink-red-7'
				"
			>
				<template v-if="result.ok">
					{{
						result.checked
							? __('The chain is intact: {0} events checked.').format(result.checked)
							: __('No events to check yet.')
					}}
				</template>
				<template v-else>
					{{ problemText(result) }}
				</template>
			</div>

			<dl class="grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2">
				<div>
					<dt class="text-ink-gray-5">{{ __('Last event (sequence)') }}</dt>
					<dd class="text-ink-gray-9">{{ status.chain_head_seq || '—' }}</dd>
				</div>
				<div>
					<dt class="text-ink-gray-5">{{ __('Chain starts at (after retention)') }}</dt>
					<dd class="text-ink-gray-9">{{ status.anchor_seq || 1 }}</dd>
				</div>
				<div class="sm:col-span-2">
					<dt class="text-ink-gray-5">{{ __('Fingerprint of the last event') }}</dt>
					<dd class="break-all font-mono text-xs text-ink-gray-8">
						{{ status.chain_head_hash || '—' }}
					</dd>
				</div>
			</dl>
		</section>

		<section class="space-y-3 rounded-md border card">
			<h2 class="text-base font-semibold text-ink-gray-9">
				{{ __('Daily seals') }}
			</h2>
			<p class="text-p-sm text-ink-gray-6">
				{{
					__(
						'Every night a seal records how many events the day had and the fingerprint of the chain. Compare it with the copy sent by email to prove nothing changed afterwards.',
					)
				}}
			</p>
			<div
				v-if="!seals.data?.length"
				class="py-4 text-center text-sm text-ink-gray-5"
			>
				{{ seals.loading ? __('Loading...') : __('No seals yet') }}
			</div>
			<div v-else class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="text-left text-ink-gray-5">
							<th class="py-1.5 pr-3 font-medium">{{ __('Day') }}</th>
							<th class="py-1.5 pr-3 font-medium">{{ __('Events') }}</th>
							<th class="py-1.5 pr-3 font-medium">{{ __('Sealed on') }}</th>
							<th class="py-1.5 font-medium">{{ __('Fingerprint') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="seal in seals.data"
							:key="seal.seq"
							class="border-t border-outline-gray-1"
						>
							<td class="py-1.5 pr-3 text-ink-gray-8">{{ formatDate(seal.date) }}</td>
							<td class="py-1.5 pr-3">{{ seal.events }}</td>
							<td class="py-1.5 pr-3 text-ink-gray-6">{{ formatDateTime(seal.sealed_at) }}</td>
							<td class="break-all py-1.5 font-mono text-xs text-ink-gray-7">
								{{ seal.last_hash }}
							</td>
						</tr>
					</tbody>
				</table>
			</div>
		</section>
	</div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button, call, createResource, toast } from 'frappe-ui'
import { AUDIT_API, formatDate, formatDateTime } from './format'

defineProps<{ status: Record<string, any> }>()
const emit = defineEmits<{ verified: [] }>()

const verifying = ref(false)
const result = ref<any>(null)

const seals = createResource({ url: `${AUDIT_API}.get_seals`, auto: true })

function problemText(check: any) {
	const reasons: Record<string, string> = {
		missing: __('Event number {0} is missing.').format(check.expected_seq),
		broken_link: __('Event number {0} is no longer linked to the previous one.').format(
			check.seq,
		),
		altered: __('Event number {0} was altered after it was recorded.').format(
			check.seq,
		),
	}
	return __('The chain is NOT intact after {0} events checked. {1}').format(
		check.checked,
		reasons[check.reason] || check.reason,
	)
}

async function verify() {
	verifying.value = true
	try {
		result.value = await call('os_lms.os_lms.os_audit.verify_chain')
		emit('verified')
	} catch (error: any) {
		toast.error(error?.messages?.[0] || __('Could not verify the chain'))
	} finally {
		verifying.value = false
	}
}
</script>
