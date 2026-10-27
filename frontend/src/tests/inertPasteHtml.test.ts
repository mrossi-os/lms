import { describe, it, expect, vi, afterEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { Editor, getSchema } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import Image from '@tiptap/extension-image'
import { RULES, inertPasteHtml } from '../../oslms-vite/inert-paste-html.js'
// Deep paths, past frappe-ui's `exports`: the paste handlers are not public API.
import { ContentPasteExtension } from '../../node_modules/frappe-ui/src/components/TextEditor/extensions/content-paste-extension'
import {
	htmlContainsImage,
	parseHtmlToSlice,
} from '../../node_modules/frappe-ui/src/molecules/editor/extensions/content-paste/paste-html-utils'

// The image upload path pulls in the whole frappe-ui barrel; these pastes never reach it.
vi.mock('../../node_modules/frappe-ui/src/components/TextEditor/extensions/image/image-extension', () => ({
	processMultipleImages: vi.fn(),
}))

// Pasted HTML must never be parsed by an element of the live page: such an
// element loads <img src=x onerror=...> at once and runs the handler before
// ProseMirror filters the markup (OWASP A17.3, 2026-10-27).

const HOSTILE = '<p>ciao</p><img src="x" onerror="window.__pasteXss = 1">'
const frappeUiSource = (file: string) => resolve(process.cwd(), 'node_modules/frappe-ui/src', file)

// Records the owner document of every element whose innerHTML gets set.
const innerHtmlOwners = () => {
	const setter = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML')!.set!
	const owners: Document[] = []
	vi.spyOn(Element.prototype, 'innerHTML', 'set').mockImplementation(function (this: Element, value: string) {
		owners.push(this.ownerDocument)
		setter.call(this, value)
	})
	return owners
}

const clipboard = (data: Record<string, string>) =>
	({ clipboardData: { files: [], getData: (type: string) => data[type] ?? '' } }) as unknown as ClipboardEvent

afterEach(() => vi.restoreAllMocks())

describe('os-inert-paste-html rule', () => {
	it('rewrites every live-page div of the frappe-ui paste handlers', () => {
		for (const rule of RULES) {
			const path = frappeUiSource(rule.file)
			const out = inertPasteHtml(readFileSync(path, 'utf8'), path)!
			expect(out, rule.file).not.toContain("document.createElement('div')")
			expect(out.split("document.implementation.createHTMLDocument('')").length - 1, rule.file).toBe(rule.count)
		}
	})

	it('leaves other modules alone', () => {
		const path = frappeUiSource('components/TextEditor/TextEditor.vue')
		expect(inertPasteHtml("document.createElement('div')", path)).toBeNull()
	})

	it('fails the build when frappe-ui changes the paste handlers', () => {
		const path = frappeUiSource(RULES[0].file)
		expect(() => inertPasteHtml('const div = 1', path)).toThrow(/frappe-ui changed/)
	})
})

describe('frappe-ui/editor paste helpers', () => {
	const schema = getSchema([StarterKit, Image])

	it('parses pasted HTML outside the live page', () => {
		const owners = innerHtmlOwners()
		const slice = parseHtmlToSlice(HOSTILE, schema)
		expect(htmlContainsImage(HOSTILE)).toBe(true)

		expect(owners.length).toBe(2)
		expect(owners.every((owner) => owner !== document)).toBe(true)
		expect(slice.content.textBetween(0, slice.content.size)).toContain('ciao')
	})
})

describe('classic TextEditor paste', () => {
	const paste = (data: Record<string, string>) => {
		const editor = new Editor({
			element: document.createElement('div'),
			extensions: [StarterKit, Image, ContentPasteExtension],
		})
		const owners = innerHtmlOwners()
		const handled = editor.view.someProp('handlePaste', (handle) => handle(editor.view, clipboard(data), null as never))
		const text = editor.getText()
		editor.destroy()
		return { owners, handled, text }
	}

	it('parses pasted HTML outside the live page', () => {
		const { owners, handled, text } = paste({ 'text/html': HOSTILE })
		expect(handled).toBe(true)
		expect(owners.length).toBe(1)
		expect(owners[0]).not.toBe(document)
		expect(text).toContain('ciao')
	})

	it('parses pasted Markdown outside the live page', () => {
		const { owners, handled, text } = paste({ 'text/plain': '# Titolo\n\n- uno\n- due' })
		expect(handled).toBe(true)
		expect(owners.length).toBe(1)
		expect(owners[0]).not.toBe(document)
		expect(text).toContain('Titolo')
	})
})
