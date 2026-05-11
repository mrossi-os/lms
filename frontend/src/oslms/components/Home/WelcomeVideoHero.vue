<template>
	<section
		v-if="visible && embed"
		class="relative overflow-hidden rounded-xl bg-black shadow-lg mb-5"
	>
		<div
			:class="[
				'relative w-full overflow-hidden bg-black',
				minimized ? 'h-24 md:h-28' : 'aspect-video',
			]"
		>
			<video
				v-if="embed.kind === 'video'"
				:src="embed.src"
				controls
				autoplay
				muted
				playsinline
				class="absolute inset-0 w-full h-full block object-cover"
				@ended="minimize"
			/>
			<div
				v-else-if="embed.kind === 'iframe'"
				class="absolute inset-0 flex items-center justify-center"
			>
				<iframe
					:src="embed.src"
					class="w-full aspect-video block"
					style="min-height: 100%"
					frameborder="0"
					referrerpolicy="strict-origin-when-cross-origin"
					allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
					allowfullscreen
				/>
			</div>
			<div
				v-if="!minimized"
				class="pointer-events-none absolute inset-x-0 top-0 p-5 md:p-7 bg-gradient-to-b from-black/75 via-black/40 to-transparent text-ink-gray-9"
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
			<div
				v-else
				class="pointer-events-none absolute inset-0 flex items-center px-4 md:px-6 bg-gradient-to-r from-black/70 via-black/30 to-transparent text-ink-gray-9"
			>
				<div class="min-w-0">
					<div class="font-medium truncate">
						{{ config.title || __('Benvenuto nella piattaforma') }}
					</div>
					<div
						v-if="config.subtitle"
						class="text-sm text-white/75 truncate"
					>
						{{ config.subtitle }}
					</div>
				</div>
			</div>
			<button
				type="button"
				class="absolute top-3 right-3 inline-flex items-center justify-center size-8 rounded-full bg-black/60 hover:bg-black/80 text-ink-gray-9 backdrop-blur-sm transition-colors"
				:aria-label="minimized ? __('Espandi') : __('Riduci')"
				@click="minimized ? (minimized = false) : minimize()"
			>
				<Maximize2 v-if="minimized" class="size-4" />
				<X v-else class="size-4" />
			</button>
		</div>
	</section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { createResource } from 'frappe-ui'
import { Maximize2, X } from 'lucide-vue-next'
import { usersStore } from '@/stores/user'

const { userResource } = usersStore()

const visible = ref(false)
const minimized = ref(false)
const config = ref({ title: '', subtitle: '', video_source: '' })
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
			return `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&mute=1&playsinline=1&rel=0`
		}
	}
	if (host === 'youtu.be') {
		const id = u.pathname.slice(1).split('/')[0]
		if (/^[\w-]{6,20}$/.test(id)) {
			return `https://www.youtube-nocookie.com/embed/${id}?autoplay=1&mute=1&playsinline=1&rel=0`
		}
	}

	// Vimeo: vimeo.com/ID, player.vimeo.com/video/ID
	if (host === 'vimeo.com' || host === 'player.vimeo.com') {
		const id = u.pathname.match(/\/(?:video\/)?(\d+)/)?.[1]
		if (id) {
			return `https://player.vimeo.com/video/${id}?autoplay=1&muted=1&playsinline=1`
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

const minimize = () => {
	minimized.value = true
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
