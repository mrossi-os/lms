/**
 * OS Audit phase 4 (docs/audit-studenti/fase-4-analisi.md §8): one live class in
 * the Attendance tab. The Gestore matches a participant the provider reported to
 * a person of the class, or marks them as an external guest, and can have the
 * attendance read again once the class has ended.
 *
 * frappe-ui is stubbed: Badge and Button are its own, FormControl is a plain
 * <select>, `call` is the spy the assertions read.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import AuditLiveClass from '@/oslms/components/osAudit/AuditLiveClass.vue'

const { callMock, toastMock } = vi.hoisted(() => ({
	callMock: vi.fn(),
	toastMock: { success: vi.fn(), error: vi.fn() },
}))

vi.mock('frappe-ui', () => ({
	call: callMock,
	toast: toastMock,
	Badge: { props: ['label', 'theme'], template: '<span data-testid="badge">{{ label }}</span>' },
	Button: {
		emits: ['click'],
		props: ['loading', 'disabled'],
		template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
	},
	FormControl: {
		props: ['modelValue', 'options', 'type'],
		emits: ['update:modelValue'],
		template: `<select data-testid="people" :value="modelValue"
			@change="$emit('update:modelValue', $event.target.value)">
			<option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
		</select>`,
	},
}))

const translate = (text: string) =>
	Object.assign(new String(text), {
		format: (...args: unknown[]) =>
			text.replace(/{(\d+)}/g, (_, i) => String(args[Number(i)])),
	})
vi.stubGlobal('__', translate)

function liveClass(overrides: Record<string, unknown> = {}) {
	return {
		name: 'lc-1',
		title: 'Kick-off',
		date: '2026-11-10',
		time: '9:00:00',
		duration: 60,
		batch_title: 'Sales team',
		provider: 'Zoom',
		teacher_name: 'Laura Verdi',
		read_status: 'Read',
		read_status_label: 'Attendance read',
		read_at: '2026-11-10 10:45:00',
		read_error: null,
		participants: [
			{
				user: 'mario@example.com',
				full_name: 'Mario Rossi',
				is_host: false,
				joined_from_platform: null,
				started_at: null,
				joined_at: '2026-11-10 09:05:00',
				left_at: '2026-11-10 09:55:00',
				duration_seconds: 2700,
				segments: 2,
				matched_by: 'email',
				matched_label: 'Email',
				names: ['mario'],
			},
		],
		unmatched: [
			{
				row: 'row-zorro',
				display_name: 'Zorro',
				email: '',
				joined_at: '2026-11-10 09:10:00',
				left_at: '2026-11-10 09:20:00',
				duration_seconds: 600,
				segments: 1,
			},
		],
		guests: [],
		people: [{ user: 'anna@example.com', full_name: 'Anna Bianchi' }],
		...overrides,
	}
}

function render(live = liveClass()) {
	return mount(AuditLiveClass, {
		props: { live },
		global: { mocks: { __: translate } },
	})
}

const button = (wrapper: any, label: string) =>
	wrapper.findAll('button').find((b: any) => b.text() === label)

beforeEach(() => {
	callMock.mockReset()
	toastMock.success.mockReset()
	toastMock.error.mockReset()
})

describe('AuditLiveClass', () => {
	it('shows the matched people with their segments and how they were matched', () => {
		const wrapper = render()
		expect(wrapper.text()).toContain('Mario Rossi')
		expect(wrapper.text()).toContain('2 segments')
		expect(wrapper.text()).toContain('Email')
		expect(wrapper.text()).toContain('Unmatched participants (1)')
	})

	it('matches an unmatched participant to the person chosen', async () => {
		callMock.mockResolvedValueOnce({ matched: 2, unmatched: 0 })
		const wrapper = render()
		const select = wrapper.get('[data-testid="people"]')
		expect(select.text()).toContain('Anna Bianchi (anna@example.com)')
		await select.setValue('anna@example.com')
		await button(wrapper, 'Match').trigger('click')
		await flushPromises()
		expect(callMock).toHaveBeenLastCalledWith('os_lms.os_lms.os_audit_live.match_participant', {
			row: 'row-zorro',
			user: 'anna@example.com',
			guest: 0,
		})
		expect(wrapper.emitted('changed')).toHaveLength(1)
	})

	it('Match stays disabled until a person is chosen', () => {
		const wrapper = render()
		expect(button(wrapper, 'Match').attributes('disabled')).toBeDefined()
	})

	it('marks a participant as an external guest without a user', async () => {
		callMock.mockResolvedValueOnce({ matched: 1, unmatched: 0 })
		const wrapper = render()
		await button(wrapper, 'External guest').trigger('click')
		await flushPromises()
		expect(callMock).toHaveBeenCalledWith('os_lms.os_lms.os_audit_live.match_participant', {
			row: 'row-zorro',
			user: undefined,
			guest: 1,
		})
		expect(toastMock.success).toHaveBeenCalledWith(expect.objectContaining({}))
	})

	it('reads the attendance again only for a class that has ended', async () => {
		callMock.mockResolvedValueOnce({ status: 'Pending' })
		const ended = render()
		await button(ended, 'Read attendance again').trigger('click')
		await flushPromises()
		expect(callMock).toHaveBeenCalledWith('os_lms.os_lms.os_audit_live.reread_live_class', {
			live_class: 'lc-1',
		})
		const future = render(liveClass({ date: '2999-01-01' }))
		expect(button(future, 'Read attendance again')).toBeUndefined()
	})

	it('shows why the read failed', () => {
		const wrapper = render(
			liveClass({
				read_status: 'Error',
				read_status_label: 'Error',
				read_error: 'Zoom answered 400: scope missing',
			}),
		)
		expect(wrapper.text()).toContain('Zoom answered 400: scope missing')
	})
})
