// The inline pdf.js viewer also serves Android/mobile browsers, and
// private serve_resource URLs are never encoded twice (entry upload-pdf-block-mobile).
import { describe, expect, it } from 'vitest'
import { encodePdfURL, usesInlinePdfViewer } from '@/utils/pdfViewer'

const nav = (userAgent: string, platform = 'Linux armv8l', maxTouchPoints = 5) => {
	return { userAgent, platform, maxTouchPoints } as unknown as Navigator
}

const ANDROID_CHROME =
	'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36'
const ANDROID_SAMSUNG =
	'Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/24.0 Chrome/117.0.0.0 Mobile Safari/537.36'
const ANDROID_FIREFOX =
	'Mozilla/5.0 (Android 14; Mobile; rv:124.0) Gecko/124.0 Firefox/124.0'
const IOS_SAFARI =
	'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'
const DESKTOP_CHROME =
	'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
const DESKTOP_FIREFOX =
	'Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0'

describe('usesInlinePdfViewer', () => {
	it.each([
		['Chrome on Android', ANDROID_CHROME],
		['Samsung Internet', ANDROID_SAMSUNG],
		['Firefox on Android', ANDROID_FIREFOX],
	])('uses the inline viewer on %s', (_name, ua) => {
		expect(usesInlinePdfViewer(nav(ua))).toBe(true)
	})

	it('still uses the inline viewer on iOS', () => {
		expect(usesInlinePdfViewer(nav(IOS_SAFARI, 'iPhone'))).toBe(true)
	})

	it.each([
		['Chrome', DESKTOP_CHROME],
		['Firefox', DESKTOP_FIREFOX],
	])('keeps the native iframe plugin on desktop %s', (_name, ua) => {
		expect(usesInlinePdfViewer(nav(ua, 'Win32', 0))).toBe(false)
	})
})

describe('encodePdfURL', () => {
	it('leaves a private serve_resource URL untouched', () => {
		const url =
			'/api/method/lms.lms.doctype.course_lesson.course_lesson.serve_resource?file=%2Fprivate%2Ffiles%2FMy%20Notes.pdf'
		expect(encodePdfURL(url)).toBe(url)
	})

	it('does not encode an already percent-encoded path again', () => {
		expect(encodePdfURL('/files/My%20Notes.pdf')).toBe('/files/My%20Notes.pdf')
	})

	it('encodes a raw path from a fresh upload', () => {
		expect(encodePdfURL('/files/My Notes.pdf')).toBe('/files/My%20Notes.pdf')
	})
})
