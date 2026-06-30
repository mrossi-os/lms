<template>
	<div class="">
		<CollapsibleSection :label="__('Visibility')">
			<div class="flex flex-col gap-y-4">
				<BooleanSwitch
					size="sm"
					v-model="doc.upcoming"
					:label="__('Upcoming')"
					:description="__('Not yet open for enrollment.')"
					@update:modelValue="markDirty()"
				/>
				<BooleanSwitch
					size="sm"
					v-model="doc.featured"
					:label="__('Featured')"
					:description="__('Highlight on the homepage.')"
					@update:modelValue="markDirty()"
				/>
				<BooleanSwitch
					size="sm"
					v-model="selfEnrollment"
					:label="__('Self enrollment')"
					:description="__('Let users enroll themselves.')"
				/>
			</div>
		</CollapsibleSection>

		<CollapsibleSection :label="__('Pricing and certification')">
			<div class="flex flex-col gap-y-4">
				<BooleanSwitch
					size="sm"
					:modelValue="Boolean(doc?.paid_course)"
					:label="__('Paid course')"
					:description="__('Charge learners to enroll in this course.')"
					@update:modelValue="setPaidCourse"
				/>

				<template v-if="doc?.paid_course">
					<Link
						v-model="doc.currency"
						doctype="Currency"
						:label="__('Currency')"
						:filters="{ enabled: 1 }"
						:placeholder="__('Select currency')"
						variant="outline"
						:required="true"
						@update:modelValue="markDirty()"
					/>
					<FormControl
						v-model="doc.course_price"
						type="number"
						min="0"
						:label="__('Course price')"
						variant="outline"
						:required="true"
						@input="markDirty()"
					/>
					<div class="border-t -mx-5" />
					<BooleanSwitch
						size="sm"
						v-model="doc.enable_certification"
						:label="__('Completion certificate')"
						:description="
							__('Issue a free certificate when learners complete the course.')
						"
						@update:modelValue="markDirty()"
					/>
				</template>

				<template v-else>
					<div class="border-t -mx-5" />
					<BooleanSwitch
						size="sm"
						v-model="doc.enable_certification"
						:label="__('Completion certificate')"
						:description="
							__('Issue a free certificate when learners complete the course.')
						"
						@update:modelValue="markDirty()"
					/>
					<BooleanSwitch
						size="sm"
						:modelValue="doc.paid_certificate"
						:label="__('Paid certificate')"
						:description="
							__(
								'Sell an evaluator-graded certificate alongside this free course.'
							)
						"
						@update:modelValue="setPaidCertificate"
					/>
					<template v-if="doc.paid_certificate">
						<Link
							v-model="doc.currency"
							doctype="Currency"
							:label="__('Currency')"
							:filters="{ enabled: 1 }"
							:placeholder="__('Select currency')"
							variant="outline"
							:required="true"
							@update:modelValue="markDirty()"
						/>
						<FormControl
							v-model="doc.course_price"
							type="number"
							min="0"
							:label="__('Certificate price')"
							variant="outline"
							:required="true"
							@input="markDirty()"
						/>
						<Link
							ref="evaluatorLinkRef"
							v-model="doc.evaluator"
							doctype="Course Evaluator"
							:label="__('Evaluator')"
							:placeholder="__('Select evaluator')"
							variant="outline"
							:onCreate="openEvaluatorModal"
							@update:modelValue="markDirty()"
						/>
						<FormControl
							v-model="doc.timezone"
							type="combobox"
							:label="__('Timezone')"
							:options="timezoneOptions"
							:placeholder="__('Select timezone')"
							variant="outline"
							@update:modelValue="markDirty()"
						/>
					</template>
				</template>

				<div class="border-t -mx-5" />
				<Switch
					size="sm"
					v-model="doc.trueskills_certificate_enabled"
					:label="__('Emetti certificato TrueSkill')"
					:description="
						__(
							'Usa TrueSkill come emettitore del certificato per questo corso. Richiede il certificato di completamento attivo.'
						)
					"
					:disabled="!doc?.enable_certification"
					@change="markDirty()"
				/>
				<div
					v-if="!doc?.enable_certification"
					class="text-sm text-ink-gray-5"
				>
					{{
						__(
							'Attiva il "Certificato di completamento" per poter abilitare l\'emissione TrueSkill.'
						)
					}}
				</div>
				<template v-if="doc?.trueskills_certificate_enabled">
					<div class="text-sm text-ink-gray-7 bg-surface-gray-2 rounded-md p-3">
						{{
							__(
								'Quando attivo, il certificato interno LMS non verrà emesso per questo corso: l\'emissione passa a TrueSkill.'
							)
						}}
					</div>
					<FormControl
						v-model="trueskillsTemplateModel"
						type="select"
						:label="__('Template certificato TrueSkill')"
						:options="trueskillTemplateOptions"
						:disabled="trueskillTemplatesResource.loading"
					/>
					<div
						v-if="trueskillTemplatesError"
						class="text-sm text-ink-red-5 bg-surface-red-1 rounded-md p-2"
					>
						{{ trueskillTemplatesError }}
					</div>
					<button
						type="button"
						class="text-sm text-ink-gray-7 underline hover:text-ink-gray-9 self-start"
						@click="openTrueskillTemplateCreator"
					>
						{{ __('+ Crea nuovo template') }}
					</button>
				</template>

				<div
					v-if="doc?.enable_certification || doc?.paid_certificate"
					class="flex flex-wrap items-center gap-1 text-p-sm text-ink-gray-6"
				>
					<span>
						{{
							__(
								'Certificates render from a Print Format. Build or customize templates from the desk.'
							)
						}}
					</span>
					<button
						type="button"
						class="font-medium text-ink-gray-8 underline"
						@click="openPrintFormats"
					>
						{{ __('Manage templates') }}
					</button>
				</div>
			</div>
		</CollapsibleSection>
	</div>

	<NewMemberModal
		v-model="showMemberModal"
		:defaultRoles="['batch_evaluator']"
		@created="onEvaluatorCreated"
	/>
	<TrueSkillsTemplateModal
		v-model="showTrueskillTemplateModal"
		:course="doc?.name"
		@created="onTrueskillTemplateCreated"
	/>

	<Dialog
		v-model:open="showPaymentsAppModal"
		:title="__('Payments app required')"
		:actions="[
			{
				label: __('Get the Payments app'),
				variant: 'solid',
				onClick: ({ close }: any) => {
					openPaymentsApp()
					close()
				},
			},
		]"
	>
		<template #default>
			<p class="text-p-base text-ink-gray-7">
				{{
					__(
						'Selling a paid course or certificate needs the Payments app. Install it from the Frappe Marketplace, then turn on pricing here.'
					)
				}}
			</p>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { FormControl, createResource, toast } from 'frappe-ui'
