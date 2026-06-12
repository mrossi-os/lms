<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Crea template TrueSkill'),
			size: 'lg',
			actions: [
				{
					label: __('Crea'),
					variant: 'solid',
					loading: createTemplateResource.loading,
					onClick: ({ close }) => submit(close),
				},
			],
		}"
	>
		<template #body-content>
			<div class="space-y-4">
				<FormControl
					v-model="form.name"
					:label="__('Nome')"
					:required="true"
					:maxlength="255"
				/>
				<FormControl
					v-model="form.description"
					type="textarea"
					:rows="3"
					:label="__('Descrizione')"
					:maxlength="255"
				/>
				<FormControl
					v-model="form.type"
					type="select"
					:label="__('Tipo')"
					:options="typeOptions"
					:required="true"
				/>
				<FormControl
					v-if="form.type === 'Openbadge'"
					v-model="form.badgeUrl"
					:label="__('Badge URL')"
					:description="
						__(
							'URL pubblico del badge OpenBadge — richiesto per i template di tipo OpenBadge.',
						)
					"
					:required="true"
				/>
				<div class="space-y-2">
					<span class="block text-xs text-ink-gray-5">
						{{ __('Immagine del badge') }}
					</span>
					<p class="text-p-sm text-ink-gray-5">
						{{
							__(
								"Caricata su TrueSkill e usata per generare il PNG dell'OpenBadge. Senza immagine sarà scaricabile solo il JSON-LD.",
							)
						}}
					</p>
					<div class="flex items-center gap-3">
						<Button
							:loading="imageUploading"
							:label="
								form.imageUrl
									? __('Sostituisci immagine')
									: __('Carica immagine')
							"
							@click="() => imageInput?.click()"
						/>
						<div
							v-if="form.imageUrl"
							class="flex items-center gap-2 text-sm text-ink-gray-6"
						>
							<span class="truncate max-w-[180px]">
								{{ imageName || form.imageUrl }}
							</span>
							<button
								type="button"
								class="text-ink-red-5"
								@click="removeImage"
							>
								{{ __('Rimuovi') }}
							</button>
						</div>
					</div>
					<input
						ref="imageInput"
						type="file"
						accept="image/*"
						class="hidden"
						@change="onImageSelected"
					/>
				</div>
				<div class="grid grid-cols-2 gap-3">
					<Switch
						size="sm"
						class="card p-3"
						v-model="form.isEnabled"
						:label="__('Abilitato')"
						:description="__('Il template può essere usato per emettere certificati.')"
					/>
					<Switch
						size="sm"
						class="card p-3"
						v-model="form.isVisible"
						:label="__('Visibile')"
						:description="__('Il template è visibile agli utenti finali.')"
					/>
				</div>
				<div
					v-if="errorMessage"
					class="text-sm text-ink-red-5 bg-surface-red-1 rounded-md p-2"
				>
					{{ errorMessage }}
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { Dialog, FormControl, Button, createResource, toast } from 'frappe-ui'
import Switch from '@/components/Controls/Switch.vue'

const show = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['created'])

const errorMessage = ref(null)
const imageInput = ref(null)
const imageUploading = ref(false)
const imageName = ref('')

const blankForm = () => ({
	name: '',
	description: '',
	type: 'Certificate',
	isEnabled: false,
	isVisible: false,
	badgeUrl: '',
	imageUrl: '',
})

const form = reactive(blankForm())

const typeOptions = [
	{ label: __('Certificate'), value: 'Certificate' },
	{ label: __('OpenBadge'), value: 'Openbadge' },
]

watch(show, (open) => {
	if (open) {
		Object.assign(form, blankForm())
		errorMessage.value = null
		imageName.value = ''
		imageUploading.value = false
	}
})

const onImageSelected = async (event) => {
	const file = event.target.files?.[0]
	event.target.value = '' // allow re-selecting the same file
	if (!file) return
	if (!file.type?.startsWith('image/')) {
		errorMessage.value = __('Seleziona un file immagine.')
		return
	}
	imageUploading.value = true
	errorMessage.value = null
	try {
		const body = new FormData()
		body.append('file', file)
		const res = await fetch(
			'/api/method/os_lms.os_lms.trueskills.api.upload_template_image',
			{
				method: 'POST',
				headers: { 'X-Frappe-CSRF-Token': window.csrf_token },
				body,
			},
		)
		const result = (await res.json())?.message || {}
		if (!result.ok) {
			errorMessage.value = result.error || __('Caricamento immagine fallito.')
			return
		}
		form.imageUrl = result.url
		imageName.value = file.name
	} catch (err) {
		errorMessage.value = String(err)
	} finally {
		imageUploading.value = false
	}
}

const removeImage = () => {
	form.imageUrl = ''
	imageName.value = ''
}

const buildPayload = () => {
	const payload = {
		name: form.name?.trim(),
		description: form.description?.trim() || undefined,
		type: form.type,
		isEnabled: !!form.isEnabled,
		isVisible: !!form.isVisible,
		imageUrl: form.imageUrl || undefined,
	}
	if (form.type === 'Openbadge') {
		payload.badge = {
			url: form.badgeUrl?.trim(),
			type: 'Achievement',
			criteria: {},
			alignments: [],
			resultDescriptions: [],
		}
	}
	return payload
}

const createTemplateResource = createResource({
	url: 'os_lms.os_lms.trueskills.api.create_template',
	onSuccess(data) {
		if (!data?.ok) {
			errorMessage.value = data?.error || __('Creazione template fallita.')
			return
		}
		toast.success(__('Template creato'))
		emit('created', data.template)
		show.value = false
	},
	onError(err) {
		errorMessage.value = err.messages?.[0] || err.message || String(err)
	},
})

const submit = (close) => {
	errorMessage.value = null
	if (!form.name?.trim()) {
		errorMessage.value = __('Il nome è obbligatorio.')
		return
	}
	if (form.type === 'Openbadge' && !form.badgeUrl?.trim()) {
		errorMessage.value = __('Per gli OpenBadge serve un Badge URL.')
		return
	}
	createTemplateResource.submit(
		{ payload: buildPayload() },
		{
			onSuccess(data) {
				if (data?.ok) close?.()
			},
		},
	)
}
</script>
