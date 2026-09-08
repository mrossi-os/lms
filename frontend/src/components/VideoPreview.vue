<template>
	<div v-if="hasPreview">
		<iframe
			v-if="isEmbed"
			:src="videoPreview.src"
			class="aspect-video w-full"
			frameborder="0"
			allow="accelerometer; encrypted-media; picture-in-picture"
			allowfullscreen
		/>
		<video
			v-else-if="videoPreview.type === 'file' && !videoError"
			:src="videoPreview.src"
			controls
			class="aspect-video w-full bg-black object-contain"
			@error="videoError = true"
		/>
		<img
			v-else-if="fallbackImage"
			:src="fallbackImage"
			class="aspect-video w-full object-cover"
		/>
	</div>
</template>
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { getVideoPreview } from '@/utils/video'

// Shared display for a course/batch preview video. It renders a single root
// element so the caller can size and frame it with a class, and nothing at all
// when there is no video to show. A video_link can be a
// YouTube or Vimeo link (render an embed iframe — NOT a <video>, which is what
// made batch previews fail), an uploaded file path (<video>), or unplayable
// (fall back to the poster image). Used by BatchOverview and BatchOverlay.
const props = defineProps<{
	videoLink?: string | null
	fallbackImage?: string | null
}>()

const videoPreview = computed(() => getVideoPreview(props.videoLink))

// YouTube and Vimeo both play through an iframe, exactly as on the course page.
const isEmbed = computed(
	() => videoPreview.value.type === 'youtube' || videoPreview.value.type === 'embed'
)

// Reset the in-browser playback error whenever the source changes.
const videoError = ref(false)
watch(
	() => props.videoLink,
	() => {
		videoError.value = false
	}
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
