frappe.ui.form.on("LMS Certificate", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("TrueSkills Issue Log"), () => {
			frappe.set_route("List", "TrueSkills Issue Log", {
				lms_certificate: frm.doc.name,
			});
		});
	},
});
