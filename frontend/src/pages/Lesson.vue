<template>
	<div v-if="lesson.data" class="">
		<header
			class="sticky top-0 z-10 flex items-center justify-between border-b main-page-header px-3 py-2.5 sm:px-5"
		>
			<Breadcrumbs class="h-7" :items="breadcrumbs" />
			<div
				class="hidden md:flex fixed top-3 z-11 items-center right-3 space-x-2"
			>
				<Tooltip v-if="canGoZen()" :text="__('Zen Mode')">
					<Button size="sm" @click="goFullScreen()">
						<template #icon>
							<Focus class="w-3.5 h-3.5 stroke-2" />
						</template>
					</Button>
				</Tooltip>
				<Button size="sm" v-if="isAdmin" @click="showVideoStats()">
					<template #icon>
						<TrendingUp class="size-3.5 stroke-1.5" />
					</template>
				</Button>
				<CertificationLinks :courseName="courseName" />
				<Button size="sm" v-if="lesson.data.prev" @click="switchLesson('prev')">
					<template #prefix>
						<ChevronLeft class="w-3.5 h-3.5 stroke-1" />
					</template>
					<span class="text-xs sm:text-sm">
						{{ __('Previous') }}
					</span>
				</Button>

				<router-link
					v-if="allowEdit()"
					:to="{
						name: 'LessonForm',
						params: {
							courseName: courseName,
							chapterNumber: props.chapterNumber,
							lessonNumber: props.lessonNumber,
						},
					}"
				>
					<Button size="sm">
						<span class="text-xs sm:text-sm">{{ __('Edit') }}</span>
					</Button>
				</router-link>

				<Button
					size="sm"
					v-if="lesson.data.next"
					@click="switchLesson('next')"
					:disabled="lessonBlocked"
				>
					<template #suffix>
						<ChevronRight class="w-3.5 h-3.5 stroke-1" />
					</template>
					<span class="text-xs sm:text-sm">{{ __('Next') }}</span>
				</Button>

				<router-link
					v-else
					:to="{
						name: 'CourseDetail',
						params: { courseName: courseName },
					}"
				>
					<Button size="sm">
						<span class="text-xs sm:text-sm">{{ __('Back to Course') }}</span>
					</Button>
				</router-link>
			</div>
			<div class="flex md:hidden items-center space-x-2">
				<CertificationLinks :courseName="courseName" />
				<Dropdown :options="mobileHeaderMenu" side="left">
					<Button size="sm">
						<template #icon>
							<MoreVertical class="w-4 h-4 stroke-1.5" />
						</template>
					</Button>
				</Dropdown>
			</div>
		</header>
		<div class="grid md:grid-cols-[70%,30%] md:h-[94vh]">
			<div v-if="lesson.data.no_preview" class="border-r">
				<div class="shadow rounded-md w-3/4 mt-10 mx-auto text-center p-4">
					<div class="flex items-center justify-center mt-4 space-x-2">
						<LockKeyholeIcon class="size-4 stroke-2 text-ink-gray-5" />
						<div class="text-lg font-semibold text-ink-gray-7">
							{{ __('This lesson is locked') }}
						</div>
					</div>
					<div class="mt-1 mb-4 text-ink-gray-7">
						{{
							__(
								'This lesson is not available for preview. Please enroll in the course to access it.',
							)
						}}
					</div>
					<Button
						v-if="user.data && !lesson.data.disable_self_learning"
						@click="enrollStudent()"
						variant="solid"
					>
						{{ __('Start Learning') }}
					</Button>
					<Badge
						theme="blue"
						size="lg"
						v-else-if="lesson.data.disable_self_learning"
						class="mt-2"
					>
						{{ __('Contact the Administrator to enroll for this course.') }}
					</Badge>
					<Button v-else @click="redirectToLogin()">
						<template #prefix>
							<LogIn class="w-4 h-4 stroke-1" />
						</template>
						{{ __('Login') }}
					</Button>
				</div>
			</div>
			<div
				v-else
				ref="lessonContainer"
				class="bg-surface-white overflow-y-auto"
				:class="{
					'overflow-y-auto': zenModeEnabled,
				}"
			>
				<div
					class="border-r pt-5 pb-10 h-full"
					:class="{
						'w-full md:w-3/5 mx-auto border-none !pt-10': zenModeEnabled,
					}"
				>
					<div class="px-5">
						<!-- Titolo e instructors sempre visibili -->
						<div
							class="flex flex-col space-y-3 md:space-y-0 md:flex-row md:items-center justify-between"
						>
							<div class="flex flex-col">
								<div class="text-3xl font-semibold text-ink-gray-9">
									{{ lesson.data.title }}
								</div>
								<CourseTagBadges
									v-if="lesson.data.tags"
									:tags="lesson.data.tags"
									size="xs"
									class="mt-2"
								/>

								<div
									v-if="zenModeEnabled"
									class="relative flex items-center space-x-2 text-sm mt-1 text-ink-gray-7 group w-fit mt-2"
								>
									<span>
										{{ lesson.data.chapter_title }} -
										{{ lesson.data.course_title }}
									</span>
									<Info class="size-3" />
									<div
										class="hidden group-hover:block rounded bg-gray-900 px-2 py-1 text-xs text-white shadow-xl absolute left-0 top-full mt-2"
									>
										{{ Math.ceil(lesson.data.membership.progress) }}%
										{{ __('completed') }}
									</div>
								</div>
							</div>

							<div
								v-if="zenModeEnabled"
								class="flex items-center space-x-2 mt-2 md:mt-0"
							>
								<Button @click="showDiscussionsInZenMode()">
									<template #icon>
										<MessageCircleQuestion class="w-4 h-4 stroke-1.5" />
									</template>
								</Button>
								<Button v-if="lesson.data.prev" @click="switchLesson('prev')">
									<template #prefix>
										<ChevronLeft class="w-4 h-4 stroke-1" />
									</template>
									<span>
										{{ __('Previous') }}
									</span>
								</Button>

								<router-link
									v-if="allowEdit()"
									:to="{
										name: 'LessonForm',
										params: {
											courseName: courseName,
											chapterNumber: props.chapterNumber,
											lessonNumber: props.lessonNumber,
										},
									}"
								>
									<Button>
										{{ __('Edit') }}
									</Button>
								</router-link>

								<Button
									v-if="lesson.data.next"
									@click="switchLesson('next')"
									:disabled="lessonBlocked"
								>
									<template #suffix>
										<ChevronRight class="w-4 h-4 stroke-1" />
									</template>
									<span>
										{{ __('Next') }}
									</span>
								</Button>

								<router-link
									v-else
									:to="{
										name: 'CourseDetail',
										params: { courseName: courseName },
									}"
								>
									<Button>
										{{ __('Back to Course') }}
									</Button>
								</router-link>
							</div>
						</div>

						<div
							v-if="
								!zenModeEnabled &&
								(user.data?.is_moderator || user.data?.is_instructor)
							"
							class="flex items-center mt-4 md:mt-2"
						>
							<span
								class="h-6 mr-1"
								:class="{
									'avatar-group overlap': lesson.data.instructors?.length > 1,
								}"
							>
								<UserAvatar
									v-for="instructor in lesson.data.instructors"
									:user="instructor"
								/>
							</span>
							<CourseInstructors
								v-if="lesson.data?.instructors"
								:instructors="lesson.data.instructors"
							/>
						</div>

						<!-- STATO BLOCCATO LEZIONE -->
						<div
							v-if="lessonBlocked"
							class="flex flex-col items-center justify-center mt-16 text-center"
						>
							<LockKeyholeIcon class="size-12 stroke-1 text-ink-gray-4 mb-4" />
							<div class="text-lg font-semibold text-ink-gray-7 mb-2">
								{{ __('Lezione bloccata') }}
							</div>
							<div class="text-base text-ink-gray-5 max-w-sm leading-6">
								{{ blockedReason }}
							</div>
						</div>

						<!-- CONTENUTO NORMALE: visibile solo se lezione non bloccata -->
						<template v-else>
							<div
								v-if="
									lesson.data.instructor_content &&
									JSON.parse(lesson.data.instructor_content)?.blocks?.length >
										1 &&
									allowInstructorContent()
								"
								class="bg-surface-gray-2 p-3 rounded-md mt-6"
							>
								<div class="text-ink-gray-5 font-medium">
									{{ __('Instructor Notes') }}
								</div>
								<div
									id="instructor-content"
									class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal"
								></div>
							</div>
							<div
								v-else-if="lesson.data.instructor_notes"
								class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal mt-8"
							>
								<LessonContent :content="lesson.data.instructor_notes" />
							</div>

							<!-- Contenuto EditorJS: può contenere quiz -->
							<div
								v-if="lesson.data.content"
								@mouseup="toggleInlineMenu"
								class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal mt-8"
							>
								<!-- Se il contenuto ha un quiz e il quiz è bloccato, mostra il blocco -->
								<div
									v-if="quizBlocked && contentHasQuiz"
									class="flex flex-col items-center justify-center mt-8 mb-8 text-center"
								>
									<LockKeyholeIcon
										class="size-12 stroke-1 text-ink-gray-4 mb-4"
									/>
									<div class="text-lg font-semibold text-ink-gray-7 mb-2">
										{{ __('Quiz bloccato') }}
									</div>
									<div class="text-base text-ink-gray-5 max-w-sm leading-6">
										{{ quizBlockedReason }}
									</div>
								</div>
								<!-- Altrimenti mostra il contenuto normale -->
								<div v-else id="editor"></div>
							</div>

							<!-- Contenuto body (markdown/LessonContent) -->
							<div
								v-else
								class="ProseMirror prose prose-table:table-fixed prose-td:p-2 prose-th:p-2 prose-td:border prose-th:border prose-td:border-outline-gray-2 prose-th:border-outline-gray-2 prose-td:relative prose-th:relative prose-th:bg-surface-gray-2 prose-sm max-w-none !whitespace-normal mt-8"
							>
								<div
									v-if="quizBlocked && lesson.data?.quiz_id"
									class="flex flex-col items-center justify-center mt-8 mb-8 text-center"
								>
									<LockKeyholeIcon
										class="size-12 stroke-1 text-ink-gray-4 mb-4"
									/>
									<div class="text-lg font-semibold text-ink-gray-7 mb-2">
										{{ __('Quiz bloccato') }}
									</div>
									<div class="text-base text-ink-gray-5 max-w-sm leading-6">
										{{ quizBlockedReason }}
									</div>
								</div>
								<LessonContent
									v-else-if="lesson.data?.body"
									:content="lesson.data.body"
									:youtube="lesson.data.youtube"
									:quizId="lesson.data.quiz_id"
								/>
							</div>
						</template>
					</div>

					<!-- Discussioni: nascoste se bloccato -->
					<div
						v-if="
							!lessonBlocked &&
							lesson.data &&
							(allowDiscussions || tabs.length > 1)
						"
						class="mt-10 pb-20 pt-5 border-t px-5"
						ref="discussionsContainer"
					>
						<Notes
							v-if="currentTab === 'Notes'"
							:lesson="lesson.data?.name"
							v-model:notes="notes"
							@updateNotes="updateNotes"
						/>
						<!-- <Discussions
							v-else-if="allowDiscussions"
							:title="'Questions'"
							:doctype="'Course Lesson'"
							:docname="lesson.data.name"
							:key="lesson.data.name"
							:emptyStateText="
								__('Ask a question to get help from the community.')
							"
						/> -->
					</div>
				</div>
			</div>
			<div class="sticky top-10">
				<div v-if="lesson.data?.name && !hasQuiz">
					<ChatBot
						:courseId="lesson.data?.course"
						:lessonId="lesson.data?.name"
					/>
				</div>
				<div class="bg-surface-menu-bar p-5 border-b m-3 rounded-md">
					<div class="text-lg font-semibold text-ink-gray-9">
						{{ lesson.data.course_title }}
					</div>
					<div
						v-if="user && lesson.data.membership"
						class="text-sm mt-4 mb-2 text-ink-gray-5"
					>
						{{ Math.ceil(lessonProgress) }}% {{ __('completed') }}
					</div>

					<ProgressBar
						v-if="user && lesson.data.membership"
						:progress="lessonProgress"
					/>
				</div>
				<div class="m-3">
					<CourseOutline
						:courseName="courseName"
						:key="chapterNumber"
						:getProgress="lesson.data.membership ? true : false"
						:lessonProgress="lessonProgress"
					/>
				</div>
			</div>
		</div>
	</div>

	<VideoStatistics
		v-if="isAdmin"
		v-model="showStatsDialog"
		:lessonName="lesson.data?.name"
		:lessonTitle="lesson.data?.title"
	/>
