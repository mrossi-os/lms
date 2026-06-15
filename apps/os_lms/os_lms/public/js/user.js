// Desk client script for the User form.
// Adds a "Reset progressi corso" button (admins only) that wipes a student's
// progress for a chosen course so the certificate can be re-issued from scratch.

frappe.ui.form.on("User", {
	refresh(frm) {
		if (frm.is_new()) return;
		if (!frappe.user.has_role("System Manager") && !frappe.user.has_role("Moderator")) {
			return;
		}
		frm.add_custom_button(
			__("Reset progressi corso"),
			() => open_reset_progress_dialog(frm),
			__("Azioni")
		);
	},
});

function open_reset_progress_dialog(frm) {
	frappe.call({
		method: "os_lms.os_lms.api.get_member_courses",
		args: { member: frm.doc.name },
		callback(r) {
			const courses = r.message || [];
			if (!courses.length) {
				frappe.msgprint(__("Questo utente non è iscritto a nessun corso."));
				return;
			}
			const options = courses.map((c) => ({
				label: `${c.course_title} (${c.progress || 0}%)`,
				value: c.course,
			}));
			const dialog = new frappe.ui.Dialog({
				title: __("Reset progressi corso"),
				fields: [
					{
						fieldname: "course",
						fieldtype: "Select",
						label: __("Corso"),
						options: options,
						reqd: 1,
					},
				],
				primary_action_label: __("Reset"),
				primary_action(values) {
					preview_and_reset(frm, values.course, dialog);
				},
			});
			dialog.show();
		},
	});
}

function preview_and_reset(frm, course, dialog) {
	// Dry-run first to show the operator exactly what will be deleted.
	frappe.call({
		method: "os_lms.os_lms.api.reset_course_progress",
		args: { member: frm.doc.name, course: course, dry_run: 1 },
		callback(r) {
			const summary = r.message;
			if (!summary) return;
			frappe.confirm(
				build_confirm_message(frm.doc.name, summary),
				() => run_reset(frm, course, dialog)
			);
		},
	});
}

function run_reset(frm, course, dialog) {
	frappe.call({
		method: "os_lms.os_lms.api.reset_course_progress",
		args: { member: frm.doc.name, course: course, dry_run: 0 },
		freeze: true,
		freeze_message: __("Reset in corso..."),
		callback() {
			dialog.hide();
			frappe.show_alert({
				message: __("Progressi del corso azzerati."),
				indicator: "green",
			});
		},
	});
}

function build_confirm_message(member, summary) {
	const d = summary.deleted || {};
	const rows = [
		[__("Avanzamento lezioni"), d.course_progress],
		[__("Quiz svolti"), d.quiz_submissions],
		[__("Consegne assignment"), d.assignment_submissions],
		[__("Certificati"), d.certificates],
		[__("TrueSkills Issue Log"), d.trueskills_issue_logs],
	];
	let items = "";
	rows.forEach(([label, count]) => {
		items += `<li>${label}: <b>${count || 0}</b></li>`;
	});
	let msg = `<p>${__("Verranno eliminati definitivamente per {0} nel corso «{1}»:", [
		frappe.utils.escape_html(member),
		frappe.utils.escape_html(summary.course_title || summary.course),
	])}</p><ul>${items}</ul>`;
	if (summary.enrollment_reset) {
		msg += `<p>${__(
			"L'iscrizione verrà azzerata (progresso 0, lezione corrente e certificato rimossi), senza rimuovere lo studente dal corso."
		)}</p>`;
	}
	msg += `<p><b>${__("Operazione irreversibile. Continuare?")}</b></p>`;
	return msg;
}
