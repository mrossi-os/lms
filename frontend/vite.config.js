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
		},
		resolve: {
			alias: [
				{
					find: /^@\/utils$/,
					replacement: path.resolve(__dirname, 'src/oslms/utils/index.js'),
				},
				{ find: '@', replacement: path.resolve(__dirname, 'src') },
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
	const filePath = path.resolve(__dirname, relativePath)
	return JSON.parse(readFileSync(filePath, 'utf-8'))
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
	return {
		name: 'os-override-theme',
		enforce: 'pre',
		resolveId(source, importer) {
			if (!importer) return null
			if (!source.startsWith('.') || !source.endsWith('.vue')) return null
			const absoluteSource = resolve(path.dirname(importer), source)
			const srcDir = resolve(__dirname, 'node_modules')
			if (!absoluteSource.startsWith(srcDir)) return null
			const relativeToSrc = absoluteSource.slice(srcDir.length)
			const overridePath = path.join(__dirname, 'src/overrides', relativeToSrc)
			if (existsSync(overridePath)) {
				console.log(`[os-override-theme] Override found: ${overridePath}`)
				return overridePath
			}
			return null
		}
	}
}
