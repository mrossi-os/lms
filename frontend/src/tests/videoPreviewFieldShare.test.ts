/**
 * VideoPreviewField — pasting a Vimeo share link as the course/batch preview
 * video. The uuid can't be embedded, so the field swaps it for the canonical
 * vimeo.com/<id>/<hash> URL that getVideoEmbedURL knows how to play. Anything
 * that isn't a share link must reach the model untouched and never round-trip
 * to the backend.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const { callMock, toastErrorMock } = vi.hoisted(() => ({
	callMock: vi.fn(),
	toastErrorMock: vi.fn(),
}))

vi.mock('frappe-ui', () => ({
	call: callMock,
	toast: { error: toastErrorMock },
	FormControl: {
		name: 'FormControl',
		props: ['modelValue'],
		emits: ['update:modelValue'],
		template:
			'<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
	},
	FormLabel: { name: 'FormLabel', template: '<label />' },
	Button: { name: 'Button', template: '<button><slot /></button>' },
	FileUploader: { name: 'FileUploader', template: '<div />' },
}))

import VideoPreviewField from '@/components/Controls/VideoPreviewField.vue'

declare global {
	interface Window {
		__: (text: string) => string
	}
}
window.__ = (text: string) => text

const SHARE_URL =
	'https://vimeo.com/share/a76b87bd-a2ca-453b-9f81-7d67827f2f80?share=copy&fl=sv&fe=ci'
const CANONICAL = 'https://vimeo.com/1209911974/d7e7b74dda'
const RESOLVED = {
	video_id: '1209911974',
	video_hash: 'd7e7b74dda',
	source: CANONICAL,
	embed: 'https://player.vimeo.com/video/1209911974?h=d7e7b74dda',
}

const emitted = (w: ReturnType<typeof mount>) =>
	(w.emitted('update:modelValue') ?? []).map((e) => (e as string[])[0])

const mountField = (modelValue = '') =>
	mount(VideoPreviewField, {
		props: { modelValue },
		// Templates resolve __ off globalProperties (see src/translation.js), not
		// the window binding the script block uses.
		global: { mocks: { __: (text: string) => text } },
	})

async function paste(url: string) {
	const w = mountField()
	await w.find('input').setValue(url)
	await flushPromises()
	return w
}

describe('VideoPreviewField with a Vimeo share link', () => {
	beforeEach(() => {
		callMock.mockReset()
		toastErrorMock.mockReset()
	})

	it('resolves a pasted share link to the canonical vimeo url', async () => {
		callMock.mockResolvedValue(RESOLVED)
		const w = await paste(SHARE_URL)

		expect(callMock).toHaveBeenCalledWith(
			'os_lms.os_lms.api.resolve_vimeo_share',
			{ url: SHARE_URL }
		)
		// The typed value lands first so nothing waits on the round-trip, then the
		// resolved one replaces it — that last value is what gets saved.
		expect(emitted(w)).toEqual([SHARE_URL, CANONICAL])
	})

	it('keeps the pasted link and warns when it cannot be resolved', async () => {
		callMock.mockRejectedValue(new Error('No video found'))
		const w = await paste(SHARE_URL)

		expect(toastErrorMock).toHaveBeenCalled()
		expect(emitted(w)).toEqual([SHARE_URL])
	})

	it('leaves a canonical vimeo link alone', async () => {
		const w = await paste(CANONICAL)
		expect(callMock).not.toHaveBeenCalled()
		expect(emitted(w)).toEqual([CANONICAL])
	})

	it('leaves youtube links and uploaded files alone', async () => {
		for (const value of ['https://youtu.be/O7FIiYsVy3U', '/files/intro.mp4']) {
			const w = await paste(value)
			expect(callMock).not.toHaveBeenCalled()
			expect(emitted(w)).toEqual([value])
		}
	})

	it('does not call the backend while a share link is half-typed', async () => {
		await paste('https://vimeo.com/share/a76b87bd-a2ca')
		expect(callMock).not.toHaveBeenCalled()
	})
})

describe('VideoPreviewField copy', () => {
	it('offers both providers when the field is empty', () => {
		expect(mountField().text()).toContain('Paste a YouTube or Vimeo link')
	})

	// The field renders no thumbnail for Vimeo (getVideoPreview is YouTube-only),
	// so the copy is the only thing telling the author the link took.
	it('confirms a vimeo link took, rather than reading as an empty field', () => {
		const text = mountField(CANONICAL).text()
		expect(text).toContain('Video link added')
		expect(text).not.toContain('Paste a YouTube or Vimeo link,')
	})

	it('confirms a youtube link took', () => {
		expect(mountField('https://youtu.be/O7FIiYsVy3U').text()).toContain(
			'Video link added'
		)
	})

	it('mentions both providers on an uploaded video', () => {
		expect(mountField('/files/intro.mp4').text()).toContain(
			'Remove it to use a YouTube or Vimeo link instead.'
		)
	})
})
