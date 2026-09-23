/**
 * PDF lesson blocks on mobile.
 *
 * Mobile browsers cannot show a PDF inside an iframe — Chrome for Android draws
 * a download placeholder and iOS Safari a static, unscrollable first page — so
 * PdfBlock swaps the frame for a card that opens the file in a new tab. Guards
 * the viewport split, and the file name shown on the card: private lesson files
 * are served through serve_resource, whose URL path ends with the whitelisted
 * method name and carries the real path in the file_url query parameter.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'

// The real frappe-ui entrypoint pulls in `~icons/lucide/*` virtual modules that
// only the app's vite config resolves. Only Button is needed here; keep the
// `link` prop, since the card's whole purpose is that outgoing anchor.
vi.mock('frappe-ui', () => ({
	Button: {
		name: 'Button',
		props: ['link', 'variant', 'iconLeft'],
		template: '<a :href="link"><slot /></a>',
	},
}))

import PdfBlock from '@/components/PdfBlock.vue'

const SERVE_RESOURCE =
	'/api/method/lms.lms.doctype.course_lesson.course_lesson.serve_resource?file_url=%2Fprivate%2Ffiles%2FDispensa%20modulo%203.pdf'

const originalWidth = window.innerWidth

const setViewport = (width: number) => {
	Object.defineProperty(window, 'innerWidth', {
		value: width,
		configurable: true,
	})
}

const mountBlock = (props: Record<string, unknown>) =>
	// Templates resolve __ off globalProperties (see src/translation.js).
	mount(PdfBlock, { props, global: { mocks: { __: (s: string) => s } } })

afterEach(() => setViewport(originalWidth))

describe('PdfBlock', () => {
	describe('on a phone viewport', () => {
		beforeEach(() => setViewport(390))

		it('replaces the unusable iframe with a card linking to the file', () => {
			const wrapper = mountBlock({ file: SERVE_RESOURCE })

			expect(wrapper.find('iframe').exists()).toBe(false)
			expect(wrapper.find('a').attributes('href')).toBe(SERVE_RESOURCE)
		})

		it('names the card after the document, not the endpoint', () => {
			const wrapper = mountBlock({ file: SERVE_RESOURCE })

			expect(wrapper.text()).toContain('Dispensa modulo 3.pdf')
			expect(wrapper.text()).not.toContain('serve_resource')
		})

		it('falls back to the path basename for a file not yet rewritten', () => {
			const wrapper = mountBlock({ file: '/private/files/Appunti lezione.pdf' })

			expect(wrapper.text()).toContain('Appunti lezione.pdf')
		})
	})

	describe('on a desktop viewport', () => {
		beforeEach(() => setViewport(1280))

		it('keeps the embedded viewer, which works there', () => {
			const wrapper = mountBlock({ file: SERVE_RESOURCE })

			expect(wrapper.find('a').exists()).toBe(false)
			expect(wrapper.find('iframe').attributes('src')).toBe(SERVE_RESOURCE)
		})

		it('hides the native toolbar when the macro asks for it', () => {
			const wrapper = mountBlock({ file: SERVE_RESOURCE, toolbar: false })

			expect(wrapper.find('iframe').attributes('src')).toBe(
				`${SERVE_RESOURCE}#toolbar=0`
			)
		})

		it('encodes a raw path that has not been through the server rewrite', () => {
			const wrapper = mountBlock({ file: '/private/files/Appunti lezione.pdf' })

			expect(wrapper.find('iframe').attributes('src')).toBe(
				'/private/files/Appunti%20lezione.pdf'
			)
		})
	})
})
