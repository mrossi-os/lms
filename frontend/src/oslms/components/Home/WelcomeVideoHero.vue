<template>
	<section
		v-if="visible && embed"
		class="relative overflow-hidden rounded-xl bg-black shadow-lg mb-5"
	>
		<div class="relative w-full aspect-video bg-black">
			<video
				v-if="embed.kind === 'video'"
				ref="videoEl"
				:src="embed.src"
				controls
				autoplay
				muted
				playsinline
				class="w-full h-full block"
				@ended="dismiss"
			/>
			<iframe
				v-else-if="embed.kind === 'iframe'"
				:src="embed.src"
				class="w-full h-full block"
				frameborder="0"
				referrerpolicy="strict-origin-when-cross-origin"
				allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
				allowfullscreen
			/>
			<div
				class="pointer-events-none absolute inset-x-0 top-0 p-5 md:p-7 bg-gradient-to-b from-black/75 via-black/40 to-transparent text-white"
			>
				<h2 class="text-xl md:text-3xl font-semibold leading-tight">
					{{ config.title || __('Benvenuto nella piattaforma') }}
				</h2>
				<p
					v-if="config.subtitle"
					class="mt-1 text-sm md:text-base text-white/85 max-w-2xl"
				>
					{{ config.subtitle }}
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
import { computed, ref, watch } from 'vue'
import { createResource } from 'frappe-ui'
import { X } from 'lucide-vue-next'
import { usersStore } from '@/stores/user'

const { userResource } = usersStore()

const visible = ref(false)
const config = ref({ title: '', subtitle: '', video_source: '' })
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
		if (data && data.enabled && data.video_source) {
			config.value = data
			visible.value = true
			markAsSeen()
		}
	},
})

// Parse the stored source into a safe render descriptor.
// - Local paths (starting with "/") → native <video>.
// - http(s) URLs → <iframe> embed (src bound via Vue, attribute-escaped).
//   For YouTube/Vimeo, the watch URL is rewritten to the player embed URL
//   (the watch page sends X-Frame-Options: sameorigin and can't be framed).
// - Everything else (including javascript:, data:, blob:, malformed) → null.
const toEmbedUrl = (u) => {
	const host = u.hostname.replace(/^www\./, '')

	// YouTube: watch?v=ID, /embed/ID, youtu.be/ID, /shorts/ID
	if (
		host === 'youtube.com' ||
		host === 'm.youtube.com' ||
		host === 'youtube-nocookie.com'
	) {
		const id =
			u.searchParams.get('v') ||
			u.pathname.match(/^\/(?:embed|shorts|v)\/([\w-]{6,20})/)?.[1]
		if (id && /^[\w-]{6,20}$/.test(id)) {
			return `https://www.youtube-nocookie.com/embed/${id}`
		}
	}
	if (host === 'youtu.be') {
		const id = u.pathname.slice(1).split('/')[0]
		if (/^[\w-]{6,20}$/.test(id)) {
			return `https://www.youtube-nocookie.com/embed/${id}`
		}
	}

	// Vimeo: vimeo.com/ID, player.vimeo.com/video/ID
	if (host === 'vimeo.com' || host === 'player.vimeo.com') {
		const id = u.pathname.match(/\/(?:video\/)?(\d+)/)?.[1]
		if (id) {
			return `https://player.vimeo.com/video/${id}`
		}
	}

	return u.toString()
}

const embed = computed(() => {
	const raw = (config.value.video_source || '').trim()
	if (!raw) return null
	if (raw.startsWith('/')) {
		return { kind: 'video', src: raw }
	}
	try {
		const u = new URL(raw)
		if (u.protocol === 'http:' || u.protocol === 'https:') {
			return { kind: 'iframe', src: toEmbedUrl(u) }
		}
	} catch {
		return null
	}
	return null
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