</template>
<script setup>
import {
	Badge,
	Breadcrumbs,
	Button,
	call,
	createListResource,
	createResource,
	Dropdown,
	Tooltip,
	usePageMeta,
	toast,
} from 'frappe-ui'
import {
	computed,
	watch,
	inject,
	provide,
	ref,
	onMounted,
	onBeforeUnmount,
	nextTick,
} from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
	ChevronLeft,
	ChevronRight,
	LockKeyholeIcon,
	LogIn,
	Focus,
	Info,
	MessageCircleQuestion,
	MoreVertical,
	Pencil,
	ArrowLeft,
	TrendingUp,
} from 'lucide-vue-next'
import { getEditorTools, enablePlyr, highlightText } from '@/utils'
import { sessionStore } from '@/stores/session'
import { useSidebar } from '@/stores/sidebar'
import EditorJS from '@editorjs/editorjs'
import LessonContent from '@/components/LessonContent.vue'
import CourseInstructors from '@/components/CourseInstructors.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import Discussions from '@/components/Discussions.vue'
import CertificationLinks from '@/components/CertificationLinks.vue'
import VideoStatistics from '@/components/Modals/VideoStatistics.vue'
import CourseOutline from '@/components/CourseOutline.vue'
import UserAvatar from '@/components/UserAvatar.vue'
import Notes from '@/components/Notes/Notes.vue'
import { getLmsRoute } from '@/utils/basePath'
import ChatBot from '@/oslms/components/ai/ChatBot.vue'
import CourseTagBadges from '@/oslms/components/CourseTagBadges.vue'

