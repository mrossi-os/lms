import type {} from '@/types/lms/LMSCourse'

declare module '@/types/lms/LMSCourse' {
	interface LMSCourse {
		enforce_lesson_order?: 0 | 1
		enforce_quiz_on_completion?: 0 | 1
		hero_enabled?: 0 | 1
		hero_media_type?: 'Video' | 'Image'
		hero_media_url?: string
	}
}
