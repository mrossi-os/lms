import { ref } from 'vue'

// OSLMS-CUSTOM: chart series colors from Brand Customize (Base/Advanced roles)
//
// os_lms branding.py writes --os-chart-1..5 when the brand sets chart colors.
// frappe-ui's charts use ECharts' built-in palette unless a page passes
// config.colors, and no LMS page does: the AxisChart/DonutChart overrides call
// withBrandChartColors() so every chart follows the brand without editing the
// pages. ECharts derives hover and label colors from the color strings, so the
// values handed over are resolved colors, not var() references.
//
// An instance without chart colors keeps today's charts untouched: the config is
// returned as is and ECharts keeps choosing its own palette.

const SERIES = 5
// ECharts "light" theme palette, used for series the brand leaves unset.
const ECHARTS_LIGHT = ['#37A2DA', '#32C5E9', '#67E0E3', '#9FE6B8', '#FFDB5C']
const BRAND_LINK = 'link[href*="os_lms.os_lms.branding.brand_css"]'

// Bumped whenever the brand stylesheet may have changed (it loads after the
// first render, and the Desk live preview swaps it), so charts recompute.
export const brandStyleVersion = ref(0)

let watching = false
function watchBrandStyles(): void {
	if (watching || typeof document === 'undefined') return
	watching = true
	const bump = () => brandStyleVersion.value++
	const listenToLinks = () => {
		document.querySelectorAll<HTMLLinkElement>(BRAND_LINK).forEach((link) => {
			if (link.dataset.osChartWatch) return
			link.dataset.osChartWatch = '1'
			link.addEventListener('load', bump)
		})
	}
	listenToLinks()
	new MutationObserver(() => {
		listenToLinks()
		bump()
	}).observe(document.head, {
		childList: true,
		subtree: true,
		characterData: true,
		attributes: true,
		attributeFilter: ['disabled', 'href'],
	})
}

export function brandChartColors(): string[] | null {
	if (typeof document === 'undefined') return null
	const style = getComputedStyle(document.documentElement)
	const colors = Array.from({ length: SERIES }, (_, i) =>
		style.getPropertyValue(`--os-chart-${i + 1}`).trim()
	)
	if (!colors.some(Boolean)) return null
	return colors.map((value, i) => value || ECHARTS_LIGHT[i])
}

export function withBrandChartColors<T extends { colors?: string[] }>(config: T): T {
	watchBrandStyles()
	// Read so the caller's computed() re-runs when the brand stylesheet changes.
	void brandStyleVersion.value
	if (config?.colors?.length) return config
	const colors = brandChartColors()
	return colors ? { ...config, colors } : config
}
