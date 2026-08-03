<template>
	<Dialog v-model:open="show" size="3xl">
		<template #body-header>
			<div class="flex items-center justify-between mb-5">
				<div class="text-4xl-semibold leading-6 text-ink-gray-9">
					{{ __('Edit Profile') }}
				</div>
				<div class="flex items-center gap-x-2">
					<Badge v-if="isDirty" theme="orange">
						{{ __('Not Saved') }}
					</Badge>
					<div class="pb-5 float-end">
						<Button variant="solid" @click="saveProfile()">
							{{ __('Save') }}
						</Button>
					</div>
				</div>
			</div>
		</template>
		<template #default>
			<div class="text-base">
				<div class="grid grid-cols-1 gap-10">
					<div class="space-y-4">
						<div class="space-y-4">
							<Uploader
								v-model="profile.image"
								:label="__('Profile Image')"
								shape="circle"
							/>

							<FormControl
								v-model="profile.first_name"
								:label="__('First Name')"
								:required="true"
							/>
							<FormControl
								v-model="profile.last_name"
								:label="__('Last Name')"
								:required="true"
							/>
							<FormControl
								v-model="profile.codice_fiscale"
								:label="__('Codice Fiscale')"
								placeholder="RSSMRA85M01H501Z"
								type="text"
								maxlength="16"
							/>
							<!-- <FormControl v-model="profile.headline" :label="__('Headline')" />

							<FormControl
								v-model="profile.linkedin"
								:label="__('LinkedIn ID')"
							/>
							<FormControl v-model="profile.github" :label="__('GitHub ID')" />
							<FormControl
								v-model="profile.twitter"
								:label="__('Twitter ID')"
							/> -->
						</div>
					</div>
					<!-- <div class="space-y-4">
						<FormControl
							v-model="profile.open_to"
							type="select"
							:options="[' ', 'Work', 'Hiring']"
							:label="__('Open to')"
							:placeholder="__('Looking for new work or hiring talent?')"
						/>
						<Link
							:label="__('Language')"
							v-model="profile.language"
							doctype="Language"
						/>
						<div>
							<div class="mb-1.5 text-p-sm-medium text-ink-gray-7">
								{{ __('Bio') }}
							</div>
							<TextEditor
								:fixedMenu="true"
								@change="(val) => (profile.bio = val)"
								:content="profile.bio"
								:rows="15"
								editorClass="prose-sm py-2 px-2 min-h-[280px] border-outline-gray-2 hover:border-outline-gray-3 rounded-b-md bg-surface-gray-3"
							/>
						</div>
					</div> -->
				</div>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import {
	Badge,
	Button,
	call,
	createResource,
	Dialog,
	FormControl,
	TextEditor,
	toast,
} from 'frappe-ui'
import { ref, reactive, watch } from 'vue'
import { sanitizeHTML } from '@/utils'
import Link from '@/components/Controls/Link.vue'

// Italian codice fiscale: 6 letters + 2 digits + letter + 2 digits + letter +
// 3 digits + letter (16 chars). Mirrors the backend pattern in safelog.py.
const CODICE_FISCALE_RE = /^[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]$/

const show = defineModel()
const reloadProfile = defineModel('reloadProfile')
const hasLanguageChanged = ref(false)
const isDirty = ref(false)
// Codice fiscale is PII and not part of get_profile_details; it is fetched
// separately, scoped to the user's own record. Keep the loaded value as the
// baseline for the dirty-state comparison.
const originalCodiceFiscale = ref('')

const props = defineProps({
	profile: {
		type: Object,
		required: true,
	},
})

const profile = reactive({
	first_name: '',
	last_name: '',
	codice_fiscale: '',
	headline: '',
	bio: '',
	image: '',
	open_to: '',
	linkedin: '',
	github: '',
	twitter: '',
})

const updateProfile = createResource({
	url: 'frappe.client.set_value',
	makeParams(values) {
		return {
			doctype: 'User',
			name: props.profile.data.name,
			fieldname: {
				user_image: profile.image || null,
				...profile,
				codice_fiscale: profile.codice_fiscale || null,
			},
		}
	},
	onSuccess(data) {
		props.profile.data = data
	},
})

const validateMandatoryFields = () => {
	let missingFields = []
	if (!profile.first_name) missingFields.push(__('First Name'))
	if (!profile.last_name) missingFields.push(__('Last Name'))
	if (missingFields.length) {
		toast.error(
			__('Please fill the mandatory fields: {0}').format(
				missingFields.join(', '),
			),
		)
		console.error('Missing mandatory fields:', missingFields)
	}
	return missingFields.length
}

const saveProfile = () => {
	let missingMandatoryFields = validateMandatoryFields()
	if (missingMandatoryFields) return
	profile.bio = sanitizeHTML(profile.bio || '')
	profile.codice_fiscale = (profile.codice_fiscale || '').trim().toUpperCase()
	if (profile.codice_fiscale && !CODICE_FISCALE_RE.test(profile.codice_fiscale)) {
		toast.error(__('Please enter a valid Codice Fiscale.'))
		return
	}
	updateProfile.submit(
		{},
		{
			onSuccess() {
				show.value = false
				reloadProfile.value.reload()
				if (hasLanguageChanged.value) {
					hasLanguageChanged.value = false
					window.location.reload()
				}
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
			},
		},
	)
}

watch(
	() => profile,
	(newVal) => {
		if (!props.profile.data) return
		let keys = Object.keys(newVal)
		keys.splice(keys.indexOf('image'), 1)
		// codice_fiscale is not part of props.profile.data; compare it separately.
		keys.splice(keys.indexOf('codice_fiscale'), 1)
		for (let key of keys) {
			if (newVal[key] !== props.profile.data[key]) {
				isDirty.value = true
				return
			}
		}
		if (profile.image !== props.profile.data.user_image) {
			isDirty.value = true
			return
		}
		if (profile.codice_fiscale !== originalCodiceFiscale.value) {
			isDirty.value = true
			return
		}
		isDirty.value = false
	},
	{ deep: true },
)

watch(
	() => props.profile.data,
	(newVal) => {
		if (newVal) {
			profile.first_name = newVal.first_name
			profile.last_name = newVal.last_name
			profile.headline = newVal.headline
			profile.language = newVal.language
			profile.bio = newVal.bio
			profile.open_to = newVal.open_to
			profile.linkedin = newVal.linkedin
			profile.github = newVal.github
			profile.twitter = newVal.twitter
			profile.image = newVal.user_image
			isDirty.value = false
			// Fetch the codice fiscale separately (not exposed by
			// get_profile_details); scoped to the user's own record.
			call('frappe.client.get_value', {
				doctype: 'User',
				filters: newVal.name,
				fieldname: 'codice_fiscale',
			}).then((res) => {
				profile.codice_fiscale = res?.codice_fiscale || ''
				originalCodiceFiscale.value = profile.codice_fiscale
			})
		}
	},
)

watch(
	() => profile.language,
	() => {
		if (profile.language !== props.profile.data.language) {
			hasLanguageChanged.value = true
		}
	},
)
</script>
