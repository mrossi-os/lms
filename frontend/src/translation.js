import { createResource } from 'frappe-ui'
import { ref } from 'vue'

/**
 * Flips once the messages are in. `translate()` reads a plain global, so a
 * `computed()` that builds a label evaluates before the fetch resolves and then
 * caches the English fallback forever — its dependencies never change again.
 * Read this ref inside such a computed to make it recompute when they land.
 */
export const translationsLoaded = ref(Boolean(window.translatedMessages))

export default function translationPlugin(app) {
	app.config.globalProperties.__ = translate
	window.__ = translate
	if (!window.translatedMessages) fetchTranslations()
}

export function translate(message) {
	let translatedMessages = window.translatedMessages || {}
	let translatedMessage = translatedMessages[message] || message

	const hasPlaceholders = /{\d+}/.test(message)
	if (!hasPlaceholders) {
		return translatedMessage
	}
	return {
		format: function (...args) {
			return translatedMessage.replace(
				/{(\d+)}/g,
				function (match, number) {
					return typeof args[number] != 'undefined'
						? args[number]
						: match
				},
			)
		},
	}
}

function fetchTranslations(lang) {
	createResource({
		url: 'lms.lms.api.get_translations',
		cache: 'translations',
		auto: true,
		transform: (data) => {
			window.translatedMessages = data
			translationsLoaded.value = true
		},
	})
}
