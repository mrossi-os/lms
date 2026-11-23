// OSLMS-CUSTOM: settings tabs shared by Settings.vue (administrators) and
// SettingsGestore.vue (Gestore + administrators). One definition per tab, so
// the two panels cannot drift apart. Builders are functions, called inside a
// computed, so every __() label re-evaluates once translations load.
// Design: docs/superpowers/specs/2026-11-18-impostazioni-gestore-design.md
import { markRaw } from 'vue'
import Members from '@/components/Settings/Members.vue'
import Categories from '@/components/Settings/Categories.vue'
import EmailTemplatePage from '@/components/Settings/EmailTemplate/EmailTemplatePage.vue'
import BrandSettings from '@/components/Settings/BrandSettings.vue'
import ZoomSettings from '@/components/Settings/ZoomSettings.vue'
import GoogleMeetSettings from '@/components/Settings/GoogleMeetSettings.vue'
import GoogleCalendarSettings from '@/components/Settings/GoogleCalendarSettings.vue'

export const courseProgressTab = () => ({
	// Stable key: the label is translated, so it cannot identify the tab.
	key: 'Course Progress',
	label: __('Course Progress'),
	icon: 'lucide-activity',
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
							min: 1,
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
})

export const categoriesTab = () => ({
	key: 'Categories',
	label: __('Categories'),
	description: __('Group courses under a category'),
	icon: 'lucide-network',
	template: markRaw(Categories),
})

export const emailTemplatesTab = () => ({
	// Stable key: before this module the tab was identified by its label "Templates".
	key: 'Email Templates',
	label: 'Templates',
	description: 'Manage the email templates for your learning system',
	icon: 'lucide-mail-plus',
	template: markRaw(EmailTemplatePage),
})

export const membersTab = () => ({
	// Key stays 'Members' so openSettings('Members') deep links keep working after upstream renamed the tab to "Users"
	key: 'Members',
	label: __('Users'),
	description: __(
		'Manage users by adding or inviting them, and assign roles to control their access and permissions',
	),
	icon: 'lucide-user',
	template: markRaw(Members),
})

export const zoomTab = () => ({
	key: 'Zoom',
	label: __('Zoom'),
	description: __('Manage zoom accounts to conduct live classes from batches'),
	icon: 'lucide-video',
	template: markRaw(ZoomSettings),
})

export const googleMeetTab = () => ({
	key: 'Google Meet',
	label: __('Google Meet'),
	description: __(
		'Manage Google Meet accounts to conduct live classes from batches',
	),
	icon: 'lucide-presentation',
	template: markRaw(GoogleMeetSettings),
})

// Google Calendar accounts for live class and evaluation invites; the caller
// decides who sees it (Settings.vue: System Manager + Gestore).
export const googleCalendarTab = (condition) => ({
	key: 'Google Calendar',
	label: __('Google Calendar'),
	description: __(
		'Manage Google Calendars used for live classes and evaluations',
	),
	icon: 'lucide-calendar',
	template: markRaw(GoogleCalendarSettings),
	...(condition ? { condition } : {}),
})

export const brandingTab = () => ({
	key: 'Branding',
	label: __('Branding'),
	icon: 'lucide-palette',
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
})

// Welcome notification and welcome video shown to students on first login.
export const welcomeTab = () => ({
	key: 'Welcome Video',
	label: __('Welcome'),
	icon: 'lucide-circle-play',
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
							allowedExtensions: ['mp4', 'webm', 'ogg', 'ogv', 'mov', 'm4v'],
							description: __(
								"Incolla un link al video (YouTube, Vimeo, ecc.) oppure scegli un file caricato tramite l'icona. I link esterni vengono mostrati in un iframe, i file locali in un player nativo.",
							),
						},
					],
				},
			],
		},
	],
})
