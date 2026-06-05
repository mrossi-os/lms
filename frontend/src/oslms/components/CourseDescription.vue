<template>
	<div class="card p-3">
		<div
			v-html="unescapedDescription"
			class="prose prose-sm max-w-none !whitespace-normal prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 overflow-hidden transition-all duration-300"
			:style="
				!isExpanded && showToggle ? `max-height: ${collapsedHeight}px` : ''
			"
		/>
		<div
			v-if="showToggle"
			class="relative flex justify-center"
			:class="!isExpanded ? '-mt-10 pt-12' : 'mt-2'"
		>
			<Button variant="outline" size="sm" @click="isExpanded = !isExpanded">
				<template #prefix>
					<ChevronDown
						class="h-4 w-4 transition-transform duration-300"
						:class="isExpanded ? 'rotate-180' : ''"
					/>
				</template>
				{{ isExpanded ? __('Mostra meno') : __('Mostra altro') }}
			</Button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Button } from 'frappe-ui'
import { ChevronDown } from 'lucide-vue-next'

const props = withDefaults(
	defineProps<{
		description?: string
		// Plain-text length above which the "show more" toggle appears.
		charLimit?: number
		// Collapsed height (px) when the toggle is shown.
		collapsedHeight?: number
	}>(),
	{ description: '', charLimit: 400, collapsedHeight: 156 },
)

const isExpanded = ref(false)

// The description is stored as HTML; decode any escaped entities (e.g. &lt;p&gt;)
// so the markup renders correctly when bound with v-html.
const unescapedDescription = computed(() => {
	const html = props.description
	if (!html) return ''
	const textarea = document.createElement('textarea')
	textarea.innerHTML = html
	return textarea.value
})

// Show the toggle only when the plain-text content exceeds the limit.
const showToggle = computed(() => {
	const text = (props.description || '').replace(/<[^>]*>/g, '')
	return text.length > props.charLimit
})
</script>
