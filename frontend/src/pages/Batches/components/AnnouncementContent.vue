<template>
	<iframe
		ref="frame"
		:srcdoc="srcdoc"
		sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"
		class="block w-full rounded-md border-0"
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
	html, body { margin: 0; padding: 12px 16px; }
	body {
		font-family: InterVar, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
		font-size: 14px;
		line-height: 1.5;
		color: #1f2937;

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
	}
	a { color: #1d5a9b; }
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
