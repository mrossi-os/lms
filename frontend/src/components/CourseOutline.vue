<template>
	<div class="card rounded-lg">
		<div
			class="flex items-center justify-between space-x-2 mb-2 p-2"
			v-if="!hideHeader && title && (outline.data?.length || allowEdit)"
			:class="{
				'sticky top-0 z-10 main-page-header border-b px-3 py-2.5 sm:px-5 rounded-t-lg':
					allowEdit,
			}"
		>
			<div
				class="font-semibold text-lg leading-5 text-ink-gray-9"
				:class="{ 'font-medium text-p-base': allowEdit }"
			>
				{{ __(title) }}
			</div>
			<Button size="sm" v-if="allowEdit" @click="openChapterModal()">
				<template #prefix>
					<Plus class="size-4 stroke-1.5" />
				</template>
				{{ __('Add') }}
			</Button>
		</div>
		<div
			v-if="allowEdit && outline.data && !outline.data.length"
			class="flex flex-col items-center justify-center gap-3 px-6 py-16 text-center text-ink-gray-5 h-full"
		>
			<BookOpen class="size-8 stroke-1.5" />
			<div class="text-sm">{{ __('No chapters yet') }}</div>
			<Button @click="openChapterModal()">
				<template #prefix>
					<Plus class="size-4 stroke-1.5" />
				</template>
				{{ __('Create chapter') }}
			</Button>
		</div>
		<div
			v-else
			:class="{
				'border-2 rounded-md py-2 px-2': showOutline && outline.data?.length,
			}"
		>
			<Draggable
				:list="outline.data"
				:disabled="!allowEdit"
				item-key="name"
				group="chapters"
				@end="updateChapterOrder"
			>
				<template #item="{ element: chapter, index }">
					<div class="chapter-item">
						<Disclosure
							v-slot="{ open }"
							:key="chapter.name"
							:defaultOpen="openChapterDetail(chapter.idx)"
						>
							<DisclosureButton
								ref=""
								class="flex items-center w-full p-2 group"
							>
								<ChevronRight
									:class="{
										'rotate-90': open,
										'rtl:rotate-180': !open,
										hidden: chapter.is_scorm_package,
										open: index == 1,
									}"
									class="h-4 w-4 text-ink-gray-9 stroke-1 transform duration-200"
								/>
								<div
									class="text-base text-start text-ink-gray-9 font-medium leading-5 ms-2"
									@click="redirectToChapter(chapter)"
								>
									{{ chapter.title }}
								</div>
								<div class="flex ms-auto gap-x-4">
									<Tooltip :text="__('Edit Chapter')" placement="bottom">
										<FilePenLine
											v-if="allowEdit"
											@click.prevent="openChapterModal(chapter)"
											class="h-4 w-4 text-ink-gray-9 invisible group-hover:visible"
										/>
									</Tooltip>
									<Tooltip :text="__('Delete Chapter')" placement="bottom">
										<Trash2
											v-if="allowEdit"
											@click.prevent="trashChapter(chapter.name)"
											class="h-4 w-4 text-ink-red-3 invisible group-hover:visible"
										/>
									</Tooltip>
								</div>
								<Check
									v-if="
										chapter.is_scorm_package && isScormChapterComplete(chapter)
									"
									class="h-4 w-4 text-ink-green-3"
								/>
							</DisclosureButton>
							<DisclosurePanel v-if="!chapter.is_scorm_package">
								<Draggable
									v-if="!chapter.is_scorm_package"
									:list="chapter.lessons"
									:disabled="!allowEdit"
									item-key="name"
									group="items"
									@end="updateOutline"
									:data-chapter="chapter.name"
								>
									<template #item="{ element: lesson }">
										<div
											class="outline-lesson pl-8 py-2 pr-4 text-ink-gray-9 flex flex-col gap-0.5"
											:class="
												isActiveLesson(lesson.number) ? 'bg-surface-gray-3' : ''
											"
										>
											<router-link
												:to="{
													name: allowEdit ? 'LessonForm' : 'Lesson',
													params: {
														courseName: courseName,
														chapterNumber: lesson.number.split('-')[0],
														lessonNumber: lesson.number.split('-')[1],
													},
												}"
											>
												<div class="flex items-center text-sm leading-5 group">
													<Tooltip
														v-if="lesson.is_complete"
														:text="__('Lesson completed')"
														placement="top"
													>
														<Check class="h-4 w-4 text-ink-green-3 mr-2" />
													</Tooltip>
													<MonitorPlay
														v-else-if="lesson.icon === 'icon-youtube'"
														class="h-4 w-4 stroke-1 mr-2"
													/>
													<HelpCircle
														v-else-if="lesson.icon === 'icon-quiz'"
														class="h-4 w-4 stroke-1 me-2"
													/>
													<NotebookPen
														v-else-if="lesson.icon === 'icon-assignment'"
														class="h-4 w-4 stroke-1 me-2"
													/>
													<SquareCode
														v-else-if="lesson.icon === 'icon-code'"
														class="h-4 w-4 stroke-1 me-2"
													/>
													<FileText
														v-else-if="lesson.icon === 'icon-list'"
														class="h-4 w-4 text-ink-gray-9 stroke-1 me-2"
													/>
													<div class="flex grow justify-between">
														{{ lesson.title }}
														<CourseTagBadges
															v-if="lesson.tags"
															:tags="lesson.tags"
															size="xs"
															class=""
														/>
													</div>
													<div class="flex items-center ml-auto space-x-2">
														<LessonAIStatus v-if="allowEdit" :lesson="lesson" />
														<Trash2
															v-if="allowEdit"
															@click.prevent="
																trashLesson(lesson.name, chapter.name)
															"
															class="h-4 w-4 text-ink-red-3 invisible group-hover:visible"
														/>
													</div>
												</div>
											</router-link>
										</div>
									</template>
								</Draggable>
								<div v-if="allowEdit" class="flex mt-2 mb-4 ps-8">
									<router-link
										v-if="!chapter.is_scorm_package"
										:to="{
											name: 'LessonForm',
											params: {
												courseName: courseName,
												chapterNumber: chapter.idx,
												lessonNumber: chapter.lessons.length + 1,
											},
										}"
									>
										<Button>
											{{ __('Add Lesson') }}
										</Button>
									</router-link>
								</div>
							</DisclosurePanel>
						</Disclosure>
					</div>
				</template>
			</Draggable>
			<div
				v-if="!outline.loading && !outline.data?.length"
				class="text-ink-gray-5 text-sm text-center py-6"
			>
				{{ __('No content available yet.') }}
			</div>
		</div>
	</div>
	<ChapterModal
		v-if="user.data"
		v-model="showChapterModal"
		v-model:outline="outline"
		:course="courseName"
		:chapterDetail="currentChapter"
	/>
	<LessonModal
		v-if="user.data && lessonContext"
		v-model:show="showLessonModal"
		:course="courseName"
		:chapterName="lessonContext.chapterName"
		:lessonIdx="lessonContext.lessonIdx"
		:lessonDetail="lessonContext.lessonDetail"
		@created="onLessonCreated"
		@updated="onLessonUpdated"
	/>
