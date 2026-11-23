<template>
	<SettingsDialog v-model="show" v-model:tab="activeTab" size="5xl">
		<template #title>{{ __('Settings') }}</template>
		<SettingsSidebar>
			<!-- OSLMS-CUSTOM: tabs are identified by a stable English `key` (tabKey) because `label` is already translated with __(); group labels print without __() -->
			<SettingsNavGroup
				v-for="group in tabs"
				:key="tabKey(group)"
				:label="group.hideLabel ? undefined : group.label"
			>
				<template #label>
					<span class="text-p-xs-medium text-ink-gray-5">
						{{ group.label }}
					</span>
				</template>
				<SettingsNavItem
					v-for="item in group.items"
					:key="tabKey(item)"
					:value="tabKey(item)"
				>
					<template #prefix>
						<!-- OSLMS-CUSTOM: os_lms tabs (buildOslmsSettingsTabs) still name lucide-vue-next components; lucide-* class names render as a span -->
						<component
							v-if="lucideIcons[item.icon]"
							:is="lucideIcons[item.icon]"
							class="size-4 shrink-0 stroke-1.5 text-ink-gray-7"
						/>
						<span v-else :class="[item.icon, 'size-4 shrink-0 text-ink-gray-7']" />
					</template>
					<span class="text-p-sm text-ink-gray-7">{{ __(item.label) }}</span>
				</SettingsNavItem>
			</SettingsNavGroup>
		</SettingsSidebar>
		<!-- OSLMS-CUSTOM: padded, scrollable content pane (re-applied on SettingsDialog at the v2.59.0 merge) -->
		<SettingsContent v-if="data.doc" id="settings-modal">
			<SettingsPanel
				v-for="item in items"
				:key="tabKey(item)"
				:value="tabKey(item)"
				class="p-8 overflow-x-auto overflow-y-auto"
			>
				<component
					v-if="item.template"
					:is="item.template"
					v-bind="panelProps(item)"
				/>
				<SettingDetails
					v-else
					:sections="item.sections"
					:label="item.label"
					:description="item.description"
					:data="data"
				/>
			</SettingsPanel>
		</SettingsContent>
	</SettingsDialog>
</template>
<script setup>
import {
	SettingsContent,
	SettingsDialog,
	SettingsNavGroup,
	SettingsNavItem,
	SettingsPanel,
	SettingsSidebar,
	createDocumentResource,
} from 'frappe-ui'
import {
	computed,
	inject,
	markRaw,
	onBeforeUnmount,
	onMounted,
	ref,
	watch,
} from 'vue'
import { useSettings } from '@/stores/settings'
import SettingDetails from '@/components/Settings/SettingDetails.vue'
import EmailConfig from '@/components/Settings/EmailAccount/EmailConfig.vue'
// OSLMS-CUSTOM: tabs shared with the manager settings panel (SettingsGestore.vue)
import {
	brandingTab,
	categoriesTab,
	courseProgressTab,
	emailTemplatesTab,
	googleCalendarTab,
	googleMeetTab,
	membersTab,
	welcomeTab,
	zoomTab,
} from '@/oslms/utils/settingsTabs'
import Badges from '@/components/Settings/Badges/Badges.vue'
import RavenSettings from '@/components/Settings/Raven/RavenSettings.vue'
import { buildOslmsSettingsTabs } from '@/oslms/utils/settings'
import * as lucideIcons from 'lucide-vue-next'

// OSLMS-CUSTOM: Google Calendar tab reserved to System Manager and Gestore
const GOOGLE_CALENDAR_ROLES = ['System Manager', 'Gestore']
// OSLMS-CUSTOM: system-wide tabs (General, Badges, Signup, SEO) reserved to administrators, hidden from Moderator/Gestore
const ADMIN_ONLY_ROLES = ['System Manager', 'Administrator']
// OSLMS-CUSTOM: os_lms integration tabs open to administrators plus Gestore
// Roles allowed on the os_lms integration tabs (TrueSkills API, Prompt AI):
// administrators plus the "Gestore" manager bundle.
const OS_INTEGRATION_ROLES = ['Gestore']

const user = inject('$user')

const canManageGoogleCalendars = () => {
	const roles = user?.data?.roles || []
	return GOOGLE_CALENDAR_ROLES.some((role) => roles.includes(role))
}

const isAdministrator = () => {
	if (user?.data?.name === 'Administrator') return true
	const roles = user?.data?.roles || []
	return ADMIN_ONLY_ROLES.some((role) => roles.includes(role))
}

const canManageOsIntegrations = () => {
	if (isAdministrator()) return true
	const roles = user?.data?.roles || []
	return OS_INTEGRATION_ROLES.some((role) => roles.includes(role))
}