import Switch from '@/components/Controls/Switch.vue'
import { computed, inject, ref, watch } from 'vue'
import { Dialog, FormControl, createResource } from 'frappe-ui'
import BooleanSwitch from '@/components/Controls/BooleanSwitch.vue'
import { computed, inject, ref } from 'vue'
import CollapsibleSection from '@/components/CollapsibleSection.vue'
import Link from '@/components/Controls/Link.vue'
import NewMemberModal from '@/components/Modals/NewMemberModal.vue'
import TrueSkillsTemplateModal from '@/oslms/components/trueskills/TrueSkillsTemplateModal.vue'
import { useSettings } from '@/stores/settings'
import type { CourseFormContext, Resource } from '@/types/api'

const { resource, markDirty } = inject<CourseFormContext>('courseForm')!
const dayjs = inject('$dayjs') as typeof import('dayjs')

const settingsStore = useSettings()
// Only block when we positively know the app is missing; if settings haven't
// loaded yet, let it through (the backend validation is the hard guard).
const paymentsAppMissing = computed<boolean>(
	() =>
		!!settingsStore.settings.data &&
		!settingsStore.settings.data.is_payments_app_installed
)

const doc = computed(() => resource.doc)
const evaluatorLinkRef = ref<{ reload: () => void } | null>(null)
const showMemberModal = ref<boolean>(false)
const showPaymentsAppModal = ref<boolean>(false)

const publishedOnLabel = computed<string>(() =>
	doc.value?.published_on
		? dayjs(doc.value.published_on).format('DD MMM YYYY')
		: ''
)

const selfEnrollment = computed<boolean>({
	get: () => !resource.doc?.disable_self_learning,
	set: (val: boolean) => {
		if (!resource.doc) return
		resource.doc.disable_self_learning = val ? 0 : 1
		markDirty()
	},
})

function setPaidCourse(val: boolean) {
	if (!resource.doc) return
	if (val && paymentsAppMissing.value) {
		showPaymentsAppModal.value = true
		return
	}
	resource.doc.paid_course = val ? 1 : 0
	// A paid course is already monetized — the paid-certificate flow only
	// applies to free courses, so clear it when switching to paid.
	if (val) resource.doc.paid_certificate = 0
	markDirty()
}

