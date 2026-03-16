<template>
	<div class="flex flex-col h-full text-base overflow-y-hidden">
		<div class="">
			<div class="flex items-center justify-between mb-2">
				<div class="flex items-center space-x-2">
					<div class="text-xl font-semibold leading-none text-ink-gray-9">
						{{ __(label) }}
					</div>
					<Badge
						v-if="aiData.isDirty"
						:label="__('Not Saved')"
						variant="subtle"
						theme="orange"
					/>
				</div>
				<Button variant="solid" :loading="aiData.save.loading" @click="update">
					{{ __('Update') }}
				</Button>
			</div>
			<div class="text-ink-gray-6 leading-5">
				{{ __(description) }}
			</div>
		</div>

		<SettingFields v-if="aiData.doc" :sections="sections" :data="aiData.doc" />
	</div>
</template>

<script setup>
import { Button, Badge, createDocumentResource, toast } from 'frappe-ui'
import SettingFields from '@/components/Settings/SettingFields.vue'

const props = defineProps({
	label: {
		type: String,
		required: true,
	},
	description: {
		type: String,
	},
	sections: {
		type: Array,
		required: true,
	},
})

const aiData = createDocumentResource({
	doctype: 'LMSA Settings',
	name: 'LMSA Settings',
	fields: ['*'],
	cache: 'LMSA Settings',
	auto: true,
})

const update = () => {
	aiData.save.submit(
		{},
		{
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		}
	)
}
</script>
