/**
 * OS Audit page formatting (oslms/components/osAudit/format.ts): times in h:mm as
 * attendance registers want them, and the one-line description of an event.
 */
import { beforeAll, describe, expect, it } from 'vitest'
import {
	describeEvent,
	exportLabel,
	formatClock,
	formatHM,
} from '../oslms/components/osAudit/format'

beforeAll(() => {
	// The app's __() returns a String with .format(); the identity is enough here.
	;(globalThis as any).__ = (text: string) =>
		Object.assign(new String(text), {
			format: (...args: unknown[]) =>
				text.replace(/{(\d+)}/g, (_, i) => String(args[Number(i)])),
		})
})

describe('formatHM', () => {
	it('rounds down to whole minutes and pads them', () => {
		expect(formatHM(0)).toBe('0:00')
		expect(formatHM(59)).toBe('0:00')
		expect(formatHM(2700)).toBe('0:45')
		expect(formatHM(3 * 3600 + 5 * 60 + 59)).toBe('3:05')
	})

	it('treats missing or negative values as zero', () => {
		expect(formatHM(null)).toBe('0:00')
		expect(formatHM(undefined)).toBe('0:00')
		expect(formatHM(-30)).toBe('0:00')
	})
})

describe('formatClock', () => {
	it('pads a single-digit hour of a Time field', () => {
		expect(formatClock('9:00:00')).toBe('09:00')
		expect(formatClock('0:30:00')).toBe('00:30')
		expect(formatClock('19:45:00')).toBe('19:45')
	})

	it('returns nothing for a missing time', () => {
		expect(formatClock(null)).toBe('')
		expect(formatClock('')).toBe('')
	})
})

describe('describeEvent', () => {
	it('gives the totals and the reason of a closed lesson visit', () => {
		expect(
			String(
				describeEvent({
					event_type: 'session_closed',
					data: { presence_seconds: 1800, active_seconds: 600, reason: 'hidden' },
				}),
			),
		).toBe('Presence 0:30, active 0:10, closed by tab hidden')
	})

	it('gives score and duration of a quiz', () => {
		expect(
			describeEvent({
				event_type: 'quiz_submit',
				data: { score: 8, score_out_of: 10, duration_seconds: 420 },
			}),
		).toBe('Score 8/10, duration 0:07')
	})

	it('hides the details of an erased event', () => {
		expect(
			String(
				describeEvent({
					event_type: 'quiz_submit',
					data: { score: 8 },
					redacted: 1,
				}),
			),
		).toBe('Personal data erased')
	})

	it('names the export report', () => {
		expect(String(exportLabel('os_audit_register'))).toBe('Attendance register')
		expect(
			String(
				describeEvent({
					event_type: 'audit_export',
					data: { report: 'os_audit_live', rows: 12 },
				}),
			),
		).toBe('Live class attendance, 12 rows')
	})
})
