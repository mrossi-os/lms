// Companion of safeUrl for local image previews, which safeUrl rejects on
// purpose: an in-memory blob: URL, or a base64 raster image read from a file the
// user just picked (the editor also previews a video being uploaded). Only
// raster images and video containers: an SVG data URL is a document that can
// carry script. Use it as `safeUrl(x) ?? safeImageData(x)` on <img>/<video> :src.
const RASTER_DATA_URL =
	/^data:(?:image\/(?:png|jpe?g|gif|webp|bmp)|video\/(?:mp4|webm|ogg|quicktime));base64,[a-z0-9+/=\s]+$/i

export const safeImageData = (value?: string | null): string | undefined => {
	if (!value) return undefined
	if (value.startsWith('blob:')) return value
	return RASTER_DATA_URL.test(value) ? value : undefined
}
