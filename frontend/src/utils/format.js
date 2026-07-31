import { useTimeAgo } from '@vueuse/core'

// Italian relative-time strings for useTimeAgo (English-only by default).
// Mirrors @vueuse's default message shape: `past`/`future` receive the
// already-formatted unit string and only wrap it when it contains a number, so
// single-unit words like "ieri"/"domani" are returned as-is (not "ieri fa").
const IT_TIME_AGO_MESSAGES = {
	justNow: 'proprio ora',
	past: (n) => (/\d/.test(n) ? `${n} fa` : n),
	future: (n) => (/\d/.test(n) ? `tra ${n}` : n),
	month: (n, past) =>
		n === 1 ? (past ? 'il mese scorso' : 'il mese prossimo') : `${n} mesi`,
	year: (n, past) =>
		n === 1 ? (past ? "l'anno scorso" : "l'anno prossimo") : `${n} anni`,
	day: (n, past) => (n === 1 ? (past ? 'ieri' : 'domani') : `${n} giorni`),
	week: (n, past) =>
		n === 1
			? past
				? 'la settimana scorsa'
				: 'la settimana prossima'
			: `${n} settimane`,
	hour: (n) => `${n} ${n === 1 ? 'ora' : 'ore'}`,
	minute: (n) => `${n} ${n === 1 ? 'minuto' : 'minuti'}`,
	second: (n) => `${n} ${n === 1 ? 'secondo' : 'secondi'}`,
	invalid: '',
}

export function timeAgo(date) {
	return useTimeAgo(date, { messages: IT_TIME_AGO_MESSAGES }).value
}

export const formatSeconds = (time) => {
	const minutes = Math.floor(time / 60)
	const seconds = Math.floor(time % 60)
	return `${minutes}:${seconds < 10 ? '0' : ''}${seconds}`
}

export const escapeHTML = (text) => {
	if (!text) return ''
	let escape_html_mapping = {
		'&': '&amp;',
		'<': '&lt;',
		'>': '&gt;',
		'"': '&quot;',
		"'": '&#39;',
		'`': '&#x60;',
		'=': '&#x3D;',
	}

	return String(text).replace(
		/[&<>"'`=]/g,
		(char) => escape_html_mapping[char]
	)
}

export const formatTimestamp = (seconds) => {
	const date = new Date(seconds * 1000)
	const hours = String(date.getUTCHours()).padStart(2, '0')
	const minutes = String(date.getUTCMinutes()).padStart(2, '0')
	const secs = String(date.getUTCSeconds()).padStart(2, '0')
	return hours > 0 ? `${hours}:${minutes}:${secs}` : `${minutes}:${secs}`
}
