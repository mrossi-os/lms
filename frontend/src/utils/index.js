import { call, toast } from 'frappe-ui'
import colorsJSON from '@/utils/frappe-ui-colors.json'
import { Quiz } from '@/utils/quiz'
import { Program } from '@/utils/program'
import { Assignment } from '@/utils/assignment'
import { Upload } from '@/utils/upload'
import { Markdown } from '@/utils/markdownParser'
import { useSettings } from '@/stores/settings'
import { usersStore } from '@/stores/user'
import Header from '@editorjs/header'
import Paragraph from '@editorjs/paragraph'
import { CodeBox } from '@/utils/code'
import NestedList from '@editorjs/nested-list'
import InlineCode from '@editorjs/inline-code'
import { Underline } from '@/utils/inline/Underline'
import { Strikethrough } from '@/utils/inline/Strikethrough'
import { AlignLeft, AlignCenter, AlignRight } from '@/utils/inline/TextAlign'
import { Color } from '@/utils/inline/Color'
import { VIMEO_SHARE_RE } from '@/utils/video'
import {
	clipboardTunes,
	clipboardTuneNames,
} from '@/utils/blockTunes/clipboardTunes'
import dayjs from '@/utils/dayjs'
import Embed from '@editorjs/embed'
import SimpleImage from '@editorjs/simple-image'
import Table from '@editorjs/table'
import ColorPicker from 'editorjs-color-picker'

class ColorPickerInline extends ColorPicker {
	checkState() {
		return false
	}

	renderActions() {
		const el = super.renderActions()
		el.style.display = 'none'
		this._actionsEl = el
		el.addEventListener(
			'mousedown',
			(e) => {
				e.preventDefault()
				const sel = window.getSelection()
				if (sel && sel.rangeCount > 0) {
					this.lastRange = sel.getRangeAt(0)
				}
			},
			true,
		)
		el.addEventListener('click', (e) => {
			if (
				e.target.classList?.contains(
					'editorjs__color-selector__container-item',
				)
			) {
				el.style.display = 'none'
			}
		})
		return el
	}

	surround(range) {
		super.surround(range)
		if (this._actionsEl) {
			this._actionsEl.style.display =
				this._actionsEl.style.display === 'none' ? '' : 'none'
		}
	}
}
import 'plyr/dist/plyr.css'
import DOMPurify from 'dompurify'

const readOnlyMode = window.read_only_mode

// Pure formatting helpers live in a leaf module to avoid a barrel import cycle
// (index.js -> editor tools -> components -> '@/utils'). Re-exported here so
// existing '@/utils' consumers keep working; cycle-prone consumers import them
// from '@/utils/format' directly.
export {
	timeAgo,
	formatSeconds,
	escapeHTML,
	formatTimestamp,
} from '@/utils/format'

export function formatTime(timeString) {
	if (!timeString) return ''
	const [hour, minute] = timeString.split(':').map(Number)
	const dummyDate = new Date(0, 0, 0, hour, minute)
	const formattedTime = new Intl.DateTimeFormat('en-US', {
		hour: 'numeric',
		minute: 'numeric',
		hour12: true,
	}).format(dummyDate)
	return formattedTime
}

export function formatNumber(number) {
	return number.toLocaleString('en-IN', {
		maximumFractionDigits: 0,
	})
}

export function formatNumberIntoCurrency(number, currency) {
	if (number) {
		return number.toLocaleString('en-IN', {
			maximumFractionDigits: 0,
			style: 'currency',
			currency: currency,
		})
	}
	return ''
}

// create a function that formats numbers in thousands to k

export function formatAmount(amount) {
	if (amount > 999) {
		return (amount / 1000).toFixed(1) + 'k'
	}
	return amount
}

export function formatRating(value) {
	const n = Number(value)
	if (!isFinite(n)) return ''
	return (Math.round(n * 10) / 10).toString()
}

export function convertToTitleCase(str) {
	if (!str) {
		return ''
	}

	return str
		.toLowerCase()
		.split(' ')
		.map(function (word) {
			return word.charAt(0).toUpperCase().concat(word.substr(1))
		})
		.join(' ')
}
export function getFileSize(file_size) {
	let value = parseInt(file_size)
	if (value > 1048576) {
		return (value / 1048576).toFixed(2) + 'M'
	} else if (value > 1024) {
		return (value / 1024).toFixed(2) + 'K'
	}
	return value
}

export function getImgDimensions(imgSrc) {
	return new Promise((resolve) => {
		let img = new Image()
		img.onload = function () {
			let { width, height } = img
			resolve({ width, height, ratio: width / height })
		}
		img.src = imgSrc
	})
}

export function htmlToText(html) {
	const div = document.createElement('div')
	div.innerHTML = html
	return div.textContent || div.innerText || ''
}

// Visual order of the inline toolbar (automad layout). References registered
// inline-tool names: EditorJS built-ins (bold/italic/link) + our custom tools.
const INLINE_TOOLBAR_ORDER = [
	'alignLeft',
	'alignCenter',
	'alignRight',
	'bold',
	'italic',
	'link',
	'inlineCode',
	'underline',
	'strikeThrough',
	'color',
]

// Vimeo's "Copy link" button yields vimeo.com/share/<uuid>, which holds no video
// id: it doesn't redirect and Vimeo's own oEmbed API rejects it, so only the
// backend can resolve it (by reading the share page — the browser can't, no
// CORS). The embed tool matches services synchronously, so the paste is caught
// by the `vimeoShare` service and finished off here once the backend answers.
class VideoEmbed extends Embed {
	onPaste(event) {
		if (event.detail.key !== 'vimeoShare') {
			super.onPaste(event)
			return
		}
		// Not awaited: EditorJS ignores the returned promise anyway, and the
		// block is already inserted, so the tool can fill itself in later.
		this.resolveVimeoShare(event.detail.data)
	}

