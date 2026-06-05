<template>
	<Dialog
		v-model="visible"
		:options="{ title: __('Golden runs'), size: '3xl' }"
	>
		<template #body-content>
			<div v-if="!editingGolden" class="space-y-3">
				<div v-if="!goldens.length" class="text-sm text-ink-gray-5">
					{{ __('Nessun golden run definito per questo scenario.') }}
				</div>
				<table v-else class="w-full text-sm">
					<thead class="text-xs text-ink-gray-5">
						<tr>
							<th class="text-left py-1">{{ __('Nome label') }}</th>
							<th class="text-left py-1">{{ __('Turn') }}</th>
							<th class="text-left py-1">{{ __('Attivo') }}</th>
							<th></th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="g in goldens"
							:key="g.name"
							class="border-t border-outline-gray-2"
						>
							<td class="py-2">{{ g.name_label }}</td>
							<td class="py-2">{{ g.turn_count }}</td>
							<td class="py-2">
								<Badge v-if="g.active" :label="__('Sì')" theme="green" />
								<Badge v-else :label="__('No')" theme="gray" />
							</td>
							<td class="py-2 text-right whitespace-nowrap">
								<Button size="sm" variant="ghost" @click="onEdit(g)">
									{{ __('Modifica') }}
								</Button>
								<Button size="sm" variant="ghost" @click="onDelete(g)">
									{{ __('Elimina') }}
								</Button>
							</td>
						</tr>
					</tbody>
				</table>
				<div class="flex justify-end">
					<Button variant="solid" @click="onNew">
						+ {{ __('Nuovo golden run') }}
					</Button>
				</div>
			</div>
			<GoldenRunEditor
				v-else
				:scenario="scenario"
				:golden="editingGolden"
				@cancel="editingGolden = null"
				@saved="onSaved"
			/>
		</template>
	</Dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Badge, Button, Dialog, createResource, toast } from 'frappe-ui'
import GoldenRunEditor from './GoldenRunEditor.vue'

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	scenario: { type: String, required: true },
})
const emit = defineEmits(['update:modelValue'])

const visible = computed({
	get: () => props.modelValue,
	set: (v) => emit('update:modelValue', v),
})

const editingGolden = ref(null)

const listRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.eval.api.list_goldens',
	makeParams() {
		return { scenario: props.scenario }
	},
})
const goldens = computed(() => listRes.data || [])

watch(visible, (open) => {
	if (open) {
		editingGolden.value = null
		listRes.submit()
	}
})

const loadRes = createResource({
	url: 'frappe.client.get',
})
async function onEdit(g) {
	const doc = await loadRes.submit({ doctype: 'LMSA Scenario Golden Run', name: g.name })
	editingGolden.value = {
		name: doc.name,
		name_label: doc.name_label,
		active: doc.active,
		expected_outcomes: doc.expected_outcomes,
		turns: JSON.parse(doc.turns || '[]'),
	}
}
function onNew() {
	editingGolden.value = {
		name: '',
		name_label: '',
		active: true,
		expected_outcomes: '',
		turns: [],
	}
}
function onSaved() {
	editingGolden.value = null
	listRes.submit()
}

const delRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.eval.api.delete_golden',
	method: 'POST',
})
async function onDelete(g) {
	if (!window.confirm(__('Eliminare il golden run "{0}"?', [g.name_label]))) return
	try {
		await delRes.submit({ golden_name: g.name })
		toast.success(__('Eliminato'))
		listRes.submit()
	} catch (e) {
		toast.error(e?.messages?.[0] || __('Eliminazione fallita'))
	}
}
</script>
