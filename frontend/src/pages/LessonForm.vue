<template>
	<div class="py-5">
		<OsLessonForm :lesson="lesson" @dirty="markDirty" />
		<div class="mt-0">
			<div class="w-5/6 mx-auto pt-4">
				<div
					class="flex justify-between cursor-pointer"
					@click="
						() => {
							openInstructorEditor = !openInstructorEditor
						}
					"
				>
					<NotebookPen class="size-4 stroke-1.5 text-ink-gray-7" />
					<span class="text-p-base font-medium text-ink-gray-8">
						{{ __('Instructor notes') }}
					</span>
					<Badge
						variant="subtle"
						theme="gray"
						size="sm"
						:label="__('private')"
					/>
					<ChevronRight
						class="instructor-notes-chevron ms-auto size-4 stroke-2 text-ink-gray-5"
					/>
				</summary>
				<BlockEditor
					ref="instructorEditor"
					class="instructor-notes-editor border-t border-outline-gray-2 py-3"
					:uploadContext="instructorUploadContext"
					@change="markDirty"
				/>
			</details>

			<!-- Lesson content -->
			<BlockEditor
				ref="editor"
				:uploadContext="contentUploadContext"
				@change="markDirty"
			/>
		</div>
	</div>
</template>
<script setup>
import { createResource, toast } from 'frappe-ui'
import { reactive, onMounted, inject, ref, onBeforeUnmount } from 'vue'
import EditorJS from '@editorjs/editorjs'
import { ChevronRight } from 'lucide-vue-next'
import {
	getEditorTools,
	getEditorI18n,
	enablePlyr,
	sanitizeEditorJs,
} from '@/utils'
import { useOnboarding, useTelemetry } from 'frappe-ui/frappe'
import { useAiContext } from '@/stores/aiContext'
import OsLessonForm from '@/oslms/pages/OsLessonForm.vue'

const editor = ref(null)
const instructorEditor = ref(null)
const user = inject('$user')
const openInstructorEditor = ref(false)
const aiContext = useAiContext()
const { capture } = useTelemetry()
const { updateOnboardingStep } = useOnboarding('learning')

const emit = defineEmits(['saved'])

// Set true only once the initial content has finished rendering, so the
// onChange events EditorJS fires during programmatic render() don't trigger a
// spurious autosave on load.
let initialLoadComplete = false

const props = defineProps({
	courseName: {
		type: String,
		required: true,
	},
	chapterNumber: {
		type: String,
		required: true,
	},
	lessonNumber: {
		type: String,
		required: true,
	},
})

const isDirty = ref(false)

// Debounced so a burst of keystrokes collapses into a single save shortly
// after the user pauses.
const autoSave = useDebounceFn(() => {
	if (isDirty.value) saveLesson()
}, 800)

function markDirty() {
	if (!lessonDetails.data?.lesson || !initialLoadComplete) return
	isDirty.value = true
	autoSave()
}

defineExpose({
	saveLesson,
	isDirty,
	lessonHasVideo: () => lessonHasVideo.value,
	lessonName: () => lessonDetails.data?.lesson?.name,
	lessonTitle: () => lesson.title,
})

onMounted(() => {
	if (!user.data?.is_moderator && !user.data?.is_instructor) {
		window.location.href = '/login'
	}
	capture('lesson_form_opened')
	enablePlyr()
})

const renderEditor = (holder) => {
	return new EditorJS({
		holder: holder,
		tools: getEditorTools(true),
		defaultBlock: 'markdown',
		i18n: getEditorI18n(),
		onChange: async (api, event) => {
			enablePlyr()
			markDirty()
		},
	})
}

const lesson = reactive({
	title: '',
	include_in_preview: false,
	body: '',
	instructor_notes: '',
	content: '',
})

const lessonHasVideo = computed(() => hasVideoContent(lesson))

const lessonDetails = createResource({
	url: 'lms.lms.utils.get_lesson_creation_details',
	params: {
		course: props.courseName,
		chapter: props.chapterNumber,
		lesson: props.lessonNumber,
	},
	auto: true,
	onSuccess(data) {
		if (data.lesson) {
			Object.keys(data.lesson).forEach((key) => {
				lesson[key] = data.lesson[key]
			})
			lesson.include_in_preview = data?.lesson?.include_in_preview
				? true
				: false
			if (data.lesson.name) aiContext.setLesson(data.lesson.name)
			addLessonContent(data)
			addInstructorNotes(data)
			enableAutoSave()
			// Initial population isn't user input.
			isDirty.value = false
		}
	},
})

