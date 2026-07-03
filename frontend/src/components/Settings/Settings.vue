<template>
	<Dialog v-model="show" :options="{ size: '5xl' }">
		<template #body>
			<div class="flex h-[calc(100vh_-_8rem)]" id="settings-modal">
				<div
					class="flex w-52 shrink-0 flex-col bg-surface-gray-2 p-2 overflow-y-auto"
				>
					<h1 class="mb-3 px-2 pt-2 text-xl-semibold text-ink-gray-9">
						{{ __('Settings') }}
					</h1>
					<div class="space-y-5">
						<div v-for="tab in tabs" :key="tab.key">
							<div
								v-if="!tab.hideLabel"
								class="mb-2 mt-3 flex cursor-pointer gap-1.5 px-1 text-base text-ink-gray-5 transition-all duration-300 ease-in-out"
							>
								<span>{{ tab.label }}</span>
							</div>
							<nav class="space-y-1">
								<div v-for="item in tab.items" @click="activeTab = item">
									<SidebarLink
										:link="item"
										:key="item.key"
										:activeTab="activeTab?.key"
									/>
								</div>
							</nav>
						</div>
					</div>
				</div>
				<div
					v-if="activeTab && data.doc"
					:key="activeTab.key"
					class="flex flex-1 flex-col p-8 bg-surface-elevation-2 overflow-x-auto overflow-y-auto"
				>
					<component
						v-if="activeTab.template"
						:is="activeTab.template"
						v-bind="{
							label: activeTab.label,
							description: activeTab.description,
							...(activeTab.key == 'Branding' ||
							activeTab.key == 'AI' ||
							activeTab.key == 'TrueSkills API'
								? { sections: activeTab.sections }
								: {}),
							...(activeTab.key == 'Members' || activeTab.key == 'Transactions'
								? { 'onUpdate:show': (val) => (show = val), show }
								: {}),
						}"
					/>
					<SettingDetails
						v-else
						:sections="activeTab.sections"
						:label="activeTab.label"
						:description="activeTab.description"
						:data="data"
					/>
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, createDocumentResource } from 'frappe-ui'
import { computed, inject, markRaw, ref, watch } from 'vue'
import { useSettings } from '@/stores/settings'
import SettingDetails from '@/components/Settings/SettingDetails.vue'
import SidebarLink from '@/components/Sidebar/SidebarLink.vue'
import Members from '@/components/Settings/Members.vue'
import Categories from '@/components/Settings/Categories.vue'
import EmailTemplatePage from '@/components/Settings/EmailTemplate/EmailTemplatePage.vue'
import EmailConfig from '@/components/Settings/EmailAccount/EmailConfig.vue'
import BrandSettings from '@/components/Settings/BrandSettings.vue'
import ZoomSettings from '@/components/Settings/ZoomSettings.vue'
import GoogleMeetSettings from '@/components/Settings/GoogleMeetSettings.vue'
import GoogleCalendarSettings from '@/components/Settings/GoogleCalendarSettings.vue'
import Badges from '@/components/Settings/Badges.vue'
import { buildOslmsSettingsTabs } from '@/oslms/utils/settings'

const GOOGLE_CALENDAR_ROLES = ['System Manager', 'Gestore']
const ADMIN_ONLY_ROLES = ['System Manager', 'Administrator']

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

const show = defineModel()
const doctype = ref('LMS Settings')
const activeTab = ref(null)
const settingsStore = useSettings()

const data = createDocumentResource({
	doctype: doctype.value,
	name: doctype.value,
	fields: ['*'],
	cache: doctype.value,
	auto: true,
})