</template>
<script setup>
import { Button, createResource, Tooltip, toast } from 'frappe-ui'
import {
	getCurrentInstance,
	inject,
	onBeforeUnmount,
	onMounted,
	ref,
	watch,
} from 'vue'
import Draggable from 'vuedraggable'
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/vue'
import {
	Check,
	ChevronRight,
	FileText,
	FilePenLine,
	HelpCircle,
	MonitorPlay,
	NotebookPen,
	Plus,
	SquareCode,
	Trash2,
	Notebook,
} from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import ChapterModal from '@/components/Modals/ChapterModal.vue'
import LessonAIStatus from '@/oslms/components/ai/Course/LessonAIStatus.vue'
import CourseTagBadges from '@/oslms/components/CourseTagBadges.vue'

interface DraggableEvent {
	item: { __draggable_context: { element: OutlineChapter | OutlineLesson } }
	from: { dataset: { chapter: string } }
	to: { dataset: { chapter: string } }
	newIndex: number
}

interface DialogAction {
	label: string
	theme?: string
	variant?: string
	onClick: (close: () => void) => void
}
type DialogFn = (opts: {
	title: string
	message: string
	actions: DialogAction[]
}) => void

import { getCurrentInstance } from 'vue'
const user = inject<SessionUser>('$user')!
const router = useRouter()
const user = inject('$user')
const socket = inject('$socket')
const showChapterModal = ref(false)
const currentChapter = ref(null)
const app = getCurrentInstance()
const { $dialog } = app.appContext.config.globalProperties

const emit = defineEmits<{
	'select-lesson': [{ chapterNumber: string; lessonNumber: string }]
}>()

interface LessonModalContext {
	chapterName: string
	chapterIdx: number
	lessonIdx: number
	lessonDetail: {
		name?: string
		title?: string
		include_in_preview?: boolean | 0 | 1
	} | null
}

const showLessonModal = ref<boolean>(false)
const lessonContext = ref<LessonModalContext | null>(null)

function openLessonModalForAdd(payload: {
	chapter: OutlineChapter
	lessonIdx: number
}) {
	lessonContext.value = {
		chapterName: payload.chapter.name,
		chapterIdx: payload.chapter.idx,
		lessonIdx: payload.lessonIdx,
		lessonDetail: null,
	}
	showLessonModal.value = true
}

function openLessonModalForEdit(payload: {
	chapter: OutlineChapter
	lesson: OutlineLesson
}) {
	lessonContext.value = {
		chapterName: payload.chapter.name,
		chapterIdx: payload.chapter.idx,
		lessonIdx: Number(payload.lesson.number.split('-')[1]) || 1,
		lessonDetail: {
			name: payload.lesson.name,
			title: payload.lesson.title,
			include_in_preview: payload.lesson.include_in_preview,
		},
	}
	showLessonModal.value = true
}

