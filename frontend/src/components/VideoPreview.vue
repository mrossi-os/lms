<template>
	<div v-if="hasPreview">
		<!-- OSLMS-CUSTOM: a YouTube/Vimeo preview plays through the same Plyr
		player the lessons use, instead of a bare provider iframe — so the
		overview shows Plyr's controls and not YouTube's own chrome (title bar,
		channel link, share/watch-later, end-screen grid). The wrapper reserves
		the 16:9 box while Plyr boots (enablePlyr waits before it scans), so the
		page doesn't jump once the player appears. -->
		<div v-if="isEmbed" class="preview-player aspect-video w-full bg-black">
			<div
				ref="embedEl"
				class="video-player"
				:data-plyr-provider="provider"
				:src="safeUrl(videoPreview.src)"
			/>
		</div>
		<!-- An uploaded file plays through VideoBlock, the same component a lesson
		uses for an uploaded video. The capture listener catches the <video>'s
		`error` (it doesn't bubble, but it still travels down the capture phase)
		so an unplayable file falls back to the poster image as before. -->
		<div
			v-else-if="videoPreview.type === 'file' && !videoError"
			@error.capture="videoError = true"
		>
			<VideoBlock :file="videoPreview.src" />
		</div>
		<img
			v-else-if="fallbackImage"
			:src="safeUrl(fallbackImage)"
			:alt="__('Video preview')"
			class="aspect-video w-full object-cover"
		/>
	</div>
</template>
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { getVideoPreview } from '@/utils/video'
import { enablePlyr } from '@/utils/plyr'
import VideoBlock from '@/components/VideoBlock.vue'
import { safeUrl } from '@/utils/safeUrl'

// Shared display for a course/batch preview video. It renders a single root
// element so the caller can size and frame it with a class, and nothing at all
// when there is no video to show. A video_link can be a
// YouTube or Vimeo link (render the Plyr embed — NOT a <video>, which is what
// made batch previews fail), an uploaded file path (VideoBlock), or unplayable
// (fall back to the poster image). Used by BatchOverview, BatchOverlay,
// CourseHero and CourseCardOverlay.
const props = defineProps<{
	videoLink?: string | null
	fallbackImage?: string | null
}>()

const videoPreview = computed(() => getVideoPreview(props.videoLink))

// YouTube and Vimeo both play through Plyr, exactly as in a lesson.
const isEmbed = computed(
	() =>
		videoPreview.value.type === 'youtube' || videoPreview.value.type === 'embed'
)

// getVideoPreview only ever returns 'embed' for a Vimeo link.
const provider = computed(() =>
	videoPreview.value.type === 'youtube' ? 'youtube' : 'vimeo'
)

const embedEl = ref<HTMLElement | null>(null)

// Reset the in-browser playback error whenever the source changes.
const videoError = ref(false)

watch(
	() => props.videoLink,
	() => {
		videoError.value = false
	}
)

// Boot Plyr once the embed element is in the DOM. The link usually arrives with
// the async doc, i.e. after mount, so this watches the source rather than
// running on mount only; enablePlyr skips elements it has already set up.
watch(
	() => (isEmbed.value ? videoPreview.value.src : ''),
	async (src) => {
		if (!src) return
		await nextTick()
		if (embedEl.value) enablePlyr()
	},
	{ immediate: true }
)

// Nothing to draw: no link, or an unplayable file with no poster to fall back on.
const hasPreview = computed(() => {
	if (isEmbed.value) return true
	if (videoPreview.value.type === 'file') {
		return !videoError.value || Boolean(props.fallbackImage)
	}
	return false
})
</script>
<style scoped>
/* Same control treatment as the lesson player (Lesson.vue carries these rules
   globally, but only while that page is loaded). The container border/radius
   is deliberately left out: the caller frames the preview itself. */
.preview-player {
	--plyr-range-fill-background: white;
	--plyr-video-control-background-hover: transparent;
}

.preview-player :deep(.plyr__volume input[type='range']) {
	display: none;
}

.preview-player :deep(.plyr__control--overlaid) {
	background: radial-gradient(
		circle,
		rgba(0, 0, 0, 0.4) 0%,
		rgba(0, 0, 0, 0.5) 50%
	);
}

.preview-player :deep(.plyr__control:hover) {
	background: none;
}
</style>
