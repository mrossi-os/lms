// Copyright (c) 2026, ELITE and contributors
// For license information, please see license.txt

// Version 2 adds the Expert table; version 1 files (one field per variable)
// are still imported.
const EXPORT_VERSION = 2;

frappe.ui.form.on("Brand Customize", {
	refresh(frm) {
		frm.add_custom_button(__("Export"), () => export_brand_settings(frm), __("Actions"));
		frm.add_custom_button(__("Import"), () => import_brand_settings(frm), __("Actions"));
		frm.add_custom_button(__("Reset Colors"), () => reset_colors(frm), __("Actions"));
		frm.add_custom_button(_p("Save as Preset"), () => save_as_preset(frm), __("Actions"));
		frm.add_custom_button(_p("Apply Preset"), () => choose_preset(frm), __("Actions"));
		add_clear_icons(frm);
		show_token_defaults(frm);
		setup_preview(frm);
		load_expert_tokens();
		render_expert_editor(frm);
		// The readability report comes with the preview CSS, also when the
		// preview is closed.
		schedule_preview(frm);
	},
	after_save(frm) {
		schedule_preview(frm);
	},
	mode(frm) {
		on_mode_change(frm);
	},
});

// ---------------------------------------------------------------------------
// Live preview (docs/brand-customize/fase-2-analisi.md)
//
// The main pages are shown in same-origin iframes. Their saved brand stylesheet
// is switched off and replaced by the CSS of the unsaved form values, which the
// server builds with the same code as the saved one. Links, buttons and forms
// are blocked inside the frames; hover and scroll keep working.
// ---------------------------------------------------------------------------

const PREVIEW_CONTEXT = "Brand Customize";
const PREVIEW_STYLE_ID = "os-brand-preview";
const PREVIEW_BRAND_LINK = 'link[href*="os_lms.branding.brand_css"]';
const PREVIEW_OPEN_KEY = "brand_customize_preview_open";
const PREVIEW_DEBOUNCE_MS = 150;
// The desktop view renders the pages at this width and scales them down to the
// panel, so they show their real desktop layout instead of a tablet one.
const PREVIEW_DEVICE_WIDTH = { desktop: 1280, phone: 375 };
const PREVIEW_TABS = [
	{ key: "home", label: "Home" },
	{ key: "courses", label: "Courses" },
	{ key: "course", label: "Course Page" },
	{ key: "lesson", label: "Lesson" },
	{ key: "course_dashboard", label: "Course Dashboard" },
	{ key: "course_editor", label: "Lesson Editor" },
	{ key: "course_settings", label: "Course Settings" },
	{ key: "batch", label: "Batch Dashboard" },
	{ key: "statistics", label: "Statistics" },
	{ key: "login", label: "Login" },
];
// The preview is read-only: some pages (lesson editor, course settings) save by
// themselves after an edit, so the keyboard only scrolls and nothing can be
// typed, pasted or dropped. Tab is blocked too, so focus cannot reach a field.
const PREVIEW_SCROLL_KEYS = new Set([
	"ArrowUp",
	"ArrowDown",
	"ArrowLeft",
	"ArrowRight",
	"PageUp",
	"PageDown",
	"Home",
	"End",
]);
const PREVIEW_BLOCKED_EVENTS = [
	"click",
	"auxclick",
	"dblclick",
	"pointerdown",
	"mousedown",
	"touchstart",
	"submit",
	"beforeinput",
	"paste",
	"cut",
	"drop",
	"dragstart",
];

const preview = {
	frm: null,
	panel: null,
	targets: null,
	frames: {},
	active: "home",
	device: "desktop",
	css: null,
	invalid: [],
	// Typed but not yet committed values (Frappe sets the doc on change/blur).
	live: {},
	seq: 0,
	timer: null,
	resize_observer: null,
	button: null,
	handlers_bound: false,
	// Field whose elements are outlined in the preview, and how to find them.
	highlight: null,
	highlights: {},
	highlight_timer: null,
	last_mode: null,
};

const _p = (text) => __(text, null, PREVIEW_CONTEXT);

function preview_fieldnames(frm) {
	return [...get_color_fieldnames(frm), "mode", "adv_radius"];
}

const fieldnames_with_prefix = (frm, prefix) =>
	get_color_fieldnames(frm).filter((fieldname) => fieldname.startsWith(prefix));

// Base and Advanced are exclusive (one mode at a time). Moving from Base to
// Advanced offers to start from the colors Base computes, so the platform
// looks the same right after the switch and each role can then be refined.
function on_mode_change(frm) {
	const previous = preview.last_mode;
	preview.last_mode = frm.doc.mode;
	// Fields of the newly shown sections get their placeholder, ✕ and live input.
	setTimeout(() => {
		add_clear_icons(frm);
		show_token_defaults(frm);
		bind_live_inputs(frm);
		render_expert_editor(frm);
	}, 0);
	// Values applied as a whole (Import, presets) bring their own mode.
	if (preview.applying_settings) return;
	if (frm.doc.mode === "Expert" && ["Base", "Advanced"].includes(previous)) {
		offer_copy_to_expert(frm, previous);
		return;
	}
	if (previous !== "Base" || frm.doc.mode !== "Advanced") return;

	const base_fields = fieldnames_with_prefix(frm, "base_");
	if (!base_fields.some((fieldname) => frm.doc[fieldname])) return;
	const role_fields = fieldnames_with_prefix(frm, "adv_");
	const has_roles = role_fields.some((fieldname) => frm.doc[fieldname]);
	const question = has_roles
		? _p("Replace the Advanced colors with the ones computed from the Base colors?")
		: _p("Start from the colors computed from the Base colors?");

	frappe.confirm(question, () => {
		frappe
			.xcall("os_lms.os_lms.branding.base_to_advanced", {
				values: JSON.stringify(collect_preview_values(frm)),
			})
			.then((roles) => {
				for (const fieldname of role_fields) frm.set_value(fieldname, (roles || {})[fieldname] || "");
				frappe.show_alert({
					message: _p("Advanced colors filled in from Base. Save to apply."),
					indicator: "green",
				});
			});
	});
}

function setup_preview(frm) {
	preview.frm = frm;
	preview.last_mode = frm.doc.mode;
	bind_preview_handlers(frm);
	ensure_preview_styles();
	bind_live_inputs(frm);

	preview.button = frm.add_custom_button(_p("Preview"), () =>
		toggle_preview(frm, !is_preview_open())
	);

	// Open unless the user closed it last time: the preview is the point of the page.
	const wanted = localStorage.getItem(PREVIEW_OPEN_KEY) !== "0";
	if (wanted && !is_preview_open()) toggle_preview(frm, true);
	else if (is_preview_open()) {
		render_preview_status();
		schedule_preview(frm);
	}
	update_preview_button();
}

function update_preview_button() {
	if (preview.button) preview.button.text(is_preview_open() ? _p("Hide Preview") : _p("Preview"));
}

// Field handlers are registered once: refresh runs again on every save/reload.
function bind_preview_handlers(frm) {
	if (preview.handlers_bound) return;
	preview.handlers_bound = true;
	for (const fieldname of preview_fieldnames(frm)) {
		frappe.ui.form.on("Brand Customize", fieldname, (form) => {
			delete preview.live[fieldname];
			schedule_preview(form);
		});
	}
}

// Frappe commits a Data/Color value on change; reading keystrokes too makes a
// typed hex show up without leaving the field.
function bind_live_inputs(frm) {
	for (const fieldname of get_color_fieldnames(frm)) {
		const field = frm.get_field(fieldname);
		if (!field || !field.$input || field.$input.data("brand-preview")) continue;
		field.$input.data("brand-preview", true);
		field.$input.on("input", () => {
			preview.live[fieldname] = field.$input.val();
			schedule_preview(frm);
		});
		field.$input.on("focus", () => set_highlight(fieldname));
		field.$input.on("blur", () => clear_highlight_soon());
	}
}

function is_preview_open() {
	return !!(preview.panel && preview.panel.is(":visible"));
}

function toggle_preview(frm, open) {
	localStorage.setItem(PREVIEW_OPEN_KEY, open ? "1" : "0");
	const wrapper = $(frm.page.wrapper);
	if (!open) {
		wrapper.removeClass("brand-preview-open");
		close_frames();
		if (preview.panel) preview.panel.remove();
		preview.panel = null;
		update_preview_button();
		return;
	}
	if (!preview.panel || !$.contains(wrapper.get(0), preview.panel.get(0))) {
		preview.panel = build_preview_panel(frm);
		// Inside the page wrapper, so Frappe hides it with the page on route change.
		wrapper.append(preview.panel);
	}
	wrapper.addClass("brand-preview-open");
	update_preview_button();
	refresh_preview_css(frm).then(() => load_targets()).then(() => show_tab(preview.active));
}

