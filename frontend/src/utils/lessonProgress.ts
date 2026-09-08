/**
 * Pure helpers for lesson-progress logic. Kept side-effect-free so they can
 * be unit-tested without mounting Lesson.vue or stubbing the Pinia store.
 */

export function resolveDwellSeconds(raw: unknown, fallback = 30): number | null {
	const n = Number(raw ?? fallback)
	if (!Number.isFinite(n) || n <= 0) return null
	return n
}

export function isVideoComplete(currentTime: number, duration: number): boolean {
	if (!Number.isFinite(currentTime) || !Number.isFinite(duration)) return false
	if (duration <= 0) return false
	return currentTime >= duration - 1
}

export function shouldStartDwellTimer(opts: {
	hasVideo: boolean
	enforceVideo: boolean | 0 | 1
}): boolean {
	return !(opts.hasVideo && !!opts.enforceVideo)
}

export function shouldAttachVideoFallback(opts: {
	hasVideo: boolean
	enforceVideo: boolean | 0 | 1
}): boolean {
	return opts.hasVideo && !!opts.enforceVideo
}

/**
 * Whether a player `error` event means the video failed to load, and completion
 * should therefore degrade to the dwell timer.
 *
 * Plyr forwards every error its provider SDK raises through one event, and not
 * all of them are about playback: Vimeo answers Plyr's `getVideoUrl()` metadata
 * call — made only to build the download control — with a PrivacyError on a
 * privacy-restricted (typically unlisted) video, and the SDK routes that through
 * the same `error` event while the video itself plays fine. Treating those as a
 * load failure disables the video enforcement on a working lesson, so an error
 * is only fatal when the player never became ready and does not name the SDK
 * method it came from. Anything else still falls back, as upstream intends.
 */
export function shouldEngageFallbackOnPlayerError(opts: {
	playerReady: boolean
	detail?: { method?: string } | null
}): boolean {
	if (opts.playerReady) return false
	if (opts.detail?.method) return false
	return true
}
