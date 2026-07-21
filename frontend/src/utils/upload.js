import AudioBlock from '@/components/AudioBlock.vue'
import VideoBlock from '@/components/VideoBlock.vue'
import FileBlock from '@/components/FileBlock.vue'
import UploadPlugin from '@/components/UploadPlugin.vue'
import { h, createApp } from 'vue'
import { Upload as UploadIcon } from 'lucide-vue-next'
import { createDialog } from '@/utils/dialogs'
import translationPlugin from '../translation'

export class Upload {
	constructor({ data, api, config, readOnly }) {
		this.data = data
		this.readOnly = readOnly
		this.config = config || {}
	}

	static get toolbox() {
		const app = createApp({
			render: () =>
				h(UploadIcon, { size: 18, strokeWidth: 1.5, color: 'black' }),
		})

		const div = document.createElement('div')
		app.mount(div)

		return {
			title: 'Upload',
			icon: div.innerHTML,
		}
	}

	static get isReadOnlySupported() {
		return true
	}

	render() {
		this.wrapper = document.createElement('div')

		if (this.data && this.data.file_url) {
			// Some uploads (e.g. certain archive types) come back from the
			// server without a file_type. Backfill it from the URL extension so
			// the block validates, renders, and re-saves with a valid type.
			if (!this.data.file_type) {
				this.data.file_type = this.getFileType(this.data)
			}
			this.renderFile(this.data)
		} else {
			this.renderFileUploader()
		}

		return this.wrapper
	}

	renderFile(file) {
		const fileType = this.getFileType(file)
		if (this.isVideo(fileType)) {
			const app = createApp(VideoBlock, {
				file: file.file_url,
				readOnly: this.readOnly,
				quizzes: file.quizzes || [],
				saveQuizzes: (quizzes) => {
					if (this.readOnly) return
					this.data.quizzes = quizzes
				},
			})
			app.use(translationPlugin)
			app.config.globalProperties.$dialog = createDialog
			app.mount(this.wrapper)
			return
		} else if (this.isAudio(fileType)) {
			const app = createApp(AudioBlock, {
				file: file.file_url,
			})
			app.mount(this.wrapper)
			return
		} else if (fileType.toLowerCase() == 'pdf') {
			this.wrapper.innerHTML = `<iframe src="${
				window.location.origin
			}${encodeURI(
				file.file_url,
			)}" width='100%' height='700px' class="mb-4" type="application/pdf"></iframe>`
			return
		} else if (this.isImage(fileType)) {
			this.wrapper.innerHTML = `<img class="mb-4" src=${encodeURI(
				file.file_url,
			)} width='100%'>`
			return
		} else {
			const app = createApp(FileBlock, {
				file: file.file_url,
			})
			app.use(translationPlugin)
			app.mount(this.wrapper)
			return
		}
	}

	renderFileUploader() {
		const app = createApp(UploadPlugin, {
			docname: this.config.docname || null,
			fieldname: this.config.fieldname || 'content',
			onFileUploaded: (file) => {
				this.data.file_url = file.file_url
				this.data.file_type = file.file_type
				this.renderFile(file)
			},
		})
		app.use(translationPlugin)
		app.mount(this.wrapper)
	}

	validate(savedData) {
		// Only file_url is required; file_type can be derived from it when the
		// server didn't provide one, so blocks with an empty file_type are
		// still valid instead of being silently dropped.
		if (!savedData || !savedData.file_url) {
			return false
		}
		return true
	}

	save(blockContent) {
		return {
			file_url: this.data.file_url,
			file_type: this.data.file_type,
			quizzes: this.data.quizzes || [],
		}
	}

	getFileType(file) {
		if (file.file_type) {
			return file.file_type
		}
		// Fall back to the extension parsed from the file URL.
		const path = (file.file_url || '').split('?')[0]
		return path.includes('.') ? path.split('.').pop() : ''
	}

	isVideo(type) {
		return ['mov', 'mp4', 'avi', 'mkv', 'webm'].includes(type.toLowerCase())
	}

	isAudio(type) {
		return ['mp3', 'wav', 'ogg'].includes(type.toLowerCase())
	}

	isImage(type) {
		return [
			'jpg',
			'jpeg',
			'png',
			'gif',
			'webp',
			'svg',
			'bmp',
			'ico',
			'avif',
			'tiff',
		].includes(type.toLowerCase())
	}
}