function build_preview_panel(frm) {
	const panel = $(`
		<div class="brand-preview" role="region">
			<div class="brand-preview-bar">
				<div class="brand-preview-tabs" role="tablist"></div>
				<div class="brand-preview-tools">
					<div class="brand-preview-devices" role="group"></div>
					<button type="button" class="btn btn-xs btn-default brand-preview-close"></button>
				</div>
			</div>
			<div class="brand-preview-status"></div>
			<div class="brand-preview-stage"></div>
		</div>
	`);
	panel.attr("aria-label", _p("Preview"));

	const tabs = panel.find(".brand-preview-tabs");
	for (const tab of PREVIEW_TABS) {
		$(`<button type="button" class="btn btn-xs brand-preview-tab" role="tab"></button>`)
			.attr("data-key", tab.key)
			.text(_p(tab.label))
			.on("click", () => show_tab(tab.key))
			.appendTo(tabs);
	}

	const devices = panel.find(".brand-preview-devices");
	for (const [device, label] of [
		["desktop", "Desktop"],
		["phone", "Phone"],
	]) {
		$(`<button type="button" class="btn btn-xs brand-preview-device"></button>`)
			.attr("data-device", device)
			.text(_p(label))
			.on("click", () => set_device(device))
			.appendTo(devices);
	}

	panel
		.find(".brand-preview-close")
		.text(_p("Close"))
		.on("click", () => toggle_preview(frm, false));

	preview.resize_observer = new ResizeObserver(() => layout_frames());
	preview.resize_observer.observe(panel.find(".brand-preview-stage").get(0));
	// The Desk sidebar can collapse without resizing the panel's stage.
	preview.resize_observer.observe($(frm.page.wrapper).get(0));
	return panel;
}

function load_targets() {
	if (preview.targets) return Promise.resolve();
	return frappe
		.xcall("os_lms.os_lms.branding.get_preview_targets")
		.then((response) => {
			preview.targets = {};
			for (const target of (response && response.pages) || []) preview.targets[target.key] = target;
			preview.highlights = (response && response.highlights) || {};
		})
		.catch(() => {
			preview.targets = {};
		});
}

function show_tab(key) {
	if (!preview.panel) return;
	preview.active = key;
	preview.panel.find(".brand-preview-tab").each(function () {
		const active = this.dataset.key === key;
		$(this).toggleClass("btn-primary", active).toggleClass("btn-default", !active);
		this.setAttribute("aria-selected", active ? "true" : "false");
		const target = preview.targets && preview.targets[this.dataset.key];
		$(this).toggleClass("brand-preview-tab-empty", !!(target && !target.url));
	});
	preview.panel.find(".brand-preview-device").each(function () {
		const active = this.dataset.device === preview.device;
		$(this).toggleClass("btn-primary", active).toggleClass("btn-default", !active);
	});

	const stage = preview.panel.find(".brand-preview-stage");
	stage.find(".brand-preview-empty").remove();
	for (const [frame_key, box] of Object.entries(preview.frames)) {
		box.toggle(frame_key === key);
	}

	const target = preview.targets && preview.targets[key];
	if (!target || !target.url) {
		const reason = (target && target.reason) || _p("This page cannot be previewed.");
		$(`<div class="brand-preview-empty"></div>`).text(reason).appendTo(stage);
		return;
	}
	if (!preview.frames[key]) preview.frames[key] = create_frame(key, target.url);
	layout_frames();
	render_preview_status();
	if (expert.filters.only_page) render_expert_rows(preview.frm);
}

function create_frame(key, url) {
	const box = $(`<div class="brand-preview-frame-box"><iframe class="brand-preview-frame"></iframe></div>`);
	const frame = box.find("iframe").get(0);
	frame.setAttribute("title", _p("Preview"));
	frame.setAttribute("tabindex", "-1");
	frame.addEventListener("load", () => prepare_frame(frame, key));
	frame.src = url;
	preview.panel.find(".brand-preview-stage").append(box);
	return box;
}

function close_frames() {
	for (const box of Object.values(preview.frames)) box.remove();
	preview.frames = {};
	if (preview.resize_observer) preview.resize_observer.disconnect();
	preview.resize_observer = null;
}

function set_device(device) {
	preview.device = device;
	show_tab(preview.active);
}

// Fits the frame width of the chosen device into the panel by scaling it down.
function layout_frames() {
	if (!preview.panel) return;
	// On narrow screens the panel covers the form, but not the Desk sidebar.
	const narrow = window.matchMedia("(max-width: 1199px)").matches;
	const page = preview.panel.parent().get(0);
	const page_left = page ? page.getBoundingClientRect().left : 0;
	preview.panel.css("left", narrow ? Math.max(0, page_left) : "");
	const stage = preview.panel.find(".brand-preview-stage");
	const available_width = stage.innerWidth();
	const available_height = stage.innerHeight();
	if (!available_width || !available_height) return;

	const device_width = PREVIEW_DEVICE_WIDTH[preview.device];
	const scale = Math.min(1, available_width / device_width);
	for (const box of Object.values(preview.frames)) {
		box.css({ width: device_width * scale, height: available_height });
		box.find("iframe").css({
			width: device_width,
			height: available_height / scale,
			transform: `scale(${scale})`,
		});
	}
}

function prepare_frame(frame, key) {
	let doc;
	try {
		doc = frame.contentDocument;
	} catch (e) {
		return; // Not same-origin: nothing can be previewed in it.
	}
	if (!doc || !doc.documentElement) return;
	const win = frame.contentWindow;

	const block = (event) => {
		event.preventDefault();
		event.stopPropagation();
		event.stopImmediatePropagation();
	};
	for (const type of PREVIEW_BLOCKED_EVENTS) win.addEventListener(type, block, true);
	win.addEventListener(
		"keydown",
		(event) => {
			if (!PREVIEW_SCROLL_KEYS.has(event.key) || event.ctrlKey || event.metaKey || event.altKey) block(event);
		},
		true
	);
	win.open = () => null;

	// The brand only colors the light theme without high contrast. The theme
	// lives in localStorage, shared with this Desk tab, so the attributes are
	// forced on the frame's <html> only and localStorage is left alone.
	const html = doc.documentElement;
	const force_light = () => {
		if (html.getAttribute("data-theme") !== "light") html.setAttribute("data-theme", "light");
		if (html.hasAttribute("data-contrast")) html.removeAttribute("data-contrast");
	};
	force_light();
	new win.MutationObserver(force_light).observe(html, {
		attributes: true,
		attributeFilter: ["data-theme", "data-contrast"],
	});

	// The login tab shows /update-password (see get_preview_targets), whose
	// primary button is .btn-update: give it the login button's class so the
	// "Button" login color shows up as it does on /login.
	if (key === "login") {
		for (const button of doc.querySelectorAll(".btn-primary")) button.classList.add("btn-login");
	}

	// The SPA appends its brand <link> at runtime: keep it off and the preview
	// <style> last in <head>.
	new win.MutationObserver(() => apply_css(frame)).observe(doc.head, { childList: true });
	apply_css(frame);
	if (expert.filters.only_page && key === preview.active) render_expert_rows(preview.frm);

	let pending = false;
	const redraw = () => {
		if (pending || !preview.highlight) return;
		pending = true;
		win.requestAnimationFrame(() => {
			pending = false;
			draw_frame_highlight(frame);
		});
	};
	win.addEventListener("scroll", redraw, true);
	win.addEventListener("resize", redraw);
	draw_frame_highlight(frame);
}

function apply_css(frame) {
	const doc = frame.contentDocument;
	if (!doc || !doc.head || preview.css === null) return;
	for (const link of doc.querySelectorAll(PREVIEW_BRAND_LINK)) {
		if (!link.disabled) link.disabled = true;
	}
	let style = doc.getElementById(PREVIEW_STYLE_ID);
	if (!style) {
		style = doc.createElement("style");
		style.id = PREVIEW_STYLE_ID;
	}
	if (style.textContent !== preview.css) style.textContent = preview.css;
	if (doc.head.lastElementChild !== style) doc.head.appendChild(style);
}

function schedule_preview(frm) {
	clearTimeout(preview.timer);
	preview.timer = setTimeout(() => refresh_preview_css(frm), PREVIEW_DEBOUNCE_MS);
}

