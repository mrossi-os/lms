<template>
	<Dialog
		v-model="visible"
		:options="{ title: __('Test simulazione'), size: 'lg' }"
	>
		<template #body-content>
			<div class="space-y-4">
				<p class="text-sm text-ink-gray-7">
					{{ __('Scegli il profilo di studente e quante conversazioni generare. Il sistema simula lo studente, esegue i 4 giudici AI e mostra trascrizioni e punteggi.') }}
				</p>

				<FormControl
					v-model="studentProfile"
					type="select"
					:label="__('Profilo studente')"
					:options="profileOptions"
					required
				/>

				<FormControl
					v-model.number="numVariants"
					type="select"
					:label="__('Numero conversazioni')"
					:options="[
						{ label: '1', value: 1 },
						{ label: '2', value: 2 },
						{ label: '3', value: 3 },
					]"
					:description="__('Più conversazioni = più robusto, ma anche più lento e costoso (max 3).')"
				/>

				<div class="flex justify-end gap-2 pt-2">
					<Button @click="visible = false">{{ __('Annulla') }}</Button>
					<Button
						variant="solid"
						:loading="starting"
						:disabled="!studentProfile"
						@click="onStart"
					>
						{{ __('Avvia test') }}
					</Button>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Button, Dialog, FormControl, createResource, toast } from 'frappe-ui'

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	scenario: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue', 'started'])

const visible = computed({
	get: () => props.modelValue,
	set: (v) => emit('update:modelValue', v),
})

const studentProfile = ref('competent')
const numVariants = ref(1)
const starting = ref(false)

const profilesRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.eval.api.list_student_profiles',
	auto: true,
})
const profileOptions = computed(() =>
	(profilesRes.data || []).map((p) => ({ label: p.label, value: p.name })),
)

watch(visible, (open) => {
	if (open) {
		studentProfile.value = 'competent'
		numVariants.value = 1
		profilesRes.reload()
	}
})

const runRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.eval.api.run_simulation_test',
	method: 'POST',
})

async function onStart() {
	if (!studentProfile.value) return
	starting.value = true
	try {
		const out = await runRes.submit({
			scenario: props.scenario,
			student_profile: studentProfile.value,
			num_variants: numVariants.value,
		})
		const evalId = out?.eval_id
		if (!evalId) return
		visible.value = false
		emit('started', {
			eval_id: evalId,
			student_profile: studentProfile.value,
			num_variants: numVariants.value,
		})
	} catch (e) {
		toast.error(e?.messages?.[0] || __('Avvio test fallito'))
	} finally {
		starting.value = false
	}
}
</script>
