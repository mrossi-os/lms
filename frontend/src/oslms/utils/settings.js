import { markRaw } from 'vue'
import { translate as __ } from '@/translation'
import AISettings from '@/oslms/components/ai/Settings/AISettings.vue'
import PromptSettings from '@/oslms/components/ai/Settings/PromptSettings.vue'
import TrueSkillsSettings from '@/oslms/components/trueskills/TrueSkillsSettings.vue'

// AI provider options (module-specific; moved out of core Settings.vue).
const aiProviders = [
	{ label: 'OpenAI', value: 'openai' },
	{ label: 'Google Gemini', value: 'gemini' },
	{ label: 'Anthropic', value: 'anthropic' },
	{ label: 'DeepSeek', value: 'deepseek' },
]

// Audio (STT/TTS) providers. DeepSeek and Anthropic have no audio API.
const audioProviders = [
	{ label: 'OpenAI', value: 'openai' },
	{ label: 'Gemini', value: 'gemini' },
]

const realTimeProviders = [
	{ label: 'OpenAI', value: 'openai' },
	{ label: 'Gemini', value: 'gemini' },
];

const turnDetectionOptions = [
	{ label: 'Basato sull\'audio', value: 'server_vad' },
	{ label: 'Basato sulla semantica', value: 'semantic_vad' },
];

