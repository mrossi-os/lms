<template>
	<div class="mt-7 mb-10">
		<h2 class="mb-3 text-xl-semibold text-ink-gray-9">
			{{ __('Certificates') }}
		</h2>
		<div
			v-if="certificates.data?.length"
			class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4"
		>
			<div
				v-for="certificate in certificates.data"
				:key="certificate.name"
				class="flex flex-col bg-surface-white border rounded-lg card cursor-pointer hover:bg-surface-menu-bar"
				@click="openCertificate(certificate)"
			>
				<div class="font-medium leading-5 mb-2 text-ink-gray-9">
					{{ certificate.course_title || certificate.batch_title }}
				</div>
				<div class="text-sm text-ink-gray-7 font-medium">
					<span> {{ __('Issued on') }}: </span>
					{{ dayjs(certificate.issue_date).format('DD MMM YYYY') }}
				</div>
				<div
					v-if="trueskillsStatus[certificate.name]?.issued"
					class="flex gap-2 mt-3 pt-3 border-t border-outline-gray-1"
					@click.stop
				>
					<button
						class="text-xs px-2 py-1 rounded border border-outline-gray-2 hover:bg-surface-gray-2 font-medium text-ink-gray-8"
						@click.stop="downloadOpenbadge(certificate.name, 'image')"
					>
						{{ __('Download Openbadge') }}
					</button>
					<button
						class="text-xs px-2 py-1 rounded border border-outline-gray-2 hover:bg-surface-gray-2 font-medium text-ink-gray-8"
						@click.stop="downloadOpenbadge(certificate.name, 'jsonp')"
					>
						{{ __('JSON-LD') }}
					</button>
				</div>
			</div>
		</div>
		<div v-else class="text-sm italic text-ink-gray-5">
			{{ __('You have not received any certificates yet.') }}
		</div>
	</div>
</template>
<script setup>
import { createListResource, createResource } from 'frappe-ui'
import { inject, onMounted, ref, watch } from 'vue'

const dayjs = inject('$dayjs')
const props = defineProps({
	profile: {
		type: Object,
		required: true,
	},
})

const trueskillsStatus = ref({})

onMounted(() => {
	if (props.profile.data?.name) {
		certificates.reload()
	}
})

const certificates = createListResource({
	doctype: 'LMS Certificate',
	filters: {
		member: props.profile.data?.name,
	},
	fields: ['name', 'course_title', 'batch_title', 'issue_date', 'template'],
	cache: ['certificates', props.profile.data?.name],
})

const trueskillsStatusResource = createResource({
	url: 'os_lms.os_lms.trueskills.api.get_issue_status',
	onSuccess(data) {
		trueskillsStatus.value = data || {}
	},
	onError() {
		trueskillsStatus.value = {}
	},
})

const loadTrueskillsStatus = (data) => {
	if (!data?.length) {
		trueskillsStatus.value = {}
		return
	}
	trueskillsStatusResource.submit({
		lms_certificates: data.map((c) => c.name),
	})
}

// Load the TrueSkills status whenever the certificate list is available.
// This is bound to the current component instance instead of the resource's
// onSuccess, because createListResource returns the cached resource (ignoring
// new options) when the tab is re-mounted, which would otherwise leave the
// freshly mounted component without its TrueSkills status.
watch(
	() => certificates.data,
	(data) => {
		loadTrueskillsStatus(data)
	},
	{ immediate: true },
)

const openCertificate = (certificate) => {
	window.open(
		`/api/method/frappe.utils.print_format.download_pdf?doctype=LMS+Certificate&name=${
			certificate.name
		}&format=${encodeURIComponent(certificate.template)}`,
	)
}

const downloadOpenbadge = (certificateName, fileFormat) => {
	const status = trueskillsStatus.value[certificateName]
	if (!status?.trueskill_id) return
	const params = new URLSearchParams({
		certificate_id: status.trueskill_id,
		file_format: fileFormat,
	})
	window.open(
		`/api/method/os_lms.os_lms.trueskills.api.download?${params.toString()}`,
	)
}
</script>
