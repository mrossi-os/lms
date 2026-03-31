<template>
	<header
		class="sticky top-0 z-10 flex items-center justify-between border-b main-page-header px-3 py-2.5 sm:px-5"
	>
		<Breadcrumbs :items="breadcrumbs" />
	</header>

	<div class="md:w-3/4 md:mx-auto py-5 mx-5">
		<!-- Upload area -->
		<div class="mb-8">
			<input
				ref="fileInput"
				type="file"
				multiple
				class="hidden"
				@change="onFilesSelected"
			/>
			<div
				class="border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors"
				:class="
					isDragging
						? 'border-ink-blue-3 bg-surface-blue-1'
						: 'border-outline-gray-2 hover:border-outline-gray-4'
				"
				@click="fileInput?.click()"
				@dragover.prevent="isDragging = true"
				@dragenter.prevent="isDragging = true"
				@dragleave.prevent="isDragging = false"
				@drop.prevent="onDrop"
			>
				<UploadIcon
					class="w-10 h-10 mx-auto mb-3"
					:class="isDragging ? 'text-ink-blue-3' : 'text-ink-gray-4'"
				/>
				<div class="text-sm font-medium text-ink-gray-7">
					{{ __('Click to select files or drag them here') }}
				</div>
				<div class="text-xs text-ink-gray-5 mt-1">
					{{ __('Any file type') }}
				</div>
			</div>

			<!-- Pending files preview -->
			<div v-if="pendingFiles.length" class="mt-4 space-y-2">
				<div class="flex items-center justify-between mb-2">
					<div class="text-sm font-medium text-ink-gray-7">
						{{ __('Selected files ({0})').format(pendingFiles.length) }}
					</div>
					<div class="flex items-center gap-2">
						<Button variant="subtle" size="sm" @click="clearPending">
							{{ __('Clear all') }}
						</Button>
						<Button
							variant="solid"
							size="sm"
							:loading="isUploading"
							@click="uploadAll"
						>
							<template #prefix>
								<UploadIcon class="w-3.5 h-3.5" />
							</template>
							{{ __('Upload') }}
						</Button>
					</div>
				</div>

				<div
					v-for="(pf, index) in pendingFiles"
					:key="pf.id"
					class="flex items-center gap-3 border rounded-lg px-4 py-3 bg-surface-white"
				>
					<img
						v-if="pf.preview"
						:src="pf.preview"
						class="w-10 h-10 rounded object-cover shrink-0"
					/>
					<component
						v-else
						:is="getFileIcon(pf.file.name)"
						class="w-5 h-5 shrink-0"
						:class="getFileIconColor(pf.file.name)"
					/>

					<div class="flex flex-col min-w-0 flex-1">
						<span class="text-sm font-medium text-ink-gray-9 truncate">
							{{ pf.file.name }}
						</span>
						<span class="text-xs text-ink-gray-5">
							{{ formatSize(pf.file.size) }}
						</span>
					</div>

					<div
						v-if="pf.status === 'uploading'"
						class="w-24 bg-surface-gray-2 rounded-full h-1.5"
					>
						<div
							class="bg-ink-blue-3 h-1.5 rounded-full transition-all"
							:style="{ width: `${pf.progress}%` }"
						/>
					</div>
					<CheckCircle
						v-else-if="pf.status === 'done'"
						class="w-4 h-4 text-ink-green-3 shrink-0"
					/>
					<Tooltip v-else-if="pf.status === 'error'" :text="pf.error">
						<AlertCircle class="w-4 h-4 text-ink-red-3 shrink-0" />
					</Tooltip>

					<button
						v-if="pf.status === 'pending' || pf.status === 'error'"
						class="p-1 rounded hover:bg-surface-gray-3 text-ink-gray-4 hover:text-ink-red-3 transition-colors shrink-0"
						@click="removePending(index)"
					>
						<X class="w-4 h-4" />
					</button>
				</div>
			</div>

			<div class="flex items-center gap-3 mt-3">
				<label
					class="flex items-center gap-1.5 text-sm text-ink-gray-6 cursor-pointer"
				>
					<input
						type="checkbox"
						v-model="uploadPrivate"
						class="rounded border-outline-gray-2 text-ink-blue-3 focus:ring-ink-blue-3"
					/>
					{{ __('Upload as private') }}
				</label>
			</div>
		</div>

		<!-- Files list header -->
		<div class="mb-4 card p-3 space-y-3">
			<div class="flex items-center justify-between">
				<div class="flex items-center gap-3">
					<div class="text-lg font-semibold text-ink-gray-9">
						{{ __('Uploaded Files') }}
					</div>
					<span v-if="totalCount > 0" class="text-sm text-ink-gray-5">
						({{ totalCount }})
					</span>
				</div>

				<div class="flex items-center gap-3">
					<div
						v-if="selectedFiles.size >= 0"
						:class="[
							'flex items-center gap-3 px-3 py-2 rounded-lg',
							selectedFiles.size > 0 ? 'bg-surface-gray-2' : '',
						]"
					>
						<span class="text-sm text-ink-gray-7" v-if="selectedFiles.size > 0">
							{{ __('Selected files ({0})').format(selectedFiles.size) }}
						</span>

						<Button
							variant="subtle"
							size="sm"
							theme="red"
							@click="confirmBulkDelete"
							v-if="selectedFiles.size > 0"
						>
							<template #prefix>
								<Trash2 class="w-3.5 h-3.5" />
							</template>
							{{ __('Delete selected') }}
						</Button>
						<Button
							v-if="files.data?.length"
							variant="outline"
							size="sm"
							@click="toggleSelectAll"
						>
							{{ allVisibleSelected ? __('Deselect all') : __('Select all') }}
						</Button>
					</div>
					<FormControl
						v-model="searchQuery"
						class="small-form"
						:placeholder="__('Search...')"
					/>
					<FormControl
						v-model="sortOrder"
						type="select"
						:options="sortOptions"
					/>
					<FormControl
						v-model="pageSizeStr"
						type="select"
						:options="pageSizeOptions"
					/>
				</div>
			</div>
		</div>

		<div v-if="files.data?.length" class="space-y-2">
			<div
				v-for="file in files.data"
				:key="file.name"
				class="flex items-center gap-3 border rounded-lg px-4 py-3 bg-surface-white hover:bg-surface-gray-7 transition-colors"
			>
				<input
					type="checkbox"
					:checked="selectedFiles.has(file.name)"
					class="rounded border-outline-gray-2 text-ink-blue-3 focus:ring-ink-blue-3 shrink-0"
					@change="toggleSelect(file.name)"
				/>
				<component
					:is="getFileIcon(file.file_name)"
					class="w-5 h-5 shrink-0"
					:class="getFileIconColor(file.file_name)"
				/>
				<div class="flex flex-col min-w-0 flex-1">
					<span class="text-sm font-medium text-ink-gray-9 truncate">
						{{ file.file_name }}
					</span>
					<span class="text-xs text-ink-gray-5">
						{{ formatSize(file.file_size) }}
						<span class="mx-1">&middot;</span>
						{{ dayjs(file.modified).format('DD MMM YYYY') }}
					</span>
				</div>
				<div class="flex items-center gap-2 shrink-0">
					<Tooltip :text="__('Download')">
						<a
							:href="file.file_url"
							target="_blank"
							download
							class="p-1.5 rounded hover:bg-surface-gray-3 text-ink-gray-5 hover:text-ink-gray-7 transition-colors"
						>
							<Download class="w-4 h-4" />
						</a>
					</Tooltip>
					<Tooltip :text="__('Delete')">
						<button
							class="p-1.5 rounded hover:bg-surface-gray-3 text-ink-gray-5 hover:text-ink-red-3 transition-colors"
							@click="confirmDelete(file)"
						>
							<Trash2 class="w-4 h-4" />
						</button>
					</Tooltip>
				</div>
			</div>
		</div>

		<div
			v-else-if="!files.loading"
			class="border border-dashed border-outline-gray-2 rounded-lg py-10 text-center"
		>
			<FileIcon class="w-8 h-8 text-ink-gray-3 mx-auto mb-2" />
			<div class="text-sm text-ink-gray-5">
				{{ __('No files uploaded yet') }}
			</div>
		</div>

		<!-- Pagination -->
		<div
			v-if="totalPages > 1"
			class="flex items-center justify-between mt-4 pt-4 border-t"
		>
			<span class="text-sm text-ink-gray-5">
				{{ __('Page {0} of {1}').format(currentPage, totalPages) }}
			</span>
			<div class="flex items-center gap-2">
				<Button
					variant="outline"
					size="sm"
					:disabled="currentPage <= 1"
					@click="currentPage--"
				>
					<template #prefix>
						<ChevronLeft class="w-4 h-4" />
					</template>
					{{ __('Previous') }}
				</Button>
				<Button
					variant="outline"
					size="sm"
					:disabled="currentPage >= totalPages"
					@click="currentPage++"
				>
					{{ __('Next') }}
					<template #suffix>
						<ChevronRight class="w-4 h-4" />
					</template>
				</Button>
			</div>
		</div>
	</div>