const addLessonContent = (data) => {
	// Return the render promise so callers (autosave arming, autofocus) wait for
	// the blocks to actually be in the DOM, not just for render() to be called.
	return editor.value.isReady().then(() => {
		if (data.lesson.content) {
			return editor.value.render(
				sanitizeEditorJs(JSON.parse(data.lesson.content))
			)
		} else if (data.lesson.body) {
			let blocks = convertToJSON(data.lesson)
			return editor.value.render({
				blocks: blocks,
			})
		}
	})
}

const addInstructorNotes = (data) => {
	return instructorEditor.value.isReady().then(() => {
		if (data.lesson.instructor_content) {
			instructorEditor.value.render(
				sanitizeEditorJs(JSON.parse(data.lesson.instructor_content)),
			)
		} else if (data.lesson.instructor_notes) {
			let blocks = convertToJSON(data.lesson)
			return instructorEditor.value.render({
				blocks: blocks,
			})
		}
	})
}

const enableAutoSave = () => {
	autoSaveInterval = setInterval(() => {
		// Only autosave when there are unsaved edits — otherwise we keep POSTing
		// the whole document every 10s while the header shows "No changes to save".
		if (isDirty.value) saveLesson({ showSuccessMessage: false })
	}, 10000)
}

const keyboardShortcut = (e) => {
	if (
		e.key === 's' &&
		(e.ctrlKey || e.metaKey) &&
		!e.target.classList.contains('ProseMirror')
	) {
		saveLesson({ showSuccessMessage: true })
		e.preventDefault()
	}
}

onBeforeUnmount(() => {
	// Best-effort flush of any unsaved edits before the editors are destroyed.
	if (isDirty.value) saveLesson()
})

const newLessonResource = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Course Lesson',
				course: props.courseName,
				chapter: lessonDetails.data?.chapter.name,
				...lesson,
			},
		}
	},
})

// Fields the editor is allowed to write. Server-managed fields like
// index_status/indexed_at (AI ingestion) must NOT be echoed back, otherwise
// every save/autosave overwrites them with the values loaded at form open.
const EDITABLE_LESSON_FIELDS = [
	'title',
	'include_in_preview',
	'body',
	'instructor_notes',
	'content',
	'instructor_content',
	'duration',
	'tags',
]

const editLesson = createResource({
	url: 'frappe.client.set_value',
	makeParams(values) {
		const fieldname = {}
		for (const key of EDITABLE_LESSON_FIELDS) {
			if (key in lesson) fieldname[key] = lesson[key]
		}
		return {
			doctype: 'Course Lesson',
			name: values.lesson,
			fieldname,
		}
	},
})

const lessonReference = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'Lesson Reference',
				parent: lessonDetails.data?.chapter.name,
				parenttype: 'Course Chapter',
				parentfield: 'lessons',
				lesson: values.lesson,
				idx: props.lessonNumber,
			},
		}
	},
})

const convertToJSON = (lessonData) => {
	let blocks = []
	// A lesson can carry the same video in BOTH the `youtube` field and a
	// `{{ YouTubeVideo }}` body macro. Without de-duping we'd emit two embed
	// blocks for one video — the symptom being a stuck preloader above a second
	// player. Key on the video id so each video renders exactly once.
	const seenYoutube = new Set()
	const youtubeKey = (url) => url.split('/').pop().split('?')[0]
	const pushYoutube = (embedUrl) => {
		const key = youtubeKey(embedUrl)
		if (seenYoutube.has(key)) return
		seenYoutube.add(key)
		blocks.push({
			type: 'embed',
			data: { service: 'youtube', embed: embedUrl },
		})
	}
	if (lessonData.youtube) {
		let youtubeID = lessonData.youtube.split('/').pop()
		pushYoutube(`https://www.youtube.com/embed/${youtubeID}`)
	}
	lessonData.body.split('\n').forEach((block) => {
		if (block.includes('{{ YouTubeVideo')) {
			let youtubeID = block.match(/\(["']([^"']+?)["']\)/)[1]
			if (!youtubeID.includes('https://'))
				youtubeID = `https://www.youtube.com/embed/${youtubeID}`
			pushYoutube(youtubeID)
		} else if (block.includes('{{ Quiz')) {
			let quiz = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'quiz',
				data: {
					quiz: quiz,
				},
			})
		} else if (block.includes('{{ Video')) {
			let video = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'upload',
				data: {
					file_url: video,
					file_type: video.split('.').pop(),
				},
			})
		} else if (block.includes('{{ Audio')) {
			let audio = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'upload',
				data: {
					file_url: audio,
					file_type: audio.split('.').pop(),
				},
			})
		} else if (block.includes('{{ PDF')) {
			let pdf = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'upload',
				data: {
					file_url: pdf,
					file_type: 'pdf',
				},
			})
		} else if (block.includes('{{ Embed')) {
			let embed = block.match(/\(["']([^"']+?)["']\)/)[1]
			blocks.push({
				type: 'embed',
				data: {
					service: embed.split('|||')[0],
					embed: embed.split('|||')[1],
				},
			})
		} else if (block.includes('![]')) {
			let image = block.match(/\((.*?)\)/)[1]
			blocks.push({
				type: 'upload',
				data: {
					file_url: image,
					file_type: 'image',
				},
			})
		} else if (block.includes('#')) {
			let level = (block.match(/#/g) || []).length
			blocks.push({
				type: 'header',
				data: {
					text: block.replace(/#/g, '').trim(),
					level: level,
				},
			})
		} else {
			blocks.push({
				type: 'paragraph',
				data: {
					text: block,
				},
			})
		}
	})

	if (lessonData.quizId) {
		blocks.push({
			type: 'quiz',
			data: {
				quiz: lessonData.quizId,
			},
		})
	}

	return blocks
}

