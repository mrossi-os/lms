/**
 * Thin wrappers around the AI tutor audio endpoints (STT / TTS).
 *
 * Audio is carried as base64 in the request/response body — see
 * apps/os_lms/os_lms/os_lms/ai/audio/api.py.
 */
import { call } from 'frappe-ui'

const TRANSCRIBE = 'os_lms.os_lms.ai.audio.api.transcribe'
const SYNTHESIZE = 'os_lms.os_lms.ai.audio.api.synthesize'

/** Read a Blob as a bare base64 string (without the data: prefix). */
export function blobToBase64(blob) {
	return new Promise((resolve, reject) => {
		const reader = new FileReader()
		reader.onerror = () => reject(reader.error)
		reader.onload = () => {
			const result = String(reader.result || '')
			const comma = result.indexOf(',')
			resolve(comma >= 0 ? result.slice(comma + 1) : result)
		}
		reader.readAsDataURL(blob)
	})
}

/** Transcribe a recorded audio Blob to text. */
export async function transcribeAudio(blob, { language = 'it' } = {}) {
	const audio = await blobToBase64(blob)
	const { text } = await call(TRANSCRIBE, {
		audio,
		mime: blob.type || 'audio/webm',
		language,
	})
	return text || ''
}

/** Synthesize speech for a piece of text. Returns a playable object URL. */
export async function synthesizeSpeech(text, { voice } = {}) {
	const res = await call(SYNTHESIZE, voice ? { text, voice } : { text })
	const bytes = base64ToBytes(res.audio)
	return URL.createObjectURL(new Blob([bytes], { type: res.mime || 'audio/mpeg' }))
}

function base64ToBytes(b64) {
	const binary = atob(b64 || '')
	const bytes = new Uint8Array(binary.length)
	for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
	return bytes
}

/** Build a playable object URL from a base64 audio payload. */
export function base64ToObjectUrl(base64, mime) {
	const bytes = base64ToBytes(base64)
	return URL.createObjectURL(new Blob([bytes], { type: mime || 'audio/mpeg' }))
}
