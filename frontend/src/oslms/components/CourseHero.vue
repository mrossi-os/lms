<template>
	<!-- OSLMS-CUSTOM: when hero is enabled the media renders as a standalone,
	full-width rounded section above the course info (not a full-bleed banner). -->
	<section class="mb-8 w-full overflow-hidden rounded-md bg-black">
		<!-- A YouTube/Vimeo link or an uploaded file goes through VideoPreview, so
		the hero uses the same player the student sees in a lesson (Plyr for the
		embeds, VideoBlock for a file) instead of a bare provider iframe. -->
		<VideoPreview
			v-if="isVideo && isPlayerSource"
			:video-link="hero?.media_url"
			class="w-full"
		/>
		<!-- Any other value is assumed to be an already embeddable URL (the field
		is free text), so it keeps the plain iframe it always had. -->
		<div v-else-if="isVideo" class="relative aspect-video w-full">
			<iframe
				:src="safeUrl(embedUrl)"
				class="absolute inset-0 w-full h-full"
				frameborder="0"
				allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
				allowfullscreen
			/>
		</div>
		<div
			v-else-if="hero?.media_type === 'Image'"
			class="relative aspect-video w-full"
		>
			<img
				:src="safeUrl(hero?.media_url)"
				:alt="title"
				class="absolute inset-0 w-full h-full object-cover"
			/>
		</div>
	</section>
</template>

<script setup lang="ts">
import { safeUrl } from '@/utils/safeUrl'
import { computed } from 'vue'
import { getVideoEmbedURL } from '@/utils/'
import { getYouTubeId, isVimeoLink } from '@/utils/video'
import VideoPreview from '@/components/VideoPreview.vue'

interface CourseHeroData {
	enabled?: boolean
	media_type?: string
	media_url?: string
}

const props = defineProps<{
	hero?: CourseHeroData | null
	title?: string
}>()

const isVideo = computed(() => props.hero?.media_type === 'Video')

// Locally uploaded files (mp4, webm, ...) play as a video, and so do YouTube
// and Vimeo links: VideoPreview covers all three. Any other value falls back to
// the generic iframe.
const DIRECT_VIDEO_EXTENSIONS = /\.(mp4|webm|ogg|ogv|mov|m4v)(\?.*)?$/i
const isPlayerSource = computed(() => {
	const url = props.hero?.media_url
	if (!url) return false
	return (
		Boolean(getYouTubeId(url)) ||
		isVimeoLink(url) ||
		DIRECT_VIDEO_EXTENSIONS.test(url)
	)
})

const embedUrl = computed(() => getVideoEmbedURL(props.hero?.media_url))
</script>
