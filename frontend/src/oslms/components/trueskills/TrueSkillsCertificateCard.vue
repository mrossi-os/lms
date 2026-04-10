<template>
	<div class="card p-4 space-y-3">
		<Switch
			size="sm"
			v-model="enabled"
			:label="__('TrueSkills Certificate')"
			:description="
				trueskillsReady
					? __('Issue a certificate via TrueSkills when the course is completed.')
					: __('TrueSkills API integration is disabled in Settings.')
			"
			:disabled="!trueskillsReady"
		/>
		<div v-if="enabled && trueskillsReady">
			<div class="mb-1.5 text-sm text-ink-gray-5">
				{{ __('Template') }}
			</div>
			<FormControl
				v-model="templateId"
				type="select"
				:options="templateOptions"
				:disabled="loadingTemplates"
			/>
		</div>
	</div>
</template>

<script setup lang="ts">
import { FormControl, call } from 'frappe-ui'
import Switch from '@/oslms/components/Form/Switch.vue'
import { useSettings } from '@/stores/settings'
import { computed, ref, watch, onMounted } from 'vue'

const settingsStore = useSettings()

const props = defineProps<{
	modelValue: boolean
	templateValue: string
}>()

const emit = defineEmits<{
	'update:modelValue': [value: boolean]
	'update:templateValue': [value: string]
	dirty: []
}>()

const trueskillsReady = computed(() => {
	return !!settingsStore.settings?.data?.trueskills_api_enabled
})

const enabled = computed({
	get: () => props.modelValue && trueskillsReady.value,
	set: (val: boolean) => {
		emit('update:modelValue', val)
		emit('dirty')
	},
})

const templateId = computed({
	get: () => props.templateValue || '',
	set: (val: string) => {
		emit('update:templateValue', val)
		emit('dirty')
	},
})

const templates = ref<{ label: string; value: string }[]>([])
const loadingTemplates = ref(false)

const templateOptions = computed(() => {
	const options = [{ label: __('Select a template'), value: '' }]
	return options.concat(templates.value)
})

const loadTemplates = async () => {
	loadingTemplates.value = true
	try {
		const data = await call('os_lms.os_lms.trueskills.api.get_templates')
		if (Array.isArray(data)) {
			templates.value = data.map((t: any) => ({
				label: t.name || t.title || t.id,
				value: t.id || t.name,
			}))
		}
	} catch {
		templates.value = []
	} finally {
		loadingTemplates.value = false
	}
}

watch(trueskillsReady, (ready) => {
	if (ready && !templates.value.length) {
		loadTemplates()
	}
})

onMounted(() => {
	if (trueskillsReady.value) {
		loadTemplates()
	}
})
</script>
