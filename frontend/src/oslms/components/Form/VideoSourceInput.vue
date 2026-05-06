<template>
	<div class="space-y-2">
		<div class="flex items-center gap-2">
			<FormControl
				type="text"
				class="flex-1 min-w-0"
				:modelValue="modelValue"
				:placeholder="placeholder || __('Paste a video URL or pick a file')"
				@update:modelValue="(v) => emit('update:modelValue', v || '')"
			/>
			<button
				type="button"
				class="shrink-0 inline-flex items-center justify-center size-10 rounded-md border text-ink-gray-6 hover:text-ink-gray-8 hover:bg-surface-gray-2"
				:title="__('Choose file')"
				@click="showPicker = !showPicker"
			>
				<FolderOpen class="size-5" />
			</button>
		</div>
		<div
			v-if="showPicker"
			class="rounded-md border border-outline-gray-2 bg-surface-gray-1 p-2"
		>
			<FilePicker
				:placeholder="__('Search a video file...')"
				:allowedExtensions="allowedExtensions"
				@update:fileUrl="onFilePicked"
			/>
		</div>
		<div v-if="modelValue" class="text-xs text-ink-gray-5">
			{{ hint }}
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { FormControl } from 'frappe-ui'
import { FolderOpen } from 'lucide-vue-next'
import FilePicker from '@/components/Controls/FilePicker.vue'

const props = defineProps({
	modelValue: { type: String, default: '' },
	placeholder: { type: String, default: '' },
	allowedExtensions: {
		type: Array,
		default: () => ['mp4', 'webm', 'ogg', 'ogv', 'mov', 'm4v'],
	},
})
const emit = defineEmits(['update:modelValue'])

const showPicker = ref(false)

const onFilePicked = (url) => {
	if (!url) return
	emit('update:modelValue', url)
	showPicker.value = false
}

const hint = computed(() => {
	const v = (props.modelValue || '').trim()
	if (!v) return ''
	if (v.startsWith('/')) return __('Local file — will render as <video>')
	try {
		const u = new URL(v)
		if (u.protocol === 'http:' || u.protocol === 'https:') {
			return __('External link — will render as <iframe> embed')
		}
		return __('Unsupported protocol — will not be rendered')
	} catch {
		return __('Not a valid URL or path — will not be rendered')
	}
})
</script>