const user = inject('$user')
const socket = inject('$socket')
const router = useRouter()
const route = useRoute()
const allowDiscussions = ref(false)
const editor = ref(null)
const instructorEditor = ref(null)
const lessonProgress = ref(0)
const lessonContainer = ref(null)
const zenModeEnabled = ref(false)
const showStatsDialog = ref(false)
const hasQuiz = ref(false)
const discussionsContainer = ref(null)
const { brand } = sessionStore()
const sidebarStore = useSidebar()
const plyrSources = ref([])
const showInlineMenu = ref(false)
const currentTab = ref(null)
const quizBlocked = ref(false)
const quizBlockedReason = ref('')

// Blocco lezioni sequenziali
const lessonBlocked = ref(false)
const blockedReason = ref('')

const tabs = ref([])

const tagResource = createResource({
	url: 'frappe.client.get_list',
	method: 'POST',
	params: {
		doctype: 'LMS OS Tag',
		fields: ['tag_name', 'color'],
		limit_page_length: 0,
	},
	auto: true,
})

const tagColorMap = computed(() => {
	if (!tagResource.data) return new Map()
	return new Map(tagResource.data.map((t) => [t.tag_name, t.color]))
})

provide('tagColorMap', tagColorMap)

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

const applyAccessFromLesson = (data) => {
	const lessonAccess = data?.lesson_access || { allowed: true }
	const quizAccess = data?.quiz_access || { allowed: true }
	lessonBlocked.value = !lessonAccess.allowed
	blockedReason.value = lessonAccess.reason || ''
	quizBlocked.value = !quizAccess.allowed
	quizBlockedReason.value = quizAccess.reason || ''
}

