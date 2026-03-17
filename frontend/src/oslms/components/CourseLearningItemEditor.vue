<template>
	<!-- Sezione Cosa Imparerai -->
	<div class="pr-5 md:pr-10 pb-5 mb-5 space-y-5 border-b">
		<div class="text-lg font-semibold text-ink-gray-9">
			{{ __('Cosa Imparerai') }}
		</div>
		<div class="text-sm text-ink-gray-5 mb-3">
			{{ __('Aggiungi fino a 9 badge per mostrare cosa imparerà lo studente') }}
		</div>

		<!-- Lista badge esistenti -->
		<div class="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
			<div
				v-for="(item, index) in learningItems"
				:key="index"
				class="relative border rounded-lg p-3 card space-y-2"
			>
				<button
					class="absolute top-2 right-2 text-ink-gray-4 hover:text-ink-red-3"
					@click="removeLearningItem(index)"
				>
					<X class="w-3.5 h-3.5" />
				</button>
				<IconPicker
					v-model="item.icon"
					:label="__('Icona')"
					@update:modelValue="syncToParent()"
				/>
				<FormControl
					v-model="item.title"
					:label="__('Titolo')"
					:required="true"
					@input="syncToParent()"
				/>
				<FormControl
					v-model="item.description"
					type="textarea"
					:rows="2"
					:label="__('Descrizione')"
					@input="syncToParent()"
				/>
			</div>
		</div>

		<!-- Pulsante aggiungi -->
		<Button
			v-if="learningItems.length < 9"
			variant="outline"
			@click="addLearningItem()"
		>
			<template #prefix>
				<Plus class="w-4 h-4" />
			</template>
			{{ __('Aggiungi Badge') }}
		</Button>
		<div v-else class="text-sm text-ink-gray-5">
			{{ __('Hai raggiunto il massimo di 9 badge') }}
		</div>
	</div>
</template>
<script setup>
import { ref, watch } from 'vue'
import { FormControl, Button } from 'frappe-ui'
import { Plus, X } from 'lucide-vue-next'
import IconPicker from '@/oslms/components/IconPicker.vue'

const props = defineProps({
	modelValue: {
		type: Object,
	},
})

const emit = defineEmits(['update:modelValue', 'dirty'])

const learningItems = ref([])

watch(
	() => props.modelValue?.name,
	() => {
		if (props.modelValue?.learning_items) {
			learningItems.value = props.modelValue.learning_items.map((item) => ({
				title: item.title || '',
				description: item.description || '',
				icon: item.icon || '',
			}))
		}
	},
	{ immediate: true },
)

const syncToParent = () => {
	if (props.modelValue) {
		props.modelValue.learning_items = learningItems.value.map((item) => ({
			title: item.title,
			description: item.description,
			icon: item.icon,
		}))
	}
	emit('dirty')
}

const addLearningItem = () => {
	if (learningItems.value.length < 9) {
		learningItems.value.push({ title: '', description: '', icon: '' })
		syncToParent()
	}
}

const removeLearningItem = (index) => {
	learningItems.value.splice(index, 1)
	syncToParent()
}
</script>
