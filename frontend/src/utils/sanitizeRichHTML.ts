import DOMPurify from 'dompurify'

// Render-side sanitizer for v-html sinks. Server-side sanitize_html already
// strips <script>/<style>/on* handlers; this is defense-in-depth that also drops
// interactive form elements so user-authored content cannot render phishing
// forms. Unlike sanitizeHTML (allowlist, for short title/bio fields) this keeps
// all presentational HTML — div/span/class/style/tables/code — so rich
// descriptions render unchanged.
//
// Kept in its own lean module (only pulls in DOMPurify) so it stays
// importable/testable without index.js's heavy EditorJS/frappe-ui import chain.
export const sanitizeRichHTML = (html?: string | null): string => {
	if (!html) return ''
	return DOMPurify.sanitize(html, {
		FORBID_TAGS: [
			'form',
			'input',
			'button',
			'textarea',
			'select',
			'option',
			'label',
			'fieldset',
		],
		FORBID_ATTR: ['formaction', 'formmethod', 'formenctype'],
	})
}

// OSLMS-CUSTOM: added for the program description; hides emptied rich fields.
// True when rich HTML shows something: the editor saves an emptied field as
// "<p></p>", which must not render as a blank block. Media counts as content.
export const hasRichContent = (html?: string | null): boolean => {
	if (!html) return false
	if (/<(img|video|iframe|table)\b/i.test(html)) return true
	return (
		html
			.replace(/<[^>]*>/g, '')
			.replace(/&nbsp;/g, ' ')
			.trim() !== ''
	)
}
