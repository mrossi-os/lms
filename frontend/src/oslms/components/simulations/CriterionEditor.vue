<template>
	<div class="border border-outline-gray-2 rounded-md">
		<!-- Accordion header: always visible -->
		<div
			class="flex items-center gap-2 p-3 cursor-pointer hover:bg-surface-gray-1 rounded-md"
			@click="toggle"
		>
			<ChevronDown
				class="size-4 stroke-1.5 text-ink-gray-5 transition-transform"
				:class="{ '-rotate-90': !expanded }"
			/>
			<div class="flex-1 text-sm font-medium text-ink-gray-9 truncate">
				{{ criterion.criterion_name || __('Nuovo criterio') }}
			</div>
			<Button
				variant="ghost"
				size="sm"
				@click.stop="emit('remove')"
			>
				<template #icon>
					<Trash2 class="size-4 stroke-1.5" />
				</template>
			</Button>
		</div>

		<!-- Accordion body: only when expanded -->
		<div
			v-if="expanded"
			class="p-3 border-t border-outline-gray-2 space-y-2"
		>
			<div class="flex gap-2 items-start">
				<FormControl
					v-model="criterion.criterion_name"
					type="text"
					class="flex-1"
					:placeholder="__('Es. Ascolto attivo')"
				/>
				<FormControl
					v-model.number="criterion.weight"
					type="number"
					step="0.05"
					min="0"
					max="1"
					class="w-24"
					:placeholder="__('Peso')"
				/>
			</div>
			<FormControl
				v-model="criterion.description"
				type="textarea"
				:rows="3"
				:placeholder="__('Descrizione (cosa va osservato)')"
			/>
			<FormControl
				v-model="criterion.observable_behaviors"
				type="textarea"
				:rows="5"
				:placeholder="__('Comportamenti osservabili (per il prompt)')"
			/>
		</div>
	</div>
</template>

<script setup>
import { Button, FormControl } from 'frappe-ui'
import { ChevronDown, Trash2 } from 'lucide-vue-next'

const props = defineProps({
	criterion: { type: Object, required: true },
	expanded: { type: Boolean, default: false },
})
const emit = defineEmits(['update:expanded', 'remove'])

function toggle() {
	emit('update:expanded', !props.expanded)
}
</script>