const tabsStructure = computed(() => {
	return [
		{
			key: 'Configuration',
			label: __('Configuration'),
			hideLabel: true,
			items: [
				{
					key: 'General',
					label: __('General'),
					icon: 'Wrench',
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
											description:
												'Notify members when a new course is published.',
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
											description:
												'Notify members when a new batch is published.',
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
											description:
												'Email template sent to students upon batch enrollment confirmation.',
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
											description:
												'Email template sent to students when they earn a certification.',
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
							label: 'Integrations',
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
				{
					label: __('Course Progress'),
					icon: 'Activity',
					description: __(
						'Control how lessons are marked complete: dwell time and enforcement toggles for video, quiz, and assignment.',
					),
					sections: [
						{
							label: __('Dwell Time'),
							columns: [
								{
									fields: [
										{
											label: __('Lesson dwell time (seconds)'),
											name: 'lesson_dwell_time',
											type: 'number',
											description: __(
												'Seconds a learner must stay on a lesson before it auto-marks complete.',
											),
										},
									],
								},
							],
						},
						{
							label: __('Enforcement'),
							columns: [
								{
									fields: [
										{
											label: __('Enforce video completion'),
											name: 'enforce_video_completion',
											type: 'checkbox',
											description: __(
												'When enabled, lessons that contain a video can only be marked complete by playing the video to the end. If the video fails to load, the dwell timer is used as a fallback.',
											),
										},
										{
											label: __('Enforce assignment completion'),
											name: 'enforce_assignment_completion',
											type: 'checkbox',
											description: __(
												'When enabled, lessons with an assignment cannot be marked complete until the assignment is submitted.',
											),
										},
									],
								},
								{
									fields: [
										{
											label: __('Enforce quiz completion'),
											name: 'enforce_quiz_completion',
											type: 'checkbox',
											description: __(
												'When enabled, lessons with a quiz cannot be marked complete until the quiz is submitted.',
											),
										},
									],
								},
							],
						},
					],
				},
				{
					key: 'Badges',
					label: __('Badges'),
					description: __(
						'Create badges and assign them to students to acknowledge their achievements',
					),
					icon: 'Award',
					template: markRaw(Badges),
					condition: isAdministrator,
				},
				{
					key: 'Categories',
					label: __('Categories'),
					description: __('Double click to edit the category'),
					icon: 'Network',
					template: markRaw(Categories),
				},
			],
		},
		{
			label: 'Email',
			items: [
				{
					label: 'Accounts',
					description: 'Manage email accounts for incoming and outgoing mail',
					icon: 'Mail',
					template: markRaw(EmailConfig),
				},
				{
					label: 'Templates',
					description: 'Manage the email templates for your learning system',
					icon: 'MailPlus',
					template: markRaw(EmailTemplatePage),
				},
			],
		},
		{
			key: 'Users',
			label: __('Users'),
			hideLabel: false,
			items: [
				{
					key: 'Members',
					label: __('Members'),
					description: __(
						'Add new members or manage roles and permissions of existing members',
					),
					icon: 'User',
					template: markRaw(Members),
				},
			],
		},
		{
			key: 'Conferencing',
			label: __('Conferencing'),
			hideLabel: false,
			items: [
				{
					key: 'Zoom',
					label: __('Zoom'),
					description: __(
						'Manage zoom accounts to conduct live classes from batches',
					),
					icon: 'Video',
					template: markRaw(ZoomSettings),
				},
				{
					key: 'Google Meet',
					label: __('Google Meet'),
					description: __(
						'Manage Google Meet accounts to conduct live classes from batches',
					),
					icon: 'Presentation',
					template: markRaw(GoogleMeetSettings),
				},
				{
					key: 'Google Calendar',
					label: __('Google Calendar'),
					description: __(
						'Manage Google Calendars used for live classes and evaluations',
					),
					icon: 'Calendar',
					template: markRaw(GoogleCalendarSettings),
					condition: canManageGoogleCalendars,
				},
			],
		},
		{
			key: 'Customize',
			label: __('Customize'),
			hideLabel: false,
			items: [
				{
					key: 'Branding',
					label: __('Branding'),
					icon: 'Blocks',
					description: __(
						'Customize the brand name and logo to make the application your own',
					),
					template: markRaw(BrandSettings),
					sections: [
						{
							columns: [
								{
									fields: [
										{
											label: __('Brand Name'),
											name: 'app_name',
											type: 'text',
										},
										{
											label: __('Logo'),
											name: 'banner_image',
											type: 'Upload',
											description: __(
												'Appears in the top left corner of the application to represent your brand.',
											),
										},
										{
											label: __('Favicon'),
											name: 'favicon',
											type: 'Upload',
											description: __(
												'Appears in the browser tab next to the page title to help users quickly identify the application.',
											),
										},
									],
								},
							],
						},
					],
				},
				{
					key: 'Sidebar',
					label: __('Sidebar'),
					icon: 'PanelLeftIcon',
					description: __('Choose the items you want to show in the sidebar'),
					sections: [
						{
							columns: [
								{
									fields: [
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
					icon: 'LogIn',
					description: __(
						'Manage the settings related to user signup and registration',
					),
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
				{
					key: 'Welcome Video',
					label: __('Welcome'),
					icon: 'PlayCircle',
					description: __(
						'Configura la notifica e il video di benvenuto mostrati agli studenti al primo login. I due possono essere attivati indipendentemente.',
					),
					sections: [
						{
							label: __('Welcome Notification'),
							columns: [
								{
									fields: [
										{
											label: __('Enable Welcome Notification'),
											name: 'welcome_notification_enabled',
											type: 'checkbox',
											description: __(
												'Se attivo, invia una notifica di benvenuto al primo accesso dello studente.',
											),
										},
										{
											label: __('Welcome Notification Message'),
											name: 'welcome_notification_message',
											type: 'textarea',
											rows: 4,
											description: __(
												'Testo della notifica di benvenuto. Indipendente dal video.',
											),
										},
									],
								},
							],
						},
						{
							label: __('Welcome Video'),
							columns: [
								{
									fields: [
										{
											label: __('Enable Welcome Video'),
											name: 'welcome_video_enabled',
											type: 'checkbox',
											description: __(
												'Se attivo, mostra il video di benvenuto agli studenti la prima volta che accedono.',
											),
										},
										{
											label: __('Welcome Video Title'),
											name: 'welcome_video_title',
											type: 'text',
											description: __(
												"Titolo mostrato sull'hero video nella home dello studente.",
											),
										},
										{
											label: __('Welcome Video Subtitle'),
											name: 'welcome_video_subtitle',
											type: 'text',
											description: __(
												"Sottotitolo opzionale mostrato sotto al titolo dell'hero video.",
											),
										},
										{
											label: __('Welcome Video'),
											name: 'welcome_video_file',
											type: 'VideoSourceInput',
											allowedExtensions: [
												'mp4',
												'webm',
												'ogg',
												'ogv',
												'mov',
												'm4v',
											],
											description: __(
												"Incolla un link al video (YouTube, Vimeo, ecc.) oppure scegli un file caricato tramite l'icona. I link esterni vengono mostrati in un iframe, i file locali in un player nativo.",
											),
										},
									],
								},
							],
						},
					],
				},
				{
					key: 'SEO',
					label: __('SEO'),
					icon: 'Search',
					description: __(
						'Manage the SEO settings to improve your website ranking on search engines',
					),
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
		...buildOslmsSettingsTabs({ isAdministrator }),
	]
})

const tabs = computed(() => {
	return tabsStructure.value
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

watch(show, async () => {
	if (show.value) {
		const currentTab = await tabs.value
			.flatMap((tab) => tab.items)
			.find((item) => item.key === settingsStore.activeTab)
		activeTab.value = currentTab || tabs.value[0].items[0]
	} else {
		activeTab.value = null
		settingsStore.isSettingsOpen = false
	}
})
</script>
