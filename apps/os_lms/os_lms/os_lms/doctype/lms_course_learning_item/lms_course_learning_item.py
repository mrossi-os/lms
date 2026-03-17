# Copyright (c) 2026, Frappe and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document




class LMSCourseLearningItem(Document):
	pass



def get_course_learning_items(course: str):
    return frappe.db.get_all(
	'LMS Course Learning Item',
	filters={
		'parent': course,
		'parenttype': 'LMS Course',
		'parentfield': 'learning_items',
	},
	fields=['title', 'description', 'icon'],
	order_by='idx asc',
	)
    
