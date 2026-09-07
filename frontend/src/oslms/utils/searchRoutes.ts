/**
 * Where a search result takes you.
 *
 * Single source of truth for both search entry points — the /search page and
 * the Cmd+K palette. They used to map doctypes to routes on their own, and had
 * drifted apart: the palette sent everything that was not a course to
 * `BatchDetail`, so a lesson, quiz, program or job landed on a batch page that
 * does not exist. Keep new indexed doctypes in this one place.
 *
 * Assignment results only reach moderators and instructors (filtered server
 * side in `get_grouped_results_custom`), which is why they can point at the
 * management page without a role check here. Quiz results also reach learners,
 * for the courses they are enrolled in, so that one branch is role-aware.
 */

type SearchRoute = {
	name: string
	params?: Record<string, string>
	query?: Record<string, string>
}

/** Result titles carry <mark> highlights, so unwrap them before reusing the text. */
const plainText = (html: string): string => {
	const el = document.createElement('div')
	el.innerHTML = html ?? ''
	return (el.textContent ?? '').trim()
}

/**
 * Open the lesson itself when the result carries its position in the course
 * outline; fall back to the course page when it does not (a lesson no chapter
 * references, or a stale search index).
 */
export const getLessonRoute = (result: any): SearchRoute => {
	const courseName = result.course || result.parent
	if (result.chapter_number && result.lesson_number) {
		return {
			name: 'Lesson',
			params: {
				courseName,
				chapterNumber: String(result.chapter_number),
				lessonNumber: String(result.lesson_number),
			},
		}
	}
	return { name: 'CourseDetail', params: { courseName } }
}

/** Returns null for a doctype with no page to open, so no navigation happens. */
export const getSearchResultRoute = (
	result: any,
	isManager = false,
): SearchRoute | null => {
	switch (result?.doctype) {
		case 'LMS Course':
			return { name: 'CourseDetail', params: { courseName: result.name } }
		case 'LMS Batch':
			return { name: 'BatchDetail', params: { batchName: result.name } }
		case 'Job Opportunity':
			return { name: 'JobDetail', params: { job: result.name } }
		case 'LMS Program':
			return { name: 'ProgramDetail', params: { programName: result.name } }
		case 'Course Lesson':
			return getLessonRoute(result)
		case 'LMS Quiz':
			// Managers edit the quiz. A learner opens the lesson that hosts it
			// instead, so the course rules — sequential unlocking included — still
			// apply; a direct link to the quiz page would bypass them.
			return isManager
				? { name: 'QuizForm', params: { quizID: result.name } }
				: getLessonRoute(result)
		case 'LMS Assignment':
			// There is no per-assignment page: the list pre-filters by title.
			return { name: 'Assignments', query: { title: plainText(result.title) } }
		default:
			return null
	}
}
