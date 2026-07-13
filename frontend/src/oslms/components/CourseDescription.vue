<template>
	<div class="">
		<div
			ref="contentRef"
			v-html="unescapedDescription"
			class="ProseMirror prose prose-sm max-w-none !whitespace-normal prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 overflow-hidden transition-all duration-300"
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
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { Button } from 'frappe-ui'
import { ChevronDown } from 'lucide-vue-next'

const props = withDefaults(
	defineProps<{
		description?: string
		// Collapsed height (px) when the toggle is shown.
		collapsedHeight?: number
	}>(),
	{ description: '', collapsedHeight: 156 },
)

const isExpanded = ref(false)
const contentRef = ref<HTMLElement | null>(null)
// Whether the rendered content actually overflows the collapsed height.
const showToggle = ref(false)

// The description is stored as HTML; decode any escaped entities (e.g. &lt;p&gt;)
// so the markup renders correctly when bound with v-html.
const unescapedDescription = computed(() => {
	const html = props.description
	if (!html) return ''
	const textarea = document.createElement('textarea')
	textarea.innerHTML = html
	return textarea.value
})

// Show the toggle only when the rendered content is taller than the collapsed
// height. scrollHeight reports the full content height even while the
// max-height clamp is applied, so it's safe to read directly.
const updateToggle = () => {
	const el = contentRef.value
	if (!el) {
		showToggle.value = false
		return
	}
	showToggle.value = el.scrollHeight > props.collapsedHeight + 1
}

let resizeObserver: ResizeObserver | null = null

onMounted(() => {
	updateToggle()
	if (typeof ResizeObserver !== 'undefined') {
		// Re-measure on layout changes (responsive reflow, async image loads).
		resizeObserver = new ResizeObserver(() => updateToggle())
		if (contentRef.value) resizeObserver.observe(contentRef.value)
	}
})

onBeforeUnmount(() => {
	resizeObserver?.disconnect()
})

// Re-measure when the description changes.
watch(
	() => props.description,
	async () => {
		await nextTick()
		updateToggle()
	},
)
</script>

<style scoped>
/*
 * The description is authored in the TextEditor. A double line break is stored
 * as an empty `<p></p>`, which collapses to zero height under `prose`, so the
 * blank line the author added disappears in this read-only view. Give empty
 * paragraphs a single line of height so the spacing matches the editor.
 * (Named text colors / highlights already render via the `.ProseMirror` class
 * on the container above, which pulls in frappe-ui's `--prose-color-*` /
 * `--prose-highlight-*` variables.)
 */
.ProseMirror :deep(p:empty)::before {
	content: '\00a0';
}
</style>
