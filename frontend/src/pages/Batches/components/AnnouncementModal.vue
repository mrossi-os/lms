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
				<!-- <FormControl
					:label="__('Reply To')"
					type="text"
					v-model="announcement.replyTo"
					:required="true"
				/> -->
				<FormControl
					:label="__('Send To')"
					type="select"
					:options="[
						{ label: __('Whole class'), value: 'all' },
						{ label: __('Specific students'), value: 'specific' },
					]"
					v-model="recipientMode"
				/>
				<div v-if="recipientMode === 'specific'" class="flex flex-col gap-2">
					<div class="text-sm text-ink-gray-5">
						{{ __('Select students') }}
						<span class="text-ink-red-3">*</span>
					</div>
					<div
						class="border rounded-md p-2 max-h-[180px] overflow-auto bg-surface-white"
					>
						<div v-if="!props.students.length" class="text-ink-gray-5 text-sm">
							{{ __('No students in this batch') }}
						</div>
						<label
							v-for="email in props.students"
							:key="email"
							class="flex items-center gap-2 py-1 cursor-pointer text-sm"
						>
							<input
								type="checkbox"
								:value="email"
								v-model="selectedStudents"
								class="cursor-pointer"
							/>
							<span class="text-white">
								{{ studentLabels[email] || email }}
							</span>
						</label>
					</div>
					<div class="text-xs text-ink-gray-5">
						{{ selectedStudents.length }} {{ __('selected') }}
					</div>
				</div>
				<div v-if="isHtmlMode" class="mb-4 flex flex-col gap-3">
					<div v-if="hasMessagePlaceholder">
						<div class="mb-1.5 text-sm text-ink-gray-5">
							{{ __('Message') }}
							<span class="text-ink-red-3">*</span>
						</div>
						<textarea
							v-model="announcement.message"
							class="w-full min-h-[120px] max-h-[240px] border rounded-md p-2 text-sm bg-surface-gray-3 border-outline-gray-2"
							:placeholder="__('Write your message here. It will be inserted into the template.')"
						></textarea>
					</div>
					<div>
						<div class="mb-1.5 flex items-center justify-between">
							<div class="text-sm text-ink-gray-5">
								{{ __('Preview') }}
							</div>
							<Button size="sm" @click="showAdvanced = !showAdvanced">
								{{ showAdvanced ? __('Hide HTML') : __('Edit HTML (advanced)') }}
							</Button>
						</div>
						<div
							class="border rounded-md p-4 bg-surface-white min-h-[200px] max-h-[400px] overflow-auto"
							v-html="previewHtml"
						></div>
						<textarea
							v-if="showAdvanced"
							v-model="announcement.announcement"
							class="mt-2 w-full min-h-[200px] max-h-[400px] border rounded-md p-2 text-sm font-mono bg-surface-gray-3 border-outline-gray-2"
							spellcheck="false"
						></textarea>
					</div>
				</div>
				<div v-else class="mb-4">
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
	Button,
	Dialog,
	FormControl,
	TextEditor,
	createResource,
	toast,
} from 'frappe-ui'
import { computed, reactive, ref, watch } from 'vue'

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
	message: '',
})

const isHtmlMode = ref(false)
const showAdvanced = ref(false)
const recipientMode = ref('all')
const selectedStudents = ref([])

const hasMessagePlaceholder = computed(() =>
	/\{\{\s*message\s*\}\}/.test(announcement.announcement || ''),
)

const escapeHtml = (str) =>
	String(str)
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')

const previewHtml = computed(() => {
	const msg = escapeHtml(announcement.message || '').replace(/\n/g, '<br>')
	return (announcement.announcement || '')
		.replace(/\{\{\s*message\s*\}\}/g, msg)
		.replace(/\{\{\s*frappe\.utils\.get_url\(\)\s*\}\}/g, window.location.origin)
})

const studentsInfo = createResource({
	url: 'frappe.client.get_list',
	makeParams() {
		return {
			doctype: 'User',
			filters: [['name', 'in', props.students]],
			fields: ['name', 'full_name'],
			limit_page_length: 0,
		}
	},
	auto: true,
})

const studentLabels = computed(() => {
	const map = {}
	;(studentsInfo.data || []).forEach((u) => {
		map[u.name] = u.full_name ? `${u.full_name} <${u.name}>` : u.name
	})
	return map
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
		isHtmlMode.value = !!result.use_html
		showAdvanced.value = false
		announcement.message = ''
		announcement.announcement = result.use_html
			? result.response_html || ''
			: result.response || ''
		console.log('[AnnouncementModal] announcement after apply:', {
			...announcement,
		})
	}
}

const announcementResource = createResource({
	url: 'os_lms.os_lms.api.send_batch_announcement',
	makeParams() {
		const recipients =
			recipientMode.value === 'specific'
				? selectedStudents.value
				: props.students
		return {
			batch: props.batch,
			recipients: recipients,
			subject: announcement.subject,
			content: announcement.announcement,
			message: announcement.message,
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
				if (
					recipientMode.value === 'specific' &&
					!selectedStudents.value.length
				) {
					return __('Select at least one student')
				}
				if (!announcement.subject) {
					return __('Subject is required')
				}
				if (!announcement.announcement) {
					return __('Announcement is required')
				}
				if (hasMessagePlaceholder.value && !announcement.message) {
					return __('Message is required')
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
