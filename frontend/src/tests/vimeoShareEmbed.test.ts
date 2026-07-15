/**
 * Vimeo share links (vimeo.com/share/<uuid>) pasted into a lesson.
 *
 * The uuid carries no video id, so the `vimeoShare` service only catches the
 * paste and VideoEmbed rewrites the block as a plain `vimeo` one once the
 * backend resolves it. Guards that the resolved block is indistinguishable
 * from a normally pasted vimeo link — the backend reads `source` for audio
 * streaming and `embed` for transcripts, so both must land in the saved data.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'

// vi.hoisted: vi.mock is lifted above these declarations, so the factory can't
// close over plain consts. '@/utils' pulls in Plyr, which reads matchMedia at
// import time — stub it here, before that import runs.
const { callMock, toastErrorMock } = vi.hoisted(() => {
	window.matchMedia ??= (() => ({
		matches: false,
		addEventListener: () => {},
		removeEventListener: () => {},
	})) as unknown as typeof window.matchMedia
	return { callMock: vi.fn(), toastErrorMock: vi.fn() }
})

// Only the surface the '@/utils' import graph pulls in (call/toast here, plus
// createResource for the stores it transitively imports).
vi.mock('frappe-ui', () => ({
	call: callMock,
	toast: { error: toastErrorMock },
	createResource: () => ({ data: null, reload: () => {}, fetch: () => {} }),
	Dialog: { name: 'Dialog', template: '<div><slot /></div>' },
	ErrorMessage: { name: 'ErrorMessage', template: '<div />' },
}))

import { getEditorTools } from '@/utils'

declare global {
	interface Window {
		__: (text: string) => string
	}
}
window.__ = (text: string) => text

const SHARE_URL =
	'https://vimeo.com/share/a76b87bd-a2ca-453b-9f81-7d67827f2f80?share=copy&fl=sv&fe=ci'
const RESOLVED = {
	video_id: '1209911974',
	video_hash: 'd7e7b74dda',
	source: 'https://vimeo.com/1209911974/d7e7b74dda',
	embed: 'https://player.vimeo.com/video/1209911974?h=d7e7b74dda',
}

const insertMock = vi.fn()

// Minimal EditorJS API surface the embed tool touches, cast like the sibling
// BlockEditor/inlineTools tests do.
function makeApi(holder: HTMLElement) {
	return {
		styles: { block: 'ce-block__content', input: 'cdx-input' },
		i18n: { t: (text: string) => text },
		blocks: {
			getCurrentBlockIndex: () => 0,
			getBlockByIndex: (index: number) =>
				index === 0 ? { id: 'block-1', holder } : undefined,
			getBlockIndex: (id: string) => (id === 'block-1' ? 0 : undefined),
			insert: insertMock,
		},
	} as never
}

/** Mirrors what EditorJS does on paste: insert+render the block, then onPaste. */
function pasteIntoEditor(url: string, service: string) {
	const tools = getEditorTools()
	const VideoEmbed = tools.embed.class as never as {
		prepare: (options: object) => void
		new (options: object): {
			onPaste: (event: object) => void
			render: () => HTMLElement
			save: () => Record<string, string>
		}
	}
	VideoEmbed.prepare({ config: tools.embed.config })

	// The `.ce-block` holder EditorJS wraps the tool's element in.
	const holder = document.createElement('div')
	document.body.appendChild(holder)

	const block = new VideoEmbed({
		data: {},
		api: makeApi(holder),
		readOnly: false,
	})
	holder.appendChild(block.render())
	block.onPaste({ detail: { key: service, data: url } })
	return block
}

describe('vimeo share link paste', () => {
	beforeEach(() => {
		document.body.innerHTML = ''
		callMock.mockReset()
		toastErrorMock.mockReset()
		insertMock.mockReset()
	})

	it('registers a vimeoShare service that matches a share link', () => {
		const services = getEditorTools().embed.config.services
		expect(services.vimeoShare.regex.test(SHARE_URL)).toBe(true)
		// The canonical form must stay with the plain (client-side) vimeo service.
		expect(services.vimeoShare.regex.test(RESOLVED.source)).toBe(false)
		expect(services.vimeo.regex.test(RESOLVED.source)).toBe(true)
	})

	it('resolves the share link and saves it as a plain vimeo block', async () => {
		callMock.mockResolvedValue(RESOLVED)
		const block = pasteIntoEditor(SHARE_URL, 'vimeoShare')
		await flushPromises()

		expect(callMock).toHaveBeenCalledWith(
			'os_lms.os_lms.api.resolve_vimeo_share',
			{ url: SHARE_URL },
		)
		const saved = block.save()
		// `vimeoShare` must not survive: the backend only knows `vimeo`.
		expect(saved.service).toBe('vimeo')
		expect(saved.source).toBe(RESOLVED.source)
		expect(saved.embed).toBe(RESOLVED.embed)
		// Plyr binds to the element this service renders.
		expect(document.querySelector('.video-player')).not.toBeNull()
	})

	it('falls back to the url as text when the backend cannot resolve it', async () => {
		callMock.mockRejectedValue(new Error('No video found'))
		pasteIntoEditor(SHARE_URL, 'vimeoShare')
		await flushPromises()

		expect(toastErrorMock).toHaveBeenCalled()
		expect(insertMock).toHaveBeenCalledWith(
			'paragraph',
			{ text: SHARE_URL },
			{},
			0,
			false,
			true,
		)
	})

	it('leaves a canonical vimeo link to the built-in sync path', async () => {
		const block = pasteIntoEditor(
			'https://vimeo.com/1209911974/d7e7b74dda?fl=pl&fe=sh',
			'vimeo',
		)
		await flushPromises()

		expect(callMock).not.toHaveBeenCalled()
		expect(block.save().embed).toBe(RESOLVED.embed)
	})
})