</template>

<script setup>
import {
	Breadcrumbs,
	Button,
	FormControl,
	Tooltip,
	createResource,
	call,
	toast,
} from 'frappe-ui'
import {
	Upload as UploadIcon,
	Download,
	Trash2,
	X,
	CheckCircle,
	AlertCircle,
	ChevronLeft,
	ChevronRight,
	FileIcon,
	FileText,
	FileSpreadsheet,
	FileImage,
	FileVideo,
	FileAudio,
	FileArchive,
	FileCode,
	Presentation,
} from 'lucide-vue-next'
import { ref, reactive, computed, watch } from 'vue'
import { watchDebounced } from '@vueuse/core'
import { createDialog } from '@/utils/dialogs'
import dayjs from 'dayjs'

const searchQuery = ref('')
const uploadPrivate = ref(false)
const isDragging = ref(false)
const isUploading = ref(false)
const fileInput = ref(null)
const pendingFiles = ref([])
const selectedFiles = reactive(new Set())
const currentPage = ref(1)
const pageSizeStr = ref('20')
const sortOrder = ref('modified desc')
const totalCount = ref(0)
const $dialog = createDialog

let idCounter = 0

const breadcrumbs = [
	{ label: __('Upload Files'), route: { name: 'FileUpload' } },
]

