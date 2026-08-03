import QuizBlock from '@/components/QuizBlock.vue'
import AssessmentPlugin from '@/components/AssessmentPlugin.vue'
import { createApp, h } from 'vue'
import { call } from 'frappe-ui'
import { usersStore } from '../stores/user'
import translationPlugin from '../translation'
import { CircleHelp } from 'lucide-vue-next'
import router from '@/router'

export class Quiz {
	constructor({ data, api, readOnly }) {
		this.data = data
		this.readOnly = readOnly
	}

	static get toolbox() {
		const app = createApp({
			render: () => h(CircleHelp, { size: 5, strokeWidth: 1.5 }),
		})

		const div = document.createElement('div')
		app.mount(div)

		return {
			title: __('Quiz'),
			icon: div.innerHTML,
		}
	}

	static get isReadOnlySupported() {
		return true
	}

	render() {
		this.wrapper = document.createElement('div')
		if (Object.keys(this.data).length) {
			this.renderQuiz(this.data.quiz)
		} else {
			this.renderQuizModal()
		}
		return this.wrapper
	}

	renderQuiz(quiz) {
		if (this.readOnly) {
			// Mount the quiz inline instead of loading the whole SPA in an iframe
			// (which flashed the app shell/sidebar before the quiz appeared). It's
			// a standalone mount — EditorJS blocks live outside the app's Vue tree —
			// so give it translation and the shared $user the quiz component needs.
			const { userResource } = usersStore()
			this.quizApp = createApp(QuizBlock, { quiz })
			this.quizApp.use(translationPlugin)
			this.quizApp.provide('$user', userResource)
			// Contain quiz render/runtime errors to this mount. Inline (unlike
			// the old iframe) the quiz shares the lesson's render tree, so an
			// uncaught error here would otherwise propagate through EditorJS and
			// blank the whole lesson.
			this.quizApp.config.errorHandler = (err) => {
				console.error('[lms] in-lesson quiz failed to render', err)
			}
			this.quizApp.mount(this.wrapper)
			return
		}
		// `quiz` is the link value (e.g. "untitled-quiz-5"), which says nothing to
		// the author — show the docname only until the title comes back.
		this.renderQuizPlaceholder(quiz)
		call('frappe.client.get_value', {
			doctype: 'LMS Quiz',
			filters: {
				name: quiz,
			},
			fieldname: ['title'],
		}).then((data) => {
			this.renderQuizPlaceholder(data?.title || quiz)
		})
		return
	}

	// Built up with textContent instead of an innerHTML template so a quiz title
	// can't inject markup into the lesson editor.
	renderQuizPlaceholder(label) {
		const box = document.createElement('div')
		box.className =
			'border rounded-md p-4 text-center bg-surface-sidebar mb-4'
		const text = document.createElement('span')
		text.className = 'font-medium'
		text.textContent = `${__('Quiz')}: ${label}`
		box.appendChild(text)
		this.wrapper.replaceChildren(box)
	}

	// Tear down the inline quiz app when EditorJS removes the block so the mount
	// doesn't leak after the lesson view is destroyed.
	destroy() {
		this.quizApp?.unmount()
	}

	renderQuizModal() {
		if (this.readOnly) {
			return
		}
		const app = createApp(AssessmentPlugin, {
			type: 'quiz',
			onAddition: (quiz) => {
				this.data.quiz = quiz
				this.renderQuiz(quiz)
			},
		})
		app.use(translationPlugin)
		app.use(router)
		app.mount(this.wrapper)
	}

	save() {
		if (Object.keys(this.data).length === 0) return {}
		return {
			quiz: this.data.quiz,
		}
	}
}
