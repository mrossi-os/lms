import { createResource } from 'frappe-ui'
import { ref } from 'vue'

const ITALIAN_FALLBACK_MESSAGES = {
        'All Courses': 'Tutti i corsi',
        Live: 'Attivi',
        New: 'Nuovo',
        Upcoming: 'In arrivo',
        Created: 'Creati',
        Unpublished: 'Non pubblicati',
        'Search by Title': 'Cerca per titolo',
        Category: 'Categoria',
        Certification: 'Certificazione',
}

const translationMessages = ref(window.translatedMessages || {})
const translationVersion = ref(0)
const translationPriorityByKey = new Map()
const requestedLanguages = new Set()
let previousItalianPreference = isItalianPreferred()
let listenersInitialized = false

export default function translationPlugin(app) {
        app.config.globalProperties.__ = translate
        window.__ = translate
        window.translatedMessages = translationMessages.value

        queueTranslationFetches()
        setTimeout(queueTranslationFetches, 1000)
        setTimeout(queueTranslationFetches, 3000)

        if (!listenersInitialized) {
                listenersInitialized = true
                window.addEventListener('focus', queueTranslationFetches)
	}
}

function translate(message) {
        // Track translation updates so components re-render as soon as fresh messages arrive.
        void translationVersion.value

        let translatedMessage =
                translationMessages.value[message] || getLocalFallback(message) || message

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
				}
			)
		},
	}
}

function getLocalFallback(message) {
        if (isItalianPreferred()) {
                return ITALIAN_FALLBACK_MESSAGES[message]
        }
}

function queueTranslationFetches() {
        syncLanguagePreferenceState()

        const languages = getLanguageCandidates()
        if (!languages.length) {
                fetchTranslations()
                return
        }

        for (const lang of languages) {
		fetchTranslations(lang)
        }
}

function syncLanguagePreferenceState() {
        const italianPreferred = isItalianPreferred()
        if (italianPreferred === previousItalianPreference) {
                return
        }

        previousItalianPreference = italianPreferred
        translationPriorityByKey.clear()
        requestedLanguages.clear()
}

function fetchTranslations(lang) {
        const normalizedLang = normalizeLang(lang)
        const languageKey = normalizedLang || '__default__'

        if (requestedLanguages.has(languageKey)) {
                return
        }

        requestedLanguages.add(languageKey)

        createResource({
                url: 'lms.lms.api.get_translations',
                method: 'GET',
                cache: false,
                params: normalizedLang ? { lang: normalizedLang } : undefined,
                auto: true,
                onError: () => {
                        requestedLanguages.delete(languageKey)
                },
                transform: (data) => {
                        mergeTranslations(data, normalizedLang)
                        return data
                },
        })
}

function mergeTranslations(data, language) {
        if (!data || typeof data !== 'object') {
                return
        }

        const priority = getTranslationPriority(language)
	let updated = false
	const nextMessages = { ...translationMessages.value }

        for (const [message, translated] of Object.entries(data)) {
		if (translated == null || translated === '') {
			continue
		}

		const existingPriority = translationPriorityByKey.get(message) || 0
		if (existingPriority > priority) {
			continue
		}

		if (nextMessages[message] !== translated || existingPriority !== priority) {
			nextMessages[message] = translated
			translationPriorityByKey.set(message, priority)
			updated = true
		}
	}

	if (!updated) {
		return
	}

	translationMessages.value = nextMessages
	window.translatedMessages = translationMessages.value
	translationVersion.value += 1
}

function getLanguageCandidates() {
        const languages = new Set()

        for (const source of collectLanguageSources()) {
                const normalized = normalizeLang(source)
                if (!normalized) {
                        continue
                }

                languages.add(normalized)

                const [baseLanguage] = normalized.split('_')
                if (baseLanguage) {
                        languages.add(baseLanguage)
                }

                if (isItalianLanguage(normalized)) {
                        languages.add('it_IT')
                        languages.add('it')
                }
        }

        return Array.from(languages)
}

function getTranslationPriority(language) {
	if (isItalianPreferred()) {
                return isItalianLanguage(language) ? 2 : 1
	}

        return 1
}

function isItalianPreferred() {
	return collectLanguageSources().some(isItalianLanguage)
}

function collectLanguageSources() {
        return [
                window.frappe?.boot?.lang,
                window.frappe?.boot?.user?.language,
                window.frappe?.boot?.user?.lang,
                window.lang,
                document?.documentElement?.lang,
                navigator?.language,
        ].filter(Boolean)
}

function isItalianLanguage(lang) {
        const normalized = normalizeLang(lang)
        return normalized === 'it' || normalized?.startsWith('it_')
}

function normalizeLang(lang) {
        if (!lang || typeof lang !== 'string') {
                return undefined
        }

        return lang.replace(/-/g, '_')
}
