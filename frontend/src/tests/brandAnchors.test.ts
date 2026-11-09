import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Brand Customize Base/Advanced roles (os_lms branding_roles.py SCOPES) recolor an
// area by redefining frappe-ui tokens on classes that already exist in the
// markup. Nothing breaks visibly when an upstream or frappe-ui update renames one:
// the role just stops working. This suite fails instead.

const ROOT = resolve(__dirname, '../..')
const read = (path: string) => readFileSync(resolve(ROOT, path), 'utf8')

describe('Brand Customize role anchors', () => {
	it('sidebar root and active item keep their surface classes', () => {
		const sidebar = read('src/components/Sidebar/AppSidebar.vue')
		expect(sidebar).toMatch(/class="[^"]*\bbg-surface-sidebar\b/)
		const link = read('src/components/Sidebar/SidebarLink.vue')
		expect(link).toContain("isActive ? 'bg-surface-elevation-3")
		expect(link).toContain('hover:bg-surface-gray-2')
	})

	it('frappe-ui buttons keep the token classes the roles scope on', () => {
		const button = read('node_modules/frappe-ui/src/components/Button/Button.vue')
		expect(button).toContain(
			'text-ink-base bg-surface-gray-10 hover:bg-surface-gray-9 active:bg-surface-gray-8',
		)
		expect(button).toContain(
			'text-ink-gray-8 bg-surface-gray-2 hover:bg-surface-gray-3 active:bg-surface-gray-4',
		)
		expect(button).toContain('border border-outline-gray-2')
	})

	it('chart overrides wrap the original frappe-ui charts', () => {
		const vite = read('vite.config.js')
		for (const chart of ['AxisChart', 'DonutChart']) {
			expect(vite).toContain(`frappe-ui-${chart.toLowerCase()}-original`)
			expect(vite).toContain(`node_modules/frappe-ui/src/components/Charts/${chart}.vue`)
			expect(read(`src/overrides/frappe-ui/src/components/Charts/${chart}.vue`)).toContain(
				'withBrandChartColors',
			)
		}
	})
})
