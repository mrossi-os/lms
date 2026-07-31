import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

export default defineConfig({
	plugins: [vue()],
	test: {
		environment: 'jsdom',
		globals: true,
		include: ['src/tests/**/*.test.{ts,js}'],
		// frappe-ui ships untranspiled sources; a test that pulls one of its
		// internal modules (e.g. the real resource cache) needs them processed by
		// vite rather than resolved as external node ESM.
		server: { deps: { inline: [/frappe-ui/] } },
	},
	resolve: {
		alias: {
			'@': path.resolve(path.dirname(fileURLToPath(import.meta.url)), 'src'),
		},
	},
})
