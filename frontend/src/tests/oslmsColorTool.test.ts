// The lesson editor's text colour tool (src/oslms/utils/inline/Color.ts),
// rebuilt on ToolButton after upstream removed its own in v2.63.0.
import { describe, it, expect, beforeEach } from 'vitest'
import type { API, InlineToolConstructorOptions } from '@editorjs/editorjs'
import { Color } from '@/oslms/utils/inline/Color'

// The global translation helper the tools call; identity is enough here.
;(window as unknown as { __: (text: string) => string }).__ = (text) => text

// Same minimal EditorJS API as inlineTools.test.ts: findParentTag honours the
// class, so a span.lms-align is not mistaken for a colour wrapper.
function makeApi(root: HTMLElement): API {
	return {
		styles: {
			inlineToolButton: 'ce-inline-tool',
			inlineToolButtonActive: 'ce-inline-tool--active',
		},
		selection: {
			findParentTag(tagName: string, className?: string): HTMLElement | null {
				const selection = window.getSelection()
				let node: Node | null =
					selection && selection.rangeCount > 0
						? selection.getRangeAt(0).commonAncestorContainer
						: null
				while (node && node !== root.parentNode) {
					if (
						node instanceof HTMLElement &&
						node.tagName === tagName.toUpperCase() &&
						(!className || node.classList.contains(className))
					) {
						return node
					}
					node = node.parentNode
				}
				return null
			},
		},
	} as unknown as API
}

function makeTool(root: HTMLElement): Color {
	const tool = new Color({
		api: makeApi(root),
	} as unknown as InlineToolConstructorOptions)
	tool.render()
	return tool
}

function select(node: Node, start: number, end: number): Range {
	const range = document.createRange()
	range.setStart(node, start)
	range.setEnd(node, end)
	const selection = window.getSelection()
	selection?.removeAllRanges()
	selection?.addRange(range)
	return range
}

describe('oslms colour tool', () => {
	let root: HTMLElement
	let host: HTMLElement

	beforeEach(() => {
		document.body.innerHTML =
			'<div id="root"><div id="p">hello world</div></div>'
		root = document.getElementById('root') as HTMLElement
		host = document.getElementById('p') as HTMLElement
	})

	it('wraps the selection in span.lms-inline-color', () => {
		const tool = makeTool(root)
		tool.renderActions()
		tool.surround(select(host.firstChild as Node, 0, 5))

		expect(host.innerHTML).toBe(
			'<span class="lms-inline-color">hello</span> world'
		)
	})

	it('writes the picked colours onto the wrapper even after the selection is gone', () => {
		const tool = makeTool(root)
		const panel = tool.renderActions()
		tool.surround(select(host.firstChild as Node, 0, 5))
		// The OS colour dialog blurs the window and collapses the selection.
		window.getSelection()?.removeAllRanges()

		const [text, highlight] = Array.from(
			panel.querySelectorAll<HTMLInputElement>('input[type="color"]')
		)
		text.value = '#ff0000'
		text.dispatchEvent(new Event('change'))
		highlight.value = '#00ff00'
		highlight.dispatchEvent(new Event('input'))

		const wrapper = host.querySelector('span.lms-inline-color') as HTMLElement
		expect(wrapper.style.color).toBe('rgb(255, 0, 0)')
		expect(wrapper.style.backgroundColor).toBe('rgb(0, 255, 0)')
	})

	it('keeps the selection when the panel is pressed', () => {
		const tool = makeTool(root)
		const panel = tool.renderActions()
		const event = new MouseEvent('mousedown', { cancelable: true })
		panel.dispatchEvent(event)

		expect(event.defaultPrevented).toBe(true)
	})

	it('unwraps an existing colour run on toggle', () => {
		host.innerHTML =
			'<span class="lms-inline-color" style="color: red">hello</span> world'
		const tool = makeTool(root)
		tool.renderActions()
		const inner = (host.firstChild as HTMLElement).firstChild as Node
		const range = select(inner, 0, 5)
		tool.checkState()
		tool.surround(range)

		expect(host.innerHTML).toBe('hello world')
	})

	it('does not treat an alignment span as a colour wrapper', () => {
		host.innerHTML =
			'<span class="lms-align" style="text-align: center; display: block;">hello world</span>'
		const tool = makeTool(root)
		tool.renderActions()
		const inner = (host.firstChild as HTMLElement).firstChild as Node
		const range = select(inner, 0, 5)

		expect(tool.checkState()).toBe(false)
		tool.surround(range)
		expect(host.querySelector('span.lms-align > span.lms-inline-color')?.textContent).toBe(
			'hello'
		)
	})
})
