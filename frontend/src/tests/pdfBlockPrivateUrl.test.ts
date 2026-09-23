/**
 * PDF lesson blocks: our additions to the upstream pdf.js viewer.
 *
 * Since v2.60.0 PdfBlock is upstream's inline pdf.js viewer (adopted by the
 * project owner in place of our mobile card). What stays ours: private lesson
 * files are served percent-encoded through the access-gated serve_resource
 * endpoint and must reach pdf.js and the fallback link unchanged (encoding them
 * again turns %20 into %2520), raw paths from fresh uploads still get encoded,
 * and the viewer's labels are translated. See inventory entry
 * upload-pdf-block-mobile.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const state = vi.hoisted(() => ({
	shouldReject: false,
	getDocument: vi.fn(),
}))

vi.mock('pdfjs-dist/legacy/build/pdf.mjs', () => ({
	getDocument: state.getDocument,
	GlobalWorkerOptions: { workerPort: null },
}))
vi.mock('@/utils/pdfWorker', () => ({
	createPdfWorker: () => ({ terminate: vi.fn(), postMessage: vi.fn() }),
}))

const SERVE_RESOURCE =
	'/api/method/lms.lms.doctype.course_lesson.course_lesson.serve_resource?file_url=%2Fprivate%2Ffiles%2FDispensa%20modulo%203.pdf'

beforeEach(() => {
	state.shouldReject = false
	state.getDocument.mockReset()
	state.getDocument.mockImplementation(() => ({
		promise: state.shouldReject
			? Promise.reject(new Error('boom'))
			: Promise.resolve({
					numPages: 1,
					destroy: vi.fn(),
					getPage: vi.fn(async () => ({
						getViewport: () => ({ width: 600, height: 800 }),
						render: () => ({ promise: Promise.resolve(), cancel: vi.fn() }),
					})),
			  }),
	}))
})
afterEach(() => {
	delete (window as any).__
	vi.resetModules()
})

async function mountPdf(file: string) {
	const { default: PdfBlock } = await import('@/components/PdfBlock.vue')
	const wrapper = mount(PdfBlock, { props: { file } })
	await flushPromises()
	await flushPromises()
	return wrapper
}

describe('PdfBlock private files', () => {
	it('hands an already-encoded serve_resource URL to pdf.js unchanged', async () => {
		await mountPdf(SERVE_RESOURCE)
		expect(state.getDocument.mock.calls[0][0].url).toBe(SERVE_RESOURCE)
	})

	it('encodes a raw path that has not been through the server rewrite', async () => {
		await mountPdf('/private/files/Appunti lezione.pdf')
		expect(state.getDocument.mock.calls[0][0].url).toBe(
			'/private/files/Appunti%20lezione.pdf',
		)
	})

	it('points the fallback link at the same URL when the PDF fails to load', async () => {
		state.shouldReject = true
		const wrapper = await mountPdf(SERVE_RESOURCE)
		const hrefs = wrapper.findAll('a').map((a) => a.attributes('href'))
		expect(hrefs).toContain(SERVE_RESOURCE)
		expect(hrefs.every((href) => !href?.includes('%2520'))).toBe(true)
	})
})

describe('PdfBlock labels', () => {
	it('translates its labels through window.__ when the app provides it', async () => {
		;(window as any).__ = (text: string) => `IT:${text}`
		state.shouldReject = true
		const wrapper = await mountPdf(SERVE_RESOURCE)
		expect(wrapper.text()).toContain('IT:This PDF could not be displayed.')
		expect(wrapper.text()).toContain('IT:Open the PDF in a new tab')
	})
})
