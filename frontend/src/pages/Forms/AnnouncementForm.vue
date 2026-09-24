<template>
	<FormShell :title="__('Make an Announcement')" size="xl" @close="close">
		<template #default>
			<div v-if="loadingBatch" class="p-4 text-base text-ink-gray-6">
				{{ __('Loading...') }}
			</div>
			<div v-else-if="refusal" class="p-4 text-base text-ink-gray-6">
				{{ refusal }}
			</div>
			<div v-else data-testid="announcement-fields" class="flex flex-col gap-4">
				<!-- OSLMS-CUSTOM: optional email toggle + announcement email template picker -->
				<div class="flex flex-wrap items-end gap-x-8 gap-y-2">
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
				<!-- OSLMS-CUSTOM: Reply To removed: os_lms send_batch_announcement needs no reply-to -->
				<!-- <FormControl
					:label="__('Reply To')"
					type="text"
					v-model="announcement.replyTo"
					:required="true"
				/> -->
				<!-- OSLMS-CUSTOM: send to the whole class or to hand-picked students -->
				<FormControl
					:label="__('Send To')"
					type="select"
					:options="[
						{ label: __('Whole class'), value: 'all' },
						{ label: __('Specific students'), value: 'specific' },
					]"
					v-model="recipientMode"
				/>
				<div
					v-if="recipientMode === 'specific'"
					role="group"
					:aria-labelledby="studentsLabelId"
					class="flex flex-col gap-2"
				>
					<div class="flex justify-between">
						<InputLabel
							:id="studentsLabelId"
							:label="__('Select students')"
							:required="true"
						/>
						<div class="text-xs text-ink-gray-5">
							{{ selectedStudents.length }} {{ __('selected') }}
							<span v-if="studentSearch">
								· {{ filteredStudents.length }} {{ __('shown') }}
							</span>
						</div>
					</div>
					<FormControl
						type="text"
						:placeholder="__('Search student...')"
						v-model="studentSearch"
					/>
					<div
						class="border rounded-md p-2 max-h-[180px] overflow-auto bg-surface-base"
					>
						<div v-if="!students.length" class="text-ink-gray-5 text-sm">
							{{ __('No students in this batch') }}
						</div>
						<div
							v-else-if="!filteredStudents.length"
							class="text-ink-gray-5 text-sm"
						>
							{{ __('No students match your search') }}
						</div>
						<div v-for="email in filteredStudents" :key="email">
							<FormControl
								type="checkbox"
								:label="studentLabels[email] || email"
								:modelValue="selectedStudents.includes(email)"
								@update:modelValue="(v) => toggleStudent(email, v)"
							/>
						</div>
					</div>
				</div>
				<!-- OSLMS-CUSTOM: three editor branches (template with {{ message }} / raw-HTML template / plain rich editor) so styled email HTML is never re-serialized by the rich editor -->
				<div
					v-if="sendEmail && isHtmlMode && hasMessagePlaceholder"
					class="mb-4 flex flex-col gap-3"
				>
					<div
						role="group"
						:aria-labelledby="messageLabelId"
						class="space-y-1.5"
					>
						<InputLabel
							:id="messageLabelId"
							:label="__('Message')"
							:required="true"
						/>
						<RichTextEditor
							:fixedMenu="true"
							:content="announcement.message"
							@change="(val) => (announcement.message = val)"
							editorClass="prose-sm py-2 px-2 min-h-[120px] max-h-[240px] overflow-auto border-outline-gray-2 hover:border-outline-gray-3 rounded-b-md bg-surface-gray-3"
							:placeholder="
								__(
									'Write your message here. It will be inserted into the template.',
								)
							"
						/>
					</div>
					<div>
						<div class="mb-1.5 flex items-center justify-between">
							<div class="text-sm text-ink-gray-5">
								{{ __('Preview') }}
							</div>
							<Button size="sm" @click="showAdvanced = !showAdvanced">
								{{
									showAdvanced ? __('Hide HTML') : __('Edit HTML (advanced)')
								}}
							</Button>
						</div>
						<div
							class="border rounded-md min-h-[200px] max-h-[400px] overflow-auto"
						>
							<AnnouncementContent :content="previewHtml" />
						</div>
						<textarea
							v-if="showAdvanced"
							v-model="announcement.announcement"
							:aria-label="__('Edit HTML (advanced)')"
							class="mt-2 w-full min-h-[200px] max-h-[400px] border rounded-md p-2 text-sm font-mono bg-surface-gray-3 border-outline-gray-2 text-ink-gray-9"
							spellcheck="false"
						></textarea>
					</div>
				</div>
				<!--
					HTML template without a {{ message }} placeholder (e.g. a generic
					email): the rich editor can't round-trip email HTML without dropping
					inline styles and buttons, so edit the raw HTML directly — body text
					and button URLs alike — with a faithful live preview above it.
				-->
				<div
					v-else-if="sendEmail && isHtmlMode"
					class="mb-4 flex flex-col gap-3"
				>
					<div>
						<div class="mb-1.5 text-sm text-ink-gray-5">
							{{ __('Preview') }}
						</div>
						<div
							class="border rounded-md min-h-[200px] max-h-[400px] overflow-auto"
						>
							<AnnouncementContent :content="previewHtml" />
						</div>
					</div>
					<div class="space-y-1.5">
						<InputLabel
							:id="htmlLabelId"
							:forId="htmlFieldId"
							:label="__('Announcement (HTML)')"
							:required="true"
						/>
						<textarea
							:id="htmlFieldId"
							v-model="announcement.announcement"
							class="w-full min-h-[240px] max-h-[400px] border rounded-md p-2 text-sm font-mono bg-surface-gray-3 border-outline-gray-2"
							spellcheck="false"
						></textarea>
					</div>
				</div>
				<div
					v-else
					role="group"
					:aria-labelledby="announcementLabelId"
					class="mb-4 space-y-1.5"
				>
					<InputLabel
						:id="announcementLabelId"
						:label="__('Announcement')"
						:required="true"
					/>
					<RichTextEditor
						:fixedMenu="true"
						:content="announcement.announcement"
						@change="(val) => (announcement.announcement = val)"
						editorClass="prose-sm py-2 px-2 min-h-[200px] border-outline-gray-2 hover:border-outline-gray-3 rounded-b-md bg-surface-gray-3"
					/>
				</div>
			</div>
		</template>
		<template #actions>
			<div
				v-if="!refusal && !loadingBatch"
				class="flex items-center justify-end"
			>
				<HeaderButton
					data-testid="announcement-save"
					:label="__('Save')"
					variant="solid"
					:loading="announcementResource.loading"
					@click="makeAnnouncement()"
				/>
			</div>
		</template>
	</FormShell>
