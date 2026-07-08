/**
 * Client-side audio re-encoding for the STT pipeline.
 *
 * MediaRecorder produces webm/opus (Chrome/Firefox) or mp4/aac (Safari). Some
 * STT providers — notably Google Gemini's native audio understanding — do NOT
 * accept webm: their documented inputs are wav, mp3, aac, ogg, flac, aiff.
 * Sending webm/opus content to Gemini yields an empty transcript (surfaced as
 * an AudioError → HTTP 500).
 *
 * Converting the recorded clip to a real 16 kHz mono 16-bit PCM WAV here makes
 * the audio turn provider-agnostic: WAV is accepted by every provider (OpenAI
 * included). 16 kHz mono is the standard STT input and keeps the base64 payload
 * small (~2 MB/min, well under the 25 MB provider cap).
 */

const TARGET_SAMPLE_RATE = 16000

/**
 * Decode a recorded audio Blob and re-encode it as a mono WAV Blob.
 * Throws if the Web Audio API is unavailable or the clip can't be decoded — the
 * caller is expected to fall back to the original clip in that case.
 */
export async function audioBlobToWav(
	blob,
	{ sampleRate = TARGET_SAMPLE_RATE } = {},
) {
	const AudioCtx = window.AudioContext || window.webkitAudioContext
	const OfflineCtx =
		window.OfflineAudioContext || window.webkitOfflineAudioContext
	if (!AudioCtx || !OfflineCtx) throw new Error('Web Audio API not available')

	const arrayBuffer = await blob.arrayBuffer()

	// Decode the compressed recording into raw PCM samples. `slice(0)` passes a
	// copy since decodeAudioData detaches the underlying buffer.
	const decodeCtx = new AudioCtx()
	let decoded
	try {
		decoded = await decodeCtx.decodeAudioData(arrayBuffer.slice(0))
	} finally {
		decodeCtx.close?.()
	}

	// Resample to the target rate and downmix to mono via an OfflineAudioContext.
	const frames = Math.max(1, Math.ceil(decoded.duration * sampleRate))
	const offline = new OfflineCtx(1, frames, sampleRate)
	const source = offline.createBufferSource()
	source.buffer = decoded
	source.connect(offline.destination)
	source.start(0)
	const rendered = await offline.startRendering()

	return encodeWav(rendered.getChannelData(0), sampleRate)
}

/** Encode Float32 PCM samples as a 16-bit mono WAV Blob. */
function encodeWav(samples, sampleRate) {
	const numFrames = samples.length
	const buffer = new ArrayBuffer(44 + numFrames * 2)
	const view = new DataView(buffer)

	const writeString = (offset, str) => {
		for (let i = 0; i < str.length; i++)
			view.setUint8(offset + i, str.charCodeAt(i))
	}

	writeString(0, 'RIFF')
	view.setUint32(4, 36 + numFrames * 2, true)
	writeString(8, 'WAVE')
	writeString(12, 'fmt ')
	view.setUint32(16, 16, true) // PCM subchunk size
	view.setUint16(20, 1, true) // audio format = PCM
	view.setUint16(22, 1, true) // channels = 1 (mono)
	view.setUint32(24, sampleRate, true)
	view.setUint32(28, sampleRate * 2, true) // byte rate = rate * channels * bytesPerSample
	view.setUint16(32, 2, true) // block align = channels * bytesPerSample
	view.setUint16(34, 16, true) // bits per sample
	writeString(36, 'data')
	view.setUint32(40, numFrames * 2, true)

	let offset = 44
	for (let i = 0; i < numFrames; i++) {
		const s = Math.max(-1, Math.min(1, samples[i]))
		view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true)
		offset += 2
	}

	return new Blob([view], { type: 'audio/wav' })
}