function collect_preview_values(frm) {
	const values = {};
	for (const fieldname of preview_fieldnames(frm)) values[fieldname] = frm.doc[fieldname] || "";
	return { ...values, ...preview.live, expert_tokens: expert_token_map(frm) };
}

function refresh_preview_css(frm) {
	const seq = ++preview.seq;
	return frappe
		.xcall("os_lms.os_lms.branding.brand_css_preview", {
			values: JSON.stringify(collect_preview_values(frm)),
		})
		.then((result) => {
			// A slower earlier answer must not overwrite a newer one.
			if (seq !== preview.seq || !result) return;
			preview.css = result.css;
			preview.invalid = result.invalid || [];
			for (const box of Object.values(preview.frames)) apply_css(box.find("iframe").get(0));
			render_preview_status();
			render_base_swatches(frm, result.roles || {});
			preview.contrast = result.contrast || [];
			render_contrast(frm);
		})
		.catch(() => {
			// Keep the last good preview; the error dialog is Frappe's own.
		});
}

function render_preview_status() {
	if (!preview.panel || !preview.frm) return;
	const frm = preview.frm;
	const dirty = frm.is_dirty() || Object.keys(preview.live).length > 0;
	const status = preview.panel.find(".brand-preview-status").empty();
	$(`<span class="indicator-pill no-indicator-dot"></span>`)
		.addClass(dirty ? "orange" : "green")
		.text(dirty ? _p("Preview of unsaved changes") : _p("Preview of saved colors"))
		.appendTo(status);
	$(`<span class="brand-preview-hint"></span>`)
		.text(_p("Links and buttons are disabled in the preview."))
		.appendTo(status);
	if (preview.invalid.length) {
		const labels = preview.invalid.map((fieldname) =>
			__(frm.get_field(fieldname)?.df.label || fieldname, null, PREVIEW_CONTEXT)
		);
		$(`<div class="brand-preview-invalid"></div>`)
			.text(__("Not previewed, the value is not valid: {0}", [labels.join(", ")], PREVIEW_CONTEXT))
			.appendTo(status);
	}
}

// --- "Where is it used": outline the elements of the focused field ----------

const HIGHLIGHT_LAYER_ID = "os-brand-highlight";
const HIGHLIGHT_MAX_BOXES = 200;
const HIGHLIGHT_KEEP_MS = 1500;

function set_highlight(fieldname) {
	clearTimeout(preview.highlight_timer);
	preview.highlight = preview.highlights[fieldname] ? fieldname : null;
	draw_highlights();
}

// The color picker steals the focus: keep the outlines a moment after blur.
function clear_highlight_soon() {
	clearTimeout(preview.highlight_timer);
	preview.highlight_timer = setTimeout(() => {
		preview.highlight = null;
		draw_highlights();
	}, HIGHLIGHT_KEEP_MS);
}

function draw_highlights() {
	for (const box of Object.values(preview.frames)) draw_frame_highlight(box.find("iframe").get(0));
}

const class_names = (element) => (element.getAttribute("class") || "").split(/\s+/);

// Elements matching the field: its CSS selectors, or the utility classes that
// read its tokens (bg-surface-gray-2, hover:text-ink-gray-7...), or a status
// color family (text-ink-green-8...).
function find_highlighted(doc, spec) {
	if (spec.probe) return new Set(probe_cached(doc, spec));
	const found = new Set();
	for (const selector of spec.selectors || []) {
		try {
			doc.querySelectorAll(selector).forEach((element) => found.add(element));
		} catch (e) {
			// An invalid selector only loses its outlines.
		}
	}
	const tokens = spec.tokens || [];
	const families = (spec.families || []).map(
		(family) => new RegExp(`-(ink|surface|outline)-${family}-\\d+$`)
	);
	if (tokens.length || families.length) {
		for (const element of doc.querySelectorAll("[class]")) {
			const matches = class_names(element).some((name) => {
				const utility = name.slice(name.lastIndexOf(":") + 1);
				return (
					tokens.some((token) => utility.endsWith(`-${token}`)) ||
					families.some((family) => family.test(utility))
				);
			});
			if (matches) found.add(element);
		}
	}
	return found;
}

function draw_frame_highlight(frame) {
	let doc;
	try {
		doc = frame && frame.contentDocument;
	} catch (e) {
		return;
	}
	if (!doc || !doc.body) return;
	let layer = doc.getElementById(HIGHLIGHT_LAYER_ID);
	const spec = preview.highlight && preview.highlights[preview.highlight];
	if (!spec) {
		if (layer) layer.remove();
		return;
	}
	if (!layer) {
		layer = doc.createElement("div");
		layer.id = HIGHLIGHT_LAYER_ID;
		layer.style.cssText = "position:fixed;inset:0;pointer-events:none;z-index:2147483647;";
		doc.body.appendChild(layer);
	}
	layer.replaceChildren();
	const view = doc.defaultView;
	let count = 0;
	for (const element of find_highlighted(doc, spec)) {
		if (layer.contains(element)) continue;
		const rect = element.getBoundingClientRect();
		const visible =
			rect.width >= 1 &&
			rect.height >= 1 &&
			rect.bottom > 0 &&
			rect.right > 0 &&
			rect.top < view.innerHeight &&
			rect.left < view.innerWidth;
		if (!visible) continue;
		const outline = doc.createElement("div");
		outline.style.cssText =
			`position:fixed;left:${rect.left}px;top:${rect.top}px;` +
			`width:${rect.width}px;height:${rect.height}px;` +
			"outline:2px solid #e11d8f;outline-offset:1px;" +
			"background:rgba(225,29,143,.08);border-radius:3px;";
		layer.appendChild(outline);
		if (++count >= HIGHLIGHT_MAX_BOXES) break;
	}
}

// --- Base: strip of the colors computed from the 4 base colors ---------------

const BASE_SWATCH_ROLES = [
	"adv_button_bg",
	"adv_sidebar_active_bg",
	"adv_link_ink",
	"adv_page_bg",
	"adv_text_ink",
	"adv_border",
	"adv_chart_1",
	"adv_chart_2",
	"adv_chart_3",
	"adv_chart_4",
	"adv_chart_5",
];

function render_base_swatches(frm, roles) {
	const field = frm.get_field("base_swatches");
	if (!field || !field.$wrapper) return;
	const wrapper = field.$wrapper.empty();
	if (frm.doc.mode !== "Base") return;
	if (!Object.keys(roles).length) {
		$(`<div class="text-muted small"></div>`)
			.text(_p("Choose a primary color to see the computed colors."))
			.appendTo(wrapper);
		return;
	}
	$(`<div class="control-label"></div>`).text(_p("Computed Colors")).appendTo(wrapper);
	const strip = $(`<div class="brand-swatches"></div>`).appendTo(wrapper);
	for (const fieldname of BASE_SWATCH_ROLES) {
		const value = roles[fieldname];
		if (!value) continue;
		const label = __(frm.get_field(fieldname)?.df.label || fieldname, null, PREVIEW_CONTEXT);
		const chip = $(`<div class="brand-swatch"><span class="brand-swatch-color"></span><span></span></div>`);
		chip.attr("title", `${label}: ${value}`);
		const sample = chip.find(".brand-swatch-color").css("background", value);
		if (fieldname === "adv_button_bg" && roles.adv_button_ink) {
			sample.css("color", roles.adv_button_ink).text("Aa");
		}
		chip.find("span").last().text(label);
		strip.append(chip);
	}
}

