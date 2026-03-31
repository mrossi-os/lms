<template>
	<div class="space-y-1.5 file-picker-component">
		<label v-if="label" class="block text-xs text-ink-gray-5">
			{{ __(label) }}
		</label>
		<div class="flex items-center gap-2">
			<Autocomplete
				ref="autocomplete"
				:options="filteredOptions"
				v-model="selectedOption"
				:placeholder="placeholder || __('Search file...')"
				class="flex-1 min-w-0"
				size="sm"
			>
				<template #item-prefix="{ option }">
					<component
						:is="getFileIcon(option.label)"
						class="w-3.5 h-3.5 shrink-0 mr-2"
						:class="getFileIconColor(option.label)"
					/>
				</template>
				<template #item-label="{ option }">
					<div class="flex flex-col">
						<span class="truncate text-sm text-white">{{ option.label }}</span>
						<span
							v-if="option.description"
							class="text-[11px] text-ink-gray-4 truncate"
						>
							{{ option.description }}
						</span>
					</div>
				</template>
				<template #footer="{ close }">
					<div class="flex items-center justify-between">
						<Button variant="ghost" @click="() => clearValue(close)">
							{{ __('Clear') }}
						</Button>
						<label
							class="flex items-center gap-1.5 text-xs text-ink-gray-5 cursor-pointer pr-1"
						>
							<input
								type="checkbox"
								v-model="includePrivate"
								class="rounded border-outline-gray-2 text-ink-blue-3 focus:ring-ink-blue-3"
							/>
							{{ __('Private') }}
						</label>
					</div>
				</template>
			</Autocomplete>
			<a
				v-if="modelValue"
				:href="selectedFileUrl"
				target="_blank"
				class="shrink-0 text-ink-gray-4 hover:text-ink-gray-7 transition-colors"
				:title="__('Open file')"
			>
				<ExternalLink class="w-4 h-4" />
			</a>
		</div>
	</div>
</template>

<script setup>
import Autocomplete from '@/components/Controls/Autocomplete.vue'
import { watchDebounced } from '@vueuse/core'
import { createResource, Button } from 'frappe-ui'
import {
	FileIcon,
	FileText,
	FileSpreadsheet,
	FileImage,
	FileVideo,
	FileAudio,
	FileArchive,
	FileCode,
	Presentation,
	ExternalLink,
} from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'

const props = defineProps({
	modelValue: {
		type: String,
		default: '',
	},
	label: {
		type: String,
		default: '',
	},
	placeholder: {
		type: String,
		default: '',
	},
	filters: {
		type: Object,
		default: () => ({}),
	},
})

const emit = defineEmits(['update:modelValue'])

const autocomplete = ref(null)
const text = ref('')
const includePrivate = ref(false)

// Cache per mantenere label e url del file selezionato
const fileCache = ref({})

const selectedOption = computed({
	get: () => {
		if (!props.modelValue) return null
		const cached = fileCache.value[props.modelValue]
		return {
			label: cached?.label || props.modelValue,
			value: props.modelValue,
		}
	},
	set: (val) => {
		if (val?.value) {
			fileCache.value[val.value] = {
				label: val.label,
				file_url: val.file_url,
			}
		}
		emit('update:modelValue', val?.value || '')
	},
})

const selectedFileUrl = computed(() => {
	if (!props.modelValue) return ''
	return fileCache.value[props.modelValue]?.file_url || ''
})

const fileFilters = computed(() => {
	const f = { is_folder: 0, ...props.filters }
	if (!includePrivate.value) {
		f.is_private = 0
	}
	return f
})

