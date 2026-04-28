<template>
	<transition
		enter-active-class="duration-300 ease-out"
		enter-from-class="transform opacity-0"
		enter-to-class="opacity-100"
		leave-active-class="duration-300 ease-in"
		leave-from-class="opacity-100"
		leave-to-class="transform opacity-0"
	>
		<div
			v-if="list.selections.size"
			class="absolute inset-x-0 bottom-6 mx-auto w-max text-base"
		>
			<div
				class="flex max-w-96 items-center gap-3 rounded-lg bg-surface-white px-4 py-2 shadow-2xl"
				:class="$attrs.class"
			>
				<slot
					v-bind="{
						selections: list.selections,
						allRowsSelected: list.allRowsSelected,
						selectAll: () => list.toggleAllRows(true),
						unselectAll: () => list.toggleAllRows(false),
					}"
				>
					<div
						class="flex flex-1 justify-between border-r border-outline-gray-2 text-ink-gray-9"
					>
						<div class="flex items-center gap-3">
							<div>{{ selectedText }}</div>
						</div>
						<div class="me-3">
							<slot
								name="actions"
								v-bind="{
									selections: list.selections,
									allRowsSelected: list.allRowsSelected,
									selectAll: () => list.toggleAllRows(true),
									unselectAll: () => list.toggleAllRows(false),
								}"
							/>
						</div>
					</div>
					<div class="flex items-center gap-1">
						<Button
							class="text-ink-gray-7"
							variant="ghost"
							@click="list.toggleAllRows(!list.allRowsSelected)"
						>
							{{ list.allRowsSelected ? __('Deselect all') : __('Select all') }}
						</Button>
					</div>
				</slot>
			</div>
		</div>
	</transition>
</template>

<script setup>
import { Button } from 'frappe-ui'
import { computed, inject } from 'vue'

defineOptions({
	inheritAttrs: false,
})

const list = inject('list')

const defaultSelectionText = (count) =>
	count === 1 ? __('1 row selected') : __('{0} rows selected').format(count)

let selectedText = computed(() => {
	const fn = list.value.options.selectionText || defaultSelectionText
	return fn(list.value.selections.size)
})
</script>
