// OSLMS-CUSTOM: text colour + highlight tool for the lesson editor.
//
// Upstream removed its inline colour tool in v2.63.0 (cc66dc6e0); the client
// kept the feature (decision 2026-09-24), so it lives here, rebuilt on the new
// ToolButton. It wraps the selection in `<span class="lms-inline-color">` with
// inline `color` / `background-color`: a plain span survives both sanitisers
// (nh3 on save, DOMPurify on load), where the old `<lms-inline-color>` element
// needed an allowlist entry on each side.
//
// It does not extend BaseInline: that class finds its wrappers by tag name, and
// `span` would also match the `span.lms-align` wrappers of the align tools.
import paintBucketIcon from 'lucide-static/icons/paint-bucket.svg?raw'
import { ToolButton } from '@/utils/inline/ToolButton'

const COLOR_CLASS = 'lms-inline-color'

/**
 * Convert a CSS `rgb(r, g, b)` string to `#rrggbb` so it can seed a native
 * `<input type="color">` (which only accepts hex). Returns hex/empty unchanged.
 */
function rgbToHex(value: string): string {
	const match = value.match(/^rgba?\((\d+),\s*(\d+),\s*(\d+)/)
	if (!match) {
		return value
	}
	const toHex = (part: string): string =>
		Number(part).toString(16).padStart(2, '0')
	return `#${toHex(match[1])}${toHex(match[2])}${toHex(match[3])}`
}

export class Color extends ToolButton {
	private panel: HTMLElement | null = null
	private textInput: HTMLInputElement | null = null
	private backgroundInput: HTMLInputElement | null = null
	// The wrappers the colour inputs write to. Captured when the panel opens so
	// the colour still applies after the native colour dialog blurs the window
	// and collapses the selection (which can close the inline toolbar).
	private activeNodes: HTMLElement[] = []

	// Bound arrow fields: stable references, so the listeners are attached once
	// and survive the inline toolbar closing while the OS dialog is open.
	private applyTextColor = (): void => {
		const value = this.textInput?.value
		this.activeNodes.forEach((node): void => {
			if (value) node.style.color = value
		})
	}

	private applyBackgroundColor = (): void => {
		const value = this.backgroundInput?.value
		this.activeNodes.forEach((node): void => {
			if (value) node.style.backgroundColor = value
		})
	}

	static get title(): string {
		return __('Color')
	}

	static get sanitize(): Record<string, unknown> {
		return { span: { class: true, style: true } }
	}

	protected get icon(): string {
		return paintBucketIcon
	}

	surround(range: Range): void {
		if (!range || range.collapsed) {
			return
		}
		if (this.state) {
			this.unwrap()
			return
		}
		const wrappers = this.wrap(range)
		if (wrappers.length) {
			this.state = true
			this.showActions(wrappers)
		}
	}

	checkState(): boolean {
		const node = this.findWrapper()
		this.state = node !== null
		if (node) {
			// After EditorJS has drawn the toolbar, as the old BaseInline did.
			setTimeout((): void => {
				this.showActions([node])
			}, 0)
		} else {
			this.hideActions()
		}
		return this.state
	}

	renderActions(): HTMLElement {
		this.panel = document.createElement('div')
		this.panel.classList.add('lms-inline-color__panel')
		this.panel.hidden = true

		// Keep the selection (and the inline toolbar) alive while the panel is
		// clicked: a native <input type="color"> would otherwise move focus out of
		// the contenteditable and collapse the selection. preventDefault on
		// mousedown blocks that but still lets the click open the OS colour dialog.
		this.panel.addEventListener('mousedown', (event: MouseEvent): void => {
			event.preventDefault()
		})

		this.textInput = this.createInput(__('Text color'))
		this.backgroundInput = this.createInput(__('Highlight'))

		// Attached once, directly on the inputs: opening the OS colour dialog can
		// close the inline toolbar before the dialog commits, and these listeners
		// write to the captured wrappers regardless of the toolbar's state.
		this.textInput.addEventListener('input', this.applyTextColor)
		this.textInput.addEventListener('change', this.applyTextColor)
		this.backgroundInput.addEventListener('input', this.applyBackgroundColor)
		this.backgroundInput.addEventListener('change', this.applyBackgroundColor)

		this.panel.append(this.textInput.parentElement as HTMLElement)
		this.panel.append(this.backgroundInput.parentElement as HTMLElement)

		return this.panel
	}

	private showActions(nodes: HTMLElement[]): void {
		if (!this.panel || !this.textInput || !this.backgroundInput) {
			return
		}
		this.activeNodes = nodes
		const { color, backgroundColor } = nodes[0].style
		this.textInput.value = color ? rgbToHex(color) : '#000000'
		this.backgroundInput.value = backgroundColor
			? rgbToHex(backgroundColor)
			: '#ffffff'
		this.panel.hidden = false
	}

	private hideActions(): void {
		if (this.panel) {
			this.panel.hidden = true
		}
	}

	private findWrapper(): HTMLElement | null {
		return this.api.selection.findParentTag('SPAN', COLOR_CLASS)
	}

	private wrapperOf(node: Node): HTMLElement | null {
		const element =
			node.nodeType === Node.ELEMENT_NODE
				? (node as Element)
				: node.parentElement
		return element?.closest<HTMLElement>(`span.${COLOR_CLASS}`) ?? null
	}

	/**
	 * One wrapper per text run the range covers, as BaseInline does: extracting
	 * the whole range into a single span would drag any block elements it spans
	 * (list items, table cells) inside an inline tag.
	 */
	private wrap(range: Range): HTMLElement[] {
		const root = range.commonAncestorContainer
		const scope =
			root.nodeType === Node.TEXT_NODE ? (root.parentNode as Node) : root
		const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT)
		const parts: { node: Text; start: number; end: number }[] = []
		let node: Node | null
		while ((node = walker.nextNode())) {
			const text = node as Text
			if (!range.intersectsNode(text) || this.wrapperOf(text)) {
				continue
			}
			const start = text === range.startContainer ? range.startOffset : 0
			const end = text === range.endContainer ? range.endOffset : text.length
			if (end > start) {
				parts.push({ node: text, start, end })
			}
		}
		const wrappers = parts.map(({ node: text, start, end }): HTMLElement => {
			if (end < text.length) {
				text.splitText(end)
			}
			if (start > 0) {
				text = text.splitText(start)
			}
			const wrapper = document.createElement('span')
			wrapper.classList.add(COLOR_CLASS)
			text.parentNode?.insertBefore(wrapper, text)
			wrapper.appendChild(text)
			return wrapper
		})
		this.select(wrappers)
		return wrappers
	}

	/** Remove the colour wrapper around the selection, keeping its content. */
	private unwrap(): void {
		const node = this.findWrapper()
		if (!node) {
			return
		}
		node.replaceWith(...Array.from(node.childNodes))
		this.state = false
		this.activeNodes = []
		this.hideActions()
	}

	/** Put the selection back across the run that was just wrapped. */
	private select(wrappers: HTMLElement[]): void {
		const selection = window.getSelection()
		if (!selection || !wrappers.length) {
			return
		}
		const next = document.createRange()
		next.setStartBefore(wrappers[0])
		next.setEndAfter(wrappers[wrappers.length - 1])
		selection.removeAllRanges()
		selection.addRange(next)
	}

	private createInput(label: string): HTMLInputElement {
		const field = document.createElement('label')
		field.classList.add('lms-inline-color__field')
		field.textContent = label
		const input = document.createElement('input')
		input.type = 'color'
		field.append(input)
		return input
	}
}
