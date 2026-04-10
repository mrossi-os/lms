<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Edit Member'),
			size: 'lg',
			actions: [
				{
					label: __('Save'),
					variant: 'solid',
					loading: submitting,
					onClick: ({ close }: any) => saveMember(close),
				},
			],
		}"
	>
		<template #body-content>
			<div v-if="loading" class="flex justify-center py-8">
				<LoadingIndicator class="size-5" />
			</div>
			<div v-else class="space-y-4">
				<div class="flex items-end gap-2">
					<FormControl
						:modelValue="memberData.email"
						:label="__('Email')"
						type="email"
						:disabled="true"
						class="flex-1"
					/>
					<Button
						variant="subtle"
						@click="goToProfile"
					>
						<template #prefix>
							<UserRound class="size-4 stroke-1.5" />
						</template>
						{{ __('Profile') }}
					</Button>
				</div>
				<div class="flex items-center gap-3">
					<FormControl
						v-model="memberData.first_name"
						:label="__('First Name')"
						placeholder="Jane"
						type="text"
						class="w-full"
					/>
					<FormControl
						v-model="memberData.last_name"
						:label="__('Last Name')"
						placeholder="Doe"
						type="text"
						class="w-full"
					/>
				</div>
				<FormControl
					v-model="memberData.codice_fiscale"
					:label="__('Codice Fiscale')"
					placeholder="RSSMRA85M01H501Z"
					type="text"
					maxlength="16"
				/>
				<div class="flex flex-col gap-2">
					<div class="text-sm text-ink-gray-5">
						{{ __('Roles') }}
					</div>
					<div class="grid md:grid-cols-2 gap-x-6 gap-y-3">
						<Switch
							size="sm"
							:label="__('Student')"
							v-model="roles.lms_student"
						/>
						<Switch
							size="sm"
							:label="__('Course Creator')"
							v-model="roles.course_creator"
						/>
						<Switch
							size="sm"
							:label="__('Evaluator')"
							v-model="roles.batch_evaluator"
						/>
						<Switch
							size="sm"
							:label="__('Moderator')"
							v-model="roles.moderator"
						/>
					</div>
				</div>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { Button, call, Dialog, FormControl, LoadingIndicator, toast } from 'frappe-ui'
import Switch from '@/oslms/components/Form/Switch.vue'
import { UserRound } from 'lucide-vue-next'
import { reactive, ref, watch } from 'vue'
import { cleanError } from '@/utils'

const show = defineModel<boolean>({ default: false })
const submitting = ref(false)
const loading = ref(false)

const props = defineProps<{
	member: { name: string; full_name: string; username: string } | null
}>()

const emit = defineEmits<{
	updated: []
	'navigate-profile': []
}>()

const goToProfile = () => {
	if (!props.member) return
	show.value = false
	emit('navigate-profile')
}

const ROLE_MAP: Record<string, string> = {
	moderator: 'Moderator',
	course_creator: 'Course Creator',
	batch_evaluator: 'Batch Evaluator',
	lms_student: 'LMS Student',
}

const memberData = reactive({
	email: '',
	first_name: '',
	last_name: '',
	codice_fiscale: '',
})

const roles = reactive({
	moderator: false,
	course_creator: false,
	batch_evaluator: false,
	lms_student: false,
})

const originalRoles = reactive({
	moderator: false,
	course_creator: false,
	batch_evaluator: false,
	lms_student: false,
})

const loadMember = async (email: string) => {
	loading.value = true
	try {
		const user = await call('frappe.client.get', {
			doctype: 'User',
			name: email,
		})
		memberData.email = user.name
		memberData.first_name = user.first_name || ''
		memberData.last_name = user.last_name || ''
		memberData.codice_fiscale = user.codice_fiscale || ''

		const userRoles = await call('lms.lms.utils.get_roles', {
			name: email,
		})
		roles.moderator = !!userRoles.moderator
		roles.course_creator = !!userRoles.course_creator
		roles.batch_evaluator = !!userRoles.batch_evaluator
		roles.lms_student = !!userRoles.lms_student

		originalRoles.moderator = roles.moderator
		originalRoles.course_creator = roles.course_creator
		originalRoles.batch_evaluator = roles.batch_evaluator
		originalRoles.lms_student = roles.lms_student
	} catch (err: any) {
		toast.error(cleanError(err.messages?.[0]) || __('Unable to load member'))
	} finally {
		loading.value = false
	}
}

watch(show, (isOpen) => {
	if (isOpen && props.member) {
		loadMember(props.member.name)
	}
})

const syncRoles = async (userEmail: string) => {
	for (const [key, role] of Object.entries(ROLE_MAP)) {
		const current = roles[key as keyof typeof roles]
		const original = originalRoles[key as keyof typeof originalRoles]
		if (current !== original) {
			await call('lms.lms.api.save_role', {
				user: userEmail,
				role,
				value: current ? 1 : 0,
			})
		}
	}
}

const saveMember = async (close?: () => void) => {
	submitting.value = true
	try {
		await call('frappe.client.set_value', {
			doctype: 'User',
			name: memberData.email,
			fieldname: {
				first_name: memberData.first_name.trim(),
				last_name: memberData.last_name.trim(),
				codice_fiscale: memberData.codice_fiscale.trim().toUpperCase(),
			},
		})

		await syncRoles(memberData.email)

		toast.success(__('Member updated successfully'))
		emit('updated')
		close?.()
	} catch (err: any) {
		toast.error(cleanError(err.messages?.[0]) || __('Unable to update member'))
	} finally {
		submitting.value = false
	}
}
</script>
