/**
 * Lesson highlights.
 *
 * A highlight used to be restored by searching the lesson for its text, which
 * always landed on the first occurrence: highlighting the third "con" lit up
 * the first one instead. Highlights now carry the character offset of the
 * selection, and the search is only a fallback for notes saved before it.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// vi.hoisted: '@/utils' pulls in Plyr, which reads matchMedia at import time,
// and that import is hoisted above plain statements.
vi.hoisted(() => {
	window.matchMedia ??= (() => ({
		matches: false,
		addEventListener: () => {},
		removeEventListener: () => {},
	})) as unknown as typeof window.matchMedia
})

// Only the surface the '@/utils' import graph pulls in.
vi.mock('frappe-ui', () => ({
	call: vi.fn(),
	toast: { error: vi.fn() },
	createResource: () => ({ data: null, reload: () => {}, fetch: () => {} }),
	Dialog: { name: 'Dialog', template: '<div><slot /></div>' },
	ErrorMessage: { name: 'ErrorMessage', template: '<div />' },
}))

import { getRangeOffset, highlightText, removeHighlight } from '@/utils'

declare global {
	interface Window {
		__: (text: string) => string
	}
}
window.__ = (text: string) => text

const CONTENT =
	'<p>Prima riga con una parola</p>' +
	'<p>Seconda riga senza nulla</p>' +
	'<p>Terza riga con la parola cercata</p>'

const root = () => document.querySelector('#editor') as HTMLElement

// Character offset of an element within the plain text of the lesson.
const offsetOf = (el: Element) => {
	const range = document.createRange()
	range.selectNodeContents(root())
	range.setEnd(el, 0)
	return range.toString().length
}

const spansOf = (name: string) =>
	Array.from(root().querySelectorAll('.highlighted-text')).filter(
		(el) => (el as HTMLElement).dataset.name === name,
	)

beforeEach(() => {
	document.body.innerHTML = `<div id="editor">${CONTENT}</div>`
})

describe('highlightText', () => {
	it('highlights the occurrence at the stored offset, not the first one', () => {
		const thirdRowCon = root().textContent!.lastIndexOf('con')

		highlightText({
			name: 'note-1',
			color: 'Yellow',
			highlighted_text: 'con',
			text_offset: thirdRowCon,
		})

		const spans = spansOf('note-1')
		expect(spans).toHaveLength(1)
		expect(spans[0].textContent).toBe('con')
		expect(offsetOf(spans[0])).toBe(thirdRowCon)
	})

	it('leaves the lesson text untouched', () => {
		const before = root().textContent

		highlightText({
			name: 'note-1',
			color: 'Yellow',
			highlighted_text: 'con',
			text_offset: root().textContent!.lastIndexOf('con'),
		})

		expect(root().textContent).toBe(before)
	})

	it('falls back to the first match for notes saved without an offset', () => {
		highlightText({
			name: 'legacy',
			color: 'Yellow',
			highlighted_text: 'con',
		})

		expect(offsetOf(spansOf('legacy')[0])).toBe(
			root().textContent!.indexOf('con'),
		)
	})

	it('falls back to the nearest match when the offset is stale', () => {
		const thirdRowCon = root().textContent!.lastIndexOf('con')

		// Two characters off: the lesson was edited after the note was saved.
		highlightText({
			name: 'stale',
			color: 'Yellow',
			highlighted_text: 'con',
			text_offset: thirdRowCon - 2,
		})

		expect(offsetOf(spansOf('stale')[0])).toBe(thirdRowCon)
	})

	it('does not draw the same note twice', () => {
		const note = {
			name: 'note-1',
			color: 'Yellow',
			highlighted_text: 'con',
			text_offset: root().textContent!.lastIndexOf('con'),
		}

		// The note list is reloaded after every change and re-highlights all of it.
		highlightText(note)
		highlightText(note)

		expect(spansOf('note-1')).toHaveLength(1)
	})

	it('highlights a selection that crosses element boundaries', () => {
		document.body.innerHTML =
			'<div id="editor"><p>testo <strong>in grassetto</strong> e oltre</p></div>'
		const phrase = 'in grassetto e'

		highlightText({
			name: 'across',
			color: 'Yellow',
			highlighted_text: phrase,
			text_offset: root().textContent!.indexOf(phrase),
		})

		const spans = spansOf('across')
		expect(spans.length).toBeGreaterThan(1)
		expect(spans.map((s) => s.textContent).join('')).toBe(phrase)
	})

	it('ignores text that is not in the lesson', () => {
		highlightText({
			name: 'missing',
			color: 'Yellow',
			highlighted_text: 'assente',
			text_offset: 0,
		})

		expect(spansOf('missing')).toHaveLength(0)
	})
})

describe('removeHighlight', () => {
	it('unwraps the spans so the text can be highlighted again', () => {
		const note = {
			name: 'note-1',
			color: 'Yellow',
			highlighted_text: 'con',
			text_offset: root().textContent!.lastIndexOf('con'),
		}
		const before = root().innerHTML

		highlightText(note)
		removeHighlight('note-1')

		expect(root().innerHTML).toBe(before)

		highlightText(note)
		expect(spansOf('note-1')).toHaveLength(1)
	})
})

describe('getRangeOffset', () => {
	it('counts the characters before the selection', () => {
		const target = root().textContent!.lastIndexOf('con')
		const paragraph = root().children[2]
		const range = document.createRange()
		range.setStart(paragraph.firstChild!, 'Terza riga '.length)
		range.setEnd(paragraph.firstChild!, 'Terza riga con'.length)

		expect(getRangeOffset(range)).toBe(target)
	})

	it('is unaffected by highlights already drawn', () => {
		highlightText({
			name: 'first',
			color: 'Yellow',
			highlighted_text: 'Prima',
			text_offset: 0,
		})

		const paragraph = root().children[2]
		const range = document.createRange()
		range.setStart(paragraph.firstChild!, 'Terza riga '.length)
		range.setEnd(paragraph.firstChild!, 'Terza riga con'.length)

		expect(getRangeOffset(range)).toBe(root().textContent!.lastIndexOf('con'))
	})

	it('returns null for a selection outside the lesson', () => {
		const outside = document.createElement('p')
		outside.textContent = 'fuori'
		document.body.appendChild(outside)

		const range = document.createRange()
		range.selectNodeContents(outside.firstChild!)

		expect(getRangeOffset(range)).toBeNull()
	})
})