function ensure_preview_styles() {
	if (document.getElementById("brand-preview-styles")) return;
	const style = document.createElement("style");
	style.id = "brand-preview-styles";
	style.textContent = `
		/* Frappe gives .container and .page-body width: 100%, so the width has to
		   shrink explicitly to leave room for the panel. */
		.brand-preview-open .container {
			width: calc(100% - var(--brand-preview-width));
			max-width: none;
			margin-left: 0;
			margin-right: var(--brand-preview-width);
		}
		.brand-preview-open { --brand-preview-width: 46vw; }
		/* The form sidebar (assign, attachments, timeline) would squeeze the fields. */
		.brand-preview-open .layout-side-section { display: none; }
		.brand-preview {
			position: fixed;
			top: var(--navbar-height, 48px);
			right: 0;
			bottom: 0;
			width: var(--brand-preview-width, 46vw);
			z-index: 1010;
			display: flex;
			flex-direction: column;
			gap: 8px;
			padding: 12px;
			background: var(--bg-color, #f8f8f8);
			border-left: 1px solid var(--border-color, #ededed);
		}
		.brand-preview-bar {
			display: flex;
			flex-wrap: wrap;
			gap: 8px;
			align-items: center;
			justify-content: space-between;
		}
		.brand-preview-tabs, .brand-preview-tools, .brand-preview-devices {
			display: flex;
			flex-wrap: wrap;
			gap: 4px;
			align-items: center;
		}
		.brand-preview-tools { gap: 8px; }
		.brand-preview-tab-empty { opacity: .55; }
		.brand-preview-status {
			display: flex;
			flex-wrap: wrap;
			gap: 4px 12px;
			align-items: center;
			font-size: var(--text-sm, 12px);
			color: var(--text-muted, #7c7c7c);
		}
		.brand-preview-invalid { width: 100%; color: var(--red-600, #c0392b); }
		.brand-preview-stage {
			position: relative;
			flex: 1;
			min-height: 0;
			display: flex;
			justify-content: center;
			overflow: hidden;
		}
		.brand-preview-frame-box {
			overflow: hidden;
			border: 1px solid var(--border-color, #ededed);
			border-radius: var(--border-radius-md, 8px);
			background: #fff;
		}
		.brand-preview-frame {
			display: block;
			border: 0;
			transform-origin: top left;
		}
		.brand-preview-empty {
			align-self: center;
			max-width: 360px;
			text-align: center;
			color: var(--text-muted, #7c7c7c);
		}
		.brand-swatches { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
		.brand-swatch {
			display: flex;
			align-items: center;
			gap: 6px;
			font-size: var(--text-sm, 12px);
			color: var(--text-muted, #7c7c7c);
		}
		.brand-swatch-color {
			display: inline-flex;
			align-items: center;
			justify-content: center;
			width: 28px;
			height: 28px;
			border-radius: var(--border-radius, 6px);
			border: 1px solid var(--border-color, #ededed);
			font-size: 11px;
			font-weight: 600;
		}
		@media (max-width: 1199px) {
			.brand-preview-open .container { width: 100%; margin-right: 0; }
			.brand-preview { width: auto; left: 0; }
		}
	`;
	document.head.appendChild(style);
}

// Shows the stock frappe-ui value as the placeholder of each empty Expert field,
// so it is clear what a value overrides. The defaults come from the compiled SPA
// stylesheet (the Desk does not load it) and only change with a new build.
let token_defaults = null;

function show_token_defaults(frm) {
	const apply = () => {
		for (const [fieldname, value] of Object.entries(token_defaults)) {
			const field = frm.get_field(fieldname);
			if (field && field.$input) field.$input.attr("placeholder", value);
		}
	};
	if (token_defaults) return apply();
	frappe
		.xcall("os_lms.os_lms.branding.get_token_defaults")
		.then((defaults) => {
			token_defaults = defaults || {};
			apply();
		})
		.catch(() => {
			// Placeholders are a hint only: the form works without them.
			token_defaults = null;
		});
}

// Color fieldnames only (theme and layout-only fields are excluded).
function get_color_fieldnames(frm) {
	return frm.meta.fields.filter((df) => df.fieldtype === "Color").map((df) => df.fieldname);
}

// Injects the clear-button styles once (needed for :hover, which inline styles can't do).
function ensure_clear_styles() {
	if (document.getElementById("brand-clear-styles")) return;
	const style = document.createElement("style");
	style.id = "brand-clear-styles";
	style.textContent = `
		.brand-clear-btn {
			display: inline-flex;
			align-items: center;
			justify-content: center;
			width: 20px;
			height: 20px;
			padding: 0;
			margin-left: 6px;
			border: 1px solid var(--border-color, #d1d8dd);
			border-radius: var(--border-radius, 6px);
			background: var(--control-bg, #f4f5f6);
			color: var(--ink-gray-6, #74808b);
			font-size: 13px;
			line-height: 1;
			cursor: pointer;
			vertical-align: middle;
			transition: background .15s, color .15s, border-color .15s;
		}
		.brand-clear-btn:hover {
			background: var(--surface-gray-3, #e8eaed);
			color: var(--ink-gray-8, #374151);
			border-color: var(--gray-400, #c0c6cc);
		}
		.brand-clear-btn:active { transform: scale(0.92); }
	`;
	document.head.appendChild(style);
}

// Adds a small "✕" button next to each Color field's label to clear that single value.
function add_clear_icons(frm) {
	ensure_clear_styles();
	for (const fieldname of get_color_fieldnames(frm)) {
		const field = frm.get_field(fieldname);
		const label = field && field.$wrapper && field.$wrapper.find(".clearfix").first();
		if (!label || !label.length || label.find(".brand-clear-btn").length) continue;

		const btn = $(
			`<button type="button" class="brand-clear-btn" title="${__("Clear value")}">✕</button>`
		);
		btn.on("click", () => frm.set_value(fieldname, ""));
		label.append(btn);
	}
}

function reset_colors(frm) {
	const color_fields = get_color_fieldnames(frm);
	const expert_count = (frm.doc.expert_tokens || []).length;
	frappe.confirm(
		__("This will clear all {0} colors. Continue?", [color_fields.length + expert_count]),
		() => {
			for (const fieldname of color_fields) frm.set_value(fieldname, "");
			clear_expert_tokens(frm);
			frappe.show_alert({ message: __("Colors cleared. Save to apply."), indicator: "orange" });
		}
	);
}

// Fieldnames that actually hold a value (skips Section/Column Break and other
// layout-only fieldtypes), so the export stays in sync as colors are added.
function get_data_fieldnames(frm) {
	return frm.meta.fields
		.filter((df) => !frappe.model.no_value_type.includes(df.fieldtype))
		.map((df) => df.fieldname);
}

// The form values, as written by Export and saved by "Save as Preset". Values
// still being typed (preview.live) are included: what the preview shows is
// what gets saved.
function brand_settings_data(frm) {
	const data = {};
	for (const fieldname of get_data_fieldnames(frm)) {
		data[fieldname] = frm.doc[fieldname] ?? null;
	}
	Object.assign(data, preview.live);
	// Table fields are layout-free but valueless for Frappe: added by hand.
	data.expert_tokens = (frm.doc.expert_tokens || []).map((row) => ({
		token: row.token,
		value: row.value,
	}));
	return data;
}

function export_brand_settings(frm) {
	const data = brand_settings_data(frm);

	const payload = {
		doctype: frm.doctype,
		version: EXPORT_VERSION,
		exported_on: frappe.datetime.now_datetime(),
		data,
	};

	const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
	const url = URL.createObjectURL(blob);
	const link = document.createElement("a");
	link.href = url;
	link.download = "brand-customize.json";
	document.body.appendChild(link);
	link.click();
	document.body.removeChild(link);
	URL.revokeObjectURL(url);
}

function import_brand_settings(frm) {
	const input = document.createElement("input");
	input.type = "file";
	input.accept = "application/json,.json";
	input.onchange = () => {
		const file = input.files && input.files[0];
		if (!file) return;

		const reader = new FileReader();
		reader.onload = () => {
			let payload;
			try {
				payload = JSON.parse(reader.result);
			} catch (e) {
				frappe.msgprint({
					title: __("Import Failed"),
					message: __("The selected file is not valid JSON."),
					indicator: "red",
				});
				return;
			}
			// The map of the old Expert fields comes with the variable list.
			load_expert_tokens().then(() => apply_brand_settings(frm, payload));
		};
		reader.readAsText(file);
	};
	input.click();
}

