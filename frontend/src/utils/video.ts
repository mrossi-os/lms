/**
 * Helpers for the shared video-preview field (course + batch). A single
 * `video_link` string can hold either a YouTube/URL link or an uploaded file's
 * URL; these resolve it to a renderable preview.
 */

const YOUTUBE_RE =
	/(?:youtube\.com\/(?:watch\?(?:.*&)?v=|embed\/|v\/|shorts\/)|youtu\.be\/)([\w-]{11})/

// A bare 11-char video id, optionally trailed by tracking params — the legacy
// stored form (e.g. "XKA94rcu8b8?si=DEk3Kh20jA4uZFCa"). Anchored so file URLs
// like "/files/intro.mp4" never match.
const BARE_ID_RE = /^([\w-]{11})(?:[?&].*)?$/

// What Vimeo's "Copy link" share button produces. The uuid carries no video id,
// the page doesn't redirect and Vimeo's oEmbed API rejects it, so a share link
// can't be embedded as-is: only os_lms.os_lms.api.resolve_vimeo_share can turn
// it into a playable vimeo.com/<id>/<hash> URL. Lives here so the lesson editor
// and the preview field match it the same way.
export const VIMEO_SHARE_RE =
	/^(?:https?:\/\/)?(?:www\.)?vimeo\.com\/share\/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\/?(?:\?\S*)?$/i

// The Vimeo forms getVideoEmbedURL can turn into a player URL: vimeo.com/<id>
// (optionally /<hash>) and player.vimeo.com/video/<id>. Share links are
// deliberately excluded — they must be resolved into one of these first.
const VIMEO_RE =
	/^(?:https?:\/\/)?(?:www\.)?(?:player\.)?vimeo\.com\/(?:video\/)?\d+/i

export function isVimeoLink(url: string | null | undefined): boolean {
	return VIMEO_RE.test(String(url ?? '').trim())
}

export function getYouTubeId(url: string | null | undefined): string | null {
	if (!url) return null
	const s = String(url).trim()
	const match = s.match(YOUTUBE_RE)
	if (match) return match[1]
	const bare = s.match(BARE_ID_RE)
	return bare ? bare[1] : null
}

const VIDEO_FILE_TYPES = ['mp4', 'webm', 'mov', 'mkv', 'm4v']

type LessonLike = {
	youtube?: string | null
	videos?: unknown[] | null
	body?: string | null
	content?: string | null
}

/**
 * Whether a lesson (course-lesson doc or editor draft) contains a video — a
 * YouTube link, an uploaded video, a {{ Video }}/{{ YouTubeVideo }} macro in the
 * legacy body, or an embed/video-upload block in the editor content. Shared by
 * the lesson view and the lesson editor so the Video Statistics affordance shows
 * in exactly the same cases.
 */
export function hasVideoContent(lesson: LessonLike | null | undefined): boolean {
	if (!lesson) return false
	if (lesson.youtube) return true
	if (lesson.videos?.length) return true
	if (lesson.body && /\{\{ (YouTubeVideo|Video)\(/.test(lesson.body)) return true
	if (lesson.content) {
		try {
			const blocks = JSON.parse(lesson.content)?.blocks || []
			return blocks.some(
				(block: { type?: string; data?: { file_type?: string } }) =>
					block.type === 'embed' ||
					(block.type === 'upload' &&
						VIDEO_FILE_TYPES.includes(block.data?.file_type ?? ''))
			)
		} catch {
			return false
		}
	}
	return false
}

export type VideoPreview = {
	type: 'youtube' | 'file' | null
	src: string
}

export function getVideoPreview(url: string | null | undefined): VideoPreview {
	const id = getYouTubeId(url)
	if (id) return { type: 'youtube', src: `https://www.youtube.com/embed/${id}` }
	if (url) {
		const src = String(url)
		// A bare filename (no scheme, no leading slash) is a legacy uploaded video
		// whose /files/ prefix was stripped on save — resolve it against the public
		// files path so <video> doesn't treat it as relative to the current route.
		const resolved =
			/^https?:\/\//.test(src) || src.startsWith('/') ? src : `/files/${src}`
		return { type: 'file', src: resolved }
	}
	return { type: null, src: '' }
}
