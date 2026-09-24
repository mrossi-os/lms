// OSLMS-CUSTOM: build-time translation of hardcoded English strings in frappe-ui.
//
// frappe-ui's new editor (frappe-ui/editor, used by RichTextEditor since LMS
// v2.63.0) renders its popovers, dialogs and media controls with English text
// and no translation hook. Instead of copying ~20 files into src/overrides
// (copies that drift silently on every frappe-ui bump), this plugin rewrites the
// listed strings into __() calls while Vite compiles frappe-ui. The original
// files stay untouched.
//
// Each rule names a file (relative to node_modules/frappe-ui/src/) and one or
// more strings. When a rule matches nothing, frappe-ui changed that string: the
// plugin warns (dev and build) so the list is updated instead of the text
// quietly going back to English. Translations live in lms/translations/it.csv.
//
// Rule kinds:
//   attr(name, text)  static attribute  name="text"  -> :name="__('text')"
//   text(text)        template text node >  text  <  -> {{ __('text') }}
//   str(text)         quoted string     'text'       -> __('text')
//                     (template expressions and script code evaluated at
//                     render/run time; never use it on module-level constants,
//                     which would be translated before the dictionary loads)
//   raw(from, to)     exact replacement, for anything else
//
// Labels built at module level (e.g. colour swatch names, media align options)
// are translated where the template renders them, with raw().

const EDITOR = 'molecules/editor/'