const sortOptions = [
	{ label: __('Newest first'), value: 'modified desc' },
	{ label: __('Oldest first'), value: 'modified asc' },
	{ label: __('Name A-Z'), value: 'file_name asc' },
	{ label: __('Name Z-A'), value: 'file_name desc' },
]

const pageSizeOptions = [
	{ label: '20', value: '20' },
	{ label: '50', value: '50' },
	{ label: '100', value: '100' },
]

const pageSize = computed(() => parseInt(pageSizeStr.value))
const totalPages = computed(() =>
	Math.max(1, Math.ceil(totalCount.value / pageSize.value)),
)

// --- Pending files ---

const addFiles = (fileList) => {
	for (const file of fileList) {
		const pf = {
			id: ++idCounter,
			file,
			preview: null,
			status: 'pending',
			progress: 0,
			error: null,
		}
		if (file.type.startsWith('image/')) {
			pf.preview = URL.createObjectURL(file)
		}
		pendingFiles.value.push(pf)
	}
}

const onFilesSelected = (e) => {
	addFiles(e.target.files)
	fileInput.value.value = ''
}

const onDrop = (e) => {
	isDragging.value = false
	if (e.dataTransfer?.files?.length) {
		addFiles(e.dataTransfer.files)
	}
}

const removePending = (index) => {
	const pf = pendingFiles.value[index]
	if (pf.preview) URL.revokeObjectURL(pf.preview)
	pendingFiles.value.splice(index, 1)
}

const clearPending = () => {
	pendingFiles.value.forEach((pf) => {
		if (pf.preview) URL.revokeObjectURL(pf.preview)
	})
	pendingFiles.value = []
}

// --- Upload via XHR ---

const uploadSingleFile = (pf) => {
	return new Promise((resolve) => {
		const xhr = new XMLHttpRequest()
		pf.status = 'uploading'
		pf.progress = 0

		xhr.upload.addEventListener('progress', (e) => {
			if (e.lengthComputable) {
				pf.progress = Math.floor((e.loaded / e.total) * 100)
			}
		})

		xhr.onreadystatechange = () => {
			if (xhr.readyState !== XMLHttpRequest.DONE) return
			if (xhr.status === 200) {
				pf.status = 'done'
				resolve(true)
			} else {
				pf.status = 'error'
				try {
					const resp = JSON.parse(xhr.responseText)
					if (resp._server_messages) {
						pf.error = JSON.parse(JSON.parse(resp._server_messages)[0]).message
					}
				} catch {
					// ignore parse errors
				}
				pf.error = pf.error || __('Upload failed')
				resolve(false)
			}
		}

		xhr.addEventListener('error', () => {
			pf.status = 'error'
			pf.error = __('Upload failed')
			resolve(false)
		})

		xhr.open('POST', '/api/method/upload_file', true)
		xhr.setRequestHeader('Accept', 'application/json')
		if (window.csrf_token && window.csrf_token !== '{{ csrf_token }}') {
			xhr.setRequestHeader('X-Frappe-CSRF-Token', window.csrf_token)
		}

		const formData = new FormData()
		formData.append('file', pf.file, pf.file.name)
		formData.append('is_private', uploadPrivate.value ? '1' : '0')
		formData.append('folder', 'Home')
		xhr.send(formData)
	})
}

