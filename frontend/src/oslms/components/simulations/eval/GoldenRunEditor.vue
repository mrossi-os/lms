<template>
	<div class="space-y-4">
		<div class="grid grid-cols-2 gap-3">
			<FormControl
				v-model="local.name_label"
				type="text"
				:label="__('Nome label')"
				required
			/>
			<FormControl
				v-model="local.active"
				type="checkbox"
				:label="__('Attivo')"
			/>
		</div>
		<FormControl
			v-model="local.expected_outcomes"
			type="textarea"
			:rows="3"
			:label="__('Outcomes attesi')"
		/>

		<div class="text-sm font-medium text-ink-gray-9">{{ __('Turn') }}</div>
		<div class="space-y-2">
			<GoldenTurnEditor
				v-for="(turn, i) in local.turns"
				:key="i"
				:turn="turn"
				:index="i"
				:canMoveUp="i > 0"
				:canMoveDown="i < local.turns.length - 1"
				@move-up="moveTurn(i, -1)"
				@move-down="moveTurn(i, 1)"
				@remove="removeTurn(i)"
			/>
		</div>
		<div class="flex gap-2">
			<Button size="sm" @click="addTurn('user')">+ {{ __('Studente') }}</Button>
			<Button size="sm" @click="addTurn('assistant')">+ {{ __('Cliente') }}</Button>
		</div>

		<div class="flex justify-end gap-2 pt-2">
			<Button @click="$emit('cancel')">{{ __('Annulla') }}</Button>
			<Button variant="solid" :loading="saving" @click="onSave">
				{{ __('Salva') }}
			</Button>
		</div>
	</div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { FormControl, Button, createResource, toast } from 'frappe-ui'
import GoldenTurnEditor from './GoldenTurnEditor.vue'

const props = defineProps({
	scenario: { type: String, required: true },
	golden: { type: Object, default: null },
})
const emit = defineEmits(['saved', 'cancel'])

const empty = () => ({
	name: '',
	name_label: '',
	active: true,
	expected_outcomes: '',
	turns: [],
})
const local = reactive(empty())

watch(
	() => props.golden,
	(g) => {
		const seed = g || empty()
		local.name = seed.name || ''
		local.name_label = seed.name_label || ''
		local.active = seed.active !== false
		local.expected_outcomes = seed.expected_outcomes || ''
		local.turns = (seed.turns || []).map((t) => ({ ...t }))
	},
	{ immediate: true },
)

function addTurn(role) {
	local.turns.push({ role, text: '' })
}
function removeTurn(i) {
	local.turns.splice(i, 1)
}
function moveTurn(i, delta) {
	const j = i + delta
	if (j < 0 || j >= local.turns.length) return
	const tmp = local.turns[i]
	local.turns[i] = local.turns[j]
	local.turns[j] = tmp
}

const saving = ref(false)
const saveRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.eval.api.save_golden',
	method: 'POST',
})
async function onSave() {
	saving.value = true
	try {
		const payload = {
			scenario: props.scenario,
			name: local.name,
			name_label: local.name_label,
			active: local.active,
			expected_outcomes: local.expected_outcomes,
			turns: local.turns,
		}
		const out = await saveRes.submit({ payload })
		toast.success(__('Golden run salvato'))
		emit('saved', out)
	} catch (e) {
		toast.error(e?.messages?.[0] || __('Salvataggio fallito'))
	} finally {
		saving.value = false
	}
}
</script>
