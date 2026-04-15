import { useTimeAgo } from '@vueuse/core'

export * from '../../utils/index.js'

const TIME_AGO_MESSAGES = {
	justNow: () => __('just now'),
	past: (n) => n,
	future: (n) => n,
	invalid: '',
	second: (n, past) =>
		past ? __('a few seconds ago') : __('in a few seconds'),
	minute: (n, past) =>
		past
			? n === 1
				? __('1 minute ago')
				: __('{0} minutes ago').format(n)
			: n === 1
				? __('in 1 minute')
				: __('in {0} minutes').format(n),
	hour: (n, past) =>
		past
			? n === 1
				? __('1 hour ago')
				: __('{0} hours ago').format(n)
			: n === 1
				? __('in 1 hour')
				: __('in {0} hours').format(n),
	day: (n, past) =>
		past
			? n === 1
				? __('yesterday')
				: __('{0} days ago').format(n)
			: n === 1
				? __('tomorrow')
				: __('in {0} days').format(n),
	week: (n, past) =>
		past
			? n === 1
				? __('1 week ago')
				: __('{0} weeks ago').format(n)
			: n === 1
				? __('in 1 week')
				: __('in {0} weeks').format(n),
	month: (n, past) =>
		past
			? n === 1
				? __('1 month ago')
				: __('{0} months ago').format(n)
			: n === 1
				? __('in 1 month')
				: __('in {0} months').format(n),
	year: (n, past) =>
		past
			? n === 1
				? __('1 year ago')
				: __('{0} years ago').format(n)
			: n === 1
				? __('in 1 year')
				: __('in {0} years').format(n),
}

export function timeAgo(date) {
	return useTimeAgo(date, { messages: TIME_AGO_MESSAGES }).value
}