const show = defineModel()
const doctype = ref('LMS Settings')
const activeTab = ref('')
const settingsStore = useSettings()

// Tells openSettings there is something here to open. Nothing mounts this on a
// phone, and a moderator asking for Settings from a routed form there would
// otherwise have their form closed for a dialog that never appeared.
onMounted(() => {
	settingsStore.isSettingsMounted = true
})
onBeforeUnmount(() => {
	settingsStore.isSettingsMounted = false
})

const data = createDocumentResource({
	doctype: doctype.value,
	name: doctype.value,
	fields: ['*'],
	cache: doctype.value,
	auto: true,
})

// OSLMS-CUSTOM: the settings tree stays here instead of upstream's
// settingsStructure.js (v2.62.0): ours carries role conditions, the os_lms tabs,
// labels translated where defined and stable keys. settingsStructure.js is not
// read by this dialog, so upstream changes to it must be ported here by hand.
const tabsStructure = computed(() => {
	return [
		{
			key: 'Configuration',
			label: __('Configuration'),
			hideLabel: false,
			items: [
				{
					key: 'General',
					label: __('General'),
					icon: 'lucide-wrench',
					description: __(
						'Configure system-wide defaults, notifications, and contact information',
					),
					// OSLMS-CUSTOM: administrators only (see ADMIN_ONLY_ROLES)
					condition: isAdministrator,
					sections: [
						{
							label: __('System Configurations'),
							columns: [
								{
									fields: [
										{
											label: __('Allow Guest Access'),
											name: 'allow_guest_access',
											description: __(
												'If enabled, users can access the course and batch lists without logging in.',
											),
											type: 'checkbox',
										},
										{
											label: __('Prevent Skipping Videos'),
											name: 'prevent_skipping_videos',
											type: 'checkbox',
											description: __(
												'If enabled, users will no able to move forward in a video',
											),
										},
									],
								},
								{
									fields: [
										{
											label: __('Disable PWA'),
											name: 'disable_pwa',
											type: 'checkbox',
											description: __(
												'If checked, users will not be able to install the application as a Progressive Web App.',
											),
										},
										{
											label: __('Send calendar invite for evaluations'),
											name: 'send_calendar_invite_for_evaluations',
											description: __(
												'If enabled, it sends google calendar invite to the student for evaluations.',
											),
											type: 'checkbox',
										},
									],
								},
							],
						},

						{
							label: __('Notifications'),
							columns: [
								{
									fields: [
										{
											label: __('Send Notification for Published Courses'),
											name: 'send_notification_for_published_courses',
											type: 'select',
											options: [' ', 'Email', 'In-app'],
											description: __(
												'Notify members when a new course is published.',
											),
										},
									],
								},
								{
									fields: [
										{
											label: __('Send Notification for Published Batches'),
											name: 'send_notification_for_published_batches',
											type: 'select',
											options: [' ', 'Email', 'In-app'],
											description: __(
												'Notify members when a new batch is published.',
											),
										},
									],
								},
							],
						},
						{
							label: __('Email Templates'),
							columns: [
								{
									fields: [
										{
											label: __('Batch Confirmation Email Template'),
											name: 'batch_confirmation_template',
											doctype: 'Email Template',
											type: 'Link',
											description: __(
												'Email template sent to students upon batch enrollment confirmation.',
											),
										},
									],
								},
								{
									fields: [
										{
											label: __('Certification Email Template'),
											name: 'certification_template',
											doctype: 'Email Template',
											type: 'Link',
											description: __(
												'Email template sent to students when they earn a certification.',
											),
										},
									],
								},
							],
						},
						{
							label: __('Contact Information'),
							columns: [
								{
									fields: [
										{
											label: __('Email'),
											name: 'contact_us_email',
											type: 'text',
											description: __(
												'Users can reach out to this email for support or inquiries.',
											),
										},
									],
								},
								{
									fields: [
										{
											label: __('URL'),
											name: 'contact_us_url',
											type: 'text',
											description: __(
												'Users can reach out to this URL for support or inquiries.',
											),
										},
									],
								},
							],
						},
						{
							label: __('Jobs'),
							columns: [
								{
									fields: [
										{
											label: __('Allow Job Posting'),
											name: 'allow_job_posting',
											type: 'checkbox',
											description: __(
												'If enabled, users can post job openings on the job board. Else only admins can post jobs.',
											),
										},
									],
								},
								{
									fields: [],
								},
							],
						},
						{
							label: __('Integrations'),
							columns: [
								{
									fields: [
										{
											label: __('Livecode URL'),
											name: 'livecode_url',
											doctype: 'Livecode URL',
											type: 'text',
											description:
												'https://docs.frappe.io/learning/falcon-self-hosting-guide',
										},
									],
								},
								{
									fields: [
										{
											label: __('Unsplash Access Key'),
											name: 'unsplash_access_key',
											description: __(
												'Allows users to pick a profile cover image from Unsplash. https://unsplash.com/documentation#getting-started.',
											),
											type: 'password',
										},
									],
								},
							],
						},
					],
				},
				// OSLMS-CUSTOM: shared with the manager panel (oslms/utils/settingsTabs.js); stable key 'Course Progress'
				courseProgressTab(),
				{
					key: 'Badges',
					label: __('Badges'),
					description: __(
						'Create badges and assign them to students to acknowledge their achievements',
					),
					icon: 'lucide-award',
					template: markRaw(Badges),
					// OSLMS-CUSTOM: administrators only (see ADMIN_ONLY_ROLES)
					condition: isAdministrator,
				},
				// OSLMS-CUSTOM: shared with the manager panel (oslms/utils/settingsTabs.js)
				categoriesTab(),
			],
		},
		{
			label: 'Email',
			items: [
				{
					label: 'Accounts',
					description: 'Manage email accounts for incoming and outgoing mail',
					icon: 'lucide-mail',
					template: markRaw(EmailConfig),
				},
				// OSLMS-CUSTOM: shared with the manager panel (oslms/utils/settingsTabs.js); stable key 'Email Templates'
				emailTemplatesTab(),
			],
		},
		{
			key: 'Users',
			label: __('User Management'),
			hideLabel: false,
			items: [
				// OSLMS-CUSTOM: shared with the manager panel (oslms/utils/settingsTabs.js); key stays 'Members' for openSettings('Members')
				membersTab(),
			],
		},
		// OSLMS-CUSTOM: upstream "Payment" group (Configuration, Gateways, Transactions, Coupons) intentionally removed from the settings dialog
		{
			key: 'Conferencing',
			label: __('Conferencing'),
			hideLabel: false,
			items: [
				// OSLMS-CUSTOM: shared with the manager panel (oslms/utils/settingsTabs.js); Google Calendar for System Manager + Gestore
				zoomTab(),
				googleMeetTab(),
				googleCalendarTab(canManageGoogleCalendars),
			],
		},
		{
			key: 'Integrations',
			label: __('Integrations'),
			hideLabel: false,
			items: [
				{
					key: 'Raven',
					label: __('Raven'),
					description: __(
						'Automatically sync Raven workspace and channel membership from your students and staff',
					),
					icon: 'lucide-messages-square',
					// OSLMS-CUSTOM: Raven is a platform-wide integration, administrators only
					condition: isAdministrator,
					template: markRaw(RavenSettings),
				},
			],
		},
		{
			key: 'Customize',
			label: __('Customize'),
			hideLabel: false,
			items: [
				// OSLMS-CUSTOM: shared with the manager panel (oslms/utils/settingsTabs.js)
				brandingTab(),
				{
					key: 'Sidebar',
					label: __('Sidebar'),
					icon: 'lucide-panel-left',
					description: __('Choose the items you want to show in the sidebar'),
					sections: [
						{
							columns: [
								{
									fields: [
										// OSLMS-CUSTOM: extra sidebar visibility toggle (Home), backed by an os_lms custom field on LMS Settings
										{
											label: __('Home'),
											name: 'home',
											type: 'checkbox',
										},
										{
											label: __('Courses'),
											name: 'courses',
											type: 'checkbox',
											description: 'Show the Courses link in the sidebar.',
										},
										{
											label: __('Batches'),
											name: 'batches',
											type: 'checkbox',
											description: 'Show the Batches link in the sidebar.',
										},
										// OSLMS-CUSTOM: extra sidebar visibility toggle (Programs), backed by an os_lms custom field on LMS Settings
										{
											label: __('Programs'),
											name: 'programs',
											type: 'checkbox',
										},
										{
											label: __('Programming Exercises'),
											name: 'programming_exercises',
											type: 'checkbox',
											description:
												'Show the Programming Exercises link in the sidebar.',
										},
										{
											label: __('Certifications'),
											name: 'certifications',
											type: 'checkbox',
											description:
												'Show the Certifications link in the sidebar.',
										},
									],
								},
								{
									fields: [
										// OSLMS-CUSTOM: extra sidebar visibility toggle (Search, Quizzes, Assignments), backed by an os_lms custom field on LMS Settings
										{
											label: __('Search'),
											name: 'search',
											type: 'checkbox',
										},
										{
											label: __('Quizzes'),
											name: 'quizzes',
											type: 'checkbox',
										},
										{
											label: __('Assignments'),
											name: 'assignments',
											type: 'checkbox',
										},
										{
											label: __('Jobs'),
											name: 'jobs',
											type: 'checkbox',
											description: 'Show the Jobs link in the sidebar.',
										},
										{
											label: __('Statistics'),
											name: 'statistics',
											type: 'checkbox',
											description: 'Show the Statistics link in the sidebar.',
										},
										{
											label: __('Notifications'),
											name: 'notifications',
											type: 'checkbox',
											description:
												'Show the Notifications link in the sidebar.',
										},
									],
								},
							],
						},
					],
				},
				{
					key: 'Signup',
					label: __('Signup'),
					icon: 'lucide-log-in',
					description: __(
						'Manage the settings related to user signup and registration',
					),
					// OSLMS-CUSTOM: administrators only (see ADMIN_ONLY_ROLES)
					condition: isAdministrator,
					sections: [
						{
							columns: [
								{
									fields: [
										{
											label: __('Identify User Category'),
											name: 'user_category',
											type: 'checkbox',
											description: __(
												'Enable this option to identify the user category during signup.',
											),
										},
										{
											label: __('Disable signup'),
											name: 'disable_signup',
											type: 'checkbox',
											description: __(
												'New users will have to be manually registered by Admins.',
											),
										},
										{
											label: __('Signup Consent HTML'),
											name: 'custom_signup_content',
											type: 'Code',
											mode: 'htmlmixed',
											rows: 10,
											description:
												'Custom HTML shown on the signup page, e.g. for consent notices or terms of service.',
										},
									],
								},
							],
						},
					],
				},
				// OSLMS-CUSTOM: welcome notification and welcome video, shared with the manager panel (oslms/utils/settingsTabs.js)
				welcomeTab(),
				{
					key: 'SEO',
					label: __('SEO'),
					icon: 'lucide-search',
					description: __(
						'Manage the SEO settings to improve your website ranking on search engines',
					),
					// OSLMS-CUSTOM: administrators only (see ADMIN_ONLY_ROLES)
					condition: isAdministrator,
					sections: [
						{
							columns: [
								{
									fields: [
										{
											label: __('Meta Description'),
											name: 'meta_description',
											type: 'textarea',
											rows: 4,
											description: __(
												"This description will be shown on lists and pages that don't have meta description",
											),
										},
										{
											label: __('Meta Keywords'),
											name: 'meta_keywords',
											type: 'textarea',
											rows: 4,
											description: __(
												'Comma separated keywords for search engines to find your website.',
											),
										},
										{
											label: __('Meta Image'),
											name: 'meta_image',
											type: 'Upload',
											size: 'lg',
											// Open Graph image: unauthenticated crawlers fetch it.
											public: true,
											description:
												'Default social-share image used when pages lack their own meta image.',
										},
									],
								},
							],
						},
					],
				},
			],
		},
		// OSLMS-CUSTOM: os_lms tabs (TrueSkills API, Configurazioni, AI, Prompt AI) injected from @/oslms/utils/settings
		...buildOslmsSettingsTabs({ isAdministrator, canManageOsIntegrations }),
	]
})

