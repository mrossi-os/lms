<template>
	<LayoutHeader>
		<template #left-header>
			<Breadcrumbs :items="breadcrumbs" />
		</template>
		<template #right-header>
			<Button variant="solid" @click="newSchema">
				+ {{ __('Nuovo schema di valutazione') }}
			</Button>
		</template>
	</LayoutHeader>

	<div class="p-5 pb-10 space-y-3">
		<div class="border rounded-md overflow-hidden">
			<table class="w-full text-sm os-table-view">
				<thead class="bg-surface-gray-2 text-xs text-ink-gray-7">
					<tr>
						<th class="text-left px-3 py-2">{{ __('Nome') }}</th>
						<th class="text-left px-3 py-2">{{ __('Scala') }}</th>
						<th class="text-left px-3 py-2">{{ __('Soglia') }}</th>
						<th class="text-left px-3 py-2">{{ __('Condivisa') }}</th>
						<th></th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="r in schemas"
						:key="r.name"
						class="border-t hover:bg-surface-gray-1"
					>
						<td class="px-3 py-2">{{ r.schema_name }}</td>
						<td class="px-3 py-2">{{ r.scoring_scale }}</td>
						<td class="px-3 py-2">{{ r.passing_threshold }}%</td>
						<td class="px-3 py-2">
							<Badge v-if="r.is_shared" :label="__('Sì')" theme="green" />
						</td>
						<td class="px-3 py-2 text-right">
							<Button size="sm" variant="outline" @click="editSchema(r.name)">
								{{ __('Modifica') }}
							</Button>
						</td>
					</tr>
					<tr v-if="!schemas.length">
						<td colspan="5" class="px-3 py-6 text-center">
							{{ __('Nessuno schema di valutazione.') }}
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<Dialog
			v-model="schemaEditorOpen"
			:options="{ title: __('Schema di valutazione'), size: '3xl' }"
		>
			<template #body-content>
				<EvaluationSchemaEditor
					:schemaName="editingSchema"
					@saved="onSchemaSaved"
				/>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { computed, ref } from 'vue'
import {
	Badge,
	Breadcrumbs,
	Button,
	Dialog,
	createResource,
	usePageMeta,
} from 'frappe-ui'
import LayoutHeader from '@/components/Layouts/LayoutHeader.vue'
import EvaluationSchemaEditor from '@/oslms/components/simulations/EvaluationSchemaEditor.vue'

usePageMeta(() => ({
	title: __('Schemi di valutazione'),
}))

const breadcrumbs = computed(() => [
	{
		label: __('Pannello simulazioni'),
		route: { name: 'InstructorReports' },
	},
	{
		label: __('Schemi di valutazione'),
		route: { name: 'EvaluationSchemas' },
	},
])

const schemasRes = createResource({
	url: 'os_lms.os_lms.ai.simulations.api.list_my_evaluation_schemas',
	auto: true,
})
const schemas = computed(() => schemasRes.data || [])

const schemaEditorOpen = ref(false)
const editingSchema = ref('')

function newSchema() {
	editingSchema.value = ''
	schemaEditorOpen.value = true
}
function editSchema(name) {
	editingSchema.value = name
	schemaEditorOpen.value = true
}
function onSchemaSaved() {
	schemaEditorOpen.value = false
	schemasRes.submit()
}
</script>