function apply_brand_settings(frm, payload, preset_name) {
	// Accept both the wrapped export format and a flat fieldname -> value object.
	const data = payload && typeof payload.data === "object" ? payload.data : payload;
	if (!data || typeof data !== "object" || Array.isArray(data)) {
		frappe.msgprint({
			title: __("Import Failed"),
			message: __("The file does not contain any brand settings."),
			indicator: "red",
		});
		return;
	}
	if (payload.doctype && payload.doctype !== frm.doctype) {
		frappe.msgprint({
			title: __("Import Failed"),
			message: __("The file was exported from {0}, not from {1}.", [
				frappe.utils.escape_html(String(payload.doctype)),
				__(frm.doctype),
			]),
			indicator: "red",
		});
		return;
	}

	const valid = new Set(get_data_fieldnames(frm));
	const legacy = expert.legacy || {};
	const to_apply = Object.entries(data).filter(([fieldname]) => valid.has(fieldname));
	const skipped = Object.keys(data).filter(
		(fieldname) => !valid.has(fieldname) && fieldname !== "expert_tokens" && !legacy[fieldname]
	);

	// Expert variables: the table of version 2, or the one-field-per-variable
	// Expert fields of version 1.
	const tokens = {};
	for (const [fieldname, css_var] of Object.entries(legacy)) {
		if (typeof data[fieldname] === "string" && data[fieldname].trim()) tokens[css_var] = data[fieldname].trim();
	}
	for (const row of Array.isArray(data.expert_tokens) ? data.expert_tokens : []) {
		if (row && typeof row.token === "string" && typeof row.value === "string" && row.value.trim()) {
			tokens[row.token.trim()] = row.value.trim();
		}
	}
	// A version 1 file always lists its Expert fields, also the empty ones: the
	// table is replaced as soon as one is present, as it is by a version 2 file.
	const has_tokens = Array.isArray(data.expert_tokens) || Object.keys(legacy).some((f) => f in data);
	const token_count = Object.keys(tokens).length;

	if (!to_apply.length && !has_tokens) {
		frappe.msgprint({
			title: __("Import Failed"),
			message: __("No matching brand settings were found in the file."),
			indicator: "red",
		});
		return;
	}

	// Empty values still clear their field, but only the set ones are counted.
	const is_set = (value) => value !== null && value !== undefined && String(value).trim() !== "";
	const count = to_apply.filter(([, value]) => is_set(value)).length + token_count;
	const question = preset_name
		? __(
				"This will overwrite the current brand settings with {0} value(s) from the preset {1}. Continue?",
				[count, frappe.utils.escape_html(preset_name)],
				PREVIEW_CONTEXT
		  )
		: __("This will overwrite the current brand settings with {0} value(s) from the file. Continue?", [
				count,
		  ]);
	frappe.confirm(question, () => {
		// The values replace the form as a whole: a mode set here must not
		// trigger the "start from the previous mode" offer of on_mode_change.
		preview.applying_settings = true;
		Promise.all(to_apply.map(([fieldname, value]) => frm.set_value(fieldname, value ?? "")))
			.then(() => {
				if (has_tokens) replace_expert_tokens(frm, tokens);
			})
			.finally(() => {
				preview.applying_settings = false;
				preview.last_mode = frm.doc.mode;
			});
		{
			let message = preset_name
				? __(
						"Preset {0} applied: {1} setting(s). Review and Save to apply.",
						[frappe.utils.escape_html(preset_name), count],
						PREVIEW_CONTEXT
				  )
				: __("Imported {0} setting(s). Review and Save to apply.", [count]);
			if (skipped.length) {
				message += "<br>" + __("Ignored unknown field(s): {0}", [
					skipped.map(frappe.utils.escape_html).join(", "),
				]);
			}
			frappe.msgprint({
				title: preset_name ? _p("Preset Applied") : __("Import Complete"),
				message,
				indicator: "green",
			});
		}
	});
}

// ---------------------------------------------------------------------------
// Expert editor (docs/brand-customize/fase-4-analisi.md)
//
// Every CSS variable of the installed SPA build, listed by the server
// (branding_tokens.py). Set values live in the hidden expert_tokens table, one
// row per variable; an emptied value removes its row.
// ---------------------------------------------------------------------------

const EXPERT_FAMILIES = [
	["surface", "Surfaces"],
	["ink", "Text"],
	["outline", "Borders"],
	["palette", "Palettes"],
	["radius", "Corner Rounding"],
	["elevation", "Shadows"],
	["focus", "Focus"],
	["plyr", "Video Player"],
	["os_lms", "Platform"],
	["other", "Other"],
];
const EXPERT_HEX_RE = /^#[0-9a-f]{6}$/i;
// Variables whose elements a style probe cannot see: the charts get their colors
// from JavaScript (brandChartColors.ts), as resolved SVG attributes.
const EXPERT_CHART_RE = /^--os-chart-\d+$/;

const expert = {
	tokens: null,
	by_name: {},
	legacy: {},
	loading: null,
	filters: { search: "", family: "", only_set: false, only_page: false, show_unused: false },
	page_tokens: new WeakMap(),
};

function load_expert_tokens() {
	if (expert.loading) return expert.loading;
	expert.loading = frappe
		.xcall("os_lms.os_lms.branding.get_expert_tokens")
		.then((response) => {
			expert.tokens = (response && response.tokens) || [];
			expert.legacy = (response && response.legacy) || {};
			expert.by_name = {};
			for (const token of expert.tokens) expert.by_name[token.name] = token;
		})
		.catch(() => {
			expert.tokens = [];
			expert.loading = null;
		});
	return expert.loading;
}

function expert_token_map(frm) {
	const map = {};
	for (const row of frm.doc.expert_tokens || []) {
		if (row.token && (row.value || "").trim()) map[row.token] = row.value.trim();
	}
	return map;
}

function set_expert_token(frm, name, value) {
	value = (value || "").trim();
	const row = (frm.doc.expert_tokens || []).find((r) => r.token === name);
	if (!value) {
		if (!row) return;
		frappe.model.clear_doc(row.doctype, row.name);
	} else if (row) {
		if (row.value === value) return;
		row.value = value;
	} else {
		frm.add_child("expert_tokens", { token: name, value });
	}
	frm.dirty();
	schedule_preview(frm);
	render_expert_count(frm);
}

function clear_expert_tokens(frm) {
	if (!(frm.doc.expert_tokens || []).length) return;
	frappe.model.clear_table(frm.doc, "expert_tokens");
	frm.dirty();
	frm.refresh_field("expert_tokens");
	render_expert_rows(frm);
	schedule_preview(frm);
}

function replace_expert_tokens(frm, tokens) {
	frappe.model.clear_table(frm.doc, "expert_tokens");
	for (const [token, value] of Object.entries(tokens)) frm.add_child("expert_tokens", { token, value });
	frm.dirty();
	frm.refresh_field("expert_tokens");
	render_expert_rows(frm);
	schedule_preview(frm);
}

// Base or Advanced -> Expert: what those modes write everywhere becomes Expert
// variables; what they write inside an area has no Expert equivalent.
function offer_copy_to_expert(frm, previous) {
	const prefix = previous === "Base" ? "base_" : "adv_";
	const fields = fieldnames_with_prefix(frm, prefix);
	if (!fields.some((fieldname) => frm.doc[fieldname])) return;
	const mode_label = _p(previous === "Base" ? "Base" : "Advanced");
	const question = (frm.doc.expert_tokens || []).length
		? __("Replace the Expert variables with the colors of the {0} mode?", [mode_label], PREVIEW_CONTEXT)
		: __("Start from the colors of the {0} mode?", [mode_label], PREVIEW_CONTEXT);

	frappe.confirm(question, () => {
		const values = { ...collect_preview_values(frm), mode: previous };
		frappe
			.xcall("os_lms.os_lms.branding.to_expert", { values: JSON.stringify(values) })
			.then((result) => {
				const tokens = (result && result.tokens) || {};
				replace_expert_tokens(frm, tokens);
				let message = __(
					"{0} variables filled in from the {1} mode. Save to apply.",
					[Object.keys(tokens).length, mode_label],
					PREVIEW_CONTEXT
				);
				if (result && result.scoped) {
					message +=
						"<br><br>" +
						__(
							"{0} colors of that mode apply only to an area (buttons, sidebar, fields...) and have no Expert equivalent: they were not copied.",
							[result.scoped],
							PREVIEW_CONTEXT
						);
				}
				frappe.msgprint({ title: _p("Expert"), message, indicator: "green" });
			});
	});
}

function render_expert_editor(frm) {
	const field = frm.get_field("expert_editor");
	if (!field || !field.$wrapper) return;
	load_expert_tokens().then(() => {
		if (frm.doc.mode !== "Expert") return;
		const wrapper = field.$wrapper;
		if (!wrapper.find(".brand-tokens").length) build_expert_editor(frm, wrapper.empty());
		render_expert_rows(frm);
	});
}

