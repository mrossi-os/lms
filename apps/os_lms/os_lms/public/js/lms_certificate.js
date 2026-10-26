frappe.ui.form.on("LMS Certificate", {
	refresh(frm) {
		// The issue log is readable by System Manager and Moderator only.
		if (frm.is_new() || !frappe.model.can_read("TrueSkills Issue Log")) return;
		frm.add_custom_button(__("TrueSkills Issue Log"), () => {
			frappe.set_route("List", "TrueSkills Issue Log", {
				lms_certificate: frm.doc.name,
			});
		});
	},
});
