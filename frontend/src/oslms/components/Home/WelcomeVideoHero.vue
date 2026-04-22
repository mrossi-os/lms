<template>
	<section
		v-if="visible"
		class="relative overflow-hidden rounded-xl bg-black shadow-lg mb-5"
	>
		<div class="relative w-full aspect-video bg-black">
			<video
				ref="videoEl"
				:src="config.file_url"
				controls
				autoplay
				muted
				playsinline
				class="w-full h-full block"
				@ended="dismiss"
			/>
			<div
				class="pointer-events-none absolute inset-x-0 top-0 p-5 md:p-7 bg-gradient-to-b from-black/75 via-black/40 to-transparent text-white"
			>
				<h2 class="text-xl md:text-3xl font-semibold leading-tight">
					{{ config.title || __('Benvenuto nella piattaforma') }}
				</h2>
				<p class="mt-1 text-sm md:text-base text-white/85 max-w-2xl">
					{{ __('Un breve video per iniziare. Buona visione!') }}
				</p>
			</div>
			<button
				type="button"
				class="absolute top-3 right-3 inline-flex items-center justify-center size-8 rounded-full bg-black/60 hover:bg-black/80 text-white backdrop-blur-sm transition-colors"
				:aria-label="__('Chiudi')"
				@click="dismiss"
			>
				<X class="size-4" />
			</button>
		</div>
	</section>
</template>

<script setup>
import { ref, watch } from 'vue'
import { createResource } from 'frappe-ui'
import { X } from 'lucide-vue-next'
import { usersStore } from '@/stores/user'

const { userResource } = usersStore()

const visible = ref(false)
const config = ref({ title: '', file_url: '' })
const videoEl = ref(null)
const hasRequestedConfig = ref(false)

const markSeenResource = createResource({
	url: 'os_lms.os_lms.api.mark_welcome_video_seen',
})

const markAsSeen = () => {
	if (userResource?.data?.welcome_video_seen) return
	markSeenResource.submit()
	if (userResource?.data) {
		userResource.data.welcome_video_seen = true
	}
}

const configResource = createResource({
	url: 'os_lms.os_lms.api.get_welcome_video_config',
	auto: false,
	onSuccess(data) {
		if (data && data.enabled && data.file_url) {
			config.value = data
			visible.value = true
			markAsSeen()
		}
	},
})

const dismiss = () => {
	if (!visible.value) return
	visible.value = false
	try {
		videoEl.value?.pause()
	} catch (e) {
		/* ignore */
	}
}

watch(
	() => userResource?.data,
	(data) => {
		if (!data) return
		if (data.welcome_video_seen) return
		if (hasRequestedConfig.value) return
		hasRequestedConfig.value = true
		configResource.fetch()
	},
	{ immediate: true },
)
</script>
