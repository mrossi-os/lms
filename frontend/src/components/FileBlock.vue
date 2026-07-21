<template>
	<div
		class="flex items-center gap-3 rounded-lg border border-outline-gray-1 p-3 mb-4 card"
	>
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
				{{ __('Click the icon to download') }}
			</span>
		</span>
		<!-- Only this icon triggers the download, not the whole card. -->
		<a
			:href="fileURL"
			:download="fileName"
			target="_blank"
			rel="noopener"
			:title="__('Download')"
			:aria-label="__('Download')"
			class="flex items-center justify-center rounded-md p-2 shrink-0 text-ink-gray-7 no-underline hover:bg-surface-gray-2 transition-colors"
		>
			<span class="lucide-download w-5 h-5" />
		</a>
	</div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
	file: {
		type: String,
		required: true,
	},
})

const fileURL = computed(() => {
	// Content fetched from the server already routes private files through the
	// access-gated serve_resource endpoint with a properly percent-encoded URL
	// (see rewrite_private_media). Running encodeURI on it again would escape the
	// percent signs (%20 → %2520) and break the download with a 404. Only encode
	// raw paths that haven't been through the server rewrite yet (fresh uploads
	// in the editor), where spaces/parens still need escaping.
	const file = props.file
	const alreadyEncoded =
		file.includes('serve_resource') || /%[0-9A-Fa-f]{2}/.test(file)
	return alreadyEncoded ? file : encodeURI(file)
})

const fileName = computed(() => {
	const path = props.file.split('/').pop() || props.file
	try {
		return decodeURIComponent(path)
	} catch (e) {
		return path
	}
})
</script>
