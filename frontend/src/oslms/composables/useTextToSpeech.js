/**
 * Text-to-speech playback for AI tutor answers.
 *
 * A single shared Audio element plays one clip at a time (unlike AudioBlock,
 * which grabs the first <audio> in the DOM). Synthesized clips are cached by
 * text so replays don't re-hit the backend.
 */
import { ref } from 'vue'
import { toast } from 'frappe-ui'
import { synthesizeSpeech } from '@/oslms/utils/audioApi'

const audioEl = typeof Audio !== 'undefined' ? new Audio() : null
const urlCache = new Map() // text -> object URL
const pending = new Map() // text -> Promise<object URL> (in-flight synthesis)
const playingId = ref(null)
const isSynthesizing = ref(false)
let synthesizingId = null

if (audioEl) {
	audioEl.addEventListener('ended', () => (playingId.value = null))
	audioEl.addEventListener('error', () => (playingId.value = null))
}

/**
 * Resolve the object URL for a piece of text, hitting the backend at most once.
 * Already-synthesized clips come straight from the cache; concurrent callers
 * (e.g. a background prefetch and a click) share the same in-flight request.
 */
function synthesize(clean, { voice } = {}) {
	const cached = urlCache.get(clean)
	if (cached) return Promise.resolve(cached)

	const inFlight = pending.get(clean)
	if (inFlight) return inFlight

	const request = synthesizeSpeech(clean, { voice })
		.then((url) => {
			urlCache.set(clean, url)
			pending.delete(clean)
			return url
		})
		.catch((e) => {
			pending.delete(clean)
			throw e
		})
	pending.set(clean, request)
	return request
}

export function useTextToSpeech() {
	async function play(text, id, { voice } = {}) {
		const clean = (text || '').trim()
		if (!clean || !audioEl) return

		// Clicking the message that is already playing toggles it off.
		if (playingId.value === id) {
			stop()
			return
		}
		stop()

		let url = urlCache.get(clean)
		if (!url) {
			isSynthesizing.value = true
			synthesizingId = id
			try {
				url = await synthesize(clean, { voice })
			} catch (e) {
				toast.error(e?.message || __('Could not read the answer aloud.'))
				return
			} finally {
				isSynthesizing.value = false
				synthesizingId = null
			}
		}

		audioEl.src = url
		try {
			await audioEl.play()
			playingId.value = id
		} catch {
			playingId.value = null
		}
	}

	function stop() {
		if (!audioEl) return
		audioEl.pause()
		playingId.value = null
	}

	function isLoading(id) {
		return isSynthesizing.value && synthesizingId === id
	}

	// Warm the cache in the background so a later click plays instantly. Errors
	// are swallowed: a failed prefetch must not surface a toast, and the click
	// path will retry and report the error then.
	function prefetch(text, { voice } = {}) {
		const clean = (text || '').trim()
		if (!clean || !audioEl) return
		synthesize(clean, { voice }).catch(() => {})
	}

	return { playingId, isSynthesizing, play, stop, isLoading, prefetch }
}
