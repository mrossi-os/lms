// OSLMS-CUSTOM: local stand-in for `@framework/ui/ConditionBuilder`.
//
// Upstream v2.63.0 builds the Raven channel-rule editor on Frappe's shared UI
// package (`@framework/ui`, linked from apps/frappe/ui), which only exists on
// Frappe develop. This stack runs version-16, where the link leads nowhere and
// the whole SPA build would fail. vite.config.js aliases the import here.
//
// It accepts the props RuleConditions.vue passes and renders a notice instead of
// the editor: Raven is not installed on our sites and the Raven settings tab is
// admin-only, so nothing else depends on it. Drop this file and the alias once
// the stack moves to a Frappe release that ships the package.
import { defineComponent, h } from 'vue'

export const ConditionBuilder = defineComponent({
	name: 'ConditionBuilder',
	props: {
		modelValue: { type: Object, default: null },
		reorderable: { type: Boolean, default: false },
		bordered: { type: String, default: '' },
		maxDepth: { type: Number, default: 0 },
		newCondition: { type: Function, default: null },
		readonly: { type: Boolean, default: false },
		columns: { type: Object, default: null },
	},
	emits: ['update:modelValue'],
	setup() {
		return () =>
			h(
				'p',
				{
					class: 'text-p-sm text-ink-gray-6',
					'data-testid': 'condition-builder-unavailable',
				},
				__(
					'The condition editor needs a newer Frappe version and is not available on this site.'
				)
			)
	},
})

export default ConditionBuilder
