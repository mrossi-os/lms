<template>
	<div class="border border-outline-gray-2 rounded-md p-3 space-y-2">
		<div class="flex items-center gap-2">
			<FormControl
				v-model="turn.role"
				type="select"
				class="w-32"
				:options="[
					{ label: __('Studente'), value: 'user' },
					{ label: __('Cliente'), value: 'assistant' },
				]"
			/>
			<div class="text-xs text-ink-gray-5">{{ __('Turn') }} #{{ index }}</div>
			<div class="flex-1" />
			<Button variant="ghost" size="sm" :disabled="!canMoveUp" @click="$emit('move-up')">
				<template #icon><ChevronUp class="size-4 stroke-1.5" /></template>
			</Button>
			<Button variant="ghost" size="sm" :disabled="!canMoveDown" @click="$emit('move-down')">
				<template #icon><ChevronDown class="size-4 stroke-1.5" /></template>
			</Button>
			<Button variant="ghost" size="sm" @click="$emit('remove')">
				<template #icon><Trash2 class="size-4 stroke-1.5" /></template>
			</Button>
		</div>
		<FormControl
			v-model="turn.text"
			type="textarea"
			:rows="3"
			:placeholder="__('Testo del turn')"
		/>
	</div>
</template>

<script setup>
import { FormControl, Button } from 'frappe-ui'
import { ChevronUp, ChevronDown, Trash2 } from 'lucide-vue-next'

defineProps({
	turn: { type: Object, required: true },
	index: { type: Number, required: true },
	canMoveUp: { type: Boolean, default: true },
	canMoveDown: { type: Boolean, default: true },
})
defineEmits(['move-up', 'move-down', 'remove'])
</script>