onMounted(() => {
	sidebarStore.isSidebarCollapsed = true
	document.addEventListener('fullscreenchange', attachFullscreenEvent)
	socket.on('update_lesson_progress', (data) => {
		if (data.course === props.courseName) {
			lessonProgress.value = data.progress
		}
	})
})

const attachFullscreenEvent = () => {
	if (document.fullscreenElement) {
		zenModeEnabled.value = true
		allowDiscussions.value = false
	} else {
		zenModeEnabled.value = false
		if (!hasQuiz.value) {
			allowDiscussions.value = true
		}
	}
}

onBeforeUnmount(() => {
	document.removeEventListener('fullscreenchange', attachFullscreenEvent)
	sidebarStore.isSidebarCollapsed = false
	trackVideoWatchDuration()
})

const lesson = createResource({
	url: 'lms.lms.utils.get_lesson',
	makeParams(values) {
		return {
			course: props.courseName,
			chapter: values ? values.chapter : props.chapterNumber,
			lesson: values ? values.lesson : props.lessonNumber,
		}
	},
	auto: true,
})

const setupLesson = (data) => {
	if (Object.keys(data).length === 0) {
		router.push({
			name: 'CourseDetail',
			params: { courseName: props.courseName },
		})
		return
	}
	if (data.is_scorm_package) {
		router.push({
			name: 'SCORMChapter',
			params: {
				courseName: props.courseName,
				chapterName: data.chapter_name,
			},
		})
	}
	lessonProgress.value = data.membership?.progress
	if (data.content) editor.value = renderEditor('editor', data.content)
	if (
		data.instructor_content &&
		JSON.parse(data.instructor_content)?.blocks?.length > 1
	)
		instructorEditor.value = renderEditor(
			'instructor-content',
			data.instructor_content,
		)
	editor.value?.isReady.then(async () => {
		checkIfDiscussionsAllowed()
		await nextTick()
		attachVideoEndedListeners()
	})
	checkQuiz()
}

