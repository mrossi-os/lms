/**
 * Formatting shared by the OS Audit page tabs (docs/audit-studenti/PIANO.md §7).
 * Times are h:mm, the format attendance registers use.
 */
import dayjs from '@/utils/dayjs'

export const AUDIT_API = 'os_lms.os_lms.os_audit_page'
export const EXPORT_API = 'os_lms.os_lms.os_audit_export'

export function formatHM(seconds?: number | null): string {
	const minutes = Math.floor(Math.max(Number(seconds) || 0, 0) / 60)
	return `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}`
}

export function formatDateTime(value?: string | null): string {
	return value ? dayjs(value).format('DD/MM/YYYY HH:mm:ss') : ''
}

export function formatDate(value?: string | null): string {
	return value ? dayjs(value).format('DD/MM/YYYY') : ''
}

export function formatTime(value?: string | null): string {
	return value ? dayjs(value).format('HH:mm') : ''
}

// A Time field comes as "9:00:00" (no leading zero), so slicing it is not enough.
export function formatClock(value?: string | null): string {
	const [hours, minutes] = String(value || '').split(':')
	if (!hours || minutes === undefined) return ''
	return `${hours.padStart(2, '0')}:${minutes.padStart(2, '0')}`
}

export function formatPercent(value?: number | null): string {
	return value === null || value === undefined ? '—' : `${value}%`
}

// The labels are read at render time, never baked into a module-level object:
// __() needs the translations, which load after this module.
function closeReason(reason?: string): string {
	switch (reason) {
		case 'page_closed':
			return __('page closed')
		case 'timeout':
			return __('inactivity')
		case 'hidden':
			return __('tab hidden')
		case 'audit_disabled':
			return __('audit turned off')
		default:
			return reason || ''
	}
}

function exportLabel(report?: string): string {
	switch (report) {
		case 'os_audit_register':
			return __('Attendance register')
		case 'os_audit_live':
			return __('Live class attendance')
		case 'os_audit_sessions':
			return __('Lesson visits')
		case 'os_audit_events':
			return __('Audit events')
		default:
			return report || ''
	}
}

export { exportLabel }

/** One readable line for the details stored with an event. */
export function describeEvent(event: {
	event_type: string
	data?: Record<string, any>
	changed_labels?: string[]
	redacted?: number
}): string {
	const data = event.data || {}
	if (event.redacted) return __('Personal data erased')
	switch (event.event_type) {
		case 'session_closed':
			return __('Presence {0}, active {1}, closed by {2}').format(
				formatHM(data.presence_seconds),
				formatHM(data.active_seconds),
				closeReason(data.reason),
			)
		case 'quiz_submit': {
			const parts = []
			if (data.score !== undefined && data.score !== null)
				parts.push(
					__('Score {0}/{1}').format(data.score, data.score_out_of ?? '—'),
				)
			if (data.duration_seconds)
				parts.push(__('duration {0}').format(formatHM(data.duration_seconds)))
			return parts.join(', ')
		}
		case 'audit_settings_changed':
			return __('Changed: {0}').format(
				(event.changed_labels || Object.keys(data.changes || {})).join(', '),
			)
		case 'daily_seal':
			return __('Day {0}: {1} events').format(formatDate(data.date), data.events)
		case 'audit_export':
			return __('{0}, {1} rows').format(exportLabel(data.report), data.rows)
		case 'audit_data_erased':
			return __('{0} events erased').format(data.events)
		case 'live_class_join':
			return data.host ? __('as teacher') : ''
		default:
			return ''
	}
}
