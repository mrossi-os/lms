/**
 * A shared browser (classroom, family PC) must not carry one student's
 * assignment submission over to the next student.
 *
 * frappe-ui's createDocumentResource keeps every document in a per-name
 * singleton and in IndexedDB (idb-keyval), and neither is cleared on logout.
 * Assignment.vue used to bind the unsaved form to the name "new" and, after
 * the insert, renamed that same resource to the saved submission and reloaded
 * it, which stored the submission under the shared "new" key. The next student
 * opening any assignment then saw that file and status, and their Save could
 * not go through (seen on staging 2026-11-11, ASG-00810).
 *
 * The real frappe-ui document resource runs here; only IndexedDB (an in-memory
 * idb-keyval), the network (resourceFetcher) and the UI widgets are faked.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'

// frappe-ui's local cache is a no-op without indexedDB; any object will do,
// idb-keyval itself is faked below.
;(globalThis as any).indexedDB ??= {}

const fake = vi.hoisted(() => ({
	idb: new Map<string, string>(),
	docs: {} as Record<string, Record<string, unknown>>,
	currentUser: '',
	inserted: [] as Record<string, unknown>[],
	routerPush: vi.fn(),
}))

vi.mock('idb-keyval', () => ({
	get: async (key: string) => fake.idb.get(key),
	set: async (key: string, value: string) => {
		fake.idb.set(key, value)
	},
	del: async (key: string) => {
		fake.idb.delete(key)
	},
}))

vi.mock('frappe-ui', async () => {
	const actual = await vi.importActual<any>('frappe-ui')
	const { defineComponent, h } = await import('vue')
	const passthrough = (tag: string) =>
		defineComponent({
			inheritAttrs: false,
			setup(_props, { slots, attrs }) {
				return () =>
					h(tag, { onClick: (attrs as any).onClick }, slots.default?.({}))
			},
		})
	return {
		...actual,
		call: async (method: string, args: any) => {
			if (method === 'frappe.client.insert') {
				const name = `ASG-SUB-${fake.inserted.length + 1}`
				const doc = {
					...args.doc,
					name,
					owner: fake.currentUser,
					status: 'Not Graded',
				}
				fake.inserted.push(doc)
				fake.docs[name] = doc
				return doc
			}
			return null
		},
		toast: { success: vi.fn(), error: vi.fn() },
		Badge: passthrough('span'),
		Button: passthrough('button'),
		FormControl: passthrough('div'),
		FileUploader: defineComponent({
			name: 'FileUploader',
			emits: ['success'],
			setup() {
				return () => h('div', { 'data-testid': 'uploader' })
			},
		}),
	}
})

vi.mock('vue-router', async (importOriginal) => ({
	...(await importOriginal<any>()),
	useRouter: () => ({
		currentRoute: { value: { name: 'AssignmentSubmission', query: {} } },
		push: fake.routerPush,
	}),
}))
vi.mock('@/components/RichTextEditor.vue', () => ({
	default: { render: () => null },
}))
vi.mock('@/components/ShortcutTooltip.vue', () => ({
	default: {
		setup(_: unknown, { slots }: any) {
			return () => slots.default?.()
		},
	},
}))
vi.mock('@/composables/useKeyboardShortcuts', () => ({
	useKeyboardShortcuts: () => {},
	saveShortcut: () => ({}),
}))

const { setConfig, getCachedDocumentResource } = await import('frappe-ui')
const { default: Assignment } = await import('@/components/Assignment.vue')

const ASSIGNMENT = 'ASG-00810'
const NEW_KEY = JSON.stringify(['LMS Assignment Submission', 'new'])

// The server side as the SPA sees it: an assignment, and a submission that
// only its owner can read (enforce_member_ownership on the real site).
async function fakeServer({ url, params }: { url: string; params: any }) {
	if (url === 'lms.lms.utils.get_assignment') {
		return { name: ASSIGNMENT, title: 'Homework', question: '<p>Q</p>', type: 'PDF' }
	}
	if (url === 'frappe.client.get') {
		const doc = fake.docs[params.name]
		if (!doc || doc.owner !== fake.currentUser) {
			throw new Error('Not permitted')
		}
		return doc
	}
	return null
}

function userResource(email: string) {
	return { data: { name: email, full_name: email } }
}

async function openAs(email: string, submissionName = 'new') {
	fake.currentUser = email
	const wrapper = mount(Assignment, {
		props: { assignmentID: ASSIGNMENT, submissionName, showTitle: false },
		global: {
			provide: { $user: userResource(email) },
			// the global `__` from setup.ts, which also handles {0} placeholders
			mocks: { __: (globalThis as any).__ },
		},
	})
	await flushPromises()
	await nextTick()
	return wrapper
}

beforeEach(() => {
	fake.idb.clear()
	fake.docs = {}
	fake.inserted = []
	fake.routerPush.mockClear()
	setConfig('resourceFetcher', fakeServer)
})

describe('assignment submission on a shared browser', () => {
	it('shows an empty form even when another student is cached under "new"', async () => {
		// What earlier builds left on the browser after student A submitted.
		fake.idb.set(
			NEW_KEY,
			JSON.stringify({
				name: 'ASG-SUB-01097',
				owner: 'student-a@example.com',
				assignment: ASSIGNMENT,
				assignment_attachment: '/private/files/student-a-homework.pdf',
				status: 'Not Graded',
			})
		)

		const wrapper = await openAs('student-b@example.com')

		expect(wrapper.text()).not.toContain('student-a-homework.pdf')
		expect(wrapper.text()).not.toContain('Not Graded')
		expect(wrapper.find('[data-testid="uploader"]').exists()).toBe(true)
		// and the leftover is wiped from this browser
		expect(fake.idb.has(NEW_KEY)).toBe(false)
	})

	it('does not store a fresh submission under the shared "new" key', async () => {
		const a = await openAs('student-a@example.com')
		a.findComponent({ name: 'FileUploader' }).vm.$emit('success', {
			file_url: '/private/files/student-a-homework.pdf',
		})
		await nextTick()
		await a.find('button').trigger('click')
		await flushPromises()

		expect(fake.inserted).toHaveLength(1)
		expect(fake.routerPush).toHaveBeenCalledWith(
			expect.objectContaining({
				params: { assignmentID: ASSIGNMENT, submissionName: 'ASG-SUB-1' },
			})
		)
		expect(fake.idb.has(NEW_KEY)).toBe(false)
		expect(
			getCachedDocumentResource('LMS Assignment Submission', 'new')
		).toBeNull()
		a.unmount()

		// Student B, same tab (no reload), opens the assignment.
		const b = await openAs('student-b@example.com')
		expect(b.text()).not.toContain('student-a-homework.pdf')
		expect(b.find('[data-testid="uploader"]').exists()).toBe(true)
	})

	it('still loads a saved submission for its owner', async () => {
		fake.docs['ASG-SUB-7'] = {
			name: 'ASG-SUB-7',
			owner: 'student-a@example.com',
			assignment: ASSIGNMENT,
			assignment_attachment: '/private/files/mine.pdf',
			status: 'Not Graded',
		}

		const wrapper = await openAs('student-a@example.com', 'ASG-SUB-7')

		expect(wrapper.text()).toContain('mine.pdf')
		expect(wrapper.text()).toContain('Not Graded')
	})
})
