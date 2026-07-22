import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path, { resolve } from 'path'
import { VitePWA } from 'vite-plugin-pwa'
import { readFileSync, existsSync } from 'fs'

export default defineConfig(async ({ mode }) => {
	const isDev = mode === 'development'
	const frappeui = await importFrappeUIPlugin(isDev)
	const configSite = await importConfigSite(isDev);

	const config = {
		define: {
			__VUE_PROD_HYDRATION_MISMATCH_DETAILS__: 'false',
			__SOCKETIO_PORT__: configSite.socketio_port
		},
		plugins: [
			osOverrideTheme(),
			osTranslateTocFallback(),
			frappeui({
				frappeProxy: true,
				lucideIcons: true,
				jinjaBootData: true,
				buildConfig: {
					indexHtmlPath: '../lms/www/_lms.html',
				},
			}),
			vue(),
			VitePWA({
				registerType: 'autoUpdate',
				devOptions: {
					enabled: false,
				},
				workbox: {
					cleanupOutdatedCaches: true,
					maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
					globDirectory: '/assets/lms/frontend',
					globPatterns: ['**/*.{js,ts,css,html,svg}'],
					runtimeCaching: [
						{
							urlPattern: ({ request }) =>
								request.destination === 'document',
							handler: 'NetworkFirst',
							options: {
								cacheName: 'html-cache',
							},
						},
					],
				},
				manifest: false,
			}),
		],
		server: {
			host: '0.0.0.0', // Accept connections from any network interface
			allowedHosts: true,
			// SCORM packages are served by Frappe's SCORMRenderer at /scorm/... .
			// frappeProxy only forwards ^/(desk|app|login|api|assets|files|private),
			// so without this the iframe's /scorm URL hits the SPA fallback and renders
			// blank. The `router` mirrors frappeProxy: Frappe resolves the site from the
			// Host header, so we must forward to http://<site>:8000 — a bare 127.0.0.1
			// target makes Frappe 404 with "127.0.0.1 does not exist". (Backend :8000.)
			proxy: {
				'/scorm': {
					target: 'http://127.0.0.1:8000',
					router: (req) =>
						`http://${req.headers.host.split(':')[0]}:8000`,
				},
			},
		},
		resolve: {
			alias: [
				// Direct path to the ORIGINAL frappe-ui Switch component, imported by its
				// override at src/overrides/frappe-ui/src/components/Switch/Switch.vue.
				// Importing `from 'frappe-ui'` there would make the osOverrideTheme plugin
				// re-route the import back onto the override itself -> infinite recursion.
				// This alias bypasses both the plugin and frappe-ui's package `exports`.
				{
					find: 'frappe-ui-switch-original',
					replacement: path.resolve(
						__dirname,
						'node_modules/frappe-ui/src/components/Switch/Switch.vue'
					),
				},
				// Same pattern as Switch: the FileUploader override re-imports
				// the ORIGINAL component to extend its components map (to register
				// `Button`, which the original imports but forgets to declare).
				{
					find: 'frappe-ui-fileuploader-original',
					replacement: path.resolve(
						__dirname,
						'node_modules/frappe-ui/src/components/FileUploader/FileUploader.vue'
					),
				},
				// Same pattern as Switch: the TextEditor override re-imports the
				// ORIGINAL component to wrap it and add the `os-editor-wrapper`
				// marker class without forking the (large) component file.
				{
					find: 'frappe-ui-texteditor-original',
					replacement: path.resolve(
						__dirname,
						'node_modules/frappe-ui/src/components/TextEditor/TextEditor.vue'
					),
				},
				{
					find: /^@\/utils$/,
					replacement: path.resolve(__dirname, 'src/oslms/utils/index.js'),
				},
				{ find: '@', replacement: path.resolve(__dirname, 'src') },
			],
			// Force one copy of tiptap/prosemirror; duplicate copies break tiptap's
			// instanceof checks and crash the list buttons. The @tiptap/* entries are
			// also declared as direct deps in package.json so the bare imports in
			// src/overrides/.../TextEditor resolve in a clean (Docker) install, where
			// they are not hoisted to the top-level node_modules.
			dedupe: [
				'@tiptap/core',
				'@tiptap/pm',
				'@tiptap/vue-3',
				'prosemirror-model',
				'prosemirror-state',
				'prosemirror-view',
				'prosemirror-transform',
			],
		},
		optimizeDeps: {
			include: [
				'feather-icons',
				'tailwind.config.js',
				'interactjs',
				'highlight.js',
				'plyr',
			],
			exclude: mode === 'production' ? [] : ['frappe-ui'],
		},
	}
	return config
})

async function importFrappeUIPlugin(isDev) {
	if (isDev) {
		try {
			const module = await import('../frappe-ui/vite')
			return module.default
		} catch (error) {
			console.warn(
				'Local frappe-ui not found, falling back to npm package:',
				error.message
			)
		}
	}
	// Fall back to npm package if local import fails
	const module = await import('frappe-ui/vite')
	return module.default
}


