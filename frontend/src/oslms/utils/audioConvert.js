/**
 * Client-side audio re-encoding for the STT pipeline.
 *
 * MediaRecorder produces webm/opus (Chrome/Firefox) or mp4/aac (Safari). Some
 * STT providers — notably Google Gemini's native audio understanding — do NOT
 * accept webm/mp4: their documented inputs are wav, mp3, aac, ogg, flac, aiff.
 * Sending an unsupported container to Gemini yields an empty transcript,
 * surfaced as an AudioError → HTTP 500.
 *
 * Converting the recorded clip to a real PCM WAV here makes the audio turn
 * provider-agnostic: WAV is accepted by every provider (OpenAI included).
 *
 * Portability note: we intentionally do NOT use OfflineAudioContext to resample.
 * Safari (and some Chromium builds) reject an OfflineAudioContext created at a
 * non-standard rate like 16 kHz, which previously made the conversion throw on
 * those browsers and silently fall back to the raw (unsupported) recording —
 * the exact reason a recording could work in one browser and 500 in another.
 * We decode with a plain AudioContext (widely supported, incl. Safari), downmix
 * to mono in JS, and encode WAV at the decoded sample rate. Gemini and OpenAI
 * accept any sample rate, so no resampling is needed.
 */

/**
 * Decode a recorded audio Blob and re-encode it as a mono WAV Blob at the
 * decoded sample rate. Throws if the Web Audio API is unavailable or the clip
 * can't be decoded — the caller is expected to fall back to the original clip.
 */
export async function audioBlobToWav(blob) {
	const AudioCtx = window.AudioContext || window.webkitAudioContext
	if (!AudioCtx) throw new Error('Web Audio API not available')

	const arrayBuffer = await blob.arrayBuffer()

	// Decode the compressed recording into raw PCM samples. `slice(0)` passes a
	// copy since decodeAudioData detaches the underlying buffer.
	const ctx = new AudioCtx()
	let decoded
	try {
		decoded = await ctx.decodeAudioData(arrayBuffer.slice(0))
	} finally {
		ctx.close?.()
	}

	return encodeWav(downmixToMono(decoded), decoded.sampleRate)
}

/** Average all channels of an AudioBuffer into a single Float32 mono track. */
function downmixToMono(buffer) {
	const channels = buffer.numberOfChannels
	if (channels === 1) return buffer.getChannelData(0)

	const length = buffer.length
	const mono = new Float32Array(length)
	for (let c = 0; c < channels; c++) {
		const data = buffer.getChannelData(c)
		for (let i = 0; i < length; i++) mono[i] += data[i]
	}
	for (let i = 0; i < length; i++) mono[i] /= channels
	return mono
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