	async resolveVimeoShare(url) {
		// Grab the block before the first await, while it is still the current one.
		const block = this.currentBlock()

		// Renders the tool's preloader with the pasted URL underneath it.
		this.data = { service: 'vimeoShare', source: url, embed: url }

		const method = 'os_lms.os_lms.api.resolve_vimeo_share'
		try {
			const resolved = await call(method, { url })
			this.data = {
				service: 'vimeo',
				source: resolved.source,
				embed: resolved.embed,
			}
		} catch {
			toast.error(__('Could not load this Vimeo video'), {
				description: __(
					'Copy the link from the video page instead of the Share button.',
				),
			})
			this.replaceWithText(block, url)
		}
	}

	currentBlock() {
		const block = this.api.blocks.getBlockByIndex(
			this.api.blocks.getCurrentBlockIndex(),
		)
		// Make sure it really is ours before handing it to replaceWithText().
		return block?.holder?.contains(this.element) ? block : null
	}

	// Leave the author with the pasted URL as text — what they'd have got before
	// share links were handled at all — rather than an empty block.
	replaceWithText(block, url) {
		if (!block) return
		const index = this.api.blocks.getBlockIndex(block.id)
		if (typeof index !== 'number' || index < 0) return
		this.api.blocks.insert(
			'paragraph',
			{ text: url },
			{},
			index,
			false,
			true,
		)
	}
}