const checkQuiz = () => {
	if (!editor.value && lesson.body) {
		const quizRegex = /\{\{ Quiz\(".*"\) \}\}/
		hasQuiz.value = quizRegex.test(lesson.body)
		if (!hasQuiz.value && !zenModeEnabled) {
			allowDiscussions.value = true
		} else {
			allowDiscussions.value = false
		}
	}
}

const renderEditor = (holder, content) => {
	if (document.getElementById(holder))
		document.getElementById(holder).innerHTML = ''
	return new EditorJS({
		holder: holder,
		tools: getEditorTools(),
		data: JSON.parse(content),
		readOnly: true,
		defaultBlock: 'embed',
	})
}

const markProgress = () => {
	if (user.data && lesson.data && !lesson.data.progress) {
		progress.submit(
			{},
			{
				onError(err) {
					console.error(err)
				},
			},
		)
	}
}

const progress = createResource({
	url: 'lms.lms.doctype.course_lesson.course_lesson.save_progress',
	makeParams() {
		return {
			lesson: lesson.data.name,
			course: props.courseName,
		}
	},
	onSuccess(data) {
		lessonProgress.value = data
	},
})

const notes = createListResource({
	doctype: 'LMS Lesson Note',
	filters: {
		lesson: lesson.data?.name,
		member: user.data?.name,
	},
	fields: ['name', 'color', 'highlighted_text', 'note'],
	cache: ['notes', lesson.data?.name, user.data?.name],
	onSuccess(data) {
		data.forEach((note) => {
			setTimeout(() => {
				highlightText(note)
			}, 500)
		})
	},
})

const mobileHeaderMenu = computed(() => {
	const options = []
	if (canGoZen()) {
		options.push({
			label: __('Zen Mode'),
			icon: Focus,
			onClick: () => goFullScreen(),
		})
	}
	if (isAdmin.value) {
		options.push({
			label: __('Statistiche'),
			icon: TrendingUp,
			onClick: () => showVideoStats(),
		})
	}
	if (lesson.data?.prev) {
		options.push({
			label: __('Previous'),
			icon: ChevronLeft,
			onClick: () => switchLesson('prev'),
		})
	}
	if (allowEdit()) {
		options.push({
			label: __('Edit'),
			icon: Pencil,
			onClick: () =>
				router.push({
					name: 'LessonForm',
					params: {
						courseName: props.courseName,
						chapterNumber: props.chapterNumber,
						lessonNumber: props.lessonNumber,
					},
				}),
		})
	}
	if (lesson.data?.next) {
		options.push({
			label: __('Next'),
			icon: ChevronRight,
			onClick: () => {
				if (!lessonBlocked.value) switchLesson('next')
			},
		})
	} else {
		options.push({
			label: __('Back to Course'),
			icon: ArrowLeft,
			onClick: () =>
				router.push({
					name: 'CourseDetail',
					params: { courseName: props.courseName },
				}),
		})
	}
	return options
})

const breadcrumbs = computed(() => {
	let crumbs = [{ label: __('Courses'), route: { name: 'Courses' } }]
	crumbs.push({
		label: lesson?.data?.course_title,
		route: { name: 'CourseDetail', params: { courseName: props.courseName } },
	})
	crumbs.push({
		label: lesson?.data?.title,
		route: {
			name: 'Lesson',
			params: {
				courseName: props.courseName,
				chapterNumber: props.chapterNumber,
				lessonNumber: props.lessonNumber,
			},
		},
	})
	return crumbs
})

