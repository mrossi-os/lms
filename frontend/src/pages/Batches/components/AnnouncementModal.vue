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
		<template #default>
			<div class="flex flex-col gap-4">
				<div class="flex items-end gap-8">
					<div class="shrink-0 pb-2">
						<FormControl
							type="checkbox"
							:label="__('Invia email insieme alla notifica')"
							v-model="sendEmail"
						/>
					</div>
					<FormControl
						v-if="sendEmail"
						class="flex-1 max-w-52"
						:label="__('Email Template')"
						type="select"
						:placeholder="__('Select option')"
						:options="templateOptions"
						v-model="announcement.template"
					/>
				</div>
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
				<div class="mb-4">
					<div class="mb-1.5 text-p-sm-medium text-ink-gray-7">
						{{ __('Announcement') }}
						<span class="text-ink-red-6">*</span>
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
import AnnouncementContent from '@/pages/Batches/components/AnnouncementContent.vue'

const show = defineModel()

/*
 * The frappe-ui TextEditor color extension renders named colors as
 * `color: var(--prose-color-<name>)`, and those CSS variables only exist inside
 * the editor (`.ProseMirror`). Anywhere else — the preview, the published
 * announcement, and the actual email the student receives — the variable is
 * undefined and the color is lost. Resolve them to real hex values (the
 * light-mode shades, which read well on the email's light background) before
 * the content is previewed or sent, so the chosen color is preserved everywhere.
 */
const NAMED_COLOR_HEX = {
	red: '#CC2929',
	blue: '#007BE0',
	green: '#278F5E',
	yellow: '#D1930D',
	orange: '#D45A08',
	purple: '#8642C2',
	pink: '#CF3A96',
	gray: '#7C7C7C',
	teal: '#0B9E92',
	cyan: '#32A4C7',
}

const inlineNamedColors = (html) =>
	String(html || '').replace(
		/var\(\s*--prose-color-(\w+)\s*\)/g,
		(match, name) => NAMED_COLOR_HEX[name] || match,
	)

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
const sendEmail = ref(false)
const studentSearch = ref('')

const DEFAULT_TEMPLATE_NAME = 'Announcement Email Template'

const hasMessagePlaceholder = computed(() =>
	/\{\{\s*message\s*\}\}/.test(announcement.announcement || ''),
)

const isEmptyHtml = (html) => {
	const stripped = String(html || '')
		.replace(/<(?!img|a)[^>]*>/g, '')
		.replace(/&nbsp;/g, '')
		.trim()
	return stripped.length === 0
}

const previewHtml = computed(() => {
	const msg = isEmptyHtml(announcement.message) ? '' : announcement.message
	const html = (announcement.announcement || '')
		.replace(/\{\{\s*message\s*\}\}/g, msg)
		.replace(
			/\{\{\s*frappe\.utils\.get_url\(\)\s*\}\}/g,
			window.location.origin,
		)
	return inlineNamedColors(html)
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

const filteredStudents = computed(() => {
	const q = studentSearch.value.trim().toLowerCase()
	if (!q) return props.students
	return props.students.filter((email) => {
		const label = studentLabels.value[email] || email
		return label.toLowerCase().includes(q)
	})
})

const toggleStudent = (email, checked) => {
	if (checked) {
		if (!selectedStudents.value.includes(email)) {
			selectedStudents.value = [...selectedStudents.value, email]
		}
	} else {
		selectedStudents.value = selectedStudents.value.filter((e) => e !== email)
	}
}

watch(
	() => announcement.template,
	(newVal) => {
		// Loads the selected template into the editor for this announcement only.
		// The Email Template document is never written back to.
		applyTemplate(newVal).catch((err) => {
			console.warn('[AnnouncementModal] could not apply template:', newVal, err)
		})
	},
)

watch(sendEmail, async (enabled) => {
	if (!enabled) {
		announcement.template = ''
		announcement.message = ''
		isHtmlMode.value = false
		showAdvanced.value = false
		return
	}
	// Pre-select the default template when present so the composer is ready to go,
	// while still leaving the picker visible for the user to choose another one.
	// The template watcher applies whatever ends up selected.
	if (!emailTemplates.data) {
		await emailTemplates.reload()
	}
	const hasDefault = (emailTemplates.data || []).some(
		(t) => t.name === DEFAULT_TEMPLATE_NAME,
	)
	announcement.template = hasDefault ? DEFAULT_TEMPLATE_NAME : ''
})

const emailTemplates = createResource({
	url: 'frappe.client.get_list',
	params: {
		doctype: 'Email Template',
		fields: ['name', 'subject', 'custom_available_for_announcements'],
		limit_page_length: 0,
	},
	auto: true,
})

// Prefer templates explicitly flagged for announcements so the list stays clean.
// If none are flagged (e.g. a fresh install where no admin has opted any in yet),
// fall back to every template so the picker is never empty.
const templateOptions = computed(() => {
	const all = emailTemplates.data || []
	const flagged = all.filter((t) => t.custom_available_for_announcements)
	const list = flagged.length ? flagged : all
	return list.map((t) => ({ label: t.name, value: t.name }))
})

const templateResource = createResource({
	url: 'frappe.client.get',
})

const applyTemplate = async (option) => {
	const templateName = typeof option === 'object' ? option?.value : option
	if (!templateName) return
	const result = await templateResource.submit({
		doctype: 'Email Template',
		name: templateName,
	})
	if (!result) {
		throw new Error(`Template not found: ${templateName}`)
	}
	announcement.subject = result.subject || ''
	isHtmlMode.value = !!result.use_html
	showAdvanced.value = false
	announcement.message = ''
	announcement.announcement = result.use_html
		? result.response_html || ''
		: result.response || ''
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
			// When emailing, bake named colors to hex so they survive in the
			// recipient's email client (which lacks the editor's CSS variables).
			// Notification-only content keeps the variables so the themed in-app
			// card can resolve them to dark-mode shades for readable contrast.
			content: sendEmail.value
				? inlineNamedColors(announcement.announcement)
				: announcement.announcement,
			message: inlineNamedColors(announcement.message),
			send_email: sendEmail.value ? 1 : 0,
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
				if (
					hasMessagePlaceholder.value &&
					isEmptyHtml(announcement.message)
				) {
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