</template>
<script setup>
import { Button, FormControl, createResource, toast } from 'frappe-ui'
import { computed, inject, reactive, ref, useId, watch } from 'vue'
import { useRoute } from 'vue-router'
import FormShell from '@/components/FormShell.vue'
import HeaderButton from '@/components/HeaderButton.vue'
import RichTextEditor from '@/components/RichTextEditor.vue'
import { InputLabel } from '@/components/Form/labeling'
import AnnouncementContent from '@/pages/Batches/components/AnnouncementContent.vue'
import {
	batchRouteLocation,
	useBatchDetails,
} from '@/composables/useBatchForms'
import { useFormRoute } from '@/composables/useFormRoute'
import { submitResource } from '@/utils/resource'

const props = defineProps({
	batchName: {
		type: String,
		required: true,
	},
})

const user = inject('$user')
const route = useRoute()
const readOnlyMode = window.read_only_mode
const announcementLabelId = useId()
const messageLabelId = useId()
const htmlLabelId = useId()
const htmlFieldId = useId()
const studentsLabelId = useId()

// C2: close()'s pop branch restores the hash by itself; its deep-link branch
// replaces to this literal location, so the tab hash has to be carried here or
// a close lands on the bare path and silently resets the page to tab 0.
const { close } = useFormRoute(
	batchRouteLocation('BatchDetail', props.batchName, route.hash)
)

// Parent context a URL cannot carry: the student list, used both as the
// recipients and as the form's own precondition. Its own fetch, NOT the page's
// instance — see useBatchForms.ts for why sharing one is not available here.
//
// There is no shared LIST cache key either: the send goes through the os_lms
// endpoint rather than inserting a row the list could pick up. The
// Announcements tab reloads its own resource when this route closes (see
// Announcements.vue), so a sent announcement shows up straight away.
const batch = useBatchDetails(() => props.batchName)

const loadingBatch = computed(() => !batch.data && batch.loading)

const students = computed(() => batch.data?.students || [])

const isAdmin = computed(() =>
	Boolean(
		user.data?.is_moderator ||
			user.data?.is_evaluator ||
			// OSLMS-CUSTOM: Docente manages batches like a moderator
			user.data?.is_docente
	)
)

