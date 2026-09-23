import AudioBlock from '@/components/AudioBlock.vue'
import VideoBlock from '@/components/VideoBlock.vue'
// OSLMS-CUSTOM: non-media uploads render as a download card
import FileBlock from '@/components/FileBlock.vue'
import PdfBlock from '@/components/PdfBlock.vue'
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
				h(UploadIcon, {
					size: 18,
					strokeWidth: 1.5,
					// OSLMS-CUSTOM: toolbox icon follows the theme instead of hard-coded black
					color: 'currentColor',
				}),
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
			// OSLMS-CUSTOM: backfill a missing file_type from the URL extension
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
		// OSLMS-CUSTOM: route by derived type: video/audio/pdf/image/other file
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
			// OSLMS-CUSTOM: PDF detected from the derived type (file_type or URL extension)
			// iOS Safari (all WebKit browsers) refuses to scroll a PDF in an
			// <iframe>, so render it inline via pdf.js. mount()/unmount() is tracked
			// so destroy() can tear the pdf.js worker + render tasks down.
			this.app = createApp(PdfBlock, {
				file: file.file_url,
			})
			this.app.use(translationPlugin)
			this.app.mount(this.wrapper)
			return
		} else if (this.isImage(fileType)) {
			this.wrapper.innerHTML = `<img class="mb-4" src=${encodeURI(
				file.file_url,
			)} width='100%'>`
			return
		} else {
			// OSLMS-CUSTOM: any other file type becomes a download card, not a broken <img>
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
			uploadContext: this.config,
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
		// OSLMS-CUSTOM: blocks without file_type stay valid
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

	// OSLMS-CUSTOM: file type fallback from the URL extension
	getFileType(file) {
		if (file.file_type) {
			return file.file_type
		}
		// Fall back to the extension parsed from the file URL.
		const path = (file.file_url || '').split('?')[0]
		return path.includes('.') ? path.split('.').pop() : ''
	}

	// EditorJS calls destroy() when a block is removed or the editor is torn down.
	// Unmounting the PdfBlock app fires its onBeforeUnmount, which cancels render
	// tasks, destroys the document, and releases the shared pdf.js worker.
	destroy() {
		if (this.app) {
			this.app.unmount()
			this.app = null
		}
	}

	isVideo(type) {
		return ['mov', 'mp4', 'avi', 'mkv', 'webm'].includes(type.toLowerCase())
	}

	isAudio(type) {
		return ['mp3', 'wav', 'ogg'].includes(type.toLowerCase())
	}

	// OSLMS-CUSTOM: explicit image check so non-images are not rendered as <img>
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
