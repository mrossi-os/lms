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
import Switch from '@/oslms/components/Form/Switch.vue'

const show = defineModel({ type: Boolean, default: false })
const emit = defineEmits(['created'])

const errorMessage = ref(null)

const blankForm = () => ({
	name: '',
	description: '',
	type: 'Certificate',
	isEnabled: false,
	isVisible: false,
	badgeUrl: '',
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
	}
})

const buildPayload = () => {
	const payload = {
		name: form.name?.trim(),
		description: form.description?.trim() || undefined,
		type: form.type,
		isEnabled: !!form.isEnabled,
		isVisible: !!form.isVisible,
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