const fileOptions = createResource({
	url: 'frappe.client.get_list',
	method: 'POST',
	params: {
		doctype: 'File',
		filters: fileFilters.value,
		or_filters: text.value
			? [
					['file_name', 'like', `%${text.value}%`],
					['name', 'like', `%${text.value}%`],
				]
			: undefined,
		fields: ['name', 'file_name', 'file_url', 'is_private'],
		order_by: 'modified desc',
		limit_page_length: 20,
	},
	auto: true,
	transform: (data) =>
		data.map((f) => ({
			label: f.file_name || f.name,
			value: f.name,
			description: f.is_private ? __('Private') : __('Public'),
			file_url: f.file_url,
		})),
})

const filteredOptions = computed(() => fileOptions.data || [])

const reload = () => {
	fileOptions.update({
		params: {
			doctype: 'File',
			filters: fileFilters.value,
			or_filters: text.value
				? [
						['file_name', 'like', `%${text.value}%`],
						['name', 'like', `%${text.value}%`],
					]
				: undefined,
			fields: ['name', 'file_name', 'file_url', 'is_private'],
			order_by: 'modified desc',
			limit_page_length: 20,
		},
	})
	fileOptions.reload()
}

watchDebounced(
	() => autocomplete.value?.query,
	(val) => {
		val = val || ''
		if (text.value === val) return
		text.value = val
		reload()
	},
	{ debounce: 300, immediate: true },
)

watch(includePrivate, () => reload())

// Risolvi il nome del file se il componente si monta con un valore già impostato
const resolveInitialFile = createResource({
	url: 'frappe.client.get_list',
	method: 'POST',
	auto: false,
	transform: (data) => {
		for (const f of data) {
			fileCache.value[f.name] = {
				label: f.file_name || f.name,
				file_url: f.file_url,
			}
		}
	},
})

watch(
	() => props.modelValue,
	(val) => {
		if (val && !fileCache.value[val]) {
			resolveInitialFile.update({
				params: {
					doctype: 'File',
					filters: { name: val },
					fields: ['name', 'file_name', 'file_url'],
					limit_page_length: 1,
				},
			})
			resolveInitialFile.reload()
		}
	},
	{ immediate: true },
)

const extToIcon = {
	pdf: FileText,
	doc: FileText,
	docx: FileText,
	txt: FileText,
	rtf: FileText,
	odt: FileText,
	xls: FileSpreadsheet,
	xlsx: FileSpreadsheet,
	csv: FileSpreadsheet,
	ods: FileSpreadsheet,
	png: FileImage,
	jpg: FileImage,
	jpeg: FileImage,
	gif: FileImage,
	svg: FileImage,
	webp: FileImage,
	bmp: FileImage,
	ico: FileImage,
	mp4: FileVideo,
	avi: FileVideo,
	mov: FileVideo,
	mkv: FileVideo,
	webm: FileVideo,
	mp3: FileAudio,
	wav: FileAudio,
	ogg: FileAudio,
	flac: FileAudio,
	zip: FileArchive,
	rar: FileArchive,
	'7z': FileArchive,
	tar: FileArchive,
	gz: FileArchive,
	ppt: Presentation,
	pptx: Presentation,
	odp: Presentation,
	html: FileCode,
	css: FileCode,
	js: FileCode,
	json: FileCode,
	xml: FileCode,
	py: FileCode,
}

const extToColor = {
	pdf: 'text-ink-red-3',
	doc: 'text-ink-blue-3',
	docx: 'text-ink-blue-3',
	xls: 'text-ink-green-3',
	xlsx: 'text-ink-green-3',
	csv: 'text-ink-green-3',
	ppt: 'text-ink-orange-3',
	pptx: 'text-ink-orange-3',
}

const getExt = (fileName) => {
	if (!fileName) return ''
	const dot = fileName.lastIndexOf('.')
	return dot > 0 ? fileName.slice(dot + 1).toLowerCase() : ''
}

const getFileIcon = (fileName) => extToIcon[getExt(fileName)] || FileIcon

const getFileIconColor = (fileName) =>
	extToColor[getExt(fileName)] || 'text-ink-gray-4'

const clearValue = (close) => {
	emit('update:modelValue', '')
	close()
}
</script>
