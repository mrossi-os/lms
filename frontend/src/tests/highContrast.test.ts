import { afterEach, describe, expect, it, vi } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import postcss from 'postcss'
import colors from '../../node_modules/frappe-ui/tailwind/generated/colors.json'

// High contrast (ESG) remaps frappe-ui tokens in styles/theme/elite/high-contrast.css.
// This suite resolves the remapped tokens against frappe-ui's own token data and
// checks the WCAG ratios on the surfaces text is read on, in both themes, so a
// frappe-ui palette change that breaks a promise fails here rather than on screen.

const ROOT = resolve(__dirname, '../..')

const themeVariables = (theme: 'light' | 'dark'): Record<string, string> => {
	const themed = (colors as any).themedVariables[theme]
	const out: Record<string, string> = {}
	for (const [group, tokens] of Object.entries(
		themed as Record<string, Record<string, string>>,
	)) {
		for (const [name, reference] of Object.entries(tokens)) {
			const resolved = reference
				.split('/')
				.reduce<any>((node, key) => (node == null ? node : node[key]), colors)
			if (typeof resolved === 'string') out[`--${group}-${name}`] = resolved
		}
	}
	return out
}

// Declarations of the stylesheet, grouped by the theme each rule applies to.
const overrides = (theme: 'light' | 'dark'): Record<string, string> => {
	const css = readFileSync(
		resolve(ROOT, 'src/styles/theme/elite/high-contrast.css'),
		'utf8',
	)
	const out: Record<string, string> = {}
	postcss.parse(css).walkRules((rule) => {
		const selector = rule.selector
		if (!selector.startsWith(":root[data-contrast='more']")) return
		if (selector.includes(' ')) return
		const forLight = selector.includes(":not([data-theme='dark'])")
		const forDark = !forLight && selector.includes("[data-theme='dark']")
		if ((forDark && theme !== 'dark') || (forLight && theme !== 'light')) return
		rule.walkDecls((decl) => {
			if (decl.prop.startsWith('--')) out[decl.prop] = decl.value
		})
	})
	return out
}

// CSS custom properties on one element resolve against the final declared
// values, so a chain that points back at itself is a cycle, not the stock value.
const resolved = (theme: 'light' | 'dark'): Record<string, string> => {
	const declared = { ...themeVariables(theme), ...overrides(theme) }
	const value = (name: string, seen: string[] = []): string => {
		if (seen.includes(name))
			throw new Error(`cycle: ${[...seen, name].join(' -> ')}`)
		const raw = declared[name]
		const reference = raw?.match(/^var\((--[\w-]+)\)$/)
		return reference ? value(reference[1], [...seen, name]) : raw
	}
	return Object.fromEntries(
		Object.keys(declared).map((name) => [name, value(name)]),
	)
}

const luminance = (hex: string): number => {
	const [r, g, b] = [1, 3, 5]
		.map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
		.map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
	return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

const ratio = (a: string, b: string): number => {
	const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x)
	return (high + 0.05) / (low + 0.05)
}

const READING_SURFACES = [
	'--surface-base',
	'--surface-gray-1',
	'--surface-gray-2',
	'--surface-elevation-1',
	'--surface-elevation-2',
	'--surface-elevation-3',
]

const worstRatio = (tokens: Record<string, string>, name: string): number =>
	Math.min(
		...READING_SURFACES.filter((surface) => tokens[surface]).map((surface) =>
			ratio(tokens[name], tokens[surface]),
		),
	)

const TEXT_TOKENS = [
	'--ink-gray-4',
	'--ink-gray-5',
	'--ink-gray-6',
	'--ink-gray-7',
	'--ink-gray-8',
	'--ink-gray-9',
	'--ink-blue-link',
	...['blue', 'red', 'green', 'amber'].flatMap((hue) =>
		[5, 6, 7, 8, 9, 10].map((shade) => `--ink-${hue}-${shade}`),
	),
]

const BORDER_TOKENS = [1, 2, 3, 4, 5].map((shade) => `--outline-gray-${shade}`)

