import { beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { config } from '@vue/test-utils'
import { safeHtml, vExternal } from '../directives'

// main.js registers these on the app, so a component that uses one renders
// wrong under a bare mount() and the failure looks like missing data rather
// than a missing directive. Registering them here keeps component tests
// rendering what the app renders.
config.global.directives = {
	...config.global.directives,
	'safe-html': safeHtml,
	external: vExternal,
}

// main.js puts `__` on window; without it a script-block translation dies on a
// bare ReferenceError. Mirrors translate(), including the contract that a
// message with {0} returns a { format } object rather than a string.
vi.stubGlobal('__', (message: string) => {
	if (!/{\d+}/.test(message)) return message
	return {
		format: (...args: unknown[]) =>
			message.replace(/{(\d+)}/g, (match, index) =>
				args[Number(index)] === undefined ? match : String(args[Number(index)])
			),
	}
})

// main.js installs Pinia on the app, so every store is live before a page
// mounts. Our grafts reach stores (AI context, settings) from pages whose
// upstream tests never set one up; a fresh active Pinia per test mirrors the
// app without leaking store state between tests.
beforeEach(() => {
	setActivePinia(createPinia())
})

// jsdom has no matchMedia. The app's responsive composables call it at setup,
// so a page using one dies before rendering. This mirrors a desktop browser
// where no media query matches; a test that needs a match stubs its own.
if (!window.matchMedia) {
	window.matchMedia = (query: string) =>
		({
			matches: false,
			media: query,
			onchange: null,
			addListener() {},
			removeListener() {},
			addEventListener() {},
			removeEventListener() {},
			dispatchEvent: () => false,
		}) as unknown as MediaQueryList
}
