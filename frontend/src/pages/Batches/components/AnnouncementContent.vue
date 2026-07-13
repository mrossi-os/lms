<template>
	<iframe
		ref="frame"
		:srcdoc="srcdoc"
		sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
		class="block w-full rounded-md border-0 card"
		scrolling="no"
		@load="onLoad"
	/>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'

const props = defineProps({
	content: {
		type: String,
		default: '',
	},
})

const frame = ref(null)
let resizeObserver = null

/*
 * Render the announcement inside an isolated iframe so it mirrors the chosen
 * email template exactly — the same way the recipient's email client renders
 * it — without the app's dark theme / `prose` styles bleeding in (which would
 * otherwise turn links and text the wrong color). The wrapper only provides
 * neutral email-client defaults (white background, dark text, blue links);
 * any styling defined by the template's own inline styles wins over these.
 */
const srcdoc = computed(
	() => `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<base target="_blank">
<style>
	html, body { margin: 0; }
	body {
		font-family: InterVar, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
		font-size: 14px;
		line-height: 1.5;
		color: #1f2937;
		color: #ffffff;
		padding: 0px;
		word-break: break-word;
		/* Fallback for announcements stored with the editor's named-color
		   variables (color: var(--prose-color-<name>)) before colors were
		   inlined as hex; mapped to light-mode shades for the light background. */
		--prose-color-red: #CC2929;
		--prose-color-blue: #007BE0;
		--prose-color-green: #278F5E;
		--prose-color-yellow: #D1930D;
		--prose-color-orange: #D45A08;
		--prose-color-purple: #8642C2;
		--prose-color-pink: #CF3A96;
		--prose-color-gray: #7C7C7C;
		--prose-color-teal: #0B9E92;
		--prose-color-cyan: #32A4C7;
		/* Highlight (text-background) colors — light shades for the light
		   email background; the editor stores highlights as
		   background-color: var(--prose-highlight-<name>). */
		--prose-highlight-red: #ffe7e7;
		--prose-highlight-blue: #e6f4ff;
		--prose-highlight-green: #e4faeb;
		--prose-highlight-yellow: #fff7d3;
		--prose-highlight-orange: #ffefe4;
		--prose-highlight-purple: #f6e9ff;
		--prose-highlight-pink: #fde8f5;
		--prose-highlight-gray: #f3f3f3;
		--prose-highlight-teal: #e6f7f4;
		--prose-highlight-cyan: #ddf7ff;
	}
	a { color: #1d5a9b; }
	/* Highlighted text keeps the surrounding color instead of the browser's
	   black <mark> default, so a colored span inside a mark still shows its
	   color. */
	mark { color: inherit; border-radius: 3px; padding: 0 2px; }
	/* An empty paragraph (a blank line from pressing Enter twice) has no
	   content, so it collapses and the blank line vanishes. A zero-width
	   non-breaking space gives it a line box so the blank line is preserved. */
	p:empty::before { content: '\\00a0'; }
	img { max-width: 100%; height: auto; }
	table { max-width: 100%; }
</style>
</head>
<body>${props.content || ''}</body>
</html>`,
)

const resize = () => {
	const el = frame.value
	const doc = el?.contentDocument || el?.contentWindow?.document
	if (!el || !doc) return
	const height = Math.max(
		doc.documentElement?.scrollHeight || 0,
		doc.body?.scrollHeight || 0,
	)
	if (height) el.style.height = `${height}px`
}

const onLoad = () => {
	resize()
	const doc = frame.value?.contentDocument
	if (!doc) return

	// Images load asynchronously and change the document height.
	doc.querySelectorAll('img').forEach((img) => {
		if (!img.complete) img.addEventListener('load', resize, { once: true })
	})

	// Keep height in sync with any later layout shifts.
	if (window.ResizeObserver && doc.body) {
		resizeObserver?.disconnect()
		resizeObserver = new ResizeObserver(() => resize())
		resizeObserver.observe(doc.body)
	}
}

onBeforeUnmount(() => resizeObserver?.disconnect())
</script>