function setPaidCertificate(val: boolean) {
	if (!resource.doc) return
	if (val && paymentsAppMissing.value) {
		showPaymentsAppModal.value = true
		return
	}
	resource.doc.paid_certificate = val ? 1 : 0
	markDirty()
}

function openPaymentsApp() {
	window.open('https://frappecloud.com/marketplace/apps/payments', '_blank')
}

const timezoneResource = createResource({
	url: 'frappe.geo.country_info.get_country_timezone_info',
	auto: true,
	transform: (data: { all_timezones: string[] }) => data.all_timezones,
}) as Resource<string[] | null>

const timezoneOptions = computed<{ label: string; value: string }[]>(() =>
	(timezoneResource.data || []).map((tz) => ({ label: tz, value: tz }))
)

function openEvaluatorModal() {
	showMemberModal.value = true
}

function openPrintFormats() {
	window.open('/app/print-format?doc_type=LMS Certificate', '_blank')
}

function onEvaluatorCreated(created: { name: string }) {
	if (!resource.doc) return
	resource.doc.evaluator = created.name
	evaluatorLinkRef.value?.reload()
	markDirty()
}

// --- TrueSkills certificate emission -----------------------------------------
interface TrueSkillsTemplate {
	id?: string | number
	value?: string | number
	name?: string
	title?: string
	label?: string
}

interface TrueSkillsTemplatesData {
	ok: boolean
	templates?: TrueSkillsTemplate[]
	error?: string
}

const trueskillTemplatesResource = createResource({
	url: 'os_lms.os_lms.trueskills.api.list_templates',
	auto: false,
	onError(err: { messages?: string[]; message?: string }) {
		toast.error(
			err.messages?.[0] || err.message || __('Failed to load templates')
		)
	},
}) as Resource<TrueSkillsTemplatesData | null>

const trueskillTemplateOptions = computed<{ label: string; value: string }[]>(
	() => {
		const placeholder = {
			label: trueskillTemplatesResource.loading
				? __('Caricamento template...')
				: __('Seleziona un template...'),
			value: '',
		}
		const data = trueskillTemplatesResource.data
		if (!data?.ok) return [placeholder]
		const templates = Array.isArray(data.templates) ? data.templates : []
		return [
			placeholder,
			...templates.map((t) => {
				const rawValue = t.id ?? t.value ?? t.name ?? ''
				return {
					label: t.name || t.title || t.label || String(rawValue),
					// Coerce to string so the native <select> can match against
					// whatever shape (number/string) the backend stores.
					value: String(rawValue),
				}
			}),
		]
	}
)

const trueskillTemplatesError = computed<string | null>(() => {
	const data = trueskillTemplatesResource.data
	if (!data || data.ok) return null
	return data.error || __('Impossibile caricare i template TrueSkill.')
})

// Proxy that keeps the select value as a string while letting the doc field
// hold whatever type the backend returns (Frappe may coerce numeric strings
// to int on read).
const trueskillsTemplateModel = computed<string>({
	get: () => {
		const v = resource.doc?.trueskills_template_id
		return v === null || v === undefined ? '' : String(v)
	},
	set: (val: string) => {
		if (!resource.doc) return
		resource.doc.trueskills_template_id = val
		markDirty()
	},
})

watch(
	() => resource.doc?.trueskills_certificate_enabled,
	(enabled) => {
		if (
			enabled &&
			!trueskillTemplatesResource.loading &&
			!trueskillTemplatesResource.data
		) {
			trueskillTemplatesResource.fetch()
		}
	},
	{ immediate: true }
)

// TrueSkill emission triggers on LMS Certificate creation, which only happens
// when completion certification is on. Keep them consistent: turning the
// completion certificate off also turns TrueSkill emission off.
watch(
	() => resource.doc?.enable_certification,
	(enabled) => {
		if (!enabled && resource.doc?.trueskills_certificate_enabled) {
			resource.doc.trueskills_certificate_enabled = 0
			markDirty()
		}
	}
)

const showTrueskillTemplateModal = ref<boolean>(false)

function openTrueskillTemplateCreator() {
	showTrueskillTemplateModal.value = true
}

function onTrueskillTemplateCreated(template: { id?: string; uid?: string }) {
	const newId = template?.id ?? template?.uid
	if (newId != null && resource.doc) {
		resource.doc.trueskills_template_id = newId
		markDirty()
	}
	trueskillTemplatesResource.fetch()
}
</script>
