<template>
	<!-- Mobile browsers cannot show a PDF inside an iframe: Chrome for Android has
	     no inline viewer and falls back to a download placeholder, while iOS Safari
	     renders a static, unscrollable first page at the document's natural width.
	     On phones we hand the file to the browser's own full viewer through a plain
	     top-level navigation instead; desktop keeps the embedded frame. -->
	<div
		v-if="isMobile"
		class="flex flex-col gap-3 rounded-lg border border-outline-gray-1 p-3 mb-4 card"
	>
		<div class="flex items-center gap-3">
			<span
				class="flex items-center justify-center rounded-md bg-surface-gray-2 p-2 shrink-0"
			>
				<span class="lucide-file-text w-5 h-5 text-ink-gray-7" />
			</span>
			<span class="flex-1 min-w-0">
				<span class="block text-base font-medium text-ink-gray-9 truncate">
					{{ fileName }}
				</span>
				<span class="block text-sm text-ink-gray-5">
					{{ __('Opens in a new tab') }}
				</span>
			</span>
		</div>
		<Button
			variant="solid"
			class="w-full"
			iconLeft="lucide-external-link"
			:link="fileURL"
		>
			{{ __('Open the PDF') }}
		</Button>
	</div>
	<iframe
		v-else
		:src="viewerURL"
		width="100%"
		height="700px"
		class="mb-4"
		type="application/pdf"
		frameborder="0"
	></iframe>
</template>

<script setup>
import { computed } from 'vue'
import { Button } from 'frappe-ui'
import { useScreenSize } from '@/utils/composables'

const { isMobile } = useScreenSize()

const props = defineProps({
	file: {
		type: String,
		required: true,
	},
	// The embedded viewer's native toolbar. The macro syntax hides it; blocks
	// added through the editor keep it, as they always have.
	toolbar: {
		type: Boolean,
		default: true,
	},
})

const fileURL = computed(() => {
	// Content fetched from the server already routes private files through the
	// access-gated serve_resource endpoint with a properly percent-encoded URL
	// (see rewrite_private_media). Running encodeURI on it again would escape the
	// percent signs (%20 → %2520). Only encode raw paths that haven't been through
	// the server rewrite yet (fresh uploads in the editor).
	const file = props.file
	const alreadyEncoded =
		file.includes('serve_resource') || /%[0-9A-Fa-f]{2}/.test(file)
	return alreadyEncoded ? file : encodeURI(file)
})

const viewerURL = computed(() =>
	props.toolbar ? fileURL.value : `${fileURL.value}#toolbar=0`
)

const fileName = computed(() => {
	// Private files are served through serve_resource, whose URL path ends with
	// the whitelisted method name and carries the real path in the file_url query
	// parameter. Read the name from that parameter so the card shows the document
	// rather than the endpoint.
	const raw = props.file || ''
	const match = raw.match(/[?&]file_url=([^&#]+)/)
	let path = raw
	if (match) {
		try {
			path = decodeURIComponent(match[1])
		} catch (e) {
			path = match[1]
		}
	}
	const base = path.split(/[?#]/)[0].split('/').pop() || path
	try {
		return decodeURIComponent(base)
	} catch (e) {
		return base
	}
})
</script>
