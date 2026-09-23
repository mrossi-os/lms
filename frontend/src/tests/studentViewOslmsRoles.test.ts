/**
 * Student View must also strip the os_lms custom roles: a Valutatore previewing a
 * lesson would otherwise still see the grading panel (entry
 * student-view-oslms-roles).
 */
import { describe, expect, it } from 'vitest'
import { asStudent } from '@/composables/useStudentView'

describe('asStudent with os_lms roles', () => {
	it('turns off the Docente and Valutatore flags', () => {
		const user = asStudent({
			name: 'val@example.com',
			is_docente: true,
			is_valutatore: true,
			roles: [],
		}) as Record<string, unknown>
		expect(user.is_docente).toBe(false)
		expect(user.is_valutatore).toBe(false)
		expect(user.is_student).toBe(true)
	})

	it('drops Valutatore, Docente and Gestore from the roles', () => {
		const user = asStudent({
			name: 'gestore@example.com',
			roles: ['Valutatore', 'Docente', 'Gestore', 'LMS Student'],
		}) as Record<string, unknown>
		expect(user.roles).toEqual(['LMS Student'])
	})
})