function build_expert_editor(frm, wrapper) {
	ensure_expert_styles();
	const editor = $(`
		<div class="brand-tokens">
			<div class="brand-tokens-tools">
				<input type="search" class="form-control input-xs brand-tokens-search">
				<select class="form-control input-xs brand-tokens-family"></select>
				<label class="brand-tokens-check"><input type="checkbox" data-filter="only_set"><span></span></label>
				<label class="brand-tokens-check"><input type="checkbox" data-filter="only_page"><span></span></label>
				<label class="brand-tokens-check"><input type="checkbox" data-filter="show_unused"><span></span></label>
			</div>
			<div class="brand-tokens-count text-muted small"></div>
			<div class="brand-tokens-list"></div>
		</div>
	`).appendTo(wrapper);

	editor
		.find(".brand-tokens-search")
		.attr("placeholder", _p("Search variables"))
		.val(expert.filters.search)
		.on("input", function () {
			expert.filters.search = this.value;
			render_expert_rows(frm);
		});

	const family = editor.find(".brand-tokens-family");
	$("<option value=''></option>").text(_p("All families")).appendTo(family);
	for (const [key, label] of EXPERT_FAMILIES) {
		$("<option></option>").attr("value", key).text(_p(label)).appendTo(family);
	}
	family.val(expert.filters.family).on("change", function () {
		expert.filters.family = this.value;
		render_expert_rows(frm);
	});

	const check_labels = {
		only_set: "Only set",
		only_page: "Only on the preview page",
		show_unused: "Show variables without effect",
	};
	editor.find(".brand-tokens-check input").each(function () {
		const key = this.dataset.filter;
		this.checked = expert.filters[key];
		$(this).next("span").text(_p(check_labels[key]));
		$(this).on("change", () => {
			expert.filters[key] = this.checked;
			render_expert_rows(frm);
		});
	});
	ensure_clear_styles();
}

function render_expert_count(frm) {
	const editor = frm.get_field("expert_editor")?.$wrapper.find(".brand-tokens");
	if (!editor || !editor.length) return;
	const shown = editor.find(".brand-token-row").length;
	editor
		.find(".brand-tokens-count")
		.text(
			__(
				"{0} of {1} variables shown · {2} set",
				[shown, (expert.tokens || []).length, Object.keys(expert_token_map(frm)).length],
				PREVIEW_CONTEXT
			)
		);
}

function render_expert_rows(frm) {
	if (!frm || frm.doc.mode !== "Expert") return;
	const editor = frm.get_field("expert_editor")?.$wrapper.find(".brand-tokens");
	if (!editor || !editor.length) return;
	const list = editor.find(".brand-tokens-list").empty();

	if (!(expert.tokens || []).length) {
		$(`<div class="text-muted small"></div>`)
			.text(_p("The list of variables is not available: the platform frontend has not been built."))
			.appendTo(list);
		return;
	}

	const values = expert_token_map(frm);
	const filters = expert.filters;
	const search = filters.search.trim().toLowerCase();
	let page_tokens = null;
	if (filters.only_page) {
		page_tokens = tokens_on_preview_page();
		if (!page_tokens) {
			$(`<div class="text-muted small"></div>`)
				.text(_p("Open the preview to use this filter."))
				.appendTo(list);
		}
	}

	// Saved variables the installed build no longer has are listed too.
	const unknown = Object.keys(values)
		.filter((name) => !expert.by_name[name])
		.map((name) => ({ name, default: "", kind: "other", family: "other", used: false, unknown: true }));

	for (const token of [...unknown, ...expert.tokens]) {
		const value = values[token.name] || "";
		if (search && !token.name.includes(search)) continue;
		if (filters.family && token.family !== filters.family) continue;
		if (filters.only_set && !value) continue;
		if (!filters.show_unused && !token.used && !value) continue;
		if (page_tokens && !page_tokens.has(token.name) && !value) continue;
		list.append(build_expert_row(frm, token, value));
	}
	if (!list.children().length) {
		$(`<div class="text-muted small"></div>`).text(_p("No variable matches the filters.")).appendTo(list);
	}
	render_expert_count(frm);
	render_contrast_badges(frm);
}

function build_expert_row(frm, token, value) {
	const row = $(`
		<div class="brand-token-row">
			<code class="brand-token-name"></code>
			<span class="brand-token-default"><span class="brand-token-sample"></span><span class="brand-token-default-text"></span></span>
			<span class="brand-token-edit">
				<input type="text" class="form-control input-xs brand-token-input" spellcheck="false">
				<input type="color" class="brand-token-picker">
				<button type="button" class="brand-clear-btn">✕</button>
			</span>
		</div>
	`);
	row.attr("data-token", token.name).toggleClass("brand-token-unused", !token.used);
	row.find(".brand-token-name").text(token.name);
	if (token.unknown) {
		row.find(".brand-token-default-text").text(_p("Not on the platform any more"));
	} else {
		row.find(".brand-token-default-text").text(token.default || _p("No standard value"));
		row.find(".brand-token-default").attr("title", token.default || "");
	}
	const is_color = ["color", "shadow"].includes(token.kind);
	if (is_color && token.default) row.find(".brand-token-sample").css("background", token.default);
	else row.find(".brand-token-sample").remove();

	const input = row.find(".brand-token-input").val(value).attr("placeholder", token.default || "");
	const picker = row.find(".brand-token-picker");
	if (token.kind === "color") {
		picker.val(to_hex(value) || to_hex(token.default) || "#000000");
		picker.attr("title", _p("Choose a color"));
	} else {
		picker.remove();
	}

	input.on("input", () => set_expert_token(frm, token.name, input.val()));
	input.on("focus", () => set_token_highlight(token));
	input.on("blur", () => clear_highlight_soon());
	picker.on("input", () => {
		input.val(picker.val());
		set_expert_token(frm, token.name, picker.val());
	});
	picker.on("focus", () => set_token_highlight(token));
	row.find(".brand-clear-btn")
		.attr("title", __("Clear value"))
		.on("click", () => {
			input.val("");
			set_expert_token(frm, token.name, "");
		});
	return row;
}

// The native color picker only takes #rrggbb: any CSS color (oklch...) is
// converted by painting it on a 1x1 canvas.
let hex_canvas = null;
function to_hex(value) {
	value = (value || "").trim();
	if (EXPERT_HEX_RE.test(value)) return value.toLowerCase();
	if (!value || value.startsWith("var(") || !CSS.supports("color", value)) return null;
	hex_canvas = hex_canvas || document.createElement("canvas").getContext("2d", { willReadFrequently: true });
	hex_canvas.clearRect(0, 0, 1, 1);
	hex_canvas.fillStyle = "#000";
	hex_canvas.fillStyle = value;
	hex_canvas.fillRect(0, 0, 1, 1);
	const [r, g, b] = hex_canvas.getImageData(0, 0, 1, 1).data;
	return "#" + [r, g, b].map((n) => n.toString(16).padStart(2, "0")).join("");
}

// --- Exact "where is it used" for Expert variables ----------------------------
//
// The variable gets an unmistakable value in the preview frame for an instant,
// and the elements whose computed style changes are the ones that use it. This
// is the isolation test of fase-3 turned into a highlight. Transitions are off
// during the probe (a running transition reports its start value) and come back
// once styles are recomputed with the real value, so nothing animates. It all
// runs in one task: the browser never paints the probe value.

const PROBE_VALUES = {
	color: "rgb(1, 254, 3)",
	shadow: "0 0 0 7px rgb(1, 254, 3)",
	length: "37.5px",
	other: "rgb(1, 254, 3)",
};
const PROBE_PROPS = [
	"color",
	"background-color",
	"background-image",
	"border-top-color",
	"border-right-color",
	"border-bottom-color",
	"border-left-color",
	"border-top-left-radius",
	"border-top-right-radius",
	"border-bottom-left-radius",
	"border-bottom-right-radius",
	"outline-color",
	"box-shadow",
	"text-decoration-color",
	"fill",
	"stroke",
	"width",
	"height",
	"gap",
	"padding-top",
	"font-family",
];
const probe_cache = new WeakMap();

function set_token_highlight(token) {
	const key = `token:${token.name}`;
	preview.highlights[key] = EXPERT_CHART_RE.test(token.name)
		? { selectors: ["[_echarts_instance_]"] }
		: { probe: token.name, kind: token.kind };
	set_highlight(key);
}

function probe_cached(doc, spec) {
	const cached = probe_cache.get(doc);
	if (cached && cached.name === spec.probe && cached.css === preview.css) return cached.elements;
	const elements = probe_token(doc, spec.probe, spec.kind);
	probe_cache.set(doc, { name: spec.probe, css: preview.css, elements });
	return elements;
}

