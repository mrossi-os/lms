/**
 * OS Audit page formatting (oslms/components/osAudit/format.ts): times in h:mm as
 * attendance registers want them, and the one-line description of an event.
 */
import { beforeAll, describe, expect, it } from 'vitest'
import {
	canRereadLive,
	describeEvent,
	exportLabel,
	formatClock,
	formatHM,
	formatPosition,
	mediaName,
	readStatusTheme,
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

describe('formatPosition and mediaName', () => {
	it('gives a video position as m:ss, or h:mm:ss past the hour', () => {
		expect(formatPosition(0)).toBe('0:00')
		expect(formatPosition(65.7)).toBe('1:05')
		expect(formatPosition(3725)).toBe('1:02:05')
		expect(formatPosition(undefined)).toBe('0:00')
	})

	it('names a platform file by its file name and an embed by its URL', () => {
		expect(mediaName('/private/files/lesson 1.mp4')).toBe('lesson 1.mp4')
		expect(mediaName('https://www.youtube.com/watch?v=abc')).toBe(
			'https://www.youtube.com/watch?v=abc',
		)
		expect(mediaName(undefined)).toBe('')
	})
})

describe('describeEvent', () => {
	it('describes video, PDF and download events', () => {
		const source = '/files/intro.mp4'
		expect(
			String(describeEvent({ event_type: 'video_pause', data: { source, position: 95 } })),
		).toBe('intro.mp4 at position 1:35')
		expect(
			String(
				describeEvent({
					event_type: 'video_seek',
					data: { source, from: 10, position: 130 },
				}),
			),
		).toBe('intro.mp4: skipped from 0:10 to 2:10')
		expect(
			describeEvent({ event_type: 'download', data: { file: '/files/handout.pdf' } }),
		).toBe('handout.pdf')
		expect(
			String(
				describeEvent({
					event_type: 'session_closed',
					data: { presence_seconds: 600, active_seconds: 300, video_seconds: 240, reason: 'timeout' },
				}),
			),
		).toBe('Presence 0:10, active 0:05, closed by inactivity, video playing 0:04')
		expect(
			String(
				describeEvent({
					event_type: 'session_closed',
					data: { presence_seconds: 49, active_seconds: 49, video_seconds: 11, reason: 'timeout' },
				}),
			),
		).toBe('Presence 0:00, active 0:00, closed by inactivity')
	})

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

describe('live attendance helpers (phase 4)', () => {
	it('colours the read status of a live class', () => {
		expect(readStatusTheme('Read')).toBe('green')
		expect(readStatusTheme('Pending')).toBe('orange')
		expect(readStatusTheme('Error')).toBe('red')
		expect(readStatusTheme('Not Held')).toBe('gray')
		expect(readStatusTheme(null)).toBe('gray')
	})

	it('allows reading again only after the end of the class', () => {
		const live = { date: '2026-11-10', time: '9:00:00', duration: 60 }
		expect(canRereadLive(live, new Date('2026-11-10T09:59:00'))).toBe(false)
		expect(canRereadLive(live, new Date('2026-11-10T10:01:00'))).toBe(true)
		expect(canRereadLive({ ...live, duration: 0 }, new Date('2026-11-10T09:30:00'))).toBe(false)
		expect(canRereadLive({ date: null, time: null })).toBe(false)
	})
})