export function getEditorTools(isInstructorEditor = false, uploadContext = {}) {
	return {
		header: {
			class: Header,
			inlineToolbar: INLINE_TOOLBAR_ORDER,
			config: {
				placeholder: 'Header',
			},
		},
		list: {
			class: NestedList,
			inlineToolbar: INLINE_TOOLBAR_ORDER,
			config: {
				defaultStyle: 'ordered',
			},
		},
		upload: {
			class: Upload,
			config: uploadContext,
		},
		table: {
			class: Table,
			inlineToolbar: INLINE_TOOLBAR_ORDER,
		},
		quiz: Quiz,
		assignment: Assignment,
		program: Program,
		markdown: {
			class: Markdown,
			inlineToolbar: INLINE_TOOLBAR_ORDER,
		},
		image: SimpleImage,
		paragraph: {
			class: Paragraph,
			inlineToolbar: INLINE_TOOLBAR_ORDER,
			config: {
				preserveBlank: true,
			},
		},
		codeBox: {
			class: CodeBox,
			config: {
				useDefaultTheme: 'dark',
			},
		},
		inlineCode: {
			class: InlineCode,
			shortcut: 'CMD+SHIFT+M',
		},
		underline: Underline,
		strikeThrough: Strikethrough,
		alignLeft: AlignLeft,
		alignCenter: AlignCenter,
		alignRight: AlignRight,
		color: Color,
		copyBlock: clipboardTunes.copyBlock,
		cutBlock: clipboardTunes.cutBlock,
		pasteBlock: clipboardTunes.pasteBlock,
		ColorPicker: {
			class: ColorPickerInline,
			config: {
				colors: [
					'#000000',
					'#5A5A5A',
					'#9E9E9E',
					'#EC7878',
					'#FF9800',
					'#FFBF00',
					'#CDDC39',
					'#4CAF50',
					'#00BCD4',
					'#0070FF',
					'#3F51B5',
					'#9C27B0',
					'#795548',
					'#FFFFFF',
				],
				columns: 7,
			},
		},
		embed: {
			class: VideoEmbed,
			inlineToolbar: false,
			config: {
				services: {
					youtube: {
						regex: /^(?:https?:\/\/)?(?:www\.)?(?:(?:youtu\.be\/)|(?:youtube\.com)\/(?:v\/|u\/\w\/|embed\/|watch))(?:(?:\?v=)?([^#&?=]*))?((?:[?&]\w*=\w*)*)$/,
						embedUrl: '<%= remote_id %>',
						/* 'https://www.youtube.com/embed/<%= remote_id %>?origin=https://plyr.io&amp;iv_load_policy=3&amp;modestbranding=1&amp;playsinline=1&amp;showinfo=0&amp;rel=0&amp;enablejsapi=1' */
						html: `<div class="video-player" data-plyr-provider="youtube"></div>`,
						id: ([id]) => id,
					},
					vimeo: {
						regex: /^(?:http[s]?:\/\/)?(?:www\.)?vimeo\.com\/(\d+)(?:\/([a-zA-Z0-9]+))?(?:\?[^\s]*)?$/,
						embedUrl:
							'https://player.vimeo.com/video/<%= remote_id %>',
						html: `<div class="video-player" data-plyr-provider="vimeo"></div>`,
						id: ([id, hash]) => (hash ? `${id}?h=${hash}` : id),
					},
					// A share link carries no video id, so this service only exists to
					// catch the paste — VideoEmbed resolves it and rewrites the block
					// as a plain `vimeo` one. It never survives in saved content.
					vimeoShare: {
						regex: VIMEO_SHARE_RE,
						embedUrl: '<%= remote_id %>',
						html: `<div class="vimeo-share-resolving"></div>`,
						id: ([uuid]) => uuid,
					},
					cloudflareStream: {
						regex: /^https:\/\/customer-[a-z0-9]+\.cloudflarestream\.com\/([a-f0-9]{32})\/watch$/,
						embedUrl:
							'https://iframe.videodelivery.net/<%= remote_id %>',
						html: `<iframe style="width:100%; height: ${
							window.innerWidth < 640 ? '15rem' : '30rem'
						};" frameborder="0" allowfullscreen></iframe>`,
					},
					bunnyStream: {
						regex: /^https:\/\/(?:iframe\.mediadelivery\.net|video\.bunnycdn\.com|player\.mediadelivery\.net)\/play\/([a-zA-Z0-9]+\/[a-zA-Z0-9-]+)$/,
						embedUrl:
							'https://player.mediadelivery.net/embed/<%= remote_id %>',
						html: `<iframe style="width:100%; height: ${
							window.innerWidth < 640 ? '15rem' : '30rem'
						};" frameborder="0" allowfullscreen></iframe>`,
					},
					codepen: true,
					aparat: {
						regex: /^(?:http[s]?:\/\/)?(?:www.)?aparat\.com\/v\/([^\/\?\&]+)\/?$/,
						embedUrl:
							'https://www.aparat.com/video/video/embed/videohash/<%= remote_id %>/vt/frame',
						html: `<iframe style="margin: 0 auto; width: 100%; height: ${
							window.innerWidth < 640 ? '15rem' : '30rem'
						};" frameborder="0" scrolling="no" allowtransparency="true"></iframe>`,
					},
					github: true,
					slides: {
						regex: /^https:\/\/docs\.google\.com\/presentation\/d\/([A-Za-z0-9_-]+)\/pub$/,
						embedUrl:
							'https://docs.google.com/presentation/d/<%= remote_id %>/embed',
						html: `<iframe style='width: 100%; height: ${
							window.innerWidth < 640 ? '15rem' : '30rem'
						}; border: 1px solid #D3D3D3; border-radius: 12px; margin: 1rem 0' frameborder='0' allowfullscreen='true'></iframe>`,
					},
					drive: {
						regex: /^https:\/\/drive\.google\.com\/file\/d\/([A-Za-z0-9_-]+)\/view(\?.+)?$/,
						embedUrl:
							'https://drive.google.com/file/d/<%= remote_id %>/preview',
						html: `<iframe style='width: 100%; height: ${
							window.innerWidth < 640 ? '15rem' : '30rem'
						}; border: 1px solid #D3D3D3; border-radius: 12px;' frameborder='0' allowfullscreen='true'></iframe>`,
					},
					docsPublic: {
						regex: /^https:\/\/docs\.google\.com\/document\/d\/([A-Za-z0-9_-]+)\/edit(\?.+)?$/,
						embedUrl:
							'https://docs.google.com/document/d/<%= remote_id %>/preview',
						html: "<iframe style='width: 100%; height: 40rem; border: 1px solid #D3D3D3; border-radius: 12px;' frameborder='0' allowfullscreen='true'></iframe>",
					},
					sheetsPublic: {
						regex: /^https:\/\/docs\.google\.com\/spreadsheets\/d\/([A-Za-z0-9_-]+)\/edit(\?.+)?$/,
						embedUrl:
							'https://docs.google.com/spreadsheets/d/<%= remote_id %>/preview',
						html: "<iframe style='width: 100%; height: 40rem; border: 1px solid #D3D3D3; border-radius: 12px;' frameborder='0' allowfullscreen='true'></iframe>",
					},
					slidesPublic: {
						regex: /^https:\/\/docs\.google\.com\/presentation\/d\/([A-Za-z0-9_-]+)\/edit(\?.+)?$/,
						embedUrl:
							'https://docs.google.com/presentation/d/<%= remote_id %>/embed',
						html: "<iframe style='width: 100%; height: 30rem; border: 1px solid #D3D3D3; border-radius: 12px; margin: 1rem 0;' frameborder='0' allowfullscreen='true'></iframe>",
					},
					codesandbox: {
						regex: /^https:\/\/codesandbox\.io\/(?:(?:p\/(?:sandbox|devbox)\/)|(?:embed\/)|(?:s\/))?([A-Za-z0-9_-]+)(?:[\/\?].*)?$/,
						embedUrl:
							'https://codesandbox.io/embed/<%= remote_id %>?view=editor+%2B+preview&module=%2Findex.html',
						html: "<iframe style='width: 100%; height: 500px; border: 0; border-radius: 4px; overflow: hidden;' sandbox='allow-modals allow-forms allow-popups allow-scripts allow-same-origin' frameborder='0' allowfullscreen='true'></iframe>",
					},
				},
			},
		},
	}
}

// EditorJS only renders its block menu, inline toolbar and block tunes in
// English unless given an i18n dictionary. We route every label through __()
// so the editor follows the user's language (translations live in the app
// translation files, e.g. lms/translations/it.csv). Keys must match the exact
// English strings EditorJS and its tools look up; namespaces mirror the tool
// registration names in getEditorTools (header, list, table, image, embed).
export function getEditorI18n() {
	return {
		direction: document.documentElement.dir === 'rtl' ? 'rtl' : 'ltr',
		messages: {
			ui: {
				blockTunes: {
					toggler: {
						'Click to tune': __('Click to tune'),
						'or drag to move': __('or drag to move'),
					},
				},
				inlineToolbar: {
					converter: {
						'Convert to': __('Convert to'),
					},
				},
				toolbar: {
					toolbox: {
						Add: __('Add'),
					},
				},
				popover: {
					Filter: __('Filter'),
					'Nothing found': __('Nothing found'),
				},
			},
			toolNames: {
				Text: __('Text'),
				Heading: __('Heading'),
				List: __('List'),
				Table: __('Table'),
				Image: __('Image'),
				Upload: __('Upload'),
				CodeBox: __('CodeBox'),
				Bold: __('Bold'),
				Italic: __('Italic'),
				Link: __('Link'),
				Color: __('Color'),
			},
			tools: {
				header: {
					'Heading 1': __('Heading 1'),
					'Heading 2': __('Heading 2'),
					'Heading 3': __('Heading 3'),
					'Heading 4': __('Heading 4'),
					'Heading 5': __('Heading 5'),
					'Heading 6': __('Heading 6'),
				},
				list: {
					Ordered: __('Ordered'),
					Unordered: __('Unordered'),
				},
				table: {
					Heading: __('Heading'),
					'With headings': __('With headings'),
					'Without headings': __('Without headings'),
					Stretch: __('Stretch'),
					Collapse: __('Collapse'),
					'Add column to left': __('Add column to left'),
					'Add column to right': __('Add column to right'),
					'Delete column': __('Delete column'),
					'Add row above': __('Add row above'),
					'Add row below': __('Add row below'),
					'Delete row': __('Delete row'),
				},
				image: {
					'Add Border': __('Add Border'),
					'Stretch Image': __('Stretch Image'),
					'Add Background': __('Add Background'),
				},
				embed: {
					'Enter a caption': __('Enter a caption'),
				},
			},
			blockTunes: {
				delete: {
					Delete: __('Delete'),
					'Click to delete': __('Click to delete'),
				},
				moveUp: {
					'Move up': __('Move up'),
				},
				moveDown: {
					'Move down': __('Move down'),
				},
			},
		},
	}
}

// Block tunes added to every block's settings menu (alongside the native
// Move up/down + Delete). Pass to EditorJS's global `tunes` config.
export function getEditorTunes() {
	return [...clipboardTuneNames]
}

export function getTimezones() {
	return [
		'Pacific/Midway',
		'Pacific/Pago_Pago',
		'Pacific/Honolulu',
		'America/Anchorage',
		'America/Vancouver',
		'America/Los_Angeles',
		'America/Tijuana',
		'America/Edmonton',
		'America/Denver',
		'America/Phoenix',
		'America/Mazatlan',
		'America/Winnipeg',
		'America/Regina',
		'America/Chicago',
		'America/Mexico_City',
		'America/Guatemala',
		'America/El_Salvador',
		'America/Managua',
		'America/Costa_Rica',
		'America/Montreal',
		'America/New_York',
		'America/Indianapolis',
		'America/Panama',
		'America/Bogota',
		'America/Lima',
		'America/Halifax',
		'America/Puerto_Rico',
		'America/Caracas',
		'America/Santiago',
		'America/St_Johns',
		'America/Montevideo',
		'America/Araguaina',
		'America/Argentina/Buenos_Aires',
		'America/Godthab',
		'America/Sao_Paulo',
		'Atlantic/Azores',
		'Canada/Atlantic',
		'Atlantic/Cape_Verde',
		'UTC',
		'Etc/Greenwich',
		'Europe/Belgrade',
		'CET',
		'Atlantic/Reykjavik',
		'Europe/Dublin',
		'Europe/London',
		'Europe/Lisbon',
		'Africa/Casablanca',
		'Africa/Nouakchott',
		'Europe/Oslo',
		'Europe/Copenhagen',
		'Europe/Brussels',
		'Europe/Berlin',
		'Europe/Helsinki',
		'Europe/Amsterdam',
		'Europe/Rome',
		'Europe/Stockholm',
		'Europe/Vienna',
		'Europe/Luxembourg',
		'Europe/Paris',
		'Europe/Zurich',
		'Europe/Madrid',
		'Africa/Bangui',
		'Africa/Algiers',
		'Africa/Tunis',
		'Africa/Harare',
		'Africa/Nairobi',
		'Europe/Warsaw',
		'Europe/Prague',
		'Europe/Budapest',
		'Europe/Sofia',
		'Europe/Istanbul',
		'Europe/Athens',
		'Europe/Bucharest',
		'Asia/Nicosia',
		'Asia/Beirut',
		'Asia/Damascus',
		'Asia/Jerusalem',
		'Asia/Amman',
		'Africa/Tripoli',
		'Africa/Cairo',
		'Africa/Johannesburg',
		'Europe/Moscow',
		'Asia/Baghdad',
		'Asia/Kuwait',
		'Asia/Riyadh',
		'Asia/Bahrain',
		'Asia/Qatar',
		'Asia/Aden',
		'Asia/Tehran',
		'Africa/Khartoum',
		'Africa/Djibouti',
		'Africa/Mogadishu',
		'Asia/Dubai',
		'Asia/Muscat',
		'Asia/Baku',
		'Asia/Kabul',
		'Asia/Yekaterinburg',
		'Asia/Tashkent',
		'Asia/Calcutta',
		'Asia/Kathmandu',
		'Asia/Novosibirsk',
		'Asia/Almaty',
		'Asia/Dacca',
		'Asia/Krasnoyarsk',
		'Asia/Dhaka',
		'Asia/Bangkok',
		'Asia/Saigon',
		'Asia/Jakarta',
		'Asia/Irkutsk',
		'Asia/Shanghai',
		'Asia/Hong_Kong',
		'Asia/Taipei',
		'Asia/Kuala_Lumpur',
		'Asia/Singapore',
		'Australia/Perth',
		'Asia/Yakutsk',
		'Asia/Seoul',
		'Asia/Tokyo',
		'Australia/Darwin',
		'Australia/Adelaide',
		'Asia/Vladivostok',
		'Pacific/Port_Moresby',
		'Australia/Brisbane',
		'Australia/Sydney',
		'Australia/Hobart',
		'Asia/Magadan',
		'SST',
		'Pacific/Noumea',
		'Asia/Kamchatka',
		'Pacific/Fiji',
		'Pacific/Auckland',
		'Asia/Kolkata',
		'Europe/Kiev',
		'America/Tegucigalpa',
		'Pacific/Apia',
	]
}

export function getUserTimezone() {
	try {
		const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
		const supportedTimezones = getTimezones()

		if (supportedTimezones.includes(timezone)) {
			return timezone // e.g., 'Asia/Calcutta', 'America/New_York', etc.
		} else {
			throw Error('unsupported timezone')
		}
	} catch (error) {
		console.error('Error getting timezone:', error)
		return null
	}
}

export function getSidebarLinks(forMobile = false) {
	let links = getSidebarItems(forMobile)

	links.forEach((link) => {
		link.items = link.items.filter((item) => {
			return item.condition ? item.condition() : true
		})
	})

	links = links.filter((link) => {
		return link.items.length > 0
	})

	return links
}

const getSidebarItems = (forMobile = false) => {
	const { userResource } = usersStore()
	const { settings } = useSettings()

	return [
		{
			label: 'General',
			hideLabel: true,
			items: [
				{
					label: 'Home',
					icon: 'Home',
					to: 'Home',
					activeFor: ['Home'],
					condition: () => {
						return userResource?.data
					},
				},
				{
					label: 'Search',
					icon: 'Search',
					action: 'commandPalette',
					shortcut: 'Mod+K',
					condition: () => {
						return !forMobile && userResource?.data
					},
				},
				{
					label: 'Notifications',
					icon: 'Bell',
					panel: 'notifications',
					condition: () => {
						return !forMobile && userResource?.data
					},
				},
			],
		},
		{
			label: 'Learning',
			hideLabel: true,
			items: [
				{
					label: 'Courses',
					icon: 'BookOpen',
					to: 'Courses',
					activeFor: ['Courses', 'CourseDetail', 'Lesson'],
				},
				{
					label: 'Programs',
					icon: 'Route',
					to: 'Programs',
					activeFor: ['Programs', 'ProgramDetail'],
					await: true,
					condition: () => {
						return checkIfCanAddProgram(forMobile)
					},
				},
				{
					label: 'Batches',
					icon: 'Users',
					to: 'Batches',
					activeFor: ['Batches', 'BatchDetail', 'Batch', 'BatchForm'],
				},
				{
					label: 'Certifications',
					icon: 'GraduationCap',
					to: 'CertifiedParticipants',
					activeFor: ['CertifiedParticipants'],
					condition: () => {
						return userResource?.data
					},
				},
				{
					label: 'Jobs',
					icon: 'Briefcase',
					to: 'Jobs',
					activeFor: ['Jobs', 'JobDetail'],
				},
				{
					label: 'Statistics',
					icon: 'TrendingUp',
					to: 'Statistics',
					activeFor: ['Statistics'],
				},
				{
					label: 'Contact Us',
					icon: settings.data?.contact_us_url ? 'Headset' : 'Mail',
					to: settings.data?.contact_us_url
						? settings.data?.contact_us_url
						: settings.data?.contact_us_email,
					condition: () => {
						return (
							(!forMobile &&
								settings?.data?.contact_us_email &&
								userResource?.data) ||
							settings?.data?.contact_us_url
						)
					},
				},
			],
		},
		{
			label: 'Assessments',
			hideLabel: true,
			items: [
				{
					label: 'Quizzes',
					icon: 'CircleHelp',
					to: 'Quizzes',
					condition: () => {
						return !forMobile && isAdmin()
					},
					activeFor: [
						'Quizzes',
						'QuizForm',
						'QuizPage',
						'QuizSubmissionList',
						'QuizSubmission',
					],
				},
				{
					label: 'Assignments',
					icon: 'Pencil',
					to: 'Assignments',
					condition: () => {
						return !forMobile && isAdmin()
					},
					activeFor: [
						'Assignments',
						'AssignmentSubmissionList',
						'AssignmentSubmission',
					],
				},
				{
					label: 'Programming Exercises',
					icon: 'Code',
					to: 'ProgrammingExercises',
					condition: () => {
						return !forMobile && isAdmin()
					},
					activeFor: [
						'ProgrammingExercises',
						'ProgrammingExerciseSubmissions',
						'ProgrammingExerciseSubmission',
					],
				},
				{
					label: 'Export Statistics',
					icon: 'Download',
					to: 'StudentStatsExport',
					activeFor: ['StudentStatsExport'],
					condition: () => {
						return !forMobile && userResource?.data?.can_export_stats
					},
				},
			],
		},
	]
}

const isAdmin = () => {
	const { userResource } = usersStore()
	return (
		userResource?.data?.is_instructor ||
		userResource?.data?.is_moderator ||
		userResource.data?.is_evaluator
	)
}

const checkIfCanAddProgram = (forMobile = false) => {
	const { userResource } = usersStore()
	const { programs } = useSettings()
	if (!userResource.data) return false
	if (forMobile) return false
	if (userResource?.data?.is_moderator || userResource?.data?.is_instructor) {
		return true
	}
	return (
		programs.data?.enrolled.length > 0 ||
		programs.data?.published.length > 0
	)
}

export function getFormattedDateRange(
	startDate,
	endDate,
	format = 'DD MMM YYYY',
) {
	if (startDate === endDate) {
		return dayjs(startDate).format(format)
	}
	return `${dayjs(startDate).format(format)} - ${dayjs(endDate).format(
		format,
	)}`
}

export function getLineStartPosition(string, position) {
	const charLength = 1
	let char = ''

	while (char !== '\n' && position > 0) {
		position = position - charLength
		char = string.substr(position, charLength)
	}

	if (char === '\n') {
		position += 1
	}

	return position
}

export function singularize(word) {
	const endings = {
		ves: 'fe',
		ies: 'y',
		i: 'us',
		zes: 'ze',
		ses: 's',
		es: 'e',
		s: '',
	}
	return word.replace(
		new RegExp(`(${Object.keys(endings).join('|')})$`),
		(r) => endings[r],
	)
}

/**
 * Builds a `["like", ...]` filter value for a free-text search box.
 *
 * Each whitespace-separated word is matched independently (joined by `%`) so a
 * multi-word query narrows results instead of requiring the exact contiguous
 * phrase: "Corso p" -> `%Corso%p%` still matches "Corso di Programmazione".
 * Words must appear in order but may have gaps. Returns null when the query is
 * empty/blank so callers can drop the filter.
 */
export function searchLikeFilter(text) {
	const words = (text || '').trim().split(/\s+/).filter(Boolean)
	if (!words.length) return null
	return ['like', `%${words.join('%')}%`]
}

export const validateFile = async (
	file,
	showToast = true,
	fileType = 'image',
) => {
	const extension = file.name.split('.').pop().toLowerCase()
	const error = (msg) => {
		if (showToast) toast.error(msg)
		console.error(msg)
		return msg
	}

	if (fileType == 'pdf' && extension != 'pdf') {
		return error(__('Only PDF files are allowed.'))
	} else if (fileType == 'document' && !['doc', 'docx'].includes(extension)) {
		return error(
			__('Only document file of type .doc or .docx are allowed.'),
		)
	} else if (fileType == 'zip' && extension != 'zip') {
		return error(__('Only ZIP files are allowed.'))
	} else if (
		['image', 'video'].includes(fileType) &&
		!file.type.startsWith(`${fileType}/`)
	) {
		return error(__('Only {0} file is allowed.').format(fileType))
	} else if (file.type === 'image/svg+xml') {
		const text = await file.text()

		const blacklist = [
			/<script[\s>]/i,
			/on\w+=["']?/i,
			/javascript:/i,
			/data:/i,
			/<iframe[\s>]/i,
			/<object[\s>]/i,
			/<embed[\s>]/i,
			/<link[\s>]/i,
		]

		for (const pattern of blacklist) {
			if (pattern.test(text)) {
				return error(__('SVG contains potentially unsafe content.'))
			}
		}
	}

	return null
}

const sanitizeJSON = (node) => {
	if (Array.isArray(node)) return node.map(sanitizeJSON)
	if (node && typeof node === 'object') {
		const temp = {}
		for (const n in node) {
			temp[n] = sanitizeJSON(node[n])
		}
		return temp
	}
	if (
		typeof node === 'string' &&
		(node.includes('<') || node.includes('>'))
	) {
		// Whitelist the Color inline tool's custom element; DOMPurify's default
		// config drops unknown tags, which would strip the text/highlight colors
		// (and the tag) every time content is loaded or rendered.
		return DOMPurify.sanitize(node, { ADD_TAGS: ['lms-inline-color'] })
	}
	return node
}

export const sanitizeEditorJs = (data) => {
	if (!data || !Array.isArray(data.blocks)) return data
	for (const node of data.blocks) {
		if (node && node.type !== 'code') {
			node.data = sanitizeJSON(node.data)
		}
	}
	return data
}

export const sanitizeHTML = (text) => {
	const iframes = {}

	const textWithoutIframes = text.replace(
		/<iframe[\s\S]*?<\/iframe>/gi,
		(match) => {
			const id = 'iframe_' + Math.random().toString(36).substr(2, 9)
			iframes[id] = match
			console.log('--- extracted iframe:', match, 'id:', id)
			return `<div data-iframe-id="${id}"></div>`
		},
	)

	const decoded = decodeEntities(textWithoutIframes)

	let sanitized = DOMPurify.sanitize(decoded, {
		ALLOWED_TAGS: [
			'b',
			'br',
			'h1',
			'h2',
			'h3',
			'h4',
			'h5',
			'h6',
			'table',
			'thead',
			'tbody',
			'tr',
			'th',
			'td',
			'i',
			'em',
			'strong',
			'a',
			'p',
			'br',
			'ul',
			'ol',
			'li',
			'img',
			'blockquote',
			'iframe',
			'video',
			'source',
			'div',
		],
		ALLOWED_ATTR: [
			'href',
			'target',
			'src',
			'rel',
			// video
			'controls',
			'autoplay',
			'loop',
			'muted',
			'width',
			'height',
			'loading',
			'uploadid',
			// iframe
			'frameborder',
			'allowfullscreen',
			'allow',
			'data-align',
			'data-interactive',
			'data-iframe-id',
		],
		ADD_TAGS: ['iframe'],
		ADD_ATTR: ['allow', 'allowfullscreen', 'frameborder'],
	})

	Object.entries(iframes).forEach(([id, iframe]) => {
		console.log('--- replacing placeholder:', id)
		sanitized = sanitized.replace(
			`<div data-iframe-id="${id}"></div>`,
			iframe,
		)
	})

	return sanitized
}

// Re-exported from a lean module so it stays testable without index.js's heavy
// frappe-ui/EditorJS import chain (same pattern as ./plyr below).
export { sanitizeRichHTML } from './sanitizeRichHTML'

export const canCreateCourse = () => {
	const { userResource } = usersStore()
	return (
		!readOnlyMode &&
		(userResource.data?.is_instructor || userResource.data?.is_moderator)
	)
}

// Plyr setup lives in ./plyr (a lean module that only pulls in Plyr + the
// settings store) so it stays importable/testable without index.js's heavy
// EditorJS/frappe-ui import chain. Re-exported here for existing callers.
export { enablePlyr } from './plyr'

const YOUTUBE_WATCH =
	/^(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?(?:.*&)?v=([\w-]{11})/i
const YOUTUBE_SHORT = /^(?:https?:\/\/)?youtu\.be\/([\w-]{11})/i
const YOUTUBE_EMBED =
	/^(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([\w-]{11})/i
const VIMEO_URL =
	/^(?:https?:\/\/)?(?:www\.)?vimeo\.com\/(\d+)(?:\/([a-zA-Z0-9]+))?/i
const VIMEO_PLAYER = /^(?:https?:\/\/)?player\.vimeo\.com\/video\/(\d+)/i

// Build an embeddable iframe URL from a course "Preview Video" value.
// Handles full YouTube and Vimeo URLs as well as legacy bare YouTube ids
// that the old backend normalization used to store.
export const getVideoEmbedURL = (value) => {
	if (!value) return ''
	const url = value.trim()

	if (YOUTUBE_EMBED.test(url)) return url
	let m = url.match(YOUTUBE_WATCH) || url.match(YOUTUBE_SHORT)
	if (m) return `https://www.youtube.com/embed/${m[1]}`

	if (VIMEO_PLAYER.test(url)) return url
	m = url.match(VIMEO_URL)
	if (m) {
		return m[2]
			? `https://player.vimeo.com/video/${m[1]}?h=${m[2]}`
			: `https://player.vimeo.com/video/${m[1]}`
	}

	// Legacy: a bare YouTube video id stored by the old normalization.
	if (/^[\w-]{11}$/.test(url)) return `https://www.youtube.com/embed/${url}`

	// Fallback: assume the value is already an embeddable URL.
	return url
}

export const createLMSCategory = (name) => {
	return call('frappe.client.insert', {
		doc: {
			doctype: 'LMS Category',
			category: name,
		},
	})
		.then((data) => {
			toast.success(__('Category created successfully'))
			return data.name
		})
		.catch((err) => {
			toast.error(
				cleanError(err.messages?.[0]) || __('Unable to create category')
			)
		})
}

export const openSettings = (category, close = null) => {
	const settingsStore = useSettings()
	if (close) {
		close()
	}
	settingsStore.activeTab = category
	settingsStore.isSettingsOpen = true
}

export const cleanError = (message) => {
	const cleanMessage = message.replace(/<[^>]+>/g, (match) => {
		return match.replace(/<\/?[^>]+(>|$)/g, '')
	})
	return cleanMessage
		.replace(/&nbsp;/g, ' ')
		.replace(/&lt;/g, '<')
		.replace(/&gt;/g, '>')
		.replace(/&quot;/g, '"')
		.replace(/&#39;/g, "'")
		.replace(/&amp;/g, '&')
		.replace(/&#x60;/g, '`')
		.replace(/&#x3D;/g, '=')
		.replace(/&#x2F;/g, '/')
		.replace(/&#x2C;/g, ',')
		.replace(/&#x3B;/g, ';')
		.replace(/&#x3A;/g, ':')
}

export const getMetaInfo = (type, route, meta) => {
	call('lms.lms.api.get_meta_info', {
		type: type,
		route: route,
	}).then((data) => {
		if (data.length) {
			data.forEach((row) => {
				if (row.key == 'description') {
					meta.description = row.value
				} else if (row.key == 'keywords') {
					meta.keywords = row.value
				}
			})
		}
	})
}

export const updateMetaInfo = (type, route, meta) => {
	call('lms.lms.api.update_meta_info', {
		meta_type: type,
		route: route,
		meta_tags: [
			{ key: 'description', value: meta.description },
			{ key: 'keywords', value: meta.keywords },
		],
	}).catch((error) => {
		toast.error(__('Failed to update meta tags {0}').format(error))
		console.error(error)
	})
}

const getRootNode = (selector = '#editor') => {
	const root = document.querySelector(selector)
	if (!root) {
		console.warn(`Root node not found for selector: ${selector}`)
	}
	return root
}

/*
 * A highlight is stored as its text plus the character offset of that text
 * within the lesson body, because the text alone is ambiguous: searching for
 * it always lands on the first occurrence, not the one the learner selected.
 * Offsets are counted over the concatenated text nodes of the root — wrapping
 * a highlight in a <span> splits text nodes but never changes the text, so an
 * offset stays valid however many highlights are already drawn.
 */
export const getRangeOffset = (range, selector = '#editor') => {
	const root = getRootNode(selector)
	if (!root || !range || !root.contains(range.startContainer)) return null

	const preRange = document.createRange()
	preRange.selectNodeContents(root)
	preRange.setEnd(range.startContainer, range.startOffset)
	return preRange.toString().length
}

// Text node slices covered by [start, end), in document order. A selection can
// span several nodes when it crosses an inline or block boundary.
const collectTextSegments = (root, start, end) => {
	const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
	const segments = []
	let consumed = 0
	let node

	while ((node = walker.nextNode())) {
		const nodeStart = consumed
		const nodeEnd = nodeStart + node.nodeValue.length
		consumed = nodeEnd

		if (nodeEnd <= start) continue
		if (nodeStart >= end) break

		const startIndex = Math.max(start - nodeStart, 0)
		const endIndex = Math.min(end - nodeStart, node.nodeValue.length)
		if (endIndex > startIndex) segments.push({ node, startIndex, endIndex })
	}

	return segments
}

// Resolve the stored offset, but only trust it when the text it points at is
// still the highlighted text — the lesson may have been edited since.
const findSegmentsAtOffset = (root, offset, phrase) => {
	if (typeof offset !== 'number' || offset < 0) return null

	const segments = collectTextSegments(root, offset, offset + phrase.length)
	if (!segments.length) return null

	const text = segments
		.map((s) => s.node.nodeValue.slice(s.startIndex, s.endIndex))
		.join('')
	return text === phrase ? segments : null
}

const getRootText = (root) => {
	const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
	let text = ''
	let node
	while ((node = walker.nextNode())) text += node.nodeValue
	return text
}

/*
 * Search fallback, used for notes saved before the offset existed and when the
 * offset no longer points at the highlighted text (the lesson was edited). An
 * offset that is merely stale is still a good hint, so pick the occurrence
 * closest to it instead of blindly taking the first one.
 */
const findSegmentsByText = (root, phrase, offset) => {
	const text = getRootText(root).toLowerCase()
	const needle = phrase.toLowerCase()
	const matches = []

	let index = text.indexOf(needle)
	while (index !== -1) {
		matches.push(index)
		index = text.indexOf(needle, index + 1)
	}
	if (!matches.length) return null

	const start =
		typeof offset === 'number'
			? matches.reduce((best, i) =>
					Math.abs(i - offset) < Math.abs(best - offset) ? i : best,
				)
			: matches[0]

	const segments = collectTextSegments(root, start, start + phrase.length)
	return segments.length ? segments : null
}

const createHighlightSpan = (color, name, scrollIntoView) => {
	const span = document.createElement('span')
	span.className = 'highlighted-text'
	if (scrollIntoView) {
		span.style.border = `2px solid ${getColor(color, 400)}`
		span.style.borderRadius = '4px'
	} else {
		span.style.backgroundColor = getColor(color, 200)
	}
	span.dataset.name = name
	return span
}

// One span per segment: surroundContents() throws when a range crosses element
// boundaries, so a multi-node selection is wrapped piece by piece. Wrapping a
// segment splits its own text node only, leaving the other segments intact.
const wrapSegmentsInHighlight = (segments, color, name, scrollIntoView) => {
	return segments.map(({ node, startIndex, endIndex }) => {
		const range = document.createRange()
		range.setStart(node, startIndex)
		range.setEnd(node, endIndex)

		const span = createHighlightSpan(color, name, scrollIntoView)
		range.surroundContents(span)
		return span
	})
}

const findHighlightSpans = (name) => {
	if (!name) return []
	return Array.from(document.querySelectorAll('.highlighted-text')).filter(
		(el) => el.dataset.name === name,
	)
}

export const highlightText = (note, scrollIntoView = false) => {
	if (!note?.highlighted_text) return

	const root = getRootNode()
	if (!root) return

	// The note list is reloaded after every change and re-highlights everything;
	// without this a second span would be nested inside the existing one.
	if (findHighlightSpans(note.name).length) return

	const phrase = note.highlighted_text
	const color = note.color.toLowerCase()

	const segments =
		findSegmentsAtOffset(root, note.text_offset, phrase) ||
		findSegmentsByText(root, phrase, note.text_offset)
	if (!segments?.length) return

	const spans = wrapSegmentsInHighlight(
		segments,
		color,
		note.name,
		scrollIntoView,
	)

	if (scrollIntoView) {
		spans[0].scrollIntoView({
			behavior: 'smooth',
			block: 'center',
		})
		setTimeout(() => {
			spans.forEach((span) => {
				span.style.border = 'none'
				span.style.borderRadius = '0px'
			})
		}, 3000)
	}
}

// Unwrap instead of just clearing the background: a leftover span would make
// the same text impossible to highlight again without nesting.
export const removeHighlight = (name) => {
	findHighlightSpans(name).forEach((span) => {
		const parent = span.parentNode
		while (span.firstChild) parent.insertBefore(span.firstChild, span)
		parent.removeChild(span)
		parent.normalize()
	})
}

export const scrollToReference = (text) => {
	highlightText({ highlighted_text: text, color: 'yellow', name: '' }, true)
}

export const blockQuotesClick = () => {
	document.querySelectorAll('blockquote').forEach((el) => {
		el.addEventListener('click', (e) => {
			const text = e.target.textContent || ''
			if (text) {
				scrollToReference(text)
			}
		})
	})
}

export const decodeEntities = (encodedString) => {
	const textarea = document.createElement('textarea')
	textarea.innerHTML = encodedString
	return textarea.value
}

export const getColor = (color, shade) => {
	let theme =
		localStorage.getItem('theme') == 'light' ? 'lightMode' : 'darkMode'
	return colorsJSON[theme][color][shade]
}

export function validateEmail(email) {
	return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email || '').trim())
}
