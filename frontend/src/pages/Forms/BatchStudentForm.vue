<template>
	<FormShell :title="__('Enroll Students')" size="lg" @close="close">
		<template #default>
			<div v-if="refusal" class="p-4 text-base text-ink-gray-6">
				{{ refusal }}
			</div>
			<div
				v-else
				data-testid="batch-student-fields"
				class="flex flex-col gap-4"
			>
				<!-- OSLMS-CUSTOM: bulk enrollment, several students picked at once; no Payment field (payments not used) -->
				<MultiLink
					doctype="User"
					v-model="selectedStudents"
					:label="__('Students')"
					:placeholder="__('Select students')"
					:required="true"
					variant="outline"
					:onCreate="openMemberSettings"
				/>
			</div>
		</template>
		<template #actions>
			<HeaderButton
				v-if="!refusal"
				data-testid="batch-student-save"
				:label="__('Save')"
				variant="solid"
				:loading="enrolling"
				@click="submit"
			/>
		</template>
	</FormShell>
</template>

<script setup>
import { computed, inject, ref } from 'vue'
import {
	createResource,
	getCachedListResource,
	getCachedResource,
	toast,
} from 'frappe-ui'
import { useOnboarding } from 'frappe-ui/frappe'
import { useRoute } from 'vue-router'
import { openSettings } from '@/utils'
import MultiLink from '@/components/Controls/MultiLink.vue'
import FormShell from '@/components/FormShell.vue'
import HeaderButton from '@/components/HeaderButton.vue'
import { batchRouteLocation } from '@/composables/useBatchForms'
import { useFormRoute } from '@/composables/useFormRoute'
import { submitResource } from '@/utils/resource'

const props = defineProps({
	batchName: {
		type: String,
		required: true,
	},
})

const user = inject('$user')
const route = useRoute()
const readOnlyMode = window.read_only_mode
const { updateOnboardingStep } = useOnboarding('learning')

const selectedStudents = ref([])
const enrolling = ref(false)

const { close, saveAndReplace } = useFormRoute(
	batchRouteLocation('BatchDetail', props.batchName, route.hash)
)

// Copied from BatchDetail.vue's isAdmin() gate on the Enroll button. A URL does
// not go through a button. Read-only was not on that button, but every other
// converted form checks it and a read-only site cannot insert.
//
// UX gate, not an authorization boundary — validate_owner() on LMS Batch
// Enrollment is, and it demands the same two roles.
// OSLMS-CUSTOM: Docente manages batches like a moderator, so it may enroll too (isFullAdmin in AdminBatchDashboard.vue)
const refusal = computed(() => {
	if (readOnlyMode) return __('This site is in read-only mode.')
	if (
		!user.data?.is_moderator &&
		!user.data?.is_evaluator &&
		!user.data?.is_docente
	) {
		return __('You do not have permission to enroll students in this batch.')
	}
	return ''
})

// This form's own insert. The modal reached the dashboard's list resource
// through `:students` and inserted into it; a routed page has no parent to
// receive that from, and a deep link has no dashboard tab mounted at all.
// A plain createResource rather than a list resource, so a save does not also
// fire frappe-ui's unfiltered follow-up list fetch.
const enrollment = createResource({
	url: 'frappe.client.insert',
	makeParams(values) {
		return {
			doc: {
				doctype: 'LMS Batch Enrollment',
				member: values.member,
				batch: props.batchName,
			},
		}
	},
})

// The Overview overlay's Seats Left comes from get_batch_details, and enrolling
// is what moves it. That resource deliberately carries no cache key
// (useBatchForms.ts explains why one must never be added back), so it cannot be
// reached by key the way the two below are — BatchDetail hosts this form in its
// own <router-view> and hands the reload down instead.
const reloadBatchDetails = inject('reloadBatchDetails', null)

// Both live on the dashboard tab behind this form. Null on a deep link, where
// that tab was never mounted — correct, since each fetches on mount.
const reloadDashboard = () => {
	getCachedListResource(['batchStudents', props.batchName])?.reload()
	getCachedResource(['batch_student_count', props.batchName])?.reload()
	reloadBatchDetails?.()
}

// MultiLink hands onCreate its popover close callback; close the dropdown
// before leaving.
//
// Leaving the form to open Settings is the modal's behaviour kept intact: the
// settings drawer would otherwise sit under a full-screen form on a phone.
const openMemberSettings = (closePopover) => {
	closePopover?.()
	if (openSettings('Members')) close()
}

// OSLMS-CUSTOM: bulk enrollment, one insert per selected student with an aggregated failure message
// Enroll a single member, resolving to whether it succeeded so the bulk loop
// can keep going and report failures (e.g. an already-enrolled student) in one
// aggregated message instead of a toast per request.
const enrollOne = async (member) => {
	let ok = false
	await submitResource(
		enrollment,
		{ member },
		{
			onSuccess() {
				ok = true
			},
			onError() {},
		}
	)
	return ok
}

const submit = async () => {
	if (refusal.value || enrolling.value) return
	if (!selectedStudents.value.length) {
		toast.error(__('Please select at least one student'))
		return
	}

	enrolling.value = true
	const failed = []
	try {
		for (const member of selectedStudents.value) {
			if (!(await enrollOne(member))) failed.push(member)
		}
	} finally {
		enrolling.value = false
	}

	const enrolled = selectedStudents.value.length - failed.length
	if (enrolled > 0) {
		if (user.data?.is_system_manager) {
			updateOnboardingStep('add_batch_student')
		}
		reloadDashboard()
	}

	if (failed.length) {
		toast.error(__('{0} student(s) could not be enrolled').format(failed.length))
		// Keep the failed ones selected so the user can review and retry.
		selectedStudents.value = failed
		return
	}

	toast.success(__('Students enrolled successfully'))
	saveAndReplace(batchRouteLocation('BatchDetail', props.batchName, route.hash))
}
</script>