const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const q = (s) => s.replace(/'/g, "\\'")

const attr = (name, text) => ({
	find: new RegExp(`(^|[\\s<])${esc(name)}="${esc(text)}"`, 'g'),
	replace: `$1:${name}="__('${q(text)}')"`,
	label: `${name}="${text}"`,
})
const text = (t) => ({
	find: new RegExp(`(>\\s*)${esc(t)}(\\s*<)`, 'g'),
	replace: `$1{{ __('${q(t)}') }}$2`,
	label: `>${t}<`,
})
const str = (t) => ({
	find: new RegExp(`(?<!__\\()'${esc(q(t))}'`, 'g'),
	replace: `__('${q(t)}')`,
	label: `'${t}'`,
})
const raw = (from, to) => ({
	find: new RegExp(esc(from), 'g'),
	replace: to.replace(/\$/g, '$$$$'),
	label: from,
})

export const FRAPPE_UI_STRINGS = {
	// Settings dialog
	['components/SettingsDialog/SettingsDialog.vue']: [
		text('Manage your settings across the tabs in this dialog.'),
	],

	// Colour pickers
	[EDITOR + 'components/font-color/fontColorController.ts']: [
		str('Text and background color'),
		str('Text Color'),
		str('Background Color'),
	],
	[EDITOR + 'components/table-color/tableCellColorController.ts']: [
		str('Cell color'),
		str('Text color'),
	],
	[EDITOR + 'components/font-color/ColorSwatchGrid.vue']: [
		raw(':text="swatch.label"', ':text="__(swatch.label)"'),
		raw(':aria-label="swatch.label"', ':aria-label="__(swatch.label)"'),
	],

	// Link and table pickers
	[EDITOR + 'extensions/link/LinkEditorPopup.vue']: [
		attr('dialog-label', 'Edit link'),
		attr('tooltip', 'Remove link'),
		attr('tooltip', 'Apply'),
		attr('tooltip', 'Copy link'),
		text('Edit'),
	],
	[EDITOR + 'components/table-size-picker/TableSizePicker.vue']: [
		attr('dialog-label', 'Insert table'),
	],

	// Embeds
	[EDITOR + 'extensions/iframe/IframeInsertDialog.vue']: [
		text('Cancel'),
		str('Update Embed'),
		str('Insert Embed'),
		str('Edit Embed'),
		raw(
			'`Embed ${platformConfig.value.name}`',
			"__('Embed {0}').format(platformConfig.value.name)"
		),
		str('https://youtube.com/watch?v=… or <iframe src=…>'),
	],
	[EDITOR + 'extensions/iframe/useIframeDialog.ts']: [
		str('Please enter a supported URL or iframe embed code'),
		str('Failed to insert embed. Please check the URL and try again.'),
	],
	[EDITOR + 'extensions/iframe/IframeNodeView.vue']: [
		attr('label', 'Resize embed'),
		text('Loading embed…'),
		attr('placeholder', 'Add caption'),
	],

	// Image gallery
	[EDITOR + 'extensions/image-group/ImageGroupUploadDialog.vue']: [
		str('Edit Images'),
		str('Upload Images'),
		text('Add images'),
		attr(
			'message',
			'Some images failed to upload. Retry or remove the marked images to continue.'
		),
		str('Cancel uploads'),
		str('Cancel'),
		text('Insert as separate images'),
		text('Save'),
		text('Drop images here'),
		str('Insert image'),
		raw('`Insert ${count} images`', "__('Insert {0} images').format(count)"),
	],
	[EDITOR + 'extensions/image-group/ImageGroupGridCell.vue']: [
		attr('aria-label', 'Remove image'),
		str('Click to add caption'),
		str('Add caption...'),
		attr('placeholder', 'Add caption...'),
		attr('aria-label', 'Image caption'),
		str('Upload failed'),
		text('Retry'),
		text('Remove'),
	],
	[EDITOR + 'extensions/image-group/ImageGroupNodeView.vue']: [
		attr('text', 'Edit gallery'),
		attr('aria-label', 'Edit gallery'),
		attr('aria-label', 'Remove image'),
	],
	[EDITOR + 'extensions/image-group/useImageGroupDialog.ts']: [
		str('Upload cancelled'),
		str('Upload failed'),
	],

	// Images, video and attachments inside the document
	[EDITOR + 'components/MediaToolbar.vue']: [
		raw(':text="align.label"', ':text="__(align.label)"'),
		raw(':aria-label="align.label"', ':aria-label="__(align.label)"'),
		str('Replace image'),
		str('Replace video'),
		str('Change link'),
		attr('text', 'Toggle caption'),
		attr('aria-label', 'Toggle caption'),
		attr('aria-label', 'Video options'),
		raw('{{ option }}', '{{ __(option) }}'),
	],
	[EDITOR + 'components/MediaNodeView.vue']: [
		str('Video preview'),
		attr('label', 'Resize media'),
		text('Try again'),
		text('Choose another'),
		text('Remove'),
		attr('placeholder', 'Add caption'),
		attr('aria-label', 'Media caption'),
	],
	[EDITOR + 'components/VideoControls.vue']: [
		str('Pause'),
		str('Play'),
		str('Unmute'),
		str('Mute'),
		attr('aria-label', 'Seek'),
		attr('text', 'Fullscreen'),
		attr('aria-label', 'Fullscreen'),
	],
	[EDITOR + 'components/AttachmentNodeView.vue']: [
		str('Attachment'),
		attr('title', 'Cancel upload'),
		attr('title', 'Try again'),
	],
	[EDITOR + 'components/UploadProgressIndicator.vue']: [
		attr('aria-label', 'Cancel upload'),
	],
	[EDITOR + 'components/image-viewer/ImageViewerControlsBar.vue']: [
		attr('text', 'Previous image'),
		attr('text', 'Next image'),
		attr('text', 'Zoom out'),
		attr('text', 'Reset zoom'),
		attr('text', 'Zoom in'),
		attr('text', 'Download image'),
		str('Exit fullscreen'),
		str('Enter fullscreen'),
		attr('text', 'Close'),
	],

	// Code, table of contents, "/" commands
	[EDITOR + 'extensions/code-block/CodeBlockComponent.vue']: [
		str('Copied!'),
		str('Copy code'),
		attr('label', 'Copy code'),
	],
	[EDITOR + 'extensions/toc-node/TocNodeView.vue']: [
		attr('title', 'Remove table of contents'),
	],
	[EDITOR + 'extensions/toc-node/toc-render.ts']: [
		str('No headings found in this document.'),
	],
	[EDITOR + 'extensions/suggestion/SuggestionList.vue']: [
		attr('dialog-label', 'Suggestions'),
		text('No results'),
		// Slash-command groups and titles are interface labels; mention items
		// render `display` (a person's name) first and are left verbatim.
		raw('{{ group.label }}', '{{ __(group.label) }}'),
		raw(
			'slotItem.display || slotItem.title || slotItem.name',
			'slotItem.display || (slotItem.title && __(slotItem.title)) || slotItem.name'
		),
	],
}

function relativeToFrappeUi(id) {
	const path = id.split('?')[0].replace(/\\/g, '/')
	const marker = '/node_modules/frappe-ui/src/'
	const at = path.lastIndexOf(marker)
	return at === -1 ? null : path.slice(at + marker.length)
}

// Some editor popovers are mounted by frappe-ui in a separate Vue render root,
// which does not inherit the app's globalProperties: a template `__` would be
// undefined there. A setup binding wins over globalProperties, so every
// rewritten SFC gets its own `__` that reads the translator from window.
const SCRIPT_SETUP = /<script setup lang="ts">/
const LOCAL_TRANSLATE =
	'\n// OSLMS-CUSTOM: injected by os-translate-frappe-ui\nconst __ = (...args: any[]) => (window as any).__(...args)\n'

export function applyFrappeUiStrings(file, code, warn = () => {}) {
	const rules = FRAPPE_UI_STRINGS[file]
	if (!rules) return null
	let out = code
	let applied = false
	for (const rule of rules) {
		rule.find.lastIndex = 0
		if (!rule.find.test(out)) {
			warn(
				`[os-translate-frappe-ui] ${file}: ${rule.label} not found; frappe-ui changed it, update frontend/oslms-vite/translate-frappe-ui.js`
			)
			continue
		}
		rule.find.lastIndex = 0
		out = out.replace(rule.find, rule.replace)
		applied = true
	}
	if (applied && file.endsWith('.vue')) {
		if (!SCRIPT_SETUP.test(out)) {
			warn(
				`[os-translate-frappe-ui] ${file}: no <script setup lang="ts"> to host __; frappe-ui changed it, update frontend/oslms-vite/translate-frappe-ui.js`
			)
		} else {
			out = out.replace(SCRIPT_SETUP, (tag) => tag + LOCAL_TRANSLATE)
		}
	}
	return out
}

export function osTranslateFrappeUi() {
	const seen = new Set()
	let isBuild = false
	return {
		name: 'os-translate-frappe-ui',
		enforce: 'pre',
		configResolved(config) {
			isBuild = config.command === 'build'
		},
		transform(code, id) {
			// Only the raw module: `.vue?vue&type=...` sub-requests are compiled
			// from the already transformed source. Other queries (the dev
			// server's `?v=<hash>` on node_modules files) are the raw module.
			if (/[?&]vue\b/.test(id)) return null
			const file = relativeToFrappeUi(id)
			if (!file || !FRAPPE_UI_STRINGS[file]) return null
			seen.add(file)
			const out = applyFrappeUiStrings(file, code, (msg) => this.warn(msg))
			return out === code ? null : { code: out, map: null }
		},
		buildEnd() {
			// In dev modules load lazily, so a missing file only means "not
			// opened yet"; in a build every file must have been seen.
			if (!isBuild) return
			for (const file of Object.keys(FRAPPE_UI_STRINGS)) {
				if (!seen.has(file)) {
					this.warn(
						`[os-translate-frappe-ui] ${file} was never compiled; frappe-ui moved or removed it, update frontend/oslms-vite/translate-frappe-ui.js`
					)
				}
			}
		},
	}
}