const switchLesson = (direction) => {
	trackVideoWatchDuration()
	let lessonIndex =
		direction === 'prev'
			? lesson.data.prev.split('.')
			: lesson.data.next.split('.')

	router.push({
		name: 'Lesson',
		params: {
			courseName: props.courseName,
			chapterNumber: lessonIndex[0],
			lessonNumber: lessonIndex[1],
		},
	})
}

watch(
	[() => route.params.chapterNumber, () => route.params.lessonNumber],
	async ([newChapterNumber, newLessonNumber]) => {
		if (newChapterNumber || newLessonNumber) {
			plyrSources.value = []
			lessonBlocked.value = false
			blockedReason.value = ''
			quizBlocked.value = false
			quizBlockedReason.value = ''
			await nextTick()
			resetLessonState(newChapterNumber, newLessonNumber)
			updateNotes()
			checkIfDiscussionsAllowed()
			checkQuiz()
		}
	},
)

const resetLessonState = (newChapterNumber, newLessonNumber) => {
	editor.value = null
	instructorEditor.value = null
	allowDiscussions.value = false
	lesson.submit({
		chapter: newChapterNumber,
		lesson: newLessonNumber,
	})
}

const trackVideoWatchDuration = () => {
	if (!lesson.data.membership) return
	let videoDetails = getVideoDetails()
	videoDetails = videoDetails.concat(getPlyrSourceDetails())
	call('lms.lms.api.track_video_watch_duration', {
		lesson: lesson.data.name,
		videos: videoDetails,
	})
}

const contentHasQuiz = computed(() => {
	if (!lesson.data?.content) return false
	try {
		const parsed = JSON.parse(lesson.data.content)
		return parsed?.blocks?.some((block) => block.type === 'quiz')
	} catch {
		return false
	}
})

const getVideoDetails = () => {
	let details = []
	const videos = document.querySelectorAll('video')
	if (videos.length > 0) {
		videos.forEach((video) => {
			if (video.currentTime == video.duration) markProgress()
			details.push({
				source: video.src,
				watch_time: video.currentTime,
			})
		})
	}
	return details
}

const getPlyrSourceDetails = () => {
	let details = []
	plyrSources.value.forEach((source) => {
		if (source.currentTime == source.duration) markProgress()
		let src = cleanYouTubeUrl(source.source)
		details.push({
			source: src,
			watch_time: source.currentTime,
		})
	})
	return details
}

const cleanYouTubeUrl = (url) => {
	if (!url) return url
	const urlObj = new URL(url)
	urlObj.searchParams.delete('t')
	return urlObj.toString()
}

watch(
	() => lesson.data,
	async (data) => {
		setupLesson(data)
		await getPlyrSource()
		updateNotes()
		markProgressIfNoVideo()
		applyAccessFromLesson(data)
	},
)

const getPlyrSource = async () => {
	await nextTick()
	if (plyrSources.value.length == 0) {
		plyrSources.value = await enablePlyr()
	}
	updateVideoWatchDuration()
}

const markProgressIfNoVideo = () => {
	if (!lesson.data?.membership) return
	const hasDomVideo = document.querySelectorAll('video').length > 0
	const hasPlyr = plyrSources.value.length > 0
	if (!hasDomVideo && !hasPlyr) {
		markProgress()
	}
}

const updateVideoWatchDuration = () => {
	if (lesson.data.videos && lesson.data.videos.length > 0) {
		lesson.data.videos.forEach((video) => {
			if (video.source.includes('youtube') || video.source.includes('vimeo')) {
				updatePlyrVideoTime(video)
			} else {
				updateVideoTime(video)
			}
		})
	}
	attachVideoEndedListeners()
}

const attachVideoEndedListeners = () => {
	const onVideoEnded = () => {
		markProgress()
		trackVideoWatchDuration()
	}

	document.querySelectorAll('video').forEach((video) => {
		if (!video._lmsEndedAttached) {
			video.addEventListener('ended', onVideoEnded)
			video._lmsEndedAttached = true
		}
	})

	plyrSources.value.forEach((plyrSource) => {
		if (!plyrSource._lmsEndedAttached) {
			plyrSource.on('ended', onVideoEnded)
			plyrSource.on('statechange', (event) => {
				if (event.detail?.code === 0) onVideoEnded()
			})
			plyrSource._lmsEndedAttached = true
		}
	})
}