const uploadAll = async () => {
	isUploading.value = true
	const toUpload = pendingFiles.value.filter(
		(pf) => pf.status === 'pending' || pf.status === 'error',
	)

	let successCount = 0
	for (const pf of toUpload) {
		const ok = await uploadSingleFile(pf)
		if (ok) successCount++
	}

	isUploading.value = false

	if (successCount > 0) {
		toast.success(
			successCount === 1
				? __('File uploaded successfully')
				: __('Selected files ({0})').format(successCount),
		)
		reloadFiles()
		reloadCount()
		pendingFiles.value = pendingFiles.value.filter((pf) => pf.status !== 'done')
	}
}

// --- Selection ---

const allVisibleSelected = computed(
	() =>
		files.data?.length > 0 &&
		files.data.every((f) => selectedFiles.has(f.name)),
)

const someVisibleSelected = computed(
	() => files.data?.some((f) => selectedFiles.has(f.name)) ?? false,
)

const selectAllVisible = () => {
	files.data?.forEach((f) => selectedFiles.add(f.name))
}

const toggleSelectAll = () => {
	if (allVisibleSelected.value) {
		files.data?.forEach((f) => selectedFiles.delete(f.name))
	} else {
		selectAllVisible()
	}
}

const toggleSelect = (name) => {
	if (selectedFiles.has(name)) {
		selectedFiles.delete(name)
	} else {
		selectedFiles.add(name)
	}
}

const confirmBulkDelete = () => {
	const count = selectedFiles.size
	$dialog({
		title: __('Delete {0} files?').format(count),
		message: __('This action cannot be undone.'),
		actions: [
			{
				label: __('Delete'),
				theme: 'red',
				variant: 'solid',
				onClick(close) {
					bulkDelete()
					close()
				},
			},
		],
	})
}

const bulkDelete = async () => {
	const names = [...selectedFiles]
	let deleted = 0
	for (const name of names) {
		try {
			await call('frappe.client.delete', {
				doctype: 'File',
				name,
			})
			deleted++
		} catch {
			// continue with remaining
		}
	}
	selectedFiles.clear()
	if (deleted > 0) {
		toast.success(__('Deleted {0} files').format(deleted))
		reloadFiles()
		reloadCount()
	}
}

// --- Uploaded files list ---

const fileFilters = { is_folder: 0, attached_to_doctype: '' }

const buildParams = () => ({
	doctype: 'File',
	filters: fileFilters,
	or_filters: searchQuery.value
		? [
				['file_name', 'like', `%${searchQuery.value}%`],
				['name', 'like', `%${searchQuery.value}%`],
			]
		: undefined,
	fields: [
		'name',
		'file_name',
		'file_url',
		'file_size',
		'is_private',
		'modified',
	],
	order_by: sortOrder.value,
	limit_start: (currentPage.value - 1) * pageSize.value,
	limit_page_length: pageSize.value,
})

const files = createResource({
	url: 'frappe.client.get_list',
	method: 'POST',
	params: buildParams(),
	auto: true,
})

const fileCount = createResource({
	url: 'frappe.client.get_count',
	method: 'POST',
	params: {
		doctype: 'File',
		filters: fileFilters,
	},
	auto: true,
	onSuccess: (data) => {
		totalCount.value = data || 0
	},
})

const reloadFiles = () => {
	files.update({ params: buildParams() })
	files.reload()
}

const reloadCount = () => {
	fileCount.update({
		params: {
			doctype: 'File',
			filters: fileFilters,
		},
	})
	fileCount.reload()
}

const reloadAll = () => {
	selectedFiles.clear()
	reloadFiles()
	reloadCount()
}

watchDebounced(
	searchQuery,
	() => {
		currentPage.value = 1
		reloadAll()
	},
	{ debounce: 300 },
)

watch(sortOrder, () => reloadFiles())

watch(pageSizeStr, () => {
	currentPage.value = 1
	reloadFiles()
})

watch(currentPage, () => {
	selectedFiles.clear()
	reloadFiles()
})

const confirmDelete = (file) => {
	$dialog({
		title: __('Delete {0}?').format(file.file_name),
		message: __('This action cannot be undone.'),
		actions: [
			{
				label: __('Delete'),
				theme: 'red',
				variant: 'solid',
				onClick(close) {
					call('frappe.client.delete', {
						doctype: 'File',
						name: file.name,
					}).then(() => {
						toast.success(__('File deleted'))
						reloadFiles()
						reloadCount()
					})
					close()
				},
			},
		],
	})
}

const formatSize = (bytes) => {
	if (!bytes) return '0 B'
	const units = ['B', 'KB', 'MB', 'GB']
	let i = 0
	let size = bytes
	while (size >= 1024 && i < units.length - 1) {
		size /= 1024
		i++
	}
	return `${size.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}

// File icons
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
</script>
