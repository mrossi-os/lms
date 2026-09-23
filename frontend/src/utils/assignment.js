import { Pencil } from 'lucide-vue-next'
import { createApp, h } from 'vue'
import AssessmentPlugin from '@/components/AssessmentPlugin.vue'
import translationPlugin from '../translation'
import { call } from 'frappe-ui'
import router from '@/router'
import { getLmsRoute } from '@/utils/basePath'

export class Assignment {
	constructor({ data, api, readOnly }) {
		this.data = data
		this.readOnly = readOnly
	}

	static get toolbox() {
		const app = createApp({
			render: () =>
				h(Pencil, { size: 18, strokeWidth: 1.5, color: 'black' }),
		})

		const div = document.createElement('div')
		app.mount(div)

		return {
			title: __('Assignment'),
			icon: div.innerHTML,
		}
	}

	static get isReadOnlySupported() {
		return true
	}

	render() {
		this.wrapper = document.createElement('div')
		if (Object.keys(this.data).length) {
			this.renderAssignment(this.data.assignment)
		} else {
			this.renderAssignmentModal()
		}
		return this.wrapper
	}

	renderAssignment(assignment) {
		// OSLMS-CUSTOM: translated placeholder when no assignment is selected (was "Assignment: undefined")
		// Saving the modal without picking an assignment passes a null value,
		// which otherwise renders "Assignment: undefined". Show a translated
		// placeholder instead.
		if (!assignment) {
			this.wrapper.innerHTML = `<div class='border rounded-md p-4 text-center bg-surface-sidebar mb-4'>
				<span class="font-medium">${__('No assignment selected')}</span>
			</div>`
			return
		}
		if (this.readOnly) {
			const renderSubmission = (submission) => {
				const submissionPath = getLmsRoute(
					`assignment-submission/${assignment}/${
						submission || 'new'
					}?fromLesson=1`,
				)
				// OSLMS-CUSTOM: os-frame class gives the in-lesson submission iframe full viewport height
				this.wrapper.innerHTML = `<iframe src="${submissionPath}" class="w-full h-[500px] os-frame"></iframe>`
			}
			call('lms.lms.api.get_own_assignment_submission', {
				assignment: assignment,
			})
				.then(renderSubmission)
				.catch(() => renderSubmission('new'))
			return
		}
		call('frappe.client.get_value', {
			doctype: 'LMS Assignment',
			filters: {
				name: assignment,
			},
			fieldname: ['title'],
		}).then((data) => {
			// OSLMS-CUSTOM: translated Assignment label in the editor preview
			this.wrapper.innerHTML = `<div class='border rounded-md p-4 text-center bg-surface-sidebar mb-4'>
				<span class="font-medium">
					${__('Assignment')}: ${data.title}
				</span>
			</div>`
			return
		})
	}

	renderAssignmentModal() {
		if (this.readOnly) {
			return
		}
		const app = createApp(AssessmentPlugin, {
			type: 'assignment',
			onAddition: (assignment) => {
				this.data.assignment = assignment
				this.renderAssignment(assignment)
			},
		})
		app.use(translationPlugin)
		app.use(router)
		app.mount(this.wrapper)
	}

	save() {
		if (Object.keys(this.data).length === 0) return {}
		return {
			assignment: this.data.assignment,
		}
	}
}
