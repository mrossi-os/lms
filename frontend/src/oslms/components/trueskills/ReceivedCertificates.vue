<template>
	<div v-if="visible">
		<div
			v-if="loading"
			class="mt-4 flex items-center gap-2 text-sm text-ink-gray-5"
		>
			<span class="lucide-loader-circle size-4 animate-spin shrink-0" />
			{{ __('Loading TrueSkills certificates...') }}
		</div>
		<div
			v-else-if="failed"
			class="mt-4 flex items-center gap-2 text-sm text-ink-gray-6"
		>
			<span class="lucide-circle-alert size-4 shrink-0" />
			<span>{{
				__('TrueSkills certificates are temporarily unavailable.')
			}}</span>
			<button class="underline hover:text-ink-gray-8" @click="load">
				{{ __('Retry') }}
			</button>
		</div>
		<div
			v-if="certificates.length"
			class="mt-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
		>
			<div
				v-for="certificate in certificates"
				:key="certificate.id"
				class="flex flex-col bg-surface-base border rounded-lg card"
				:class="
					hasImage(certificate) ? 'cursor-pointer hover:bg-surface-sidebar' : ''
				"
				@click="openBadge(certificate)"
			>
				<div
					class="font-medium leading-5 mb-2 text-ink-gray-9 flex items-center gap-2"
				>
					<span
						v-if="busyId === certificate.id"
						class="lucide-loader-circle size-4 animate-spin text-ink-gray-6 shrink-0"
					/>
					<span>{{ certificate.name }}</span>
				</div>
				<div class="text-sm-medium text-ink-gray-7">
					<span> {{ __('Issued on') }}: </span>
					{{ dayjs(certificate.created_at).format('DD MMM YYYY') }}
				</div>
				<div class="text-xs text-ink-gray-5 mt-1">
					{{ __('Issued by TrueSkills') }}
				</div>
				<div
					v-if="certificate.formats.length"
					class="flex gap-2 mt-3 pt-3 border-t border-outline-gray-1"
					@click.stop
				>
					<button
						v-if="certificate.formats.includes('image')"
						class="text-xs-medium px-2 py-1 rounded border border-outline-gray-2 hover:bg-surface-gray-2 text-ink-gray-8"
						@click.stop="download(certificate, 'image')"
					>
						{{ __('Download Openbadge') }}
					</button>
					<button
						v-if="certificate.formats.includes('jsonp')"
						class="text-xs-medium px-2 py-1 rounded border border-outline-gray-2 hover:bg-surface-gray-2 text-ink-gray-8"
						@click.stop="download(certificate, 'jsonp')"
					>
						{{ __('JSON-LD') }}
					</button>
				</div>
			</div>
		</div>
	</div>
</template>
<script setup>
// Certificates TrueSkills issued straight to the profile owner's
// email (e.g. in bulk from its own platform), not requested by Elite. The
// server looks them up by email and forwards the files; this component only
// renders them. It reports `{ count, loading }` so the profile tab can decide
// whether to show its "no certificates" message.
import { call } from 'frappe-ui'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useCertificateViewer } from '@/oslms/composables/useCertificateViewer'

const props = defineProps({
	// Profile whose certificates are listed; the server resolves its email.
	profile: {
		type: Object,
		required: true,
	},
})
const emit = defineEmits(['state'])

const dayjs = inject('$dayjs')
const $user = inject('$user')
const { openReceivedBadge, downloadReceivedFile } = useCertificateViewer()

// Same rule as the server: the owner, administrators and "Gestore". The server
// enforces it; this only avoids a call that would be refused.
const canSee = computed(() => {
	const viewer = $user?.data
	if (!viewer || !props.profile.data?.username) return false
	if (viewer.name === props.profile.data.name) return true
	if (viewer.name === 'Administrator') return true
	const roles = viewer.roles || []
	return roles.includes('System Manager') || roles.includes('Gestore')
})

const certificates = ref([])
// Starts loading when a call is going to be made, so the tab never flashes its
// "no certificates" message before the list arrives.
const loading = ref(canSee.value)
const failed = ref(false)
const busyId = ref(null)

// Nothing is shown when the integration is off, so the profile stays as it was.
const enabled = ref(true)
const visible = computed(() => canSee.value && enabled.value)

const hasImage = (certificate) => certificate.formats.includes('image')

const load = async () => {
	if (!canSee.value) {
		certificates.value = []
		return
	}
	loading.value = true
	failed.value = false
	try {
		const data = await call(
			'os_lms.os_lms.trueskills.received.list_received_certificates',
			{ username: props.profile.data.username },
		)
		enabled.value = data.status !== 'disabled'
		failed.value = data.status === 'unavailable'
		certificates.value = data.certificates || []
	} catch {
		// Refused or broken: the rest of the tab must keep working.
		failed.value = true
		certificates.value = []
	} finally {
		loading.value = false
	}
}

const target = (certificate, format) => ({
	username: props.profile.data.username,
	id: certificate.id,
	format,
	formats: certificate.formats,
})

// After a failure the certificate may have been withdrawn: refresh the list.
const settle = async (excType) => {
	if (excType === 'DoesNotExistError') await load()
}

const run = async (certificate, action) => {
	if (busyId.value) return
	busyId.value = certificate.id
	try {
		await settle(await action())
	} finally {
		busyId.value = null
	}
}

const openBadge = (certificate) => {
	if (!hasImage(certificate)) return
	run(certificate, () => openReceivedBadge(target(certificate, 'image')))
}

const download = (certificate, format) =>
	run(certificate, () => downloadReceivedFile(target(certificate, format)))

watch(
	[certificates, loading, enabled],
	() => {
		emit('state', {
			count: enabled.value ? certificates.value.length : 0,
			loading: loading.value,
		})
	},
	{ immediate: true },
)

onMounted(load)
</script>
