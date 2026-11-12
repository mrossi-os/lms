<template>
	<div>
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b bg-surface-base px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
		</header>

		<div v-if="!allowed" class="p-10 text-center text-ink-gray-6">
			{{ __('You are not allowed to use OS Audit.') }}
		</div>

		<div
			v-else-if="page.loading && !page.data"
			class="flex flex-1 items-center justify-center p-10"
		>
			<LoadingIndicator class="size-5 text-ink-gray-5" />
		</div>

		<div v-else-if="page.error" class="p-10 text-center text-ink-gray-6">
			{{ page.error.messages?.[0] || __('Could not load OS Audit.') }}
		</div>

		<div v-else-if="page.data" class="mx-auto max-w-6xl space-y-5 p-5">
			<section
				class="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-md border card text-sm"
			>
				<Badge
					:theme="status.active ? 'green' : 'gray'"
					size="lg"
					:label="status.active ? __('Audit active') : __('Audit off')"
				/>
				<span class="text-ink-gray-6">
					{{ __('Events recorded') }}:
					<span class="font-medium text-ink-gray-9">{{ status.events }}</span>
				</span>
				<span class="text-ink-gray-6">
					{{ __('Lesson visits in progress') }}:
					<span class="font-medium text-ink-gray-9">{{
						status.open_sessions
					}}</span>
				</span>
				<span class="text-ink-gray-6">
					{{ __('Last daily seal') }}:
					<span class="font-medium text-ink-gray-9">{{
						status.last_seal
							? formatDate(status.last_seal.date)
							: __('None yet')
					}}</span>
				</span>
			</section>

			<div class="overflow-x-auto">
				<TabButtons :options="tabs" v-model="tab" class="w-fit" />
			</div>

			<AuditSettings
				v-if="tab === 'settings'"
				:page="page.data"
				@saved="(data) => page.setData(data)"
			/>
			<AuditLog
				v-else-if="tab === 'log'"
				:event-types="page.data.event_types"
			/>
			<AuditAttendance v-else-if="tab === 'attendance'" />
			<AuditExports v-else-if="tab === 'export'" />
			<AuditIntegrity
				v-else-if="tab === 'integrity'"
				:status="status"
				@verified="page.reload()"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
/*
 * OS Audit page (docs/audit-studenti/PIANO.md §7), System Manager and Gestore only
 * (can_use_os_audit from get_user_info; every endpoint checks it again).
 * The page loads with one call (get_page); each tab asks only for what is searched.
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
	Badge,
	Breadcrumbs,
	LoadingIndicator,
	TabButtons,
	createResource,
} from 'frappe-ui'
import { usersStore } from '@/stores/user'
import AuditSettings from '@/oslms/components/osAudit/AuditSettings.vue'
import AuditLog from '@/oslms/components/osAudit/AuditLog.vue'
import AuditAttendance from '@/oslms/components/osAudit/AuditAttendance.vue'
import AuditExports from '@/oslms/components/osAudit/AuditExports.vue'
import AuditIntegrity from '@/oslms/components/osAudit/AuditIntegrity.vue'
import { AUDIT_API, formatDate } from '@/oslms/components/osAudit/format'

const TAB_KEYS = ['settings', 'log', 'attendance', 'export', 'integrity']

const route = useRoute()
const router = useRouter()
const { userResource } = usersStore()

const allowed = computed(() => Boolean(userResource?.data?.can_use_os_audit))

const breadcrumbs = computed(() => [
	{ label: __('OS Audit'), route: { name: 'OsAudit' } },
])

const tabs = computed(() => [
	{ label: __('Settings'), value: 'settings' },
	{ label: __('Log'), value: 'log' },
	{ label: __('Attendance'), value: 'attendance' },
	{ label: __('Export'), value: 'export' },
	{ label: __('Integrity'), value: 'integrity' },
])

// The tab lives in the URL (?tab=), so a link opens the same tab.
const initialTab = String(route.query.tab || '')
const tab = ref(TAB_KEYS.includes(initialTab) ? initialTab : 'settings')
watch(tab, (value) => {
	router.replace({ query: { ...route.query, tab: value } })
})

const page = createResource({
	url: `${AUDIT_API}.get_page`,
	auto: allowed.value,
})

watch(allowed, (value) => {
	if (value && !page.data && !page.loading) page.fetch()
})

const status = computed(() => page.data?.status || {})
</script>
