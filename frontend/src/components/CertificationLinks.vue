<template>
	<router-link
		v-if="certification.data && certification.data.certificate"
		:to="{
			name: 'ProfileCertificates',
			params: { username: user.data?.username },
		}"
	>
		<Button class="w-full">
			<template #prefix>
				<span class="lucide-graduation-cap size-4" />
			</template>
			{{ __('View Certificate') }}
		</Button>
	</router-link>
	<div
		v-else-if="
			certification.data &&
			certification.data.membership &&
			certification.data.paid_certificate &&
			user.data?.is_student
		"
	>
		<router-link
			v-if="!certification.data.membership.purchased_certificate"
			:to="{
				name: 'Billing',
				params: {
					type: 'certificate',
					name: courseName,
				},
			}"
		>
			<Button class="w-full">
				<template #prefix>
					<span class="lucide-graduation-cap size-4" />
				</template>
				{{ __('Get Certified') }}
			</Button>
		</router-link>
		<router-link
			v-else-if="!certification.data.membership.certificate"
			:to="{
				name: 'CourseCertification',
				params: {
					courseName: courseName,
				},
			}"
		>
			<Button class="w-full">
				<template #prefix>
					<span class="lucide-graduation-cap size-4" />
				</template>
				{{ __('Get Certified') }}
			</Button>
		</router-link>
	</div>
</template>
<script setup lang="ts">
import { Button, createResource } from 'frappe-ui'
import { inject } from 'vue'
import type { CertificationInfo, Resource, SessionUser } from '@/types/api'

const user = inject<SessionUser>('$user')!

const props = defineProps<{
	courseName: string
}>()

const certification = createResource({
	url: 'lms.lms.api.get_certification_details',
	makeParams() {
		return {
			course: props.courseName,
		}
	},
	auto: user.data ? true : false,
}) as Resource<CertificationInfo | null>
</script>
