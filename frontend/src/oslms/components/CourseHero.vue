<template>
	<section
		class="relative -mx-5 -mt-5 mb-8 h-[58vh] max-h-[60vh] md:h-[50vh] md:max-h-[50vh] bg-black overflow-hidden"
	>
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
		<div
			class="absolute inset-x-0 bottom-0 p-6 md:p-8 bg-gradient-to-t from-black/80 via-black/50 to-transparent text-ink-gray-9 pointer-events-none"
		>
			<h1 class="text-2xl md:text-4xl font-semibold text-ink-gray-9">
				{{ title }}
			</h1>
			<p
				v-if="shortIntroduction"
				class="mt-2 max-w-3xl text-sm md:text-base text-white/85 leading-6"
			>
				{{ shortIntroduction }}
			</p>
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
	shortIntroduction?: string
}>()

// Locally uploaded files (mp4, webm, ...) render as a native <video>; any other
// value (e.g. a YouTube/Vimeo link) is embedded through an <iframe>.
const DIRECT_VIDEO_EXTENSIONS = /\.(mp4|webm|ogg|ogv|mov|m4v)(\?.*)?$/i
const isDirectVideoFile = (url?: string) =>
	!!url && DIRECT_VIDEO_EXTENSIONS.test(url)

const embedUrl = computed(() => getVideoEmbedURL(props.hero?.media_url))
</script>