// OSLMS-CUSTOM: stable tab identity (English key), falling back to the label for tabs that carry no key
const tabKey = (item) => item.key || item.label

const items = computed(() => tabs.value.flatMap((group) => group.items))

// Members and Transactions own dialogs of their own and need to close Settings.
// OSLMS-CUSTOM: props switch on the stable tab key; os_lms templates (AI, TrueSkills API) receive their field sections
const panelProps = (item) => ({
	label: item.label,
	description: item.description,
	...(['Branding', 'AI', 'TrueSkills API'].includes(item.key)
		? { sections: item.sections }
		: {}),
	...(['Members', 'Transactions'].includes(item.key)
		? { 'onUpdate:show': (val) => (show.value = val), show: show.value }
		: {}),
})

const tabs = computed(() => {
	return tabsStructure.value
		// OSLMS-CUSTOM: whole groups can carry a role condition; groups left empty are dropped
		.filter((tab) => !tab.condition || tab.condition())
		.map((tab) => {
			return {
				...tab,
				items: tab.items.filter((item) => {
					return !item.condition || item.condition()
				}),
			}
		})
		.filter((tab) => tab.items.length > 0)
})

watch(show, () => {
	if (show.value) {
		// OSLMS-CUSTOM: deep links (openSettings) match the stable key, not the translated label
		const stored = items.value
			.find((item) => item.key === settingsStore.activeTab)
		activeTab.value = tabKey(stored || items.value[0])
	} else {
		activeTab.value = ''
		settingsStore.isSettingsOpen = false
	}
})
</script>
