/**
 * Speech-to-text recording lifecycle for the AI tutor chat.
 *
 * Owns the getUserMedia permission flow + MediaRecorder and exposes a simple
 * toggle. When a recording ends (manually or at the duration cap) the clip is
 * transcribed via the backend and delivered through the `onTranscript`
 * callback — the caller decides what to do with the text (e.g. fill the input).
 */
import { ref } from 'vue'
import { toast } from 'frappe-ui'
import { transcribeAudio } from '@/oslms/utils/audioApi'
import { audioBlobToWav } from '@/oslms/utils/audioConvert'

// Cap recording length so the clip stays well under the 25 MB provider limit.
const MAX_DURATION_MS = 60_000

function pickMimeType() {
	if (typeof MediaRecorder === 'undefined') return ''
	// Safari has no webm/opus — fall back to mp4; Chrome/Firefox use webm.
	const candidates = [
		'audio/webm;codecs=opus',
		'audio/webm',
		'audio/mp4',
		'audio/ogg',
	]
	return candidates.find((t) => MediaRecorder.isTypeSupported?.(t)) || ''
}

export function useSpeechToText({
	language = 'it',
	onTranscript,
	onAudio,
} = {}) {
	const isRecording = ref(false)
	const isTranscribing = ref(false)
	const isSupported = ref(
		typeof navigator !== 'undefined' &&
			!!navigator.mediaDevices?.getUserMedia &&
			typeof MediaRecorder !== 'undefined',
	)

	let recorder = null
	let chunks = []
	let stopTimer = null

	async function start() {
		if (isRecording.value || isTranscribing.value) return
		if (!isSupported.value) {
			toast.error(__('Audio recording is not supported by this browser.'))
			return
		}
		let stream
		try {
			stream = await navigator.mediaDevices.getUserMedia({ audio: true })
		} catch (e) {
			toast.error(__('Microphone access was denied.'))
			return
		}
		const mimeType = pickMimeType()
		recorder = new MediaRecorder(
			stream,
			mimeType ? { mimeType } : undefined,
		)
		chunks = []
		recorder.ondataavailable = (e) => {
			if (e.data && e.data.size) chunks.push(e.data)
		}
		recorder.onstop = onStop
		recorder.start()
		isRecording.value = true
		stopTimer = setTimeout(stop, MAX_DURATION_MS)
	}

	function stop() {
		if (!recorder || !isRecording.value) return
		clearTimeout(stopTimer)
		recorder.stop()
		isRecording.value = false
	}

	async function onStop() {
		const tracks = recorder?.stream?.getTracks() || []
		tracks.forEach((t) => t.stop())
		let blob = new Blob(chunks, {
			type: recorder?.mimeType || 'audio/webm',
		})
		recorder = null
		chunks = []
		if (!blob.size) return

		// Re-encode to WAV before handing the clip off: some STT providers
		// (Gemini native audio) can't decode the browser's webm/opus recording.
		// WAV is accepted by every provider; on any failure we keep the raw clip
		// (OpenAI still accepts webm) so conversion can only help, never break.
		try {
			blob = await audioBlobToWav(blob)
		} catch {
			// Keep the original recording.
		}
		// Raw mode: hand back the recorded clip and skip transcription — the
		// caller sends the audio to a combined endpoint that does STT itself.
		if (onAudio) {
			onAudio(blob)
			return
		}
		isTranscribing.value = true
		try {
			const text = await transcribeAudio(blob, { language })
			if (text) onTranscript?.(text)
		} catch (e) {
			toast.error(e?.message || __('Transcription failed.'))
		} finally {
			isTranscribing.value = false
		}
	}

	function toggle() {
		if (isRecording.value) stop()
		else start()
	}

	return { isRecording, isTranscribing, isSupported, start, stop, toggle }
}
