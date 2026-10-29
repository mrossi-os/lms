<template>
	<div class="flex flex-col h-full text-base overflow-y-auto">
		<div class="">
			<div class="flex items-center justify-between mb-2">
				<div class="flex items-center space-x-2">
					<div class="text-xl font-semibold leading-none text-ink-gray-9">
						{{ __(label) }}
					</div>
					<Badge
						v-if="limits.isDirty"
						:label="__('Not Saved')"
						variant="subtle"
						theme="orange"
					/>
				</div>
				<Button variant="solid" :loading="limits.save.loading" @click="update">
					{{ __('Update') }}
				</Button>
			</div>
			<div class="text-ink-gray-6 leading-5">
				{{ __(description) }}
			</div>
		</div>

		<SettingFields v-if="limits.doc" :sections="sections" :data="limits.doc" />
	</div>
</template>

<script setup>
import { computed } from 'vue'
import { Button, Badge, createDocumentResource, toast } from 'frappe-ui'
import SettingFields from '@/components/Settings/SettingFields.vue'

// Limits on what one student may spend on AI simulations (OWASP H-3/H-4). Kept
// out of the AI tab: that one edits LMSA Settings, which holds the provider keys
// and is for administrators only; this single is open to the Gestore too.
defineProps({
	label: {
		type: String,
		required: true,
	},
	description: {
		type: String,
	},
})

const limits = createDocumentResource({
	doctype: 'LMSA Simulation Limits',
	name: 'LMSA Simulation Limits',
	fields: ['*'],
	cache: 'LMSA Simulation Limits',
	auto: true,
})

const sections = computed(() => [
	{
		label: __('Chat'),
		columns: [
			{
				fields: [
					{
						label: __('Messaggi al minuto'),
						name: 'chat_messages_per_minute',
						type: 'number',
						description: __(
							'Messaggi, scritti o vocali, che uno studente può inviare in un minuto.',
						),
					},
					{
						label: __('Caratteri per messaggio'),
						name: 'max_message_chars',
						type: 'number',
						description: __('Lunghezza massima di un messaggio dello studente.'),
					},
					{
						label: __('Messaggi per sessione'),
						name: 'max_messages_per_session',
						type: 'number',
						description: __(
							"Messaggi dello studente in una sessione. All'ultimo il personaggio chiude la conversazione.",
						),
					},
				],
			},
			{
				fields: [
					{
						label: __('Avvii all’ora'),
						name: 'session_starts_per_hour',
						type: 'number',
						description: __(
							'Simulazioni che uno studente può avviare o ripetere in un’ora.',
						),
					},
					{
						label: __('Sessioni al giorno'),
						name: 'daily_sessions_per_user',
						type: 'number',
						description: __('Sessioni di simulazione che uno studente può aprire in un giorno.'),
					},
				],
			},
		],
	},
	{
		label: __('Voce'),
		columns: [
			{
				fields: [
					{
						label: __('Connessioni per sessione'),
						name: 'voice_tokens_per_session',
						type: 'number',
						description: __(
							'Collegamenti al servizio vocale per una sessione: il primo più le riconnessioni.',
						),
					},
					{
						label: __('Connessioni all’ora'),
						name: 'voice_tokens_per_hour',
						type: 'number',
						description: __(
							'Collegamenti al servizio vocale che uno studente può ottenere in un’ora.',
						),
					},
				],
			},
			{
				fields: [
					{
						label: __('Durata massima in secondi'),
						name: 'voice_max_session_seconds',
						type: 'number',
						description: __(
							'Durata massima di una sessione vocale. Con Gemini la chiamata viene chiusa dal servizio; con OpenAI vale solo il timer della piattaforma.',
						),
					},
				],
			},
		],
	},
])

const update = () => {
	limits.save.submit(
		{},
		{
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}
</script>
