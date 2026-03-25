import { frappeRequest } from 'frappe-ui'

const AVAILABLE_DOCTYPES = {
	"LMS Badge": true,
	"Course Chapter": true,
	"LMS Course": true,
	"LMS Enrollment": true,
	"User": true
}



export function resourceFetcher(options) {
	return frappeRequest(options).then((data) => {
		if (
			options.url === 'frappe.desk.search.search_link' &&
			options.params?.doctype === 'DocType'
		) {
			console.log('Filtering DocType search_link results:', data)
			// Filter results here
			return data.filter(r => AVAILABLE_DOCTYPES[r.value] === true)
		}
		return data
	})
}