async function importConfigSite(isDev) {
	let relativePath = '../../../sites/common_site_config.json'
	if (isDev) {
		relativePath = '../common_site_config.json';
	}
	let filePath = path.resolve(__dirname, relativePath)
	if(!existsSync(filePath)) {
		filePath = path.resolve(__dirname, '../common_site_config.json')
	}
	return JSON.parse(readFileSync(filePath, 'utf-8'))
}


// frappe-ui's tocNode extension lives in a `.ts` file, so it is out of reach of
// osOverrideTheme (which only intercepts `.vue`). Its `renderHTML` serialization
// path hardcodes an English empty-state string, shown in the read-only render of
// a saved Table-of-Contents block that has no headings. Translate that single
// literal to match the interactive NodeView (the TocNodeView.vue override).
// NOTE: a targeted string replace — re-verify the matched literal after any
// frappe-ui bump; a wording change upstream makes this silently no-op.
function osTranslateTocFallback() {
	return {
		name: 'os-translate-toc-fallback',
		enforce: 'pre',
		transform(code, id) {
			if (
				id
					.replace(/\\/g, '/')
					.endsWith('/extensions/toc-node/toc-node-extension.ts')
			) {
				return code.replace(
					"'No headings found in this document.',",
					"'Non ci sono intestazioni in questo documento.',"
				)
			}
			return null
		},
	}
}

// Vite plugin that allows overriding Vue components from node_modules
// (e.g. frappe-ui) with local versions placed in `src/overrides/`.
//
// How it works:
//   1. Intercepts every relative `.vue` import resolved during bundling.
//   2. Checks whether the resolved absolute path falls inside `node_modules/`.
//   3. If it does, looks for a file at the same relative path under
//      `frontend/src/overrides/` (e.g. `src/overrides/frappe-ui/src/Button.vue`).
//   4. When a matching override exists, the plugin returns its path instead,
//      so the override is bundled in place of the original component.
//
// The plugin runs with `enforce: 'pre'` so it takes priority over other
// resolve plugins (including Vite's default resolver).
function osOverrideTheme() {
	const srcDir = resolve(__dirname, 'src')
	const overridesDir = resolve(__dirname, 'src/overrides')
	const nodeModulesDir = resolve(__dirname, 'node_modules')

	return {
		name: 'os-override-theme',
		enforce: 'pre',
		resolveId(source, importer) {
			if (!importer || !source.endsWith('.vue')) return null

			// Imports made *by* an override file must never be re-overridden. A
			// wrap-style override imports the original component it replaces — either
			// directly or via an escape-hatch alias (e.g. `frappe-ui-switch-original`)
			// that `resolve.alias` rewrites to the original's absolute path before this
			// hook runs. Without this guard that import resolves back onto the override
			// itself -> infinite render recursion. (The `absoluteSource` guard below
			// only catches targets already inside src/overrides; it does not cover an
			// override importing its original from node_modules/src.)
			const importerPath = importer.split('?')[0]
			if (importerPath.startsWith(overridesDir)) return null

			// Resolve the import to an absolute path. Vite applies `resolve.alias`
			// before this hook, so `@/` imports usually arrive already rewritten to
			// an absolute path; we still handle the `@/` and relative forms for the
			// cases that reach us un-rewritten (e.g. node_modules deps like frappe-ui).
			let absoluteSource
			if (path.isAbsolute(source)) {
				absoluteSource = source
			} else if (source.startsWith('@/')) {
				absoluteSource = resolve(srcDir, source.slice(2))
			} else if (source.startsWith('.')) {
				absoluteSource = resolve(path.dirname(importer), source)
			} else {
				return null
			}

			// Never re-intercept files already inside src/overrides, otherwise an
			// override importing the original would loop back onto itself.
			if (absoluteSource.startsWith(overridesDir)) return null

			// Mirror both node_modules/* and src/* under src/overrides/ and use the
			// override when a file exists at the same relative path. Note: the two
			// namespaces share src/overrides/, which is safe because node_modules
			// paths start with a package name (e.g. frappe-ui/) while src paths
			// start with pages/, components/, oslms/, etc.
			let relativeToRoot
			if (absoluteSource.startsWith(nodeModulesDir)) {
				relativeToRoot = absoluteSource.slice(nodeModulesDir.length)
			} else if (absoluteSource.startsWith(srcDir)) {
				relativeToRoot = absoluteSource.slice(srcDir.length)
			} else {
				return null
			}

			const overridePath = path.join(overridesDir, relativeToRoot)
			if (existsSync(overridePath)) {
				console.log(`[os-override-theme] Override found: ${overridePath}`)
				return overridePath
			}
			return null
		}
	}
}
