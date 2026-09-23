<template>
	<FileUploader
		:fileTypes="acceptedFileTypes"
		:uploadArgs="uploadArgs"
		:validateFile="validateFile"
		@success="(data) => addFile(data)"
		@failure="onFailure"
		ref="fileUploader"
		class="hide"
	/>
</template>
<script setup>
import { FileUploader, toast } from 'frappe-ui'
import { onMounted, ref, nextTick, computed } from 'vue'

const fileUploader = ref(null)
const emit = defineEmits(['fileUploaded'])

// OSLMS-CUSTOM: accept documents and archives in lesson uploads, not only media + PDF
// Media types get an inline player/preview (see the isVideo/isAudio/isImage +
// PDF branches in utils/upload.js). Everything else is offered as a download
// link via FileBlock, so we allow a broader set of document/archive types.
const mediaExtensions = [
	'jpg',
	'jpeg',
	'png',
	'gif',
	'webp',
	'svg',
	'mp4',
	'mov',
	'webm',
	'avi',
	'mkv',
	'mp3',
	'wav',
	'ogg',
]
const documentExtensions = [
	'pdf',
	'doc',
	'docx',
	'xls',
	'xlsx',
	'ppt',
	'pptx',
	'csv',
	'txt',
	'rtf',
	'odt',
	'ods',
	'odp',
	'zip',
	'rar',
	'7z',
]
const allowedExtensions = [...mediaExtensions, ...documentExtensions]

// `accept` filter for the native picker: broad media wildcards cover the media
// types; the document/archive types are listed explicitly.
const acceptedFileTypes = [
	'image/*',
	'video/*',
	'audio/*',
	...documentExtensions.map((ext) => `.${ext}`),
]

const props = defineProps({
	onFileUploaded: {
		type: Function,
		required: true,
	},
	uploadContext: {
		type: Object,
		default: () => ({}),
	},
})

// Attach to the lesson only once it exists: a null docname with doctype set
// makes the File doctype reject the upload.
const uploadArgs = computed(() => {
	const args = { private: true }
	const docname = props.uploadContext?.docname
	if (docname) {
		args.doctype = 'Course Lesson'
		args.docname = docname
		args.fieldname = props.uploadContext?.fieldname || 'content'
	}
	return args
})

onMounted(async () => {
	await nextTick()
	const fileInput = fileUploader.value.$el.querySelector('input[type="file"]')
	if (fileInput) {
		fileInput.click()
	}
})

const addFile = (file) => {
	// OSLMS-CUSTOM: derive file_type from the extension when Frappe omits it
	// Frappe doesn't populate file_type for every extension (e.g. some archive
	// types). Fall back to the extension from the file name/URL so the block
	// always has a valid type for validation and rendering.
	const source = file.file_name || file.file_url || ''
	const extension = source.includes('.') ? source.split('.').pop() : ''
	props.onFileUploaded({
		file_url: file.file_url,
		file_type: file.file_type || extension,
	})
}

// OSLMS-CUSTOM: toast upload failures instead of leaving an empty block
// Surface upload failures (e.g. file too large for the site's max_file_size)
// instead of leaving the block silently empty and invalid on reload.
const onFailure = (error) => {
	let message = __('Error uploading file.')
	if (error?.message) {
		message = error.message
	} else if (error?._server_messages) {
		try {
			message = JSON.parse(JSON.parse(error._server_messages)[0]).message
		} catch (e) {
			// keep the default message
		}
	} else if (error?.exc) {
		try {
			message = JSON.parse(error.exc)[0].split('\n').slice(-2, -1)[0]
		} catch (e) {
			// keep the default message
		}
	}
	toast.error(message)
}

const validateFile = (file) => {
	let extension = file.name.split('.').pop().toLowerCase()
	// OSLMS-CUSTOM: validate against the broadened extension list, translated message
	if (!allowedExtensions.includes(extension)) {
		return __('File type .{0} is not supported.').format(extension)
	}
}

const isVideo = (type) => {
	return ['mov', 'mp4', 'avi', 'mkv', 'webm'].includes(type.toLowerCase())
}

const isAudio = (type) => {
	return ['mp3', 'wav', 'ogg'].includes(type.toLowerCase())
}
</script>
