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
const playingId = ref(null)
const isSynthesizing = ref(false)
let synthesizingId = null

if (audioEl) {
	audioEl.addEventListener('ended', () => (playingId.value = null))
	audioEl.addEventListener('error', () => (playingId.value = null))
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
				url = await synthesizeSpeech(clean, { voice })
				urlCache.set(clean, url)
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

	return { playingId, isSynthesizing, play, stop, isLoading }
}