// Extra settings tabs contributed by the os_lms module. Injected into
// Settings.vue's `tabsStructure` via spread so the core file stays close to
// upstream and future merges stay conflict-free. This is a factory (not a
// static const) so __() labels and condition() re-evaluate reactively inside
// the computed; `isAdministrator` is passed in to reuse the core role logic.
export function buildOslmsSettingsTabs({ isAdministrator } = {}) {
	return [
		// TrueSkills API — previously an item inside the core "Configuration"
		// group; wrapped in a hideLabel group to keep it rendering as a bare tab.
		{
			key: 'TrueSkills',
			hideLabel: true,
			condition: isAdministrator,
			items: [
				{
					key: 'TrueSkills API',
					label: __('TrueSkills API'),
					icon: 'KeyRound',
					description: __(
						'Configure the TrueSkills API integration for your learning system',
					),
					condition: isAdministrator,
					template: markRaw(TrueSkillsSettings),
					sections: [
						{
							label: __('TrueSkills API'),
							columns: [
								{
									fields: [
										{
											label: __('Enable TrueSkills API'),
											name: 'trueskills_api_enabled',
											type: 'checkbox',
											description: __(
												'If enabled, the TrueSkills API integration will be active.',
											),
										},
										{
											label: __('API Key'),
											name: 'trueskills_api_key',
											type: 'password',
											description: __(
												'The API key used to authenticate requests to the TrueSkills API.',
											),
										},
										{
											label: __('API Endpoint'),
											name: 'trueskills_api_endpoint',
											type: 'text',
											description: __(
												'Base URL of the TrueSkills API (e.g. https://api.trueskills.example/v1).',
											),
										},
									],
								},
							],
						},
					],
				},
			],
		},
		{
			key: 'Configurazioni',
			label: __('Configurazioni'),
			hideLabel: false,
			condition: isAdministrator,
			items: [
				{
					key: 'Corsi',
					label: __('Corsi'),
					icon: 'BookOpen',
					description: __('Impostazioni relative ai corsi'),
					condition: isAdministrator,
					sections: [],
				},
				{
					key: 'Classi',
					label: __('Classi'),
					icon: 'Laptop',
					description: __('Impostazioni relative alle classi'),
					condition: isAdministrator,
					sections: [
						{
							label: __('Classi Live'),
							columns: [
								{
									fields: [
										{
											label: __('Abilita Classi Live'),
											name: 'enable_live_classes',
											type: 'checkbox',
											description: __(
												'Se attivo, la tab Classi Live e le funzionalità correlate sono visibili a tutti gli utenti.',
											),
										},
									],
								},
							],
						},
					],
				},
			],
		},
		{
			key: 'AI',
			label: __('AI'),
			hideLabel: false,
			items: [
				{
					key: 'AI',
					label: __('AI'),
					icon: 'BrainCircuit',
					description: __(
						'Configure AI assistant settings for your learning system',
					),
					template: markRaw(AISettings),
					condition: isAdministrator,
					sections: [
						{
							label: __('Rag Tutor'),
							columns: [
								{
									fields: [
										{
											label: __('Enabled'),
											name: 'enabled',
											type: 'checkbox',
											description: __(
												'Enable AI features for your learning system.',
											),
										},
									],
								},
								{
									fields: [
										{
											label: __('Embedding Model'),
											name: 'embedding_model',
											type: 'text',
											description: __(
												'The model used to generate embeddings for content indexing.',
											),
										},
										{
											label: __('LLM Model'),
											name: 'llm_model',
											type: 'text',
											description: __(
												'The model used to chatbot.',
											),
										},
										{
											label: __('Chunk Size'),
											name: 'chunk_size',
											type: 'number',
											description: __(
												'Number of characters per text chunk for indexing.',
											),
										},
										{
											label: __('Chunk Overlap'),
											name: 'chunk_overlap',
											type: 'number',
											description: __(
												'Character overlap between consecutive chunks.',
											),
										},
										{
											label: __('Top K'),
											name: 'top_k',
											type: 'number',
											description: __(
												'Number of relevant chunks to retrieve for context.',
											),
										},
									],
								},
							],
						},
						{
							label: __('Api Keys'),
							columns: [
								{
									fields: [
										{
											label: __('OpenAI Key'),
											name: 'openai_key',
											type: 'text',
										},
										{
											label: __('OpenAI Base URL'),
											name: 'openai_base_url',
											type: 'text',
											description: __(
												'Optional override for OpenAI-compatible endpoints (Ollama, vLLM, LM Studio, ...).',
											),
										},

										{
											label: __('Google Gemini API Key'),
											name: 'gemini_key',
											type: 'text',
										},
									],
								},
								{
									fields: [
										{
											label: __('Vimeo Api Key'),
											name: 'vimeo_api_key',
											type: 'text',
											description: __(
												'Api vimeo for transcript.',
											),
										},
										{
											label: __('DeepSeek API Key'),
											name: 'deepseek_key',
											type: 'text',
										},
										{
											label: __('Anthropic API Key'),
											name: 'anthropic_key',
											type: 'text',
										},
									],
								},
							],
						},
						{
							label: __('AI Simulation'),
							columns: [
								{
									fields: [
										{
											label: __('Enabled'),
											name: 'simulations_enabled',
											type: 'checkbox',
											description: __(
												'Enable AI Simulations for your learning system.',
											),
										},
										{
											label: __('Chat LLM Provider'),
											name: 'simulation_chat_provider',
											type: 'select',
											options: aiProviders,
										},
										{
											label: __('Chat Model'),
											name: 'simulation_chat_model',
											type: 'text',
										},
									],
								},
								{
									fields: [
										{
											label: __('Default LLM Provider'),
											name: 'simulation_provider_default',
											type: 'select',
											options: aiProviders,
										},
										{
											label: __('Debrief LLM Provider'),
											name: 'simulation_debrief_provider',
											type: 'select',
											options: aiProviders,
										},
										{
											label: __('Debrief Model'),
											name: 'simulation_debrief_model',
											type: 'text',
										},
									],
								},
								{
									fields: [
										{
											label: __('Abilita Simulazioni vocali realtime'),
											name: 'realtime_enabled',
											type: 'checkbox'
										},
										{
											label: __('Provider LLM per Simulazioni vocali'),
											name: 'realtime_provider',
											type: 'select',
											options: realTimeProviders,
										},
										{
											label: __('Modello simulazioni vocali'),
											name: 'realtime_model',
											type: 'text',
											description: __(
												'Modello da utilizzare per le simulazioni vocali. Deve essere compatibile con il provider selezionato.',
											),
										},
										{
											label: __('Voce simulazioni vocali'),
											name: 'realtime_voice',
											type: 'text',
											description: __(
												'Vooce da utilizzare per le simulazioni vocali. Deve essere compatibile con il provider selezionato.',
											),
										},
										{
											label: __('Turn detection'),
											name: 'turn_detection',
											type: 'select',
											options: turnDetectionOptions,
										},
										{
											label: __('Sessione massima in secondi'),
											name: 'realtime_max_session_seconds',
											type: 'number',
											description: __(
												'Secondi massimi che una sessione può durare.',
											),
										},
									]
								}
							],
						},
						{
							label: __('Audio (dettatura e lettura vocale)'),
							columns: [
								{
									fields: [
										{
											label: __('Abilita dettatura vocale'),
											name: 'stt_enabled',
											type: 'checkbox',
											description: __(
												'Attiva il microfono per dettare i messaggi invece di digitarli.',
											),
										},
										{
											label: __('Provider servizio per conversione audio/testo'),
											name: 'stt_provider',
											type: 'select',
											options: audioProviders,
										},
										{
											label: __('Modello dettatura vocale'),
											name: 'stt_model',
											type: 'text',
											placeholder:
												'gpt-4o-mini-transcribe',
											description: __(
												'Modello llm da utilizzare per la conversione audio/testo. Il modello deve essere compatibile con il provider selezionato.',
											),
										},
									],
								},
								{
									fields: [
										{
											label: __('Abilita lettura vocale dei messaggi'),
											name: 'tts_enabled',
											type: 'checkbox',
											description: __(
												'Attiva la voce che legge automaticamente le risposte.',
											),
										},
										{
											label: __('Provider servizio per conversione testo/audio'),
											name: 'tts_provider',
											type: 'select',
											options: audioProviders,
										},
										{
											label: __('Modello lettura vocale'),
											name: 'tts_model',
											type: 'text',
											placeholder: 'gpt-4o-mini-tts',
											description: __(
												'Modello di sintesi vocale; deve corrispondere al provider selezionato.',
											),
										},
										{
											label: __('Voce lettura vocale'),
											name: 'tts_voice',
											type: 'text',
											placeholder: 'alloy',
											description: __(
												'Voce da utilizzare per la sintesi vocale; deve corrispondere al provider selezionato.',
											),
										}
									],
								},
							],
						},
					],
				},
			],
		},
		// AI system prompts (tutor + coach). Admin-only for now via
		// `condition: isAdministrator`; relax the condition to open it to
		// other roles later.
		{
			key: 'Prompt AI',
			hideLabel: true,
			condition: isAdministrator,
			items: [
				{
					key: 'Prompt AI',
					label: __('Prompt AI'),
					icon: 'ScrollText',
					description: __(
						'Modifica i system prompt delle AI: Tutor, Coach e simulazioni (personaggio e generatore di scenario).',
					),
					condition: isAdministrator,
					template: markRaw(PromptSettings),
				},
			],
		},
	]
}