function probe_token(doc, name, kind) {
	const view = doc.defaultView;
	if (!view || !doc.head || !doc.body) return [];
	const freeze = doc.createElement("style");
	freeze.textContent = "*,*::before,*::after{transition:none!important;animation:none!important}";
	doc.head.appendChild(freeze);

	const elements = [...doc.body.querySelectorAll("*")].filter(
		(element) => !element.closest(`#${HIGHLIGHT_LAYER_ID}`)
	);
	const read = (element) => {
		const style = view.getComputedStyle(element);
		return PROBE_PROPS.map((prop) => style.getPropertyValue(prop)).join("|");
	};
	const before = elements.map(read);
	const probe = doc.createElement("style");
	probe.textContent = `:root, *, *::before, *::after { ${name}: ${PROBE_VALUES[kind] || PROBE_VALUES.other} !important; }`;
	doc.head.appendChild(probe);
	const changed = elements.filter((element, i) => read(element) !== before[i]);
	probe.remove();
	// Styles are recomputed with the real value while transitions are still off:
	// turning them back on then changes no value, so nothing animates.
	for (const element of elements) view.getComputedStyle(element).color;
	freeze.remove();
	return changed;
}

// --- "Only on the preview page" ----------------------------------------------
//
// Variables read by the style rules that match some element of the open preview
// page, plus inline styles and SVG attributes. Exact for CSS; the charts are
// added when the page has one (their colors come from JavaScript).

