<template>
	<Dialog v-model="show" :options="{ size: '5xl' }">
		<template #body>
			<div class="flex h-[calc(100vh_-_8rem)] card" id="settings-modal">
				<div
					class="flex w-52 shrink-0 flex-col bg-surface-gray-2 p-2 overflow-y-auto"
				>
					<h1 class="mb-3 px-2 pt-2 text-lg font-semibold text-ink-gray-9">
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
					class="flex flex-1 flex-col p-8 bg-surface-modal overflow-x-auto"
				>
					<component
						v-if="activeTab.template"
						:is="activeTab.template"
						v-bind="{
							label: activeTab.label,
							description: activeTab.description,
							...(activeTab.key == 'Branding' || activeTab.key == 'AI'
								? { sections: activeTab.sections }
								: {}),
							...(activeTab.key == 'Evaluators' ||
							activeTab.key == 'Members' ||
							activeTab.key == 'Transactions'
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
import { computed, markRaw, ref, watch } from 'vue'
import { useSettings } from '@/stores/settings'
import SettingDetails from '@/components/Settings/SettingDetails.vue'
import SidebarLink from '@/components/Sidebar/SidebarLink.vue'
import Members from '@/components/Settings/Members.vue'
import Evaluators from '@/components/Settings/Evaluators.vue'
import Categories from '@/components/Settings/Categories.vue'
import EmailTemplates from '@/components/Settings/EmailTemplates.vue'
import BrandSettings from '@/components/Settings/BrandSettings.vue'
import PaymentGateways from '@/components/Settings/PaymentGateways.vue'
import Coupons from '@/components/Settings/Coupons/Coupons.vue'
import Transactions from '@/components/Settings/Transactions/Transactions.vue'
import ZoomSettings from '@/components/Settings/ZoomSettings.vue'
import GoogleMeetSettings from '@/components/Settings/GoogleMeetSettings.vue'
import Badges from '@/components/Settings/Badges.vue'
import AISettings from '@/oslms/components/ai/Settings/AISettings.vue'

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
							label: '',
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
					key: 'Badges',
					label: __('Badges'),
					description: __(
						'Create badges and assign them to students to acknowledge their achievements',
					),
					icon: 'Award',
					template: markRaw(Badges),
				},
				{
					key: 'Categories',
					label: __('Categories'),
					description: __('Double click to edit the category'),
					icon: 'Network',
					template: markRaw(Categories),
				},
				{
					key: 'Email Templates',
					label: __('Email Templates'),
					description: __(
						'Manage the email templates for your learning system',
					),
					icon: 'MailPlus',
					template: markRaw(EmailTemplates),
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
				{
					key: 'Evaluators',
					label: __('Evaluators'),
					icon: 'UserCircle2',
					description: __(
						'Add new evaluators or check the slots of existing evaluators',
					),
					template: markRaw(Evaluators),
				},
			],
		},
		// {
		// 	key: 'Payment',
		// 	label: __('Payment'),
		// 	hideLabel: false,
		// 	items: [
		// 		{
		// 			key: 'Configuration',
		// 			label: __('Configuration'),
		// 			icon: 'CreditCard',
		// 			description: __(
		// 				'Manage all your payment related settings and defaults',
		// 			),
		// 			sections: [
		// 				{
		// 					columns: [
		// 						{
		// 							fields: [
		// 								{
		// 									label: __('Default Currency'),
		// 									name: 'default_currency',
		// 									type: 'Link',
		// 									doctype: 'Currency',
		// 								},
		// 								{
		// 									label: __('Show USD equivalent amount'),
		// 									name: 'show_usd_equivalent',
		// 									type: 'checkbox',
		// 									description: __(
		// 										'If enabled, it shows the USD equivalent amount for all transactions based on the current exchange rate.',
		// 									),
		// 								},
		// 								{
		// 									label: __('Apply rounding on equivalent'),
		// 									name: 'apply_rounding',
		// 									type: 'checkbox',
		// 									description: __(
		// 										'If enabled, it applies rounding on the USD equivalent amount.',
		// 									),
		// 								},
		// 							],
		// 						},
		// 						{
		// 							fields: [
		// 								{
		// 									label: __('Payment Gateway'),
		// 									name: 'payment_gateway',
		// 									type: 'Link',
		// 									doctype: 'Payment Gateway',
		// 								},
		// 								{
		// 									label: __('Apply GST for India'),
		// 									name: 'apply_gst',
		// 									type: 'checkbox',
		// 									description: __(
		// 										'If enabled, GST will be applied to the price for students from India.',
		// 									),
		// 								},
		// 							],
		// 						},
		// 					],
		// 				},
		// 				{
		// 					label: __('Payment Reminders'),
		// 					columns: [
		// 						{
		// 							fields: [
		// 								{
		// 									label: __('Send payment reminders for batch'),
		// 									name: 'send_payment_reminders_for_batch',
		// 									type: 'checkbox',
		// 									description: __(
		// 										'If enabled, it sends payment reminders to students who left the payment incomplete for a batch.',
		// 									),
		// 								},
		// 							],
		// 						},
		// 						{
		// 							fields: [
		// 								{
		// 									label: __('Send payment reminders for course'),
		// 									name: 'send_payment_reminders_for_course',
		// 									type: 'checkbox',
		// 									description: __(
		// 										'If enabled, it sends payment reminders to students who left the payment incomplete for a course.',
		// 									),
		// 								},
		// 							],
		// 						},
		// 					],
		// 				},
		// 			],
		// 		},
		// 		{
		// 			key: 'Gateways',
		// 			label: __('Gateways'),
		// 			icon: 'DollarSign',
		// 			template: markRaw(PaymentGateways),
		// 			description: __('Add and manage all your payment gateways'),
		// 		},
		// 		{
		// 			key: 'Transactions',
		// 			label: __('Transactions'),
		// 			icon: 'Landmark',
		// 			template: markRaw(Transactions),
		// 			description: __('View all your payment transactions'),
		// 		},
		// 		{
		// 			key: 'Coupons',
		// 			label: __('Coupons'),
		// 			icon: 'Ticket',
		// 			template: markRaw(Coupons),
		// 			description: __('Manage discount coupons for courses and batches'),
		// 		},
		// 	],
		// },
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
										},
										{
											label: __('Batches'),
											name: 'batches',
											type: 'checkbox',
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
										},
										{
											label: __('Certifications'),
											name: 'certifications',
											type: 'checkbox',
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
										},
										{
											label: __('Statistics'),
											name: 'statistics',
											type: 'checkbox',
										},
										{
											label: __('Notifications'),
											name: 'notifications',
											type: 'checkbox',
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
										},
									],
								},
							],
						},
					],
				},
				{
					key: 'Welcome Video',
					label: __('Welcome Video'),
					icon: 'PlayCircle',
					description: __(
						'Configura il video di benvenuto mostrato agli studenti al primo login',
					),
					sections: [
						{
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
										},
									],
								},
							],
						},
					],
				},
			],
		},
		{
			key: 'AI',
			label: __('AI'),
			hideLabel: false,
			items: [
				{
					key: 'AI',
					label: __('AI'),
					icon: 'BrainCircuit',
					description: __(
						'Configure AI assistant settings for your learning system',
					),
					template: markRaw(AISettings),
					sections: [
						{
							label: __('Configuration'),
							columns: [
								{
									fields: [
										{
											label: __('Enabled'),
											name: 'enabled',
											type: 'checkbox',
											description: __(
												'Enable AI features for your learning system.',
											),
										},
										{
											label: __('Embedding Model'),
											name: 'embedding_model',
											type: 'text',
											description: __(
												'The model used to generate embeddings for content indexing.',
											),
										},
										{
											label: __('Embedding Model'),
											name: 'embedding_model',
											type: 'text',
											description: __(
												'The model used to generate embeddings for content indexing.',
											),
										},
										{
											label: __('LLM Model'),
											name: 'llm_model',
											type: 'text',
											description: __('The model used to chatbot.'),
										},
										{
											label: __('LLM System Prompt'),
											name: 'system_prompt',
											type: 'textarea',
											description: __('System prompt use with chatbot.'),
										},
										{
											label: __('Open AI Key'),
											name: 'openai_key',
											type: 'text',
											description: __('OpenAI key.'),
										},
									],
								},
								{
									fields: [
										{
											label: __('Chunk Size'),
											name: 'chunk_size',
											type: 'number',
											description: __(
												'Number of characters per text chunk for indexing.',
											),
										},
										{
											label: __('Chunk Overlap'),
											name: 'chunk_overlap',
											type: 'number',
											description: __(
												'Character overlap between consecutive chunks.',
											),
										},
										{
											label: __('Top K'),
											name: 'top_k',
											type: 'number',
											description: __(
												'Number of relevant chunks to retrieve for context.',
											),
										},
										{
											label: __('Vimeo Api Key'),
											name: 'vimeo_api_key',
											type: 'text',
											description: __('Api vimeo for transcript.'),
										},
									],
								},
							],
						},
					],
				},
			],
		},
	]
})

const tabs = computed(() => {
	return tabsStructure.value.map((tab) => {
		return {
			...tab,
			items: tab.items.filter((item) => {
				return !item.condition || item.condition()
			}),
		}
	})
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