// Lifted off BatchDetail.vue's "Make Announcement" button, which renders only
// for an admin outside read-only mode and disables itself with no students.
//
// UX gate, not an authorization boundary — the server-side check in
// os_lms send_batch_announcement is.
const refusal = computed(() => {
	if (readOnlyMode) return __('This site is in read-only mode.')
	if (!isAdmin.value)
		return __('You are not permitted to make an announcement for this batch.')
	if (!students.value.length)
		return __('Add students to the batch to make an announcement')
	return null
})

/*
 * The rich editor's color extension (RichTextEditor, frappe-ui/editor) renders
 * named colors as
 * `color: var(--prose-color-<name>)`, and those CSS variables only exist inside
 * the editor (`.ProseMirror`). Anywhere else — the preview, the published
 * announcement, and the actual email the student receives — the variable is
 * undefined and the color is lost. Resolve them to real hex values (the
 * light-mode shades, which read well on the email's light background) before
 * the content is previewed or sent, so the chosen color is preserved everywhere.
 */
// OSLMS-CUSTOM: bake editor named colors/highlights to hex for preview and email
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
	// frappe-ui/editor palette adds indigo, aliased to the violet hue
	indigo: '#5F46C7',
}

// Highlights are stored the same way, as
// `background-color: var(--prose-highlight-<name>)`. Resolve them to light
// shades (which read well on the light email/preview background) so the
// highlight survives outside the editor too.
const NAMED_HIGHLIGHT_HEX = {
	red: '#ffe7e7',
	blue: '#e6f4ff',
	green: '#e4faeb',
	yellow: '#fff7d3',
	orange: '#ffefe4',
	purple: '#f6e9ff',
	pink: '#fde8f5',
	gray: '#f3f3f3',
	teal: '#e6f7f4',
	cyan: '#ddf7ff',
	indigo: '#f0ebff',
}

const inlineNamedColors = (html) =>
	String(html || '')
		.replace(
			/var\(\s*--prose-color-(\w+)\s*\)/g,
			(match, name) => NAMED_COLOR_HEX[name] || match,
		)
		.replace(
			/var\(\s*--prose-highlight-(\w+)\s*\)/g,
			(match, name) => NAMED_HIGHLIGHT_HEX[name] || match,
		)

// The editors are bound through :content (not left uncontrolled) because a
// picked template loads its text into them for this announcement.
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

// OSLMS-CUSTOM: default announcement email template preselected
const DEFAULT_TEMPLATE_NAME = 'Announcement Email Template'

// OSLMS-CUSTOM: template with {{ message }} placeholder edits only the message
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

// OSLMS-CUSTOM: student names for the specific-recipients picker
// Fetched only once the picker is shown: the student list itself arrives
// asynchronously with the batch details, so there is nothing to ask for at setup.
const studentsInfo = createResource({
	url: 'frappe.client.get_list',
	makeParams() {
		return {
			doctype: 'User',
			filters: [['name', 'in', students.value]],
			fields: ['name', 'full_name'],
			limit_page_length: 0,
		}
	},
})

watch(
	[recipientMode, students],
	([mode, list]) => {
		if (mode === 'specific' && list.length) studentsInfo.reload()
	},
	{ immediate: true },
)

const studentLabels = computed(() => {
	const map = {}
	;(studentsInfo.data || []).forEach((u) => {
		map[u.name] = u.full_name ? `${u.full_name} <${u.name}>` : u.name
	})
	return map
})

const filteredStudents = computed(() => {
	const q = studentSearch.value.trim().toLowerCase()
	if (!q) return students.value
	return students.value.filter((email) => {
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
			console.warn('[AnnouncementForm] could not apply template:', newVal, err)
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

// OSLMS-CUSTOM: templates flagged custom_available_for_announcements first
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
	// OSLMS-CUSTOM: send via os_lms: in-app notification + optional email to chosen recipients
	url: 'os_lms.os_lms.api.send_batch_announcement',
	makeParams() {
		const recipients =
			recipientMode.value === 'specific'
				? selectedStudents.value
				: students.value
		return {
			batch: props.batchName,
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

const makeAnnouncement = () => {
	if (refusal.value) return
	submitResource(
		announcementResource,
		{},
		{
			validate() {
				if (!students.value.length) {
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
				if (hasMessagePlaceholder.value && isEmptyHtml(announcement.message)) {
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
		}
	)
}
</script>
