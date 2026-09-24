// WebKit refuses to scroll a PDF inside an <iframe>, and on iOS/iPadOS every
// browser is WebKit, so the lesson PDF shows page 1 or nothing. Those engines
// get the inline pdf.js viewer (PdfBlock.vue); everywhere else keeps the native
// <iframe> plugin, which is faster, has the browser's own toolbar, and doesn't
// ship ~144kB of pdf.js.
export function usesWebkitPdfViewer(nav: Navigator = navigator): boolean {
	const ua = nav.userAgent || ''
	// iPadOS 13+ reports itself as MacIntel, so touch points disambiguate it.
	const isIOS =
		/iP(hone|ad|od)/.test(ua) ||
		(nav.platform === 'MacIntel' && nav.maxTouchPoints > 1)
	// Blink and Gecko both carry "AppleWebKit" in their UA for legacy reasons;
	// their own engine tokens are what actually rule Safari out.
	const isSafari =
		/AppleWebKit/.test(ua) && !/Chrom(e|ium)|Edg\/|OPR\//.test(ua)
	return isIOS || isSafari
}

// OSLMS-CUSTOM: mobile browsers outside iOS (Chrome, Samsung Internet, Firefox
// on Android) do not render a PDF in an <iframe> either: they show a download
// placeholder. They get the inline pdf.js viewer too; desktop non-Safari
// browsers keep upstream's native plugin.
export function usesInlinePdfViewer(nav: Navigator = navigator): boolean {
	return usesWebkitPdfViewer(nav) || /Android|Mobi/i.test(nav.userAgent || '')
}

// OSLMS-CUSTOM: private lesson files already come percent-encoded through the
// access-gated serve_resource endpoint (see rewrite_private_media); encoding them
// again would escape the percent signs (%20 -> %2520) and break the fetch. Only
// raw paths from fresh editor uploads still need encoding.
export function encodePdfURL(file: string): string {
	const alreadyEncoded =
		file.includes('serve_resource') || /%[0-9A-Fa-f]{2}/.test(file)
	return alreadyEncoded ? file : encodeURI(file)
}
