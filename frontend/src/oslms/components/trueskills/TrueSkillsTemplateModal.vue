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
								'Usata per generare il PNG dell\'OpenBadge. PNG, JPG, WebP o GIF (no SVG). Senza immagine sarà scaricabile solo il JSON-LD.',
							)
						}}
					</p>
					<div class="flex items-center gap-3">
						<Button
							:loading="imageBusy"
							:label="
								form.imageBase64
									? __('Sostituisci immagine')
									: __('Carica immagine')
							"
							@click="() => imageInput?.click()"
						/>
						<div
							v-if="form.imageBase64"
							class="flex items-center gap-2 text-sm text-ink-gray-6"
						>
							<span class="truncate max-w-[180px]">{{ imageName }}</span>
							<button
								type="button"
								class="text-ink-red-5"
								@click="removeImage"
							>
								{{ __('Rimuovi') }}
							</button>
						</div>
					</div>
					<FormControl
						v-if="!form.imageBase64"
						v-model="form.imageUrl"
						:label="__('oppure path immagine già su TrueSkill (opzionale)')"
						placeholder="4/2/template_xxxxxxxx.png"
					/>
					<input
						ref="imageInput"
						type="file"
						accept="image/png,image/jpeg,image/webp,image/gif"
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
const imageBusy = ref(false)
const imageName = ref('')

const ALLOWED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif']
const MAX_IMAGE_BYTES = 25 * 1024 * 1024 // base64 grows ~33%; stays under the ~30 MB body limit

const blankForm = () => ({
	name: '',
	description: '',
	type: 'Certificate',
	isEnabled: false,
	isVisible: false,
	badgeUrl: '',
	imageUrl: '',
	imageBase64: '',
	imageFileName: '',
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
		imageBusy.value = false
	}
})

const onImageSelected = (event) => {
	const file = event.target.files?.[0]
	event.target.value = '' // allow re-selecting the same file
	if (!file) return
	errorMessage.value = null
	if (!ALLOWED_IMAGE_TYPES.includes(file.type)) {
		errorMessage.value = __('Formato non supportato. Usa PNG, JPG, WebP o GIF (no SVG).')
		return
	}
	if (file.size > MAX_IMAGE_BYTES) {
		errorMessage.value = __('Immagine troppo grande (max ~25 MB).')
		return
	}
	imageBusy.value = true
	const reader = new FileReader()
	reader.onload = () => {
		// data-URI (data:image/...;base64,...): TrueSkill accepts it directly.
		form.imageBase64 = reader.result
		form.imageFileName = file.name
		imageName.value = file.name
		imageBusy.value = false
	}
	reader.onerror = () => {
		errorMessage.value = __('Lettura del file fallita.')
		imageBusy.value = false
	}
	reader.readAsDataURL(file)
}

const removeImage = () => {
	form.imageBase64 = ''
	form.imageFileName = ''
	imageName.value = ''
}

const buildPayload = () => {
	const payload = {
		name: form.name?.trim(),
		description: form.description?.trim() || undefined,
		type: form.type,
		isEnabled: !!form.isEnabled,
		isVisible: !!form.isVisible,
	}
	// imageBase64 takes precedence over imageUrl (server-side rule).
	if (form.imageBase64) {
		payload.imageBase64 = form.imageBase64
		if (form.imageFileName) payload.imageFileName = form.imageFileName
	} else if (form.imageUrl?.trim()) {
		payload.imageUrl = form.imageUrl.trim()
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