const STATE_PSEUDO_RE = /::?(?!not\(|is\(|where\(|has\()[a-z-]+(\([^()]*\))?/gi;
const VAR_NAME_RE = /var\(\s*(--[\w-]+)/g;

function tokens_on_preview_page() {
	const box = preview.frames[preview.active];
	const frame = box && box.find("iframe").get(0);
	let doc;
	try {
		doc = frame && frame.contentDocument;
	} catch (e) {
		return null;
	}
	if (!doc || !doc.body || !doc.body.children.length) return null;
	const cached = expert.page_tokens.get(doc);
	if (cached && cached.css === preview.css && cached.size === doc.body.querySelectorAll("*").length) {
		return cached.tokens;
	}

	const view = doc.defaultView;
	const tokens = new Set();
	const add_refs = (text) => {
		for (const match of (text || "").matchAll(VAR_NAME_RE)) tokens.add(match[1]);
	};
	const matches = (selector) => {
		const plain = selector.replace(STATE_PSEUDO_RE, "").trim();
		try {
			return !!doc.querySelector(plain || "*");
		} catch (e) {
			return false;
		}
	};
	const walk = (rules) => {
		for (const rule of rules) {
			if (rule.media && !view.matchMedia(rule.media.mediaText).matches) continue;
			if (rule.selectorText !== undefined) {
				const text = rule.style && rule.style.cssText;
				if (text && text.includes("var(") && matches(rule.selectorText)) add_refs(text);
			}
			if (rule.cssRules) walk(rule.cssRules);
		}
	};
	for (const sheet of doc.styleSheets) {
		if (sheet.disabled) continue;
		try {
			walk(sheet.cssRules);
		} catch (e) {
			// Cross-origin stylesheets cannot be read; they hold no platform variables.
		}
	}
	for (const element of doc.querySelectorAll("[style*='var('], [fill*='var('], [stroke*='var(']")) {
		add_refs(element.getAttribute("style"));
		add_refs(element.getAttribute("fill"));
		add_refs(element.getAttribute("stroke"));
	}
	if (doc.querySelector("[_echarts_instance_]")) {
		for (let n = 1; n <= 5; n++) tokens.add(`--os-chart-${n}`);
	}
	expert.page_tokens.set(doc, {
		css: preview.css,
		size: doc.body.querySelectorAll("*").length,
		tokens,
	});
	return tokens;
}

function ensure_expert_styles() {
	if (document.getElementById("brand-expert-styles")) return;
	const style = document.createElement("style");
	style.id = "brand-expert-styles";
	style.textContent = `
		.brand-tokens-tools {
			display: flex;
			flex-wrap: wrap;
			gap: 8px 12px;
			align-items: center;
			margin-bottom: 6px;
		}
		.brand-tokens-search { max-width: 240px; }
		.brand-tokens-family { max-width: 180px; }
		.brand-tokens-check {
			display: inline-flex;
			gap: 4px;
			align-items: center;
			margin: 0;
			font-size: var(--text-sm, 12px);
			font-weight: normal;
		}
		.brand-tokens-count { margin-bottom: 6px; }
		.brand-tokens-list {
			max-height: 70vh;
			overflow-y: auto;
			border: 1px solid var(--border-color, #ededed);
			border-radius: var(--border-radius-md, 8px);
		}
		.brand-token-row {
			display: grid;
			grid-template-columns: minmax(180px, 1.2fr) minmax(120px, 1fr) minmax(200px, 1.2fr);
			gap: 8px;
			align-items: center;
			padding: 4px 8px;
			border-bottom: 1px solid var(--border-color, #ededed);
		}
		.brand-token-row:last-child { border-bottom: 0; }
		.brand-token-unused .brand-token-name { opacity: .6; }
		.brand-token-name {
			font-size: 12px;
			background: none;
			padding: 0;
			overflow-wrap: anywhere;
		}
		.brand-token-default {
			display: flex;
			gap: 6px;
			align-items: center;
			min-width: 0;
			font-size: var(--text-sm, 12px);
			color: var(--text-muted, #7c7c7c);
		}
		.brand-token-default-text {
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
		}
		.brand-token-sample {
			flex: none;
			width: 16px;
			height: 16px;
			border-radius: 4px;
			border: 1px solid var(--border-color, #ededed);
		}
		.brand-token-edit { display: flex; gap: 4px; align-items: center; }
		.brand-token-picker {
			flex: none;
			width: 26px;
			height: 26px;
			padding: 0;
			border: 1px solid var(--border-color, #ededed);
			border-radius: 4px;
			background: none;
		}
		.brand-token-edit .brand-clear-btn { margin-left: 0; }
		@media (max-width: 767px) {
			.brand-token-row { grid-template-columns: 1fr; }
		}
	`;
	document.head.appendChild(style);
}

// ---------------------------------------------------------------------------
// Readability (docs/brand-customize/fase-5-analisi.md)
//
// The server measures the contrast of the text/background pairs on screen with
// the colors of the active mode (branding_contrast.py). Only pairs harder to
// read than with the standard colors are warnings (decision G1); saving is
// never blocked (D6).
// ---------------------------------------------------------------------------

const CONTRAST_LEVELS = { ok: 0, stock: 1, low: 2 };

const ratio_text = (value) => format_number(value, null, 1);

// Fields of the form behind a pair, for the active mode.
function contrast_fields(entry, mode) {
	const fields = entry.fields || {};
	if (fields.login) return fields.login;
	if (mode === "Base") return fields.base || [];
	if (mode === "Advanced") return fields.advanced || [];
	return fields.expert || [];
}

function render_contrast(frm) {
	render_contrast_badges(frm);
	const field = frm.get_field("contrast_report");
	if (!field || !field.$wrapper) return;
	const wrapper = field.$wrapper.empty();
	const entries = preview.contrast || [];
	if (!entries.length) return;
	ensure_contrast_styles();

	const low = entries.filter((entry) => entry.level === "low");
	const as_stock = entries.filter((entry) => entry.level === "stock");
	const box = $(`<div class="brand-contrast"></div>`).appendTo(wrapper);
	$(`<div class="control-label"></div>`).text(_p("Readability")).appendTo(box);

	if (!low.length) {
		$(`<div class="brand-contrast-ok"></div>`)
			.text(_p("All colors read at least as well as the standard ones."))
			.appendTo(box);
	} else {
		box.addClass("brand-contrast-warning");
		$(`<div class="brand-contrast-intro"></div>`)
			.text(_p("These colors are harder to read than the standard ones. Click a row to go to its color."))
			.appendTo(box);
		const list = $(`<ul class="brand-contrast-list"></ul>`).appendTo(box);
		for (const entry of low) {
			const row = $(`<li class="brand-contrast-row" role="button" tabindex="0"></li>`);
			$(`<span class="brand-contrast-sample">Aa</span>`)
				.css({ color: entry.fg, background: entry.bg })
				.appendTo(row);
			$(`<span></span>`)
				.text(
					__(
						"{0}: {1}:1 (minimum {2}:1, standard colors {3}:1)",
						[entry.label, ratio_text(entry.ratio), ratio_text(entry.minimum), ratio_text(entry.stock)],
						PREVIEW_CONTEXT
					)
				)
				.appendTo(row);
			row.on("click keydown", (event) => {
				if (event.type === "keydown" && !["Enter", " "].includes(event.key)) return;
				event.preventDefault();
				go_to_contrast_field(frm, entry);
			});
			list.append(row);
		}
	}
	if (as_stock.length) {
		$(`<div class="brand-contrast-note"></div>`)
			.text(
				__(
					"{0} other pairs are under the WCAG minimum, as they are with the standard colors.",
					[as_stock.length],
					PREVIEW_CONTEXT
				)
			)
			.appendTo(box);
	}
}

function go_to_contrast_field(frm, entry) {
	const fields = contrast_fields(entry, frm.doc.mode);
	if (frm.doc.mode === "Expert" && !(entry.fields || {}).login) {
		const token = fields[0];
		const editor = frm.get_field("expert_editor")?.$wrapper;
		if (!token || !editor) return;
		expert.filters.search = token;
		editor.find(".brand-tokens-search").val(token);
		render_expert_rows(frm);
		const input = editor.find(`.brand-token-row[data-token="${token}"] .brand-token-input`).get(0);
		if (input) {
			input.scrollIntoView({ block: "center" });
			input.focus();
		}
		return;
	}
	const fieldname = fields.find((name) => frm.get_field(name));
	if (fieldname) frm.scroll_to_field(fieldname);
}

// "AA ✓" or the ratio next to the text field of each pair (Advanced, login,
// Expert rows). Base has the summary only: its pairs depend on 4 colors together.
function render_contrast_badges(frm) {
	$(frm.wrapper).find(".brand-contrast-badge").remove();
	const mode = frm.doc.mode;
	const worst = {};
	for (const entry of preview.contrast || []) {
		const login = !!(entry.fields || {}).login;
		if (mode === "Base" && !login) continue;
		const target = contrast_fields(entry, mode)[0];
		if (!target) continue;
		const current = worst[target];
		if (
			!current ||
			CONTRAST_LEVELS[entry.level] > CONTRAST_LEVELS[current.level] ||
			(entry.level === current.level && entry.ratio < current.ratio)
		) {
			worst[target] = { ...entry, login };
		}
	}
	if (!Object.keys(worst).length) return;
	ensure_contrast_styles();

	for (const [target, entry] of Object.entries(worst)) {
		const badge = $(`<span class="brand-contrast-badge"></span>`).addClass(`brand-contrast-${entry.level}`);
		if (entry.level === "ok") badge.text(_p("AA ✓"));
		else if (entry.level === "stock")
			badge.text(__("As standard ({0}:1)", [ratio_text(entry.ratio)], PREVIEW_CONTEXT));
		else badge.text(__("Low contrast ({0}:1)", [ratio_text(entry.ratio)], PREVIEW_CONTEXT));
		badge.attr("title", `${entry.label}: ${ratio_text(entry.ratio)}:1`);

		if (mode === "Expert" && !entry.login) {
			$(frm.wrapper)
				.find(`.brand-token-row[data-token="${target}"] .brand-token-name`)
				.after(badge);
		} else {
			const label = frm.get_field(target)?.$wrapper.find(".control-label").first();
			if (label && label.length) label.append(badge);
		}
	}
}

function ensure_contrast_styles() {
	if (document.getElementById("brand-contrast-styles")) return;
	const style = document.createElement("style");
	style.id = "brand-contrast-styles";
	style.textContent = `
		.brand-contrast { padding: var(--padding-sm) var(--padding-md); border-radius: var(--border-radius-md);
			background: var(--subtle-fg); margin-bottom: var(--margin-sm); }
		.brand-contrast-warning { background: var(--bg-orange); }
		.brand-contrast-ok { color: var(--text-color); }
		.brand-contrast-intro { margin-bottom: 4px; }
		.brand-contrast-list { list-style: none; padding: 0; margin: 0; }
		.brand-contrast-row { display: flex; align-items: center; gap: 8px; padding: 3px 4px; cursor: pointer;
			border-radius: var(--border-radius-sm); }
		.brand-contrast-row:hover, .brand-contrast-row:focus-visible { background: var(--fg-color); }
		.brand-contrast-sample { display: inline-flex; align-items: center; justify-content: center; width: 32px;
			height: 20px; border-radius: 4px; font-weight: 600; font-size: 11px; border: 1px solid var(--border-color); }
		.brand-contrast-note { color: var(--text-muted); font-size: var(--text-sm); margin-top: 4px; }
		.brand-contrast-badge { margin-left: 6px; padding: 0 6px; border-radius: 9px; font-size: 11px;
			font-weight: 500; white-space: nowrap; }
		.brand-contrast-ok.brand-contrast-badge { background: var(--bg-green); color: var(--text-on-green); }
		.brand-contrast-stock.brand-contrast-badge { background: var(--subtle-fg); color: var(--text-muted); }
		.brand-contrast-low.brand-contrast-badge { background: var(--bg-orange); color: var(--text-on-orange); }
	`;
	document.head.appendChild(style);
}

// ---------------------------------------------------------------------------
// Presets (docs/brand-customize/fase-5-analisi.md, §3.4)
//
// A preset is the Export data saved in the site (Brand Preset). Applying one
// runs the Import code: the form is filled, nothing applies until it is saved.
// ---------------------------------------------------------------------------

function save_as_preset(frm) {
	const dialog = new frappe.ui.Dialog({
		title: _p("Save as Preset"),
		fields: [
			{
				fieldname: "preset_name",
				fieldtype: "Data",
				label: _p("Preset Name"),
				reqd: 1,
				description: _p("The current colors, including changes not saved yet."),
			},
		],
		primary_action_label: __("Save"),
		primary_action(values) {
			save(values.preset_name, 0);
		},
	});
	const save = (name, overwrite) =>
		frappe
			.xcall("os_lms.os_lms.branding_presets.save_preset", {
				preset_name: name,
				values: JSON.stringify(brand_settings_data(frm)),
				overwrite,
			})
			.then((result) => {
				if (result && result.exists) {
					frappe.confirm(_p("A preset with this name already exists. Overwrite it?"), () =>
						save(name, 1)
					);
					return;
				}
				dialog.hide();
				frappe.show_alert({
					message: __("Preset saved: {0}", [frappe.utils.escape_html(result.name)], PREVIEW_CONTEXT),
					indicator: "green",
				});
			});
	dialog.show();
}

function choose_preset(frm) {
	frappe.xcall("os_lms.os_lms.branding_presets.get_presets").then((presets) => {
		if (!(presets || []).length) {
			frappe.msgprint({
				title: _p("Apply Preset"),
				message: _p("There are no presets yet. Use Save as Preset first."),
				indicator: "blue",
			});
			return;
		}
		ensure_contrast_styles();
		ensure_preset_styles();
		const dialog = new frappe.ui.Dialog({
			title: _p("Apply Preset"),
			fields: [{ fieldname: "list", fieldtype: "HTML" }],
		});
		const list = $(`<div class="brand-presets"></div>`);
		for (const preset of presets) {
			const row = $(`
				<button type="button" class="brand-preset-row">
					<span class="brand-preset-swatches"></span>
					<span class="brand-preset-name"></span>
					<span class="brand-preset-meta"></span>
				</button>
			`);
			for (const value of preset.swatches || []) {
				$(`<span class="brand-preset-swatch"></span>`).css("background", value).appendTo(row.find(".brand-preset-swatches"));
			}
			row.find(".brand-preset-name").text(preset.name);
			row.find(".brand-preset-meta").text(
				`${_p(preset.mode || "Expert")} · ${frappe.datetime.str_to_user(preset.modified)}`
			);
			row.on("click", () => {
				dialog.hide();
				frappe
					.xcall("os_lms.os_lms.branding_presets.get_preset", { name: preset.name })
					.then((result) => apply_brand_settings(frm, { data: result.data }, result.name));
			});
			list.append(row);
		}
		dialog.fields_dict.list.$wrapper.append(list);
		dialog.show();
	});
}

function ensure_preset_styles() {
	if (document.getElementById("brand-preset-styles")) return;
	const style = document.createElement("style");
	style.id = "brand-preset-styles";
	style.textContent = `
		.brand-presets { display: flex; flex-direction: column; gap: 6px; }
		.brand-preset-row { display: flex; align-items: center; gap: 10px; width: 100%; text-align: left;
			padding: 8px 10px; border: 1px solid var(--border-color); border-radius: var(--border-radius-md);
			background: var(--fg-color); }
		.brand-preset-row:hover, .brand-preset-row:focus-visible { background: var(--subtle-fg); }
		.brand-preset-swatches { display: inline-flex; gap: 2px; min-width: 76px; }
		.brand-preset-swatch { width: 16px; height: 16px; border-radius: 4px; border: 1px solid var(--border-color); }
		.brand-preset-name { font-weight: 500; flex: 1; }
		.brand-preset-meta { color: var(--text-muted); font-size: var(--text-sm); }
	`;
	document.head.appendChild(style);
}
