// Brand Customize — browser test of Export / Import / presets.
//
// Run it in the browser console on /desk/brand-customize (System Manager), with
// the form saved (not dirty). It drives the real Actions buttons: Export is
// captured instead of downloaded, Import receives generated files, confirmations
// are answered automatically. Nothing is saved: the form is reloaded after every
// case, and the one preset it creates is deleted by its exact name.
// Server side of the same contract: os_lms/tests/test_brand_customize_import_export.py
//
// Usage: paste the file, then `await runBrandImportExportTests()`; or pass
// { exportOnly: true } to get the current export (to import it on another site).

window.runBrandImportExportTests = async function ({ exportOnly = false } = {}) {
	const frm = cur_frm;
	if (!frm || frm.doctype !== "Brand Customize") throw new Error("Open /desk/brand-customize first");
	if (frm.is_dirty()) throw new Error("Save or discard the form first");

	const PRESET = "zz-test-import-export";
	// The form script's own translation helper (its labels use this context).
	const _p = (text) => __(text, null, "Brand Customize");
	const results = [];
	const messages = [];
	const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
	const settle = async () => {
		await wait(150);
		for (let i = 0; i < 50 && (frappe.dom.freeze_count || $(".modal:visible").length > 1); i++) await wait(100);
		await wait(450);
	};

	// --- hooks -------------------------------------------------------------
	let confirm_answer = true;
	let next_file = null;
	let last_blob = null;
	const original = {
		confirm: frappe.confirm,
		msgprint: frappe.msgprint,
		show_alert: frappe.show_alert,
		create_url: URL.createObjectURL,
		revoke_url: URL.revokeObjectURL,
		anchor_click: HTMLAnchorElement.prototype.click,
		input_click: HTMLInputElement.prototype.click,
	};
	frappe.confirm = (question, yes, no) => {
		messages.push({ type: "confirm", text: String(question) });
		if (confirm_answer) yes && yes();
		else no && no();
	};
	frappe.msgprint = (message) => {
		const m = typeof message === "string" ? { message } : message || {};
		messages.push({ type: "msgprint", title: String(m.title || ""), text: String(m.message || "") });
	};
	frappe.show_alert = (message) => messages.push({ type: "alert", text: String(message.message || message) });
	URL.createObjectURL = (blob) => {
		last_blob = blob;
		return "blob:brand-test";
	};
	URL.revokeObjectURL = () => {};
	HTMLAnchorElement.prototype.click = function () {
		if (this.download) return;
		return original.anchor_click.call(this);
	};
	HTMLInputElement.prototype.click = function () {
		if (this.type === "file" && next_file) {
			const transfer = new DataTransfer();
			transfer.items.add(next_file);
			this.files = transfer.files;
			next_file = null;
			this.onchange();
			return;
		}
		return original.input_click.call(this);
	};
	const restore = () => {
		frappe.confirm = original.confirm;
		frappe.msgprint = original.msgprint;
		frappe.show_alert = original.show_alert;
		URL.createObjectURL = original.create_url;
		URL.revokeObjectURL = original.revoke_url;
		HTMLAnchorElement.prototype.click = original.anchor_click;
		HTMLInputElement.prototype.click = original.input_click;
	};

	// --- helpers -----------------------------------------------------------
	const button = (label) => {
		const btn = frm.custom_buttons[label];
		if (!btn) throw new Error(`No button ${label}`);
		return btn;
	};
	const fieldnames = () =>
		frm.meta.fields.filter((df) => !frappe.model.no_value_type.includes(df.fieldtype)).map((df) => df.fieldname);
	const state = () => {
		const values = {};
		for (const f of fieldnames()) values[f] = frm.doc[f] || "";
		values.expert_tokens = (frm.doc.expert_tokens || [])
			.filter((row) => (row.value || "").trim())
			.map((row) => `${row.token}=${row.value}`)
			.sort();
		return values;
	};
	const normalise = (data) => {
		const values = {};
		for (const f of fieldnames()) values[f] = data[f] || "";
		values.expert_tokens = (data.expert_tokens || []).map((row) => `${row.token}=${row.value}`).sort();
		return values;
	};
	const diff = (a, b) =>
		Object.keys({ ...a, ...b }).filter((k) => JSON.stringify(a[k]) !== JSON.stringify(b[k]));
	const do_export = async () => {
		last_blob = null;
		button(__("Export")).click();
		await settle();
		return JSON.parse(await last_blob.text());
	};
	const do_import = async (content, { answer = true } = {}) => {
		messages.length = 0;
		confirm_answer = answer;
		const text = typeof content === "string" ? content : JSON.stringify(content);
		next_file = new File([text], "brand-customize.json", { type: "application/json" });
		button(__("Import")).click();
		await settle();
		confirm_answer = true;
	};
	const discard = async () => {
		await frm.reload_doc();
		await settle();
	};
	const until = async (condition, timeout = 8000) => {
		for (let waited = 0; waited < timeout; waited += 100) {
			if (condition()) return true;
			await wait(100);
		}
		return false;
	};
	const last = (type) => [...messages].reverse().find((m) => m.type === type);
	const check = (name, ok, detail = "") => results.push({ name, ok: !!ok, detail: ok ? "" : detail });

	try {
		const initial = state();
		const E0 = await do_export();
		if (exportOnly) return E0;

		// 1. Export format
		check("export: wrapper", E0.doctype === "Brand Customize" && E0.version === 2 && E0.exported_on, JSON.stringify(E0).slice(0, 200));
		check("export: every value field", diff(Object.keys(E0.data).filter((k) => k !== "expert_tokens").sort(), fieldnames().sort()).length === 0, Object.keys(E0.data).join());
		check("export: equals the saved form", diff(normalise(E0.data), initial).length === 0, diff(normalise(E0.data), initial).join());
		check("export: Expert rows as a list", Array.isArray(E0.data.expert_tokens));

		// 2. Unsaved values are exported (what the preview shows)
		await frm.set_value("login_input_ink", "#123456");
		frm.add_child("expert_tokens", { token: "--ink-gray-8", value: "#111111" });
		const E1 = await do_export();
		check("export: unsaved field", E1.data.login_input_ink === "#123456", E1.data.login_input_ink);
		check("export: unsaved Expert row", E1.data.expert_tokens.some((r) => r.token === "--ink-gray-8"), JSON.stringify(E1.data.expert_tokens));
		await discard();

		// 3. Round trip: import the export onto a changed form, export again
		await frm.set_value("mode", "Expert");
		await frm.set_value("base_primary", "#000000");
		await frm.set_value("login_ink", "#00ff00");
		frm.add_child("expert_tokens", { token: "--ink-gray-9", value: "#ff0000" });
		await settle();
		const offers = messages.filter((m) => m.type === "confirm").length;
		await do_import(E0);
		check("round trip: form equals the file", diff(state(), initial).length === 0, diff(state(), initial).join());
		check("round trip: form is dirty (Save needed)", frm.is_dirty());
		check("round trip: re-export is identical", diff(normalise((await do_export()).data), normalise(E0.data)).length === 0);
		check("round trip: success message", /Import|Importat/.test(last("msgprint")?.title + last("msgprint")?.text), JSON.stringify(last("msgprint")));
		check("round trip: no 'copy to Expert' offer while importing", messages.filter((m) => m.type === "confirm").length === 1, `${offers} ${JSON.stringify(messages)}`);
		await discard();

		// 4. One file per mode
		const files = {
			Base: { mode: "Base", base_primary: "#c2185b", base_accent: "#1565c0", base_background: "", base_gray_tint: "#0a2e5a", expert_tokens: [] },
			Advanced: { mode: "Advanced", adv_button_bg: "#2e7d32", adv_page_bg: "#fafafa", adv_radius: "Large", expert_tokens: [] },
			Expert: { mode: "Expert", expert_tokens: [{ token: "--surface-gray-2", value: "#eeeeee" }, { token: "--radius-lg", value: "12px" }] },
		};
		for (const [mode, data] of Object.entries(files)) {
			await do_import({ doctype: "Brand Customize", version: 2, data });
			const s = state();
			const wrong = Object.entries(data).filter(([k, v]) => k !== "expert_tokens" && s[k] !== v).map(([k]) => k);
			check(`${mode} file: fields set`, s.mode === mode && !wrong.length, `${s.mode} ${wrong}`);
			check(`${mode} file: Expert rows replaced`, JSON.stringify(s.expert_tokens) === JSON.stringify(normalise(data).expert_tokens), JSON.stringify(s.expert_tokens));
			check(`${mode} file: fields not in the file untouched`, s.login_bg_from === initial.login_bg_from);
			await discard();
		}

		// 5. Version 1 files (one field per Expert variable)
		const legacy = (await frappe.xcall("os_lms.os_lms.branding.get_expert_tokens")).legacy;
		const v1 = (values) => {
			const data = {};
			for (const f of Object.keys(legacy)) data[f] = null;
			return { doctype: "Brand Customize", version: 1, data: { ...data, mode: "Expert", ...values } };
		};
		await do_import(v1({ surface_gray_10: "#333333", company_primary: "#c2185b" }));
		check("v1 file: old fields become rows", JSON.stringify(state().expert_tokens) === JSON.stringify(["--color-company-primary=#c2185b", "--surface-gray-10=#333333"]), JSON.stringify(state().expert_tokens));
		check("v1 file: old fields not reported as unknown", !/surface_gray_10/.test(last("msgprint")?.text), last("msgprint")?.text);
		await discard();
		await do_import(v1({}));
		check("v1 file with empty Expert fields clears the rows", state().expert_tokens.length === 0, JSON.stringify(state().expert_tokens));
		await discard();

		// 6. Flat object, unknown fields, empty values, bad rows
		await do_import({ base_primary: "#abcdef", made_up_field: "x" });
		check("flat object: field set", frm.doc.base_primary === "#abcdef");
		check("flat object without rows keeps the Expert rows", JSON.stringify(state().expert_tokens) === JSON.stringify(initial.expert_tokens));
		check("unknown field reported", /made_up_field/.test(last("msgprint")?.text), last("msgprint")?.text);
		check("confirmation counts the set values", /\b1\b/.test(last("confirm")?.text), last("confirm")?.text);
		await discard();
		await do_import({ data: { login_ink: null, login_bg_from: "" } });
		check("empty values clear their fields", !frm.doc.login_ink && !frm.doc.login_bg_from, `${frm.doc.login_ink} ${frm.doc.login_bg_from}`);
		check("all-empty file counts 0 values", /\b0\b/.test(last("confirm")?.text), last("confirm")?.text);
		await discard();
		await do_import({ data: { expert_tokens: [null, "x", { token: "--a" }, { token: "--ink-gray-5", value: 5 }, { token: " --ink-gray-6 ", value: " #222222 " }] } });
		check("malformed rows skipped, good one trimmed", JSON.stringify(state().expert_tokens) === JSON.stringify(["--ink-gray-6=#222222"]), JSON.stringify(state().expert_tokens));
		await discard();

		// 7. Files that must be refused, leaving the form as it was
		const refused = [
			["invalid JSON", "{not json"],
			["JSON array", "[1, 2]"],
			["JSON string", '"hello"'],
			["null", "null"],
			["no known field", { data: { foo: 1 } }],
			["other doctype", { doctype: "Website Settings", version: 2, data: { base_primary: "#000000" } }],
		];
		for (const [name, content] of refused) {
			await do_import(content);
			const msg = last("msgprint");
			check(`refused: ${name}`, msg && /Failed|non riuscita/.test(msg.title) && !last("confirm") && diff(state(), initial).length === 0 && !frm.is_dirty(), JSON.stringify(msg));
			await discard();
		}

		// 8. Cancelling the confirmation changes nothing
		await do_import(E1, { answer: false });
		check("cancel: nothing changed", diff(state(), initial).length === 0 && !frm.is_dirty(), diff(state(), initial).join());

		// 9. Presets: Save as Preset (unsaved values) -> Apply Preset
		await frm.set_value("mode", "Advanced");
		await frm.set_value("adv_button_bg", "#6a1b9a");
		await frm.set_value("login_ink", "");
		await settle();
		const expected = state();
		messages.length = 0;
		button(_p("Save as Preset")).click();
		await until(() => cur_dialog && cur_dialog.title === _p("Save as Preset") && cur_dialog.$wrapper.is(":visible"));
		const dialog = cur_dialog;
		await dialog.set_value("preset_name", PRESET);
		dialog.get_primary_btn().click();
		check("preset: saved", await until(() => last("alert")?.text.includes(PRESET)), JSON.stringify(messages));
		dialog.hide();
		await discard();
		check("preset: form back to saved", diff(state(), initial).length === 0);
		messages.length = 0;
		button(_p("Apply Preset")).click();
		const preset_row = () =>
			$(".brand-preset-row:visible").filter((_, el) => $(el).find(".brand-preset-name").text() === PRESET);
		check("preset: listed", await until(() => preset_row().length === 1));
		preset_row().click();
		await until(() => last("msgprint"));
		await settle();
		check("preset: confirmation names the preset", last("confirm")?.text.includes(PRESET), last("confirm")?.text);
		check("preset: applied equals what was saved", diff(state(), expected).length === 0, diff(state(), expected).join());
		check("preset: empty field cleared", !frm.doc.login_ink, frm.doc.login_ink);
		await discard();
	} finally {
		restore();
		try {
			if (await frappe.db.exists("Brand Preset", PRESET)) {
				await frappe.xcall("frappe.client.delete", { doctype: "Brand Preset", name: PRESET });
			}
		} catch (e) {
			results.push({ name: "cleanup preset", ok: false, detail: String(e) });
		}
		await frm.reload_doc();
	}
	const failed = results.filter((r) => !r.ok);
	return { passed: results.length - failed.length, failed: failed.length, failures: failed, all: results.map((r) => `${r.ok ? "PASS" : "FAIL"} ${r.name}`) };
};
