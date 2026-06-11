<template>
	<div class="">
		<CollapsibleSection :label="__('Visibility')">
			<div class="flex flex-col gap-y-4">
				<Switch
					size="sm"
					v-model="doc.upcoming"
					:label="__('Upcoming')"
					:description="__('Not yet open for enrollment.')"
					@change="markDirty()"
				/>
				<Switch
					size="sm"
					v-model="doc.featured"
					:label="__('Featured')"
					:description="__('Highlight on the homepage.')"
					@change="markDirty()"
				/>
				<Switch
					size="sm"
					v-model="selfEnrollment"
					:label="__('Self enrollment')"
					:description="__('Let users enroll themselves.')"
				/>
			</div>
		</CollapsibleSection>

		<CollapsibleSection :label="__('Pricing and certification')">
			<div class="flex flex-col gap-y-4">
				<Switch
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
						@update:modelValue="markDirty()"
					/>
					<FormControl
						v-model="doc.course_price"
						:label="__('Course price')"
						variant="outline"
						@input="markDirty()"
					/>
					<div class="border-t -mx-5" />
					<Switch
						size="sm"
						v-model="doc.enable_certification"
						:label="__('Completion certificate')"
						:description="
							__('Issue a free certificate when learners complete the course.')
						"
						:disabled="!!doc?.trueskills_certificate_enabled"
						@change="markDirty()"
					/>
				</template>

				<template v-else>
					<div class="border-t -mx-5" />
					<Switch
						size="sm"
						v-model="doc.enable_certification"
						:label="__('Completion certificate')"
						:description="
							__('Issue a free certificate when learners complete the course.')
						"
						:disabled="!!doc?.trueskills_certificate_enabled"
						@change="markDirty()"
					/>
					<Switch
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
							@update:modelValue="markDirty()"
						/>
						<FormControl
							v-model="doc.course_price"
							:label="__('Certificate price')"
							variant="outline"
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
							'Usa TrueSkill come emettitore del certificato per questo corso. Sostituisce il certificato interno LMS.'
						)
					"
					@change="markDirty()"
				/>
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
		@created="onTrueskillTemplateCreated"
	/>
</template>

<script setup lang="ts">
import { FormControl, createResource, toast } from 'frappe-ui'
import Switch from '@/components/Controls/Switch.vue'
import { computed, inject, ref, watch } from 'vue'
import CollapsibleSection from '@/components/CollapsibleSection.vue'
import Link from '@/components/Controls/Link.vue'
import NewMemberModal from '@/components/Modals/NewMemberModal.vue'
import TrueSkillsTemplateModal from '@/oslms/components/trueskills/TrueSkillsTemplateModal.vue'
import type { CourseFormContext, Resource } from '@/types/api'

const { resource, markDirty } = inject<CourseFormContext>('courseForm')!
const dayjs = inject('$dayjs') as typeof import('dayjs')

const doc = computed(() => resource.doc)
const evaluatorLinkRef = ref<{ reload: () => void } | null>(null)
const showMemberModal = ref<boolean>(false)

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
	resource.doc.paid_course = val ? 1 : 0
	// A paid course is already monetized — the paid-certificate flow only
	// applies to free courses, so clear it when switching to paid.
	if (val) resource.doc.paid_certificate = 0
	markDirty()
}

function setPaidCertificate(val: boolean) {
	if (!resource.doc) return
	resource.doc.paid_certificate = val ? 1 : 0
	markDirty()
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
