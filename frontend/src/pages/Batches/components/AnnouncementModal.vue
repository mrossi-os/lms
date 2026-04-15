<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Make an Announcement'),
			size: 'xl',
			actions: [
				{
					label: __('Submit'),
					variant: 'solid',
					onClick: (close) => makeAnnouncement(close),
				},
			],
		}"
	>
		<template #body-content>
			<div class="flex flex-col gap-4">
				<FormControl
					:label="__('Email Template')"
					type="select"
					:placeholder="__('Select option')"
					:options="emailTemplates.data || []"
					v-model="announcement.template"
				/>
				<FormControl
					:label="__('Subject')"
					type="text"
					v-model="announcement.subject"
					:required="true"
				/>
				<FormControl
					:label="__('Reply To')"
					type="text"
					v-model="announcement.replyTo"
					:required="true"
				/>
				<div class="mb-4">
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('Announcement') }}
						<span class="text-ink-red-3">*</span>
					</div>
					<TextEditor
						:fixedMenu="true"
						:content="announcement.announcement"
						@change="(val) => (announcement.announcement = val)"
						editorClass="prose-sm py-2 px-2 min-h-[200px] border-outline-gray-2 hover:border-outline-gray-3 rounded-b-md bg-surface-gray-3"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import {
	Dialog,
	FormControl,
	TextEditor,
	createResource,
	toast,
} from 'frappe-ui'
import { reactive, watch } from 'vue'

const show = defineModel()

const props = defineProps({
	batch: {
		type: String,
		required: true,
	},
	students: {
		type: Array,
		required: true,
	},
})

const announcement = reactive({
	template: '',
	subject: '',
	replyTo: '',
	announcement: '',
})

watch(
	() => announcement.template,
	(newVal) => {
		console.log('[AnnouncementModal] template changed:', newVal)
		applyTemplate(newVal)
	},
)

const emailTemplates = createResource({
	url: 'frappe.client.get_list',
	params: {
		doctype: 'Email Template',
		fields: ['name', 'subject'],
	},
	auto: true,
	transform(data) {
		return data.map((t) => ({ label: t.name, value: t.name }))
	},
})

const templateResource = createResource({
	url: 'frappe.client.get',
})

const applyTemplate = async (option) => {
	const templateName = typeof option === 'object' ? option?.value : option
	console.log('[AnnouncementModal] applyTemplate called with:', {
		option,
		templateName,
	})
	if (!templateName) return
	const result = await templateResource.submit({
		doctype: 'Email Template',
		name: templateName,
	})
	console.log('[AnnouncementModal] template result:', result)
	if (result) {
		announcement.subject = result.subject || ''
		announcement.announcement = result.response || ''
		console.log('[AnnouncementModal] announcement after apply:', {
			...announcement,
		})
	}
}

const announcementResource = createResource({
	url: 'frappe.core.doctype.communication.email.make',
	makeParams() {
		return {
			recipients: announcement.replyTo,
			bcc: props.students.join(', '),
			subject: announcement.subject,
			content: announcement.announcement,
			doctype: 'LMS Batch',
			name: props.batch,
			send_email: 1,
		}
	},
})

const makeAnnouncement = (close) => {
	announcementResource.submit(
		{},
		{
			validate() {
				if (!props.students.length) {
					return __('No students in this batch')
				}
				if (!announcement.subject) {
					return __('Subject is required')
				}
				if (!announcement.announcement) {
					return __('Announcement is required')
				}
				if (!announcement.replyTo) {
					return __('Reply To is required')
				}
			},
			onSuccess() {
				close()
				toast.success(__('Announcement has been sent successfully'))
			},
			onError(err) {
				toast.error(__(err.messages?.[0] || err))
			},
		},
	)
}
</script>
