<template>
	<!-- OSLMS-CUSTOM: when hero is enabled the media renders as a standalone,
	full-width rounded section above the course info (not a full-bleed banner). -->
	<section class="mb-8 w-full overflow-hidden rounded-md bg-black">
		<div class="relative aspect-video w-full">
			<template v-if="hero?.media_type === 'Video'">
				<video
					v-if="isDirectVideoFile(hero?.media_url)"
					:src="hero?.media_url"
					controls
					class="absolute inset-0 w-full h-full object-cover"
				/>
				<iframe
					v-else
					:src="embedUrl"
					class="absolute inset-0 w-full h-full"
					frameborder="0"
					allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
					allowfullscreen
				/>
			</template>
			<img
				v-else-if="hero?.media_type === 'Image'"
				:src="hero?.media_url"
				:alt="title"
				class="absolute inset-0 w-full h-full object-cover"
			/>
		</div>
	</section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getVideoEmbedURL } from '@/utils/'

interface CourseHeroData {
	enabled?: boolean
	media_type?: string
	media_url?: string
}

const props = defineProps<{
	hero?: CourseHeroData | null
	title?: string
}>()

// Locally uploaded files (mp4, webm, ...) render as a native <video>; any other
// value (e.g. a YouTube/Vimeo link) is embedded through an <iframe>.
const DIRECT_VIDEO_EXTENSIONS = /\.(mp4|webm|ogg|ogv|mov|m4v)(\?.*)?$/i
const isDirectVideoFile = (url?: string) =>
	!!url && DIRECT_VIDEO_EXTENSIONS.test(url)

const embedUrl = computed(() => getVideoEmbedURL(props.hero?.media_url))
</script>