describe('high-contrast tokens', () => {
	for (const theme of ['light', 'dark'] as const) {
		describe(`in the ${theme} theme`, () => {
			const tokens = resolved(theme)

			it.each(TEXT_TOKENS)('%s reaches 7:1 (WCAG AAA)', (name) => {
				expect(worstRatio(tokens, name)).toBeGreaterThanOrEqual(7)
			})

			it.each(BORDER_TOKENS)('%s reaches 3:1', (name) => {
				expect(worstRatio(tokens, name)).toBeGreaterThanOrEqual(3)
			})
		})
	}

	it('starts from text that fails without it, so the remap is doing the work', () => {
		const stock = themeVariables('light')
		expect(worstRatio(stock, '--ink-gray-5')).toBeLessThan(4.5)
	})
})

// ---------------------------------------------------------------------------
// The index.html bootstrap and src/oslms/utils/contrast.ts state the same rule.

const html = readFileSync(resolve(ROOT, 'index.html'), 'utf8')

const bootstrapSource = (): string => {
	const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(
		(match) => match[1],
	)
	const source = scripts.find((body) => body.includes('data-contrast'))
	if (!source) throw new Error('index.html has no data-contrast bootstrap')
	return source
}

type Scenario = { stored: Record<string, string>; systemMore: boolean }

const mediaQueryList = (query: string, systemMore: boolean) => ({
	matches: query.includes('prefers-contrast') && systemMore,
	addEventListener: () => {},
	removeEventListener: () => {},
})

const runBootstrap = ({ stored, systemMore }: Scenario): boolean => {
	let contrast = false
	const documentStub = {
		documentElement: {
			setAttribute: (name: string, value: string) => {
				if (name === 'data-contrast') contrast = value === 'more'
			},
		},
	}
	new Function('window', 'document', 'localStorage', bootstrapSource())(
		{ matchMedia: (query: string) => mediaQueryList(query, systemMore) },
		documentStub,
		{ getItem: (key: string) => stored[key] ?? null },
	)
	return contrast
}

const runModule = async ({ stored, systemMore }: Scenario) => {
	localStorage.clear()
	for (const [key, value] of Object.entries(stored))
		localStorage.setItem(key, value)
	vi.stubGlobal('matchMedia', (query: string) =>
		mediaQueryList(query, systemMore),
	)
	vi.resetModules()
	return import('../oslms/utils/contrast')
}

afterEach(() => {
	vi.unstubAllGlobals()
	localStorage.clear()
	document.documentElement.removeAttribute('data-contrast')
})

describe('the high-contrast preference', () => {
	it('resolves in the bootstrap exactly as in contrast.ts', async () => {
		const scenarios: Scenario[] = [
			{ stored: {}, systemMore: false },
			{ stored: {}, systemMore: true },
			{ stored: { contrastPreference: 'more' }, systemMore: false },
			{ stored: { contrastPreference: 'normal' }, systemMore: true },
			{ stored: { contrastPreference: 'system' }, systemMore: true },
			{ stored: { contrastPreference: 'nonsense' }, systemMore: false },
		]
		for (const scenario of scenarios) {
			const module = await runModule(scenario)
			expect(runBootstrap(scenario)).toBe(module.highContrast.value)
		}
	})

	it('follows the OS until the user flips it, then keeps the choice', async () => {
		const module = await runModule({ stored: {}, systemMore: true })
		expect(module.highContrast.value).toBe(true)
		expect(document.documentElement.getAttribute('data-contrast')).toBe('more')

		module.toggleContrast()

		expect(module.highContrast.value).toBe(false)
		expect(localStorage.getItem('contrastPreference')).toBe('normal')
		expect(document.documentElement.hasAttribute('data-contrast')).toBe(false)
	})

	it('adds its row to the phone page right after Colour mode', async () => {
		const module = await runModule({ stored: {}, systemMore: false })
		// afterEach unstubs every global, setup.ts's __ included.
		vi.stubGlobal('__', (message: string) => message)
		const groups = module.withContrastRow(
			[
				{
					key: 'Settings',
					rows: [
						{ key: 'colour-mode', label: 'Colour mode', action: 'colour-mode' },
						{ key: 'Log out', label: 'Log out', action: 'logout' },
					],
				},
			],
			false,
		)
		expect(groups[0].rows.map((row) => row.key)).toEqual([
			'colour-mode',
			module.CONTRAST_ACTION,
			'Log out',
		])
	})
})
