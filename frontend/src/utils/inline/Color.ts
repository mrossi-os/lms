import { BaseInline } from './BaseInline'
import { paintBucketIcon } from './icons'

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

/**
 * Text-color + highlight inline tool. Wraps the selection in a sanitized
 * `<lms-inline-color>` element carrying inline `color` / `background-color`,
 * edited via two native color inputs in the toolbar action panel.
 *
 * frappe-ui ships no ColorPicker component, so native `<input type="color">`
 * is used here (verified against node_modules/frappe-ui/src/components).
 */
export class Color extends BaseInline {
	private panel: HTMLElement | null = null
	private textInput: HTMLInputElement | null = null
	private backgroundInput: HTMLInputElement | null = null
	// The wrapped element the color inputs write to. Captured when the panel
	// opens so the color still applies after the native color dialog blurs the
	// window and collapses the selection (which can close the inline toolbar).
	private activeNode: HTMLElement | null = null

	// Bound arrow fields: stable references, so re-registering is idempotent and
	// they survive the inline toolbar's clear().
	private applyTextColor = (): void => {
		if (this.activeNode && this.textInput) {
			this.activeNode.style.color = this.textInput.value
		}
	}

	private applyBackgroundColor = (): void => {
		if (this.activeNode && this.backgroundInput) {
			this.activeNode.style.backgroundColor = this.backgroundInput.value
		}
	}

	static get title(): string {
		return __('Color')
	}

	static get sanitize(): Record<string, boolean> {
		return { 'lms-inline-color': true }
	}

	protected get tag(): string {
		return 'LMS-INLINE-COLOR'
	}

	protected get icon(): string {
		return paintBucketIcon
	}

	renderActions(): HTMLElement {
		this.panel = document.createElement('div')
		this.panel.classList.add('lms-inline-color__panel')
		this.panel.hidden = true

		// Keep the selection (and the inline toolbar) alive while the panel is
		// clicked: a native <input type="color"> would otherwise move focus out of
		// the contenteditable and collapse the selection. preventDefault on
		// mousedown blocks that but still lets the click open the OS color dialog.
		this.panel.addEventListener('mousedown', (event: MouseEvent): void => {
			event.preventDefault()
		})

		this.textInput = this.createInput(__('Text color'))
		this.backgroundInput = this.createInput(__('Highlight'))

		// Attach the apply listeners ONCE, directly on the inputs. Opening the OS
		// color dialog blurs the window and can close the inline toolbar — which
		// calls clear() and would remove anything registered via BaseInline.listen
		// — before the dialog commits. Persistent listeners writing to the captured
		// activeNode apply the color regardless of the toolbar's state.
		this.textInput.addEventListener('input', this.applyTextColor)
		this.textInput.addEventListener('change', this.applyTextColor)
		this.backgroundInput.addEventListener('input', this.applyBackgroundColor)
		this.backgroundInput.addEventListener('change', this.applyBackgroundColor)

		this.panel.append(this.textInput.parentElement as HTMLElement)
		this.panel.append(this.backgroundInput.parentElement as HTMLElement)

		return this.panel
	}

	protected showActions(node: HTMLElement): void {
		if (!this.panel || !this.textInput || !this.backgroundInput) {
			return
		}
		this.activeNode = node
		const { color, backgroundColor } = node.style
		this.textInput.value = color ? rgbToHex(color) : '#000000'
		this.backgroundInput.value = backgroundColor
			? rgbToHex(backgroundColor)
			: '#ffffff'
		this.panel.hidden = false
	}

	protected hideActions(): void {
		if (this.panel) {
			this.panel.hidden = true
		}
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
