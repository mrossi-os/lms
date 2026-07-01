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
					<FormControl
						v-if="course"
						type="checkbox"
						v-model="useCourseCertificate"
						:label="__('Usa il certificato del corso come immagine')"
					/>
					<div v-if="useCourseCertificate" class="space-y-2">
						<p class="text-p-sm text-ink-gray-5">
							{{
								__(
									'Il certificato di completamento del corso viene reso in PNG e usato come immagine del badge.',
								)
							}}
						</p>
						<img
							v-if="form.imageBase64"
							:src="form.imageBase64"
							alt=""
							class="max-h-40 rounded border border-outline-gray-2"
						/>
					</div>
					<template v-else>
						<FilePicker
							v-model="imageFile"
							:label="__('Immagine del badge')"
							:allowedExtensions="['png', 'jpg', 'jpeg', 'webp', 'gif']"
							:placeholder="__('Scegli un\'immagine dalla libreria…')"
							@update:fileUrl="onImagePicked"
						/>
						<p class="text-p-sm text-ink-gray-5">
							{{
								__(
									'Scegli un\'immagine già caricata nella LMS. Serve per generare il PNG dell\'OpenBadge; senza immagine sarà scaricabile solo il JSON-LD.',
								)
							}}
						</p>
					</template>
					<p v-if="imageBusy" class="text-p-sm text-ink-gray-5">
						{{ __('Conversione immagine…') }}
					</p>
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
import { Dialog, FormControl, createResource, toast } from 'frappe-ui'
import Switch from '@/components/Controls/BooleanSwitch.vue'
import FilePicker from '@/components/Controls/FilePicker.vue'

const show = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['created'])
const props = defineProps({
	course: { type: String, default: '' },
})

const errorMessage = ref(null)
const imageFile = ref('')
const imageBusy = ref(false)
const useCourseCertificate = ref(false)

const certificateImageResource = createResource({
	url: 'os_lms.os_lms.trueskills.api.render_certificate_image',
})

const MAX_IMAGE_BYTES = 25 * 1024 * 1024 // base64 grows ~33%; stays under the ~30 MB body limit

const blankForm = () => ({
	name: '',
	description: '',
	type: 'Certificate',
	isEnabled: false,
	isVisible: false,
	badgeUrl: '',
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
		imageFile.value = ''
		useCourseCertificate.value = false
		imageBusy.value = false
	}
})

// Clearing the FilePicker drops the image too (unless the certificate is used).
watch(imageFile, (val) => {
	if (!val && !useCourseCertificate.value) {
		form.imageBase64 = ''
		form.imageFileName = ''
	}
})

// "Use the course certificate": render the completion certificate to a PNG on
// the backend and use it as the badge image; clear back to the FilePicker when
// unchecked.
watch(useCourseCertificate, async (val) => {
	if (!val) {
		form.imageBase64 = ''
		form.imageFileName = ''
		return
	}
	imageFile.value = ''
	errorMessage.value = null
	imageBusy.value = true
	try {
		const data = await certificateImageResource.submit({ course: props.course })
		if (!data?.ok) {
			errorMessage.value =
				data?.error || __('Generazione immagine certificato fallita.')
			form.imageBase64 = ''
			form.imageFileName = ''
			return
		}
		form.imageBase64 = data.image_base64
		form.imageFileName = data.filename || 'certificate.png'
	} catch (err) {
		errorMessage.value = err?.messages?.[0] || err?.message || String(err)
		form.imageBase64 = ''
		form.imageFileName = ''
	} finally {
		imageBusy.value = false
	}
})

const blobToDataUri = (blob) =>
	new Promise((resolve, reject) => {
		const reader = new FileReader()
		reader.onload = () => resolve(reader.result)
		reader.onerror = reject
		reader.readAsDataURL(blob)
	})

// TrueSkill can't read our URLs, so fetch the bytes and send them inline as
// base64 (data-URI). Shared by the FilePicker and the course image.
const fetchImageToBase64 = async (url) => {
	if (!url) return
	errorMessage.value = null
	imageBusy.value = true
	try {
		const res = await fetch(url)
		if (!res.ok) throw new Error('HTTP ' + res.status)
		const blob = await res.blob()
		if (blob.size > MAX_IMAGE_BYTES) {
			errorMessage.value = __('Immagine troppo grande (max ~25 MB).')
			form.imageBase64 = ''
			form.imageFileName = ''
			return
		}
		form.imageBase64 = await blobToDataUri(blob)
		form.imageFileName = url.split('/').pop()?.split('?')[0] || 'image'
	} catch (err) {
		errorMessage.value = __('Lettura immagine fallita: ') + String(err)
		form.imageBase64 = ''
		form.imageFileName = ''
	} finally {
		imageBusy.value = false
	}
}

const onImagePicked = (fileUrl) => fetchImageToBase64(fileUrl)

const buildPayload = () => {
	const payload = {
		name: form.name?.trim(),
		description: form.description?.trim() || undefined,
		type: form.type,
		isEnabled: !!form.isEnabled,
		isVisible: !!form.isVisible,
	}
	if (form.imageBase64) {
		payload.imageBase64 = form.imageBase64
		if (form.imageFileName) payload.imageFileName = form.imageFileName
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