const updatePlyrVideoTime = (video) => {
	plyrSources.value.forEach((plyrSource) => {
		plyrSource.on('ready', () => {
			if (plyrSource.source === video.source) {
				plyrSource.embed.seekTo(video.watch_time, true)
				plyrSource.play()
				plyrSource.pause()
			}
		})
	})
}

const updateVideoTime = (video) => {
	const videos = document.querySelectorAll('video')
	if (videos.length > 0) {
		videos.forEach((vid) => {
			if (vid.src === video.source) {
				let watch_time = video.watch_time < vid.duration ? video.watch_time : 0
				if (vid.readyState >= 1) {
					vid.currentTime = watch_time
				} else {
					vid.addEventListener('loadedmetadata', () => {
						vid.currentTime = watch_time
					})
				}
			}
		})
	}
}

const checkIfDiscussionsAllowed = () => {
	hasQuiz.value = false
	JSON.parse(lesson.data?.content)?.blocks?.forEach((block) => {
		if (block.type === 'quiz') {
			hasQuiz.value = true
		}
	})

	if (
		!hasQuiz.value &&
		!zenModeEnabled.value &&
		(lesson.data?.membership ||
			user.data?.is_moderator ||
			user.data?.is_instructor)
	) {
		allowDiscussions.value = true
	} else {
		allowDiscussions.value = false
	}
}

const isAdmin = computed(() => {
	let isInstructor = lesson.data?.instructors?.includes(user.data?.name)
	return user.data?.is_moderator || isInstructor
})

const allowEdit = () => {
	if (window.read_only_mode) return false
	return isAdmin.value
}

const allowInstructorContent = () => {
	if (window.read_only_mode) return false
	return isAdmin.value
}

const enrollment = createResource({
	url: 'frappe.client.insert',
	makeParams() {
		return {
			doc: {
				doctype: 'LMS Enrollment',
				course: props.courseName,
				member: user.data?.name,
			},
		}
	},
})

const enrollStudent = () => {
	enrollment.submit(
		{},
		{
			onSuccess() {
				window.location.reload()
			},
			onError(err) {
				toast.error(__(err.messages?.[0] || err))
				console.error(err)
			},
		},
	)
}

const toggleInlineMenu = async () => {
	showInlineMenu.value = false
	return
	await nextTick()
	let selection = window.getSelection()
	if (selection.toString()) {
		showInlineMenu.value = true
	}
}

const showVideoStats = () => {
	showStatsDialog.value = true
}

const canGoZen = () => {
	if (
		user.data?.is_moderator ||
		user.data?.is_instructor ||
		user.data?.is_evaluator
	)
		return true
	if (lesson.data?.membership) return true
	return false
}

const goFullScreen = () => {
	if (lessonContainer.value.requestFullscreen) {
		lessonContainer.value.requestFullscreen()
	} else if (lessonContainer.value.mozRequestFullScreen) {
		lessonContainer.value.mozRequestFullScreen()
	} else if (lessonContainer.value.webkitRequestFullscreen) {
		lessonContainer.value.webkitRequestFullscreen()
	} else if (lessonContainer.value.msRequestFullscreen) {
		lessonContainer.value.msRequestFullscreen()
	}
}

const showDiscussionsInZenMode = () => {
	if (allowDiscussions.value) {
		allowDiscussions.value = false
	} else {
		allowDiscussions.value = true
		currentTab.value = 'Community'
		scrollDiscussionsIntoView()
	}
}

const scrollDiscussionsIntoView = () => {
	nextTick(() => {
		discussionsContainer.value?.scrollIntoView({
			behavior: 'smooth',
			block: 'center',
			inline: 'nearest',
		})
	})
}

const updateNotes = () => {
	if (!user.data) return
	notes.update({
		filters: {
			lesson: lesson.data?.name,
			member: user.data?.name,
		},
	})
	notes.reload()
}

watch(allowDiscussions, () => {
	if (!isAdmin.value) {
		if (!tabs.value.find((tab) => tab.value === 'Notes')) {
			tabs.value.push({
				label: __('Notes'),
				value: 'Notes',
			})
		}
		currentTab.value = 'Notes'
	} else {
		currentTab.value = allowDiscussions.value ? 'Community' : null
	}
	if (allowDiscussions.value) {
		if (!tabs.value.find((tab) => tab.value === 'Community')) {
			tabs.value.push({
				label: __('Community'),
				value: 'Community',
			})
		}
	}
})

