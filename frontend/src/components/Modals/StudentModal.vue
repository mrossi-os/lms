<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Enroll Students'),
			size: 'lg',
			actions: [
				{
					label: __('Submit'),
					variant: 'solid',
					loading: enrolling,
					onClick: (close) => addStudents(close),
				},
			],
		}"
	>
		<template #body-content>
			<div class="flex flex-col gap-4">
				<MultiLink
					doctype="User"
					v-model="selectedStudents"
					:label="__('Students')"
					:placeholder="__('Select students')"
					:required="true"
					variant="outline"
					:onCreate="
						(close) => {
							close()
							openSettings('Members')
							show = false
						}
					"
				/>
			</div>
		</template>
	</Dialog>
</template>
<script setup>
import { Dialog, toast } from 'frappe-ui'
import { ref, inject } from 'vue'
import { useOnboarding } from 'frappe-ui/frappe'
import { openSettings } from '@/utils'
import MultiLink from '@/components/Controls/MultiLink.vue'

const selectedStudents = ref([])
const enrolling = ref(false)
const user = inject('$user')
const { updateOnboardingStep } = useOnboarding('learning')
const show = defineModel()

const props = defineProps({
	batch: {
		type: Object,
		default: null,
	},
	students: {
		type: Object,
		default: null,
	},
})

// Enroll a single member, resolving to whether it succeeded so the bulk loop
// can keep going and report failures (e.g. an already-enrolled student) in one
// aggregated message instead of a toast per request.
function enrollOne(member) {
	return new Promise((resolve) => {
		props.students.insert.submit(
			{
				member,
				batch: props.batch.data?.name,
			},
			{
				onSuccess: () => resolve(true),
				onError: () => resolve(false),
			},
		)
	})
}

const addStudents = async (close) => {
	if (!selectedStudents.value.length) {
		toast.error(__('Please select at least one student'))
		return
	}

	enrolling.value = true
	const failed = []
	for (const member of selectedStudents.value) {
		const ok = await enrollOne(member)
		if (!ok) failed.push(member)
	}
	enrolling.value = false

	const enrolled = selectedStudents.value.length - failed.length
	if (enrolled > 0) {
		if (user.data?.is_system_manager) updateOnboardingStep('add_batch_student')
		props.batch.reload()
	}

	if (failed.length) {
		toast.error(__('{0} student(s) could not be enrolled').format(failed.length))
		// Keep the failed ones selected so the user can review and retry.
		selectedStudents.value = failed
		return
	}

	toast.success(__('Students enrolled successfully'))
	selectedStudents.value = []
	close()
}
</script>
