<template>
	<div class="flex flex-col h-full text-base overflow-y-auto">
		<div class="flex items-center justify-between mb-2">
			<div class="flex items-center space-x-2">
				<div class="text-xl font-semibold leading-none text-ink-gray-9">
					{{ __(label) }}
				</div>
				<Badge
					v-if="isDirty"
					:label="__('Non salvato')"
					variant="subtle"
					theme="orange"
				/>
			</div>
			<Button variant="solid" :loading="saving" @click="saveAll">
				{{ __('Salva') }}
			</Button>
		</div>
		<div class="text-ink-gray-6 leading-5 mb-6">
			{{ __(description) }}
		</div>

		<section v-for="p in prompts" :key="p.name" class="mb-8">
			<template v-if="p.res.doc">
				<SettingFields :sections="p.sections" :data="p.res.doc" />
				<p
					v-if="p.res.doc.available_placeholders"
					class="text-p-sm text-ink-gray-5 mt-2"
				>
					{{ __('Segnaposto disponibili') }}:
					<span class="font-mono">{{ p.res.doc.available_placeholders }}</span>
				</p>
			</template>
			<p v-else-if="!p.res.get.loading" class="text-p-sm text-ink-orange-5">
				{{
					__('Prompt non trovato: {0}. Esegui la migrazione del sito.').format(
						p.name,
					)
				}}
			</p>
		</section>
	</div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { Badge, Button, createDocumentResource, toast } from 'frappe-ui'
import { translate as __ } from '@/translation'
import SettingFields from '@/components/Settings/SettingFields.vue'

defineProps({
	label: { type: String, required: true },
	description: { type: String, default: '' },
})

// Editable field set per prompt. `enabled` off = the loader falls back to the
// built-in default prompt, so surface that clearly.
function buildSections(title) {
	return [
		{
			label: title,
			columns: [
				{
					fields: [
						{
							label: __('Abilitato'),
							name: 'enabled',
							type: 'checkbox',
							description: __(
								'Se disattivo, viene usato il prompt di default incorporato nel codice.',
							),
						},
						{
							label: __('System prompt'),
							name: 'system_template',
							type: 'textarea',
							rows: 16,
							description: __(
								'Istruzioni di sistema principali per l\'AI.',
							),
						},
						{
							label: __('User template'),
							name: 'user_template',
							type: 'textarea',
							rows: 6,
							description: __(
								'Messaggio utente (opzionale). Lascia vuoto se non usato.',
							),
						},
						{
							label: __('Temperatura'),
							name: 'temperature',
							type: 'number',
							description: __(
								'Creatività delle risposte (0 = deterministico).',
							),
						},
						{
							label: __('Max tokens'),
							name: 'max_tokens',
							type: 'number',
							description: __('Lunghezza massima della risposta.'),
						},
					],
				},
			],
		},
	]
}

// The LMSA Prompt Template rows exposed in this panel. The record `name`
// equals its `purpose` (autoname: field:purpose), so we address them directly.
// Add a row here to surface another prompt.
const PROMPTS = [
	{ name: 'tutor', title: __('Tutor AI') },
	{ name: 'debrief', title: __('Coach AI') },
	{ name: 'role_play', title: __('Personaggio simulazione (role-play)') },
	{
		name: 'scenario_variant_generator',
		title: __('Generatore variante scenario'),
	},
]

const prompts = PROMPTS.map((p) => ({
	name: p.name,
	title: p.title,
	sections: buildSections(p.title),
	res: createDocumentResource({
		doctype: 'LMSA Prompt Template',
		name: p.name,
		fields: ['*'],
		auto: true,
	}),
}))

const saving = ref(false)
const isDirty = computed(() => prompts.some((p) => p.res.isDirty))

async function saveAll() {
	saving.value = true
	try {
		const jobs = prompts
			.filter((p) => p.res.isDirty)
			.map((p) => p.res.save.submit())
		if (!jobs.length) {
			toast.success(__('Nessuna modifica da salvare'))
			return
		}
		await Promise.all(jobs)
		toast.success(__('Prompt salvati'))
	} catch (err) {
		toast.error(err.messages?.[0] || err.message || __('Salvataggio fallito'))
	} finally {
		saving.value = false
	}
}
</script>
