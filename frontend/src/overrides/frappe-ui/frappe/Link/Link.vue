<template>
	<div class="flex flex-col gap-1.5" :class="attrs.class" :style="attrs.style">
		<FormLabel v-if="label" :label="label" size="sm" :required="required" />
		<Combobox
			v-model="model"
			:placeholder="placeholder || `Select ${doctype}`"
			:options="linkOptions"
			@input="handleInputChange"
			@focus="onFocus"
			:open-on-focus="!justSelected"
			v-bind="attrsWithoutClassStyle"
			:variant="props.variant"
		>
			<template #create-new="{ searchTerm }">
				<LucidePlus class="size-4 mr-2" />
				<span class="font-medium"> Create new {{ doctype }}</span>
			</template>
		</Combobox>
	</div>
</template>

<script setup lang="ts">
import { watch, useAttrs, computed, ref, nextTick } from 'vue'
// @ts-ignore
import {
	Combobox,
	type ComboboxOption,
	FormLabel,
	createResource,
	debounce,
} from 'frappe-ui'
import { Plus as LucidePlus } from 'lucide-vue-next'
import { resourceFetcher } from '@/plugins/resourceFetcherPlugin'

interface SelectOption {
	label: string
	value: string
}

interface LinkProps {
	doctype: string
	label?: string
	filters?: Record<string, any>
	placeholder?: string
	variant?: 'subtle' | 'outline' | 'ghost'
	required?: boolean
	allowCreate?: boolean
}

const props = withDefaults(defineProps<LinkProps>(), {
	label: '',
	filters: () => ({}),
	variant: 'subtle',
})
const model = defineModel<string | null>({ default: '' })
const emit = defineEmits<{
	(e: 'create', searchTerm: string): void
}>()

const justSelected = ref(false)

watch(model, () => {
	justSelected.value = true
	nextTick(() => {
		setTimeout(() => {
			justSelected.value = false
		}, 200)
	})
})
defineOptions({ inheritAttrs: false })

const attrs = useAttrs() as Record<string, any>
const attrsWithoutClassStyle = computed(() => {
	return Object.fromEntries(
		Object.entries(attrs).filter(([key]) => key !== 'class' && key !== 'style'),
	)
})

const options = createResource({
	url: 'frappe.desk.search.search_link',
	params: {
		doctype: props.doctype,
		txt: '',
		filters: props.filters,
	},
	method: 'POST',
	resourceFetcher: resourceFetcher,
	transform: (data: SelectOption[]) => {
		return data.map((doc) => ({
			label: doc.label || doc.value,
			value: doc.value,
		}))
	},
})

const createNewOption = {
	type: 'custom' as const,
	key: 'create_new',
	label: 'Create New',
	slotName: 'create-new',
	condition: () => true,
	onClick: ({ searchTerm }: { searchTerm: string }) =>
		emit('create', searchTerm),
} as ComboboxOption

const linkOptions = computed(() => {
	const _options = options.data || []
	if (props.allowCreate) {
		return [..._options, createNewOption]
	}
	return _options
})

const loadOptions = (txt: string = '') => {
	options.update({
		params: {
			txt,
			doctype: props.doctype,
			filters: props.filters,
		},
	})
	options.reload()
}

const onFocus = () => {
	if (!justSelected.value) {
		loadOptions('')
	}
}

const handleInputChange = debounce((inputString: string) => {
	loadOptions(inputString || '')
}, 300)

watch([() => props.doctype, () => props.filters], () => loadOptions(''), {
	immediate: true,
	deep: true,
})
</script>