const redirectToLogin = () => {
	window.location.href = `/login?redirect-to=${getLmsRoute(
		`courses/${props.courseName}`,
	)}`
}

usePageMeta(() => {
	return {
		title: lesson?.data?.title,
		icon: brand.favicon,
	}
})
</script>
<style>
.avatar-group {
	display: inline-flex;
	align-items: center;
}

.avatar-group .avatar {
	transition: margin 0.1s ease-in-out;
}

.lesson-content p {
	margin-bottom: 1rem;
	line-height: 1.7;
}

.lesson-content li {
	line-height: 1.7;
}

.lesson-content ol {
	list-style: auto;
	margin: revert;
	padding: 1rem;
}

.lesson-content ul {
	list-style: auto;
	padding: 1rem;
	margin: revert;
}

.lesson-content img {
	border: 1px solid theme('colors.gray.200');
	border-radius: 0.5rem;
}

.lesson-content code {
	display: block;
	overflow-x: auto;
	padding: 1rem 1.25rem;
	background: #011627;
	color: #d6deeb;
	border-radius: 0.5rem;
	margin: 1rem 0;
}

.lesson-content a {
	color: theme('colors.gray.900');
	text-decoration: underline;
	font-weight: 500;
}

.embed-tool__caption,
.cdx-simple-image__caption {
	display: none;
}

.ce-block__content {
	max-width: unset;
}

#editor .codex-editor__redactor,
#instructor-content .codex-editor__redactor {
	padding-bottom: 0px !important;
}

.codeBoxHolder {
	display: flex;
	flex-direction: column;
	justify-content: flex-start;
	align-items: flex-start;
}

.codeBoxTextArea {
	width: 100%;
	min-height: 30px;
	padding: 10px;
	border-radius: 2px 2px 2px 0;
	border: none !important;
	outline: none !important;
	font: 14px monospace;
}

.codeBoxSelectDiv {
	display: flex;
	flex-direction: column;
	justify-content: flex-start;
	align-items: flex-start;
	position: relative;
}

.codeBoxSelectInput {
	border-radius: 0 0 20px 2px;
	padding: 2px 26px;
	padding-top: 0;
	padding-right: 0;
	text-align: left;
	cursor: pointer;
	border: none !important;
	outline: none !important;
}

.codeBoxSelectDropIcon {
	position: absolute !important;
	left: 10px !important;
	bottom: 0 !important;
	width: unset !important;
	height: unset !important;
	font-size: 16px !important;
}

.codeBoxSelectPreview {
	display: none;
	flex-direction: column;
	justify-content: flex-start;
	align-items: flex-start;
	border-radius: 2px;
	box-shadow: 0 3px 15px -3px rgba(13, 20, 33, 0.13);
	position: absolute;
	top: 100%;
	margin: 5px 0;
	max-height: 30vh;
	overflow-x: hidden;
	overflow-y: auto;
	z-index: 10000;
}

.codeBoxSelectItem {
	width: 100%;
	padding: 5px 20px;
	margin: 0;
	cursor: pointer;
}

.codeBoxSelectItem:hover {
	opacity: 0.7;
}

.codeBoxSelectedItem {
	background-color: lightblue !important;
}

.codeBoxShow {
	display: flex !important;
}

.dark {
	color: #abb2bf;
	background-color: #282c34;
}

.light {
	color: #383a42;
	background-color: #fafafa;
}

.codeBoxTextArea {
	line-height: 1.7;
}

.tc-table {
	border-left: 1px solid #e8e8eb;
}

.plyr__volume input[type='range'] {
	display: none;
}

.plyr__control--overlaid {
	background: radial-gradient(
		circle,
		rgba(0, 0, 0, 0.4) 0%,
		rgba(0, 0, 0, 0.5) 50%
	);
}

.plyr__control:hover {
	background: none;
}

.plyr--video {
	border: 1px solid theme('colors.gray.200');
	border-radius: 8px;
}

:root {
	--plyr-range-fill-background: white;
	--plyr-video-control-background-hover: transparent;
}
</style>
