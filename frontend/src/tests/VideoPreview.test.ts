import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// Plyr can't boot in jsdom (and enablePlyr waits before it scans the document),
// so stub it: these tests only assert the markup Plyr is handed.
const enablePlyr = vi.hoisted(() => vi.fn())
vi.mock('@/utils/plyr', () => ({ enablePlyr }))

// VideoBlock mounts a real <video> (jsdom can't drive it); stub it to a marker
// that exposes the file it was handed and still emits the media `error` the
// fallback relies on.
vi.mock('@/components/VideoBlock.vue', () => ({
	default: {
		props: ['file'],
		template: `<video data-testid="video-block" :src="file" />`,
	},
}))

import VideoPreview from '@/components/VideoPreview.vue'

const player = (w: ReturnType<typeof mount>) => w.find('.video-player')

describe('VideoPreview', () => {
	it('hands a youtube link to the lesson player (not a <video>)', () => {
		const w = mount(VideoPreview, {
			props: { videoLink: 'https://youtu.be/O7FIiYsVy3U?si=22FPigXQedh7jAlz' },
		})
		expect(player(w).attributes('data-plyr-provider')).toBe('youtube')
		expect(player(w).attributes('src')).toBe(
			'https://www.youtube.com/embed/O7FIiYsVy3U'
		)
		expect(w.find('iframe').exists()).toBe(false)
		expect(w.find('[data-testid="video-block"]').exists()).toBe(false)
	})

	it('renders VideoBlock for an uploaded file path', () => {
		const w = mount(VideoPreview, { props: { videoLink: '/files/intro.mp4' } })
		const video = w.find('[data-testid="video-block"]')
		expect(video.exists()).toBe(true)
		expect(video.attributes('src')).toBe('/files/intro.mp4')
		expect(player(w).exists()).toBe(false)
	})

	it('falls back to the image when the file video errors', async () => {
		const w = mount(VideoPreview, {
			props: {
				videoLink: '/files/intro.mov',
				fallbackImage: '/files/thumb.jpg',
			},
		})
		await w.find('[data-testid="video-block"]').trigger('error')
		expect(w.find('[data-testid="video-block"]').exists()).toBe(false)
		const img = w.find('img')
		expect(img.exists()).toBe(true)
		expect(img.attributes('src')).toBe('/files/thumb.jpg')
	})

	it('renders nothing without a link', () => {
		const w = mount(VideoPreview, { props: { videoLink: null } })
		expect(player(w).exists()).toBe(false)
		expect(w.find('[data-testid="video-block"]').exists()).toBe(false)
		expect(w.find('img').exists()).toBe(false)
	})

	it('hands a vimeo link to the lesson player (not a <video>)', () => {
		// Regression: a Vimeo link used to reach the <video> branch, fail to load
		// and leave the page with no player and no frame at all. The hash has to
		// survive in the src — Plyr reads it from there for unlisted videos.
		const w = mount(VideoPreview, {
			props: { videoLink: 'https://vimeo.com/1209911974/d7e7b74dda' },
		})
		expect(player(w).attributes('data-plyr-provider')).toBe('vimeo')
		expect(player(w).attributes('src')).toBe(
			'https://player.vimeo.com/video/1209911974?h=d7e7b74dda'
		)
		expect(w.find('[data-testid="video-block"]').exists()).toBe(false)
	})

	it('draws no frame when an unplayable file has no image to fall back on', async () => {
		const w = mount(VideoPreview, { props: { videoLink: '/files/intro.mov' } })
		await w.find('[data-testid="video-block"]').trigger('error')
		expect(w.find('div').exists()).toBe(false)
	})
})
