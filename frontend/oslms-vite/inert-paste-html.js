// OSLMS-CUSTOM: parse pasted HTML in an inert document (XSS on paste).
//
// Both frappe-ui editors (the classic TextEditor and frappe-ui/editor) put the
// clipboard HTML into a <div> created in the live page, through innerHTML, before
// ProseMirror's schema filters it. An element owned by the live document loads its
// images at once, so <img src=x onerror=...> runs its handler even though the
// attribute never reaches the editor. A <div> owned by a document made with
// createHTMLDocument has no browsing context: it loads nothing and runs nothing,
// which is how ProseMirror itself reads clipboard HTML.
//
// The plugin rewrites `document.createElement('div')` in the listed files while
// Vite compiles frappe-ui; the files in node_modules stay untouched. Each rule says
// how many it must find. When frappe-ui changes, the build fails, so the paste
// handlers get checked again instead of the fix silently going away.

const LIVE_DIV = "document.createElement('div')"
const INERT_DIV = "document.implementation.createHTMLDocument('').createElement('div')"

export const RULES = [
	{ file: 'components/TextEditor/extensions/content-paste-extension.ts', count: 2 },
	{ file: 'molecules/editor/extensions/content-paste/paste-html-utils.ts', count: 2 },
]

export function inertPasteHtml(code, id) {
	const path = id.replace(/\\/g, '/').split('?')[0]
	const rule = RULES.find((r) => path.endsWith(`/frappe-ui/src/${r.file}`))
	if (!rule) return null
	const parts = code.split(LIVE_DIV)
	if (parts.length - 1 !== rule.count) {
		throw new Error(
			`os-inert-paste-html: expected ${rule.count} × ${LIVE_DIV} in frappe-ui/src/${rule.file}, ` +
				`found ${parts.length - 1}. frappe-ui changed: re-check its paste handlers before updating the rule.`
		)
	}
	return parts.join(INERT_DIV)
}

export function osInertPasteHtml() {
	return {
		name: 'os-inert-paste-html',
		enforce: 'pre',
		transform(code, id) {
			const out = inertPasteHtml(code, id)
			return out === null ? null : { code: out, map: null }
		},
	}
}