function saveLesson() {
	// The debounced autosave can fire as the component tears down; bail if the
	// editors are already gone.
	if (!editor.value || !instructorEditor.value) return
	editor.value.save().then((outputData) => {
		outputData = removeEmptyBlocks(outputData)
		const bodyHasContent = hasEditorContent(outputData)
		if (shouldSkipLessonSave(lesson.title, bodyHasContent)) return
		// Only overwrite stored content when the body has real content. A
		// transient/empty editor (hot-reload remount, render race, mid
		// lesson-switch) serialises to just an empty paragraph and must not wipe
		// what's saved.
		if (bodyHasContent) {
			lesson.content = JSON.stringify(outputData)
		}
		instructorEditor.value.save().then((outputData) => {
			outputData = removeEmptyBlocks(outputData)
			lesson.instructor_content = JSON.stringify(outputData)
			// instructor_content is now the source of truth; clear the legacy
			// instructor_notes field so removed notes don't reappear on the
			// lesson page via the fallback render path.
			lesson.instructor_notes = ''
			if (lessonDetails.data?.lesson) {
				editCurrentLesson()
			} else {
				createNewLesson()
			}
		})
	})
}

const removeEmptyBlocks = (outputData) => {
	let blocks = outputData.blocks.filter((block) => {
		return Object.keys(block.data).length > 0 || block.type == 'paragraph'
	})
	outputData.blocks = blocks
	return outputData
}

const createNewLesson = () => {
	newLessonResource.submit(
		{},
		{
			validate() {
				return validateLesson()
			},
			onSuccess(data) {
				lessonReference.submit(
					{ lesson: data.name },
					{
						onSuccess() {
							if (user.data?.is_system_manager)
								updateOnboardingStep('create_first_lesson')

							capture('lesson_created')
							toast.success(__('Lesson created successfully'))
							isDirty.value = false
							emit('saved', { isNew: true })
							lessonDetails.reload()
						},
					},
				)
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		},
	)
}

const editCurrentLesson = () => {
	editLesson.submit(
		{
			lesson: lessonDetails.data.lesson.name,
		},
		{
			validate() {
				return validateLesson()
			},
			onSuccess() {
				isDirty.value = false
				emit('saved', {
					name: lessonDetails.data.lesson.name,
					title: lesson.title,
					include_in_preview: lesson.include_in_preview,
					isNew: false,
				})
			},
			onError(err) {
				toast.error(err.message)
			},
		},
	)
}

const validateLesson = () => {
	if (!lesson.title) {
		return 'Title is required'
	}
}
</script>
<style>
/* Native <details> disclosure: drop the default marker triangle and drive the
   chevron rotation off the [open] state instead of a JS toggle. */
.instructor-notes > summary {
	list-style: none;
}
.instructor-notes > summary::-webkit-details-marker {
	display: none;
}
.instructor-notes-chevron {
	transition: transform 200ms;
}
.instructor-notes[open] .instructor-notes-chevron {
	transform: rotate(90deg);
}
[dir='rtl'] .instructor-notes:not([open]) .instructor-notes-chevron {
	transform: rotate(180deg);
}

/* Indent the instructor-notes editor so EditorJS's block controls (the +
   add button and drag handle, which live in the left gutter and span ~70px)
   sit fully inside the bordered card instead of spilling into the page
   margin. Scoped so the full-width content editor is unaffected. */
.instructor-notes-editor .ce-block__content,
.instructor-notes-editor .ce-toolbar__content {
	margin-inline-start: 4.5rem;
}

/* Both editors are .codex-editor siblings with z-index: 1, so the content
   editor (later in the DOM) paints over the instructor editor's popovers —
   the popover's z-index: 4 is trapped inside its editor's stacking context.
   Lift the instructor editor one level so its + menu renders on top. */
.instructor-notes-editor .codex-editor {
	z-index: 2;
}
</style>
