/**
 * Repro for the reported bug: "a student opens a quiz from the batch dashboard
 * and sees 'This quiz has no questions available yet.' instead of the Start
 * button; reloading the page makes the button appear."
 *
 * Quiz.vue fetches the quiz through a *cached* resource
 * (cache: ['quiz_with_questions', quizName]). frappe-ui's createResource returns
 * the SAME resource object for a repeated cache key and discards the new
 * options — so the second component instance keeps the first instance's
 * transform(), and its own `questionsByName` map stays empty. populateQuestions()
 * then filters every row out and the template falls into the "no questions" branch.
 *
 * These tests use the REAL createResource (cache included) so the assertion is
 * about production behaviour, not a stub.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

const QUIZ = 'quiz-with-3-questions'

const questionsByName = {
	q1: { name: 'q1', question: 'Q one?', type: 'Choices', multiple: 0, option_1: 'a', option_2: 'b' },
	q2: { name: 'q2', question: 'Q two?', type: 'Choices', multiple: 0, option_1: 'a', option_2: 'b' },
	q3: { name: 'q3', question: 'Q three?', type: 'Choices', multiple: 0, option_1: 'a', option_2: 'b' },
}

const quizPayload = () => ({
	quiz: {
		name: QUIZ,
		title: 'Quiz di classe',
		duration: 0,
		passing_percentage: 60,
		max_attempts: 0,
		show_answers: 0,
		shuffle_questions: 0,
		questions: [
			{ question: 'q1', marks: 1 },
			{ question: 'q2', marks: 1 },
			{ question: 'q3', marks: 1 },
		],
	},
	questions_by_name: JSON.parse(JSON.stringify(questionsByName)),
})

let fetchCount = 0

// Real resource layer (cache semantics included), stubbed UI pieces.
vi.mock('frappe-ui', async () => {
	const resources = await import(
		'../../node_modules/frappe-ui/src/resources/resources.js'
	)
	const { setConfig } = await import('../../node_modules/frappe-ui/src/utils/config')

	setConfig('resourceFetcher', async (options: any) => {
		if (options.url === 'lms.lms.utils.get_quiz_with_questions') {
			fetchCount++
			return quizPayload()
		}
		if (options.url === 'frappe.client.get_list') return []
		return null
	})

	const stub = { template: '<div><slot /></div>' }
	return {
		createResource: resources.createResource,
		Badge: stub,
		Button: { template: '<button><slot /></button>' },
		Checkbox: stub,
		Dialog: stub,
		LoadingIndicator: { template: '<div class="loading" />' },
		ListView: stub,
		TextEditor: stub,
		FormControl: stub,
		call: vi.fn(),
		toast: { warning: vi.fn(), error: vi.fn() },
	}
})

vi.mock('@/components/ProgressBar.vue', () => ({ default: { template: '<div />' } }))

// @ts-expect-error test global
window.__ = (text: string) => text
// @ts-expect-error String.format is provided by frappe's translation bootstrap
if (!String.prototype.format) {
	// eslint-disable-next-line no-extend-native
	String.prototype.format = function (...args: any[]) {
		return this.replace(/\{(\d+)\}/g, (m: string, i: number) => String(args[i] ?? m))
	}
}

const Quiz = (await import('@/components/Quiz.vue')).default

const mountQuiz = async () => {
	const wrapper = mount(Quiz, {
		props: { quizName: QUIZ },
		global: {
			provide: { $user: { data: { name: 'student@test.com', is_student: true } } },
			mocks: { __: (text: string) => text },
		},
	})
	await flushPromises()
	await flushPromises()
	return wrapper
}

describe('Quiz.vue — cached resource across remounts', () => {
	beforeEach(() => {
		fetchCount = 0
	})

	// One test: frappe-ui's resource cache is module-global, so a second `it`
	// would already start warm and hide which mount broke.
	it('keeps the questions when the same quiz is reopened in the same session', async () => {
		// First navigation to the quiz — cold cache.
		const first = await mountQuiz()
		expect(first.text()).toContain('Start')
		expect(first.text()).toContain('This quiz consists of 3 questions.')
		first.unmount()

		// Second navigation to the same quiz, no page reload in between.
		const second = await mountQuiz()
		expect(fetchCount).toBeGreaterThan(1) // the resource did refetch
		expect(second.text()).not.toContain('This quiz has no questions available yet.')
		expect(second.text()).toContain('Start')
		second.unmount()
	})
})