function onLessonCreated(created: { name: string; number: string }) {
	outline.reload()
	const ctx = lessonContext.value
	if (!ctx) return
	const chapterNumber = String(ctx.chapterIdx)
	const lessonNumber = created.number
	if (props.inlineSelect) {
		emit('select-lesson', { chapterNumber, lessonNumber })
		return
	}
	if (props.editorLinks) {
		router.push({
			name: 'CourseDetail',
			params: { courseName: props.courseName },
			hash: '#course editor',
			query: {
				editLesson: `${chapterNumber}-${lessonNumber}`,
				lessonMode: 'edit',
			},
		})
	}
}

function onLessonUpdated(_payload: { name: string }) {
	outline.reload()
}

const props = withDefaults(
	defineProps<{
		courseName: string
		showOutline?: boolean
		title?: string
		allowEdit?: boolean
		getProgress?: boolean
		completedLesson?: string | null
		inlineSelect?: boolean
		editorLinks?: boolean
		selectedLessonNumber?: string
		hideHeader?: boolean
	}>(),
	{
		showOutline: false,
		title: '',
		allowEdit: false,
		getProgress: false,
		inlineSelect: false,
		editorLinks: false,
		selectedLessonNumber: '',
		completedLesson: null,
		hideHeader: false,
	}
)

defineExpose({ openChapterModal })

const outline = createResource({
	url: 'lms.lms.utils.get_course_outline',
	cache: ['course_outline', props.courseName],
	makeParams() {
		return {
			course: props.courseName,
			progress: !!user.data?.name,
		}
	},
	auto: true,
}) as Resource<OutlineChapter[] | null>

watch(
	() => props.courseName,
	() => {
		outline.reload()
	},
)

watch(
	() => props.completedLesson,
	(lessonName) => {
		if (!lessonName || !outline.data) return
		for (const chapter of outline.data) {
			const found = chapter.lessons?.find((l) => l.name === lessonName)
			if (found) {
				found.is_complete = true
				break
			}
		}
	},
)

const onLessonProgressUpdate = (data) => {
	if (data?.course === props.courseName) {
		outline.reload()
	}
}

onMounted(() => {
	socket?.on('update_lesson_progress', onLessonProgressUpdate)
})

onBeforeUnmount(() => {
	socket?.off('update_lesson_progress', onLessonProgressUpdate)
})

const deleteLesson = createResource({
	url: 'lms.lms.api.delete_lesson',
	makeParams(values: { lesson: string; chapter: string }) {
		return values
	},
	onSuccess() {
		outline.reload()
		toast.success(__('Lesson deleted successfully'))
	},
})

const updateLessonIndex = createResource({
	url: 'lms.lms.api.update_lesson_index',
	makeParams(values: {
		lesson: string
		sourceChapter: string
		targetChapter: string
		idx: number
	}) {
		return values
	},
	onSuccess() {
		toast.success(__('Lesson moved successfully'))
	},
})

const updateChapterIndex = createResource({
	url: 'lms.lms.api.update_chapter_index',
	makeParams(values: { chapter: string; course: string; idx: number }) {
		return values
	},
	onSuccess() {
		toast.success(__('Chapter moved successfully'))
	},
})

const deleteChapter = createResource({
	url: 'lms.lms.api.delete_chapter',
	makeParams(values: { chapter: string }) {
		return values
	},
	onSuccess() {
		outline.reload()
		toast.success(__('Chapter deleted successfully'))
	},
})

function trashLesson(lessonName: string, chapterName: string) {
	$dialog({
		title: __('Delete this lesson?'),
		message: __(
			'Deleting this lesson will permanently remove it from the course. This action cannot be undone. Are you sure you want to continue?',
		),
		actions: [
			{
				label: __('Delete'),
				theme: 'red',
				variant: 'solid',
				onClick(close) {
					deleteLesson.submit({ lesson: lessonName, chapter: chapterName })
					close()
				},
			},
		],
	})
}

function trashChapter(chapterName: string) {
	$dialog({
		title: __('Delete this chapter?'),
		message: __(
			'Deleting this chapter will also delete all its lessons and permanently remove it from the course. This action cannot be undone. Are you sure you want to continue?',
		),
		actions: [
			{
				label: __('Delete'),
				theme: 'red',
				variant: 'solid',
				onClick(close) {
					deleteChapter.submit({ chapter: chapterName })
					close()
				},
			},
		],
	})
}

function openChapterModal(chapter: OutlineChapter | null = null) {
	currentChapter.value = chapter
	showChapterModal.value = true
}

function updateOutline(e: DraggableEvent) {
	updateLessonIndex.submit({
		lesson: e.item.__draggable_context.element.name,
		sourceChapter: e.from.dataset.chapter,
		targetChapter: e.to.dataset.chapter,
		idx: e.newIndex,
	})
}

function updateChapterOrder(e: DraggableEvent) {
	updateChapterIndex.submit({
		chapter: e.item.__draggable_context.element.name,
		course: props.courseName,
		idx: e.newIndex,
	})
}
</script>
