<template>
	<Dialog
		v-model="show"
		:options="{
			size: '2xl',
		}"
	>
		<template #body-title>
			<div class="flex items-center justify-between space-x-2 text-base w-full">
				<div class="text-xl font-semibold text-ink-gray-9">
					{{
						programName === 'new' ? __('Create Program') : __('Edit Program')
					}}
				</div>
				<Badge theme="orange" v-if="dirty">
					{{ __('Not Saved') }}
				</Badge>
			</div>
		</template>
		<template #body-content>
			<div class="text-base">
				<div class="grid grid-cols-1 md:grid-cols-2 gap-5 pb-5">
					<FormControl
						v-model="program.title"
						:label="__('Title')"
						type="text"
						:required="true"
						@change="dirty = true"
					/>
					<div class="flex flex-col space-y-3">
						<FormControl
							v-model="program.published"
							:label="__('Published')"
							type="checkbox"
							@change="dirty = true"
						/>
						<FormControl
							v-model="program.enforce_course_order"
							:label="__('Enforce Course Order')"
							type="checkbox"
							@change="dirty = true"
						/>
					</div>
				</div>
				<div class="pb-5 col-span-2">
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('Description') }}
					</div>
					<TextEditor
						:content="program.description"
						@change="
							(val) => {
								program.description = val
								dirty = true
							}
						"
						:editable="true"
						:fixedMenu="true"
						editorClass="prose-sm max-w-none border-b border-x border-outline-gray-modals bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]"
					/>
				</div>
				<div class="pb-5">
					<div class="flex items-center justify-between mt-5 mb-4">
						<div class="text-lg font-semibold text-ink-gray-9">
							{{ __('Courses') }}
						</div>
						<Button @click="openForm('course')">
							<template #prefix>
								<Plus class="h-4 w-4 stroke-1.5" />
							</template>
							<span>
								{{ __('Add') }}
							</span>
						</Button>
					</div>
					<ListView
						v-if="program.program_courses?.length > 0"
						:columns="courseColumns"
						:rows="program.program_courses"
						:options="{
							selectable: true,
							resizeColumn: true,
							showTooltip: false,
							selectionText,
						}"
						rowKey="course"
					>
						<ListHeader
							class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
						>
							<ListHeaderItem :item="item" v-for="item in courseColumns" />
						</ListHeader>
						<ListRows>
							<Draggable
								:list="program.program_courses"
								:item-key="programName === 'new' ? 'course' : 'name'"
								group="items"
								@end="updateOrder"
								class="cursor-move"
							>
								<template #item="{ element: row }">
									<ListRow :row="row" />
								</template>
							</Draggable>
						</ListRows>
						<ListSelectBanner>
							<template #actions="{ unselectAll, selections }">
								<div class="flex gap-2">
									<Button
										variant="ghost"
										@click="
											remove(
												selections,
												unselectAll,
												'program_courses',
												'course',
											)
										"
									>
										<Trash2 class="h-4 w-4 stroke-1.5" />
									</Button>
								</div>
							</template>
						</ListSelectBanner>
					</ListView>
					<div v-else class="text-ink-gray-7">
						{{ __('No courses added yet.') }}
					</div>
				</div>

				<div>
					<div class="flex items-center justify-between mt-5 mb-4">
						<div class="text-lg font-semibold text-ink-gray-9">
							{{ __('Members') }}
						</div>
						<div class="space-x-2">
							<Button
								v-if="programMembers.data?.length > 0"
								@click="showProgressDialog = true"
							>
								<template #prefix>
									<TrendingUp class="size-4 stroke-1.5" />
								</template>
								{{ __('Progress Summary') }}
							</Button>
							<Button @click="openMemberForm('direct')">
								<template #prefix>
									<Plus class="h-4 w-4 stroke-1.5" />
								</template>
								{{ __('Add Member') }}
							</Button>
							<Button @click="openMemberForm('batch')">
								<template #prefix>
									<Plus class="h-4 w-4 stroke-1.5" />
								</template>
								{{ __('Add Group') }}
							</Button>
						</div>
					</div>
					<ListView
						v-if="program.program_members?.length > 0"
						:columns="memberColumns"
						:rows="program.program_members"
						:options="{
							selectable: true,
							resizeColumn: true,
							selectionText,
						}"
						rowKey="member"
					>
						<ListHeader
							class="mb-2 grid items-center space-x-4 rounded bg-surface-gray-2 p-2"
						>
							<ListHeaderItem :item="item" v-for="item in memberColumns" />
						</ListHeader>
						<ListRows>
							<ListRow :row="row" v-for="row in program.program_members" />
						</ListRows>
						<ListSelectBanner>
							<template #actions="{ unselectAll, selections }">
								<div class="flex gap-2">
									<Button
										variant="ghost"
										@click="
											remove(
												selections,
												unselectAll,
												'program_members',
												'member',
											)
										"
									>
										<Trash2 class="h-4 w-4 stroke-1.5" />
									</Button>
								</div>
							</template>
						</ListSelectBanner>
					</ListView>
					<div v-else class="text-ink-gray-7">
						{{ __('No members added yet.') }}
					</div>
				</div>
			</div>
			<Dialog
				v-model="showFormDialog"
				:options="{
					size: 'lg',
					title:
						currentForm == 'course'
							? __('Add Course to Program')
							: __('Enroll Member to Program'),
					actions: [
						{
							label: __('Add'),
							variant: 'solid',
							onClick: ({ close }: { close: () => void }) =>
								currentForm == 'course' ? addCourses(close) : addMember(close),
						},
					],
				}"
			>
				<template #body-content>
					<div @click.stop class="min-h-[300px]">
						<MultiSelect
							v-if="currentForm == 'course'"
							v-model="selectedCourses"
							doctype="LMS Course"
							:label="__('Courses')"
							:autofocus="false"
							ref="multiSelectRef"
							:exclude="
								(program.program_courses || []).map((c: any) => c.course)
							"
						/>
						<Link
							v-if="currentForm == 'member'"
							v-model="member"
							doctype="User"
							:filters="{ ignore_user_type: 1 }"
							:label="__('Program Member')"
							:onCreate="
								(value: string, close: () => void) =>
									openSettings('Members', close)
							"
						/>
					</div>
				</template>
			</Dialog>
			<!-- Dialog aggiungi membro diretto -->
			<Dialog
				v-model="showMemberDialog"
				:options="{
					size: 'lg',
					title: __('Add Members'),
					actions: [
						{
							label: __('Add'),
							variant: 'solid',
							onClick: ({ close }: { close: () => void }) => addMembers(close),
						},
					],
				}"
			>
				<template #body-content>
					<div @click.stop class="min-h-[300px]">
						<MultiSelect
							v-model="selectedMembers"
							doctype="User"
							:filters="{ ignore_user_type: 1 }"
							:label="__('Members')"
							:autofocus="false"
							:exclude="
								(program.program_members || []).map((m: any) => m.member)
							"
						/>
					</div>
				</template>
			</Dialog>

			<!-- Dialog aggiungi da batch -->
			<Dialog
				v-model="showBatchDialog"
				:options="{
					size: 'lg',
					title: __('Add Members from Batch'),
					actions: [
						{
							label: __('Add'),
							variant: 'solid',
							onClick: ({ close }: { close: () => void }) =>
								addMembersFromBatch(close),
						},
					],
				}"
			>
				<template #body-content>
					<div @click.stop class="min-h-[300px] space-y-3">
						<Link
							v-model="selectedBatch"
							doctype="LMS Batch"
							:label="__('Select Batch')"
						/>
						<div v-if="batchMembersList.length > 0">
							<div class="flex items-center justify-between mb-2">
								<span class="text-sm text-ink-gray-5">
									{{ batchMembersList.length }} {{ __('members found') }}
								</span>
								<Button variant="ghost" @click="selectAllBatchMembers">
									{{ __('Select All') }}
								</Button>
							</div>
							<div
								class="max-h-[200px] overflow-y-auto space-y-1 border rounded-md p-2"
							>
								<div
									v-for="m in batchMembersList"
									:key="m.member"
									class="flex items-center gap-2 px-2 py-1.5 rounded cursor-pointer hover:bg-surface-gray-2"
									:class="{
										'bg-surface-gray-2': selectedMembers.includes(m.member),
									}"
									@click="toggleMemberSelection(m.member)"
								>
									<input
										type="checkbox"
										:checked="selectedMembers.includes(m.member)"
										class="pointer-events-none"
									/>
									<span class="text-sm text-ink-gray-8">{{
										m.member_name
									}}</span>
									<span class="text-xs text-ink-gray-5 ml-auto">{{
										m.member
									}}</span>
								</div>
							</div>
						</div>
						<div
							v-else-if="selectedBatch && !batchEnrollments.loading"
							class="text-sm text-ink-gray-5"
						>
							{{ __('No members found in this batch') }}
						</div>
					</div>
				</template>
			</Dialog>
			<ProgramProgressSummary
				v-model="showProgressDialog"
				:programName="programName"
				:programMembers="programMembers.data"
			/>
		</template>
		<template #actions="{ close }">
			<div class="flex justify-end space-x-2">
				<Button
					v-if="programName != 'new'"
					@click="deleteProgram(close)"
					variant="outline"
					theme="red"
				>
					<template #prefix>
						<Trash2 class="size-4 stroke-1.5" />
					</template>
					{{ __('Delete') }}
				</Button>
				<Button variant="solid" @click="saveProgram(close)">
					{{ __('Save') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import {
	Badge,
	Button,
	createListResource,
	createResource,
	Dialog,
	FormControl,
	ListView,
	ListHeader,
	ListHeaderItem,
	ListRows,
	ListRow,
	toast,
	TextEditor,
} from 'frappe-ui'
import ListSelectBanner from '@/overrides/frappe-ui/src/components/ListView/ListSelectBanner.vue'
import { computed, ref, watch, getCurrentInstance } from 'vue'
import { Plus, Trash2, TrendingUp } from 'lucide-vue-next'
import { Programs, Program } from '@/types/programs'
import { sanitizeHTML, openSettings } from '@/utils'
import Link from '@/components/Controls/Link.vue'
import Draggable from 'vuedraggable'
import ProgramProgressSummary from '@/pages/Programs/ProgramProgressSummary.vue'
import MultiSelect from '@/components/Controls/MultiSelect.vue'

const show = defineModel<boolean>()
const programs = defineModel<Programs>('programs')
const showFormDialog = ref(false)
const currentForm = ref<'course' | 'member'>('course')
const selectedCourses = ref<string[]>([])
const member = ref<string>('')
const showProgressDialog = ref(false)
const dirty = ref(false)
const showMemberDialog = ref(false)
const showBatchDialog = ref(false)
const selectedBatch = ref<string>('')
const selectedMembers = ref<string[]>([])
const batchMembersList = ref<any[]>([])

const app = getCurrentInstance()
const { $dialog } = app.appContext.config.globalProperties
const multiSelectRef = ref(null)

const props = withDefaults(
	defineProps<{
		programName: string | null
	}>(),
	{
		programName: 'new',
	},
)

const program = ref<Program>({
	name: '',
	title: '',
	description: '',
	published: false,
	enforce_course_order: false,
	program_courses: [],
	program_members: [],
})

const loadProgramData = () => {
	if (!props.programName) return
	setProgramData()
	if (props.programName !== 'new') {
		fetchCourses()
		fetchMembers()
	}
}

watch(() => props.programName, loadProgramData, { immediate: true })

watch(show, (isOpen) => {
	if (isOpen) loadProgramData()
})

watch(selectedBatch, async (val) => {
	if (!val) return
	batchMembersList.value = []
	selectedMembers.value = []

	try {
		const response = await fetch('/api/method/frappe.client.get_list', {
			method: 'POST',
			headers: {
				'Content-Type': 'application/json',
				'X-Frappe-CSRF-Token': (window as any).csrf_token,
				Accept: 'application/json',
			},
			body: JSON.stringify({
				doctype: 'LMS Batch Enrollment',
				fields: ['member', 'member_name'],
				filters: [['batch', '=', val]],
				limit_page_length: 500,
			}),
		})
		const json = await response.json()
		const existing = program.value.program_members.map((m: any) => m.member)
		batchMembersList.value = (json.message || []).filter(
			(d: any) => !existing.includes(d.member),
		)
	} catch (e) {
		console.error('fetch error:', e)
	}
})

const batchEnrollments = createResource({
	url: 'frappe.client.get_list',
	makeParams(values) {
		return {
			doctype: 'LMS Batch Enrollment',
			fields: ['member', 'member_name'],
			filters: { batch: values.batch },
			limit: 500,
		}
	},
	onSuccess(data: any[]) {
		const existing = program.value.program_members.map((m: any) => m.member)
		batchMembersList.value = data.filter((d) => !existing.includes(d.member))
	},
})

const openMemberForm = (mode: 'direct' | 'batch') => {
	selectedMembers.value = []
	if (mode === 'direct') {
		showMemberDialog.value = true
	} else {
		selectedBatch.value = ''
		batchMembersList.value = []
		showBatchDialog.value = true
	}
}
const toggleMemberSelection = (memberValue: string) => {
	const idx = selectedMembers.value.indexOf(memberValue)
	if (idx > -1) selectedMembers.value.splice(idx, 1)
	else selectedMembers.value.push(memberValue)
}

const selectAllBatchMembers = () => {
	selectedMembers.value = batchMembersList.value.map((m) => m.member)
}

const setProgramData = () => {
	let isNew = true

	programs.value?.data.forEach((p: Program) => {
		if (p.name === props.programName) {
			isNew = false
			const existingCourses = program.value.program_courses
			const existingMembers = program.value.program_members
			program.value = { ...p }
			program.value.title = p.title || p.name
			program.value.program_courses = Array.isArray(existingCourses)
				? existingCourses
				: []
			program.value.program_members = Array.isArray(existingMembers)
				? existingMembers
				: []
		}
	})

	if (isNew) {
		program.value = {
			name: '',
			title: '',
			description: '',
			published: false,
			enforce_course_order: false,
			program_courses: [],
			program_members: [],
		}
	}
	dirty.value = false
}

const programCourses = createListResource({
	doctype: 'LMS Program Course',
	fields: ['course', 'course_title', 'name', 'idx'],
	cache: ['programCourses', props.programName],
	parent: 'LMS Program',
	orderBy: 'idx',
	onSuccess(data: ProgramCourse[]) {
		program.value.program_courses = data
	},
})

const programMembers = createListResource({
	doctype: 'LMS Program Member',
	fields: ['member', 'full_name', 'progress', 'name'],
	cache: ['programMembers', props.programName],
	parent: 'LMS Program',
	orderBy: 'creation desc',
	onSuccess(data: ProgramMember[]) {
		program.value.program_members = data
	},
})

const fetchCourses = () => {
	programCourses.update({
		filters: {
			parent: props.programName,
			parenttype: 'LMS Program',
			parentfield: 'program_courses',
		},
	})
	programCourses.reload()
}

const fetchMembers = () => {
	programMembers.update({
		filters: {
			parent: props.programName,
			parenttype: 'LMS Program',
		},
	})
	programMembers.reload()
}

const validateTitle = () => {
	program.value.name = sanitizeHTML(program.value.name.trim())
}

const saveProgram = (close: () => void) => {
	validateTitle()
	program.value.description = sanitizeHTML(program.value.description)
	if (props.programName === 'new') createNewProgram(close)
	else updateProgram(close)
	dirty.value = false
}

const createNewProgram = (close: () => void) => {
	programs.value.insert.submit(
		{
			title: program.value.title,
			description: program.value.description,
			published: program.value.published,
			enforce_course_order: program.value.enforce_course_order,
			program_courses: program.value.program_courses,
			program_members: program.value.program_members,
		},
		{
			onSuccess() {
				close()
				programs.value.reload()
				toast.success(__('Program created successfully'))
			},
			onError(err: any) {
				toast.warning(__(err.messages?.[0] || err))
			},
		},
	)
}

const updateProgram = async (close: () => void) => {
	try {
		const newTitle = program.value.title
		const oldName = props.programName

		// Se il titolo è cambiato, prima rinomina il documento
		if (newTitle !== oldName) {
			const renameResponse = await fetch(
				'/api/method/frappe.client.rename_doc',
				{
					method: 'POST',
					headers: {
						'Content-Type': 'application/json',
						'X-Frappe-CSRF-Token': (window as any).csrf_token,
					},
					body: JSON.stringify({
						doctype: 'LMS Program',
						old_name: oldName,
						new_name: newTitle,
						merge: false,
					}),
				},
			)
			const renameJson = await renameResponse.json()
			if (renameJson.exc) {
				toast.warning(
					renameJson._server_messages
						? JSON.parse(JSON.parse(renameJson._server_messages)[0]).message
						: renameJson.exc,
				)
				return
			}
		}

		const cleanCourses = program.value.program_courses.map((c: any) => {
			const row: any = {
				doctype: 'LMS Program Course',
				course: c.course,
				course_title: c.course_title,
				idx: c.idx,
			}
			if (c.name) row.name = c.name
			return row
		})

		const cleanMembers = program.value.program_members.map((m: any) => {
			const row: any = {
				doctype: 'LMS Program Member',
				member: m.member,
				full_name: m.full_name,
				progress: m.progress || 0,
				idx: m.idx,
			}
			if (m.name) row.name = m.name
			return row
		})

		const saveResponse = await fetch(
			`/api/resource/LMS%20Program/${encodeURIComponent(newTitle)}`,
			{
				method: 'PUT',
				headers: {
					'Content-Type': 'application/json',
					'X-Frappe-CSRF-Token': (window as any).csrf_token,
				},
				body: JSON.stringify({
					title: newTitle,
					description: program.value.description,
					published: program.value.published ? 1 : 0,
					enforce_course_order: program.value.enforce_course_order ? 1 : 0,
					program_courses: cleanCourses,
					program_members: cleanMembers,
				}),
			},
		)

		const saveJson = await saveResponse.json()
		if (saveJson.exc) {
			toast.warning(
				saveJson._server_messages
					? JSON.parse(JSON.parse(saveJson._server_messages)[0]).message
					: saveJson.exc,
			)
			return
		}

		await programs.value.reload()
		close()
		toast.success(__('Program updated successfully'))
	} catch (err: any) {
		toast.warning(err.message)
	}
}

const openForm = (formType: 'course' | 'member') => {
	currentForm.value = formType
	showFormDialog.value = true
	if (formType === 'course') {
		selectedCourses.value = []
	} else {
		member.value = ''
	}
}

const addCourses = (close: () => void) => {
	if (!selectedCourses.value.length) {
		toast.warning(__('Please select at least one course'))
		return
	}

	let added = 0
	const availableOptions = multiSelectRef.value?.cachedOptions || []

	selectedCourses.value.forEach((courseValue) => {
		const existingCourse = program.value.program_courses.find(
			(c: any) => c.course === courseValue,
		)
		if (!existingCourse) {
			const option = availableOptions.find((o: any) => o.value === courseValue)
			program.value.program_courses.push({
				course: courseValue,
				course_title: option?.label || option?.description || courseValue,
				idx: program.value.program_courses.length + 1,
			})
			added++
		}
	})

	if (added > 0 && props.programName !== 'new') {
		dirty.value = true
	}

	close()
	toast.success(__(`${added} course(s) added to program successfully`))
}

const addMembers = (close: () => void) => {
	if (!selectedMembers.value.length) {
		toast.warning(__('Please select at least one member'))
		return
	}
	let added = 0
	selectedMembers.value.forEach((memberValue) => {
		const existing = program.value.program_members.find(
			(m: any) => m.member === memberValue,
		)
		if (!existing) {
			program.value.program_members.push({ member: memberValue })
			added++
		}
	})
	if (added > 0 && props.programName !== 'new') dirty.value = true
	close()
	toast.success(__(`${added} member(s) added successfully`))
}

const addMembersFromBatch = (close: () => void) => {
	if (!selectedMembers.value.length) {
		toast.warning(__('Please select at least one member'))
		return
	}
	let added = 0
	selectedMembers.value.forEach((memberValue) => {
		const existing = program.value.program_members.find(
			(m: any) => m.member === memberValue,
		)
		if (!existing) {
			const found = batchMembersList.value.find((m) => m.member === memberValue)
			program.value.program_members.push({
				member: memberValue,
				full_name: found?.member_name || memberValue,
			})
			added++
		}
	})
	if (added > 0 && props.programName !== 'new') dirty.value = true
	close()
	toast.success(__(`${added} member(s) added successfully`))
}

const updateCounts = async (
	type: 'member' | 'course',
	action: 'add' | 'remove',
) => {
	if (!props.programName) return

	let memberCount = programMembers.data?.length || 0
	let courseCount = programCourses.data?.length || 0

	if (type === 'member') {
		memberCount += action === 'add' ? 1 : -1
	} else {
		courseCount += action === 'add' ? 1 : -1
	}

	await programs.value.setValue.submit(
		{
			name: props.programName,
			member_count: memberCount,
			course_count: courseCount,
		},
		{
			onSuccess() {
				setProgramData()
			},
			onError(err: any) {
				toast.warning(__(err.messages?.[0] || err))
			},
		},
	)
}

const updateOrder = async (e: DragEvent) => {
	let sourceIdx = e.from.dataset.idx
	let targetIdx = e.to.dataset.idx

	if (props.programName === 'new') {
		let courses = program.value.program_courses
		courses.splice(targetIdx, 0, courses.splice(sourceIdx, 1)[0])
		courses.forEach((course, index) => {
			course.idx = index + 1
		})
		dirty.value = true
	} else {
		let courses = programCourses.data
		courses.splice(targetIdx, 0, courses.splice(sourceIdx, 1)[0])

		for (const [index, course] of courses.entries()) {
			programCourses.setValue.submit(
				{
					name: course.name,
					idx: index + 1,
				},
				{
					onError(err: any) {
						toast.warning(__(err.messages?.[0] || err))
					},
				},
			)
			await wait(100)
		}
	}
}

const wait = (ms: number) => new Promise((res) => setTimeout(res, ms))

const remove = (
	selections: Iterable<string>,
	unselectAll: () => void,
	listField: string,
	rowKey: string,
) => {
	const selectionsSet = new Set(selections)
	const list = (program.value as any)[listField]
	if (!Array.isArray(list)) return
	;(program.value as any)[listField] = list.filter(
		(item: any) => !selectionsSet.has(item[rowKey]),
	)
	dirty.value = true
	unselectAll()
}

const deleteProgram = (close: () => void) => {
	if (props.programName == 'new') return
	$dialog({
		title: __('Delete Program'),
		message: __(
			'Are you sure you want to delete this program? This action cannot be undone.',
		),
		actions: [
			{
				label: __('Delete'),
				theme: 'red',
				variant: 'solid',
				onClick(closeDialog) {
					programs.value?.delete.submit(props.programName, {
						onSuccess() {
							toast.success(__('Program deleted successfully'))
							close()
							closeDialog()
						},
						onError(err: any) {
							toast.warning(__(err.messages?.[0] || err))
							closeDialog()
						},
					})
				},
			},
		],
	})
}

const selectionText = (count: number) =>
	count === 1 ? __('1 row selected') : __('{0} rows selected').format(count)

const courseColumns = computed(() => {
	return [
		{
			label: 'Title',
			key: props.programName === 'new' ? 'course' : 'course_title',
			width: 1,
		},
	]
})

const memberColumns = computed(() => {
	return [
		{
			label: 'Member',
			key: 'member',
			width: 3,
			align: 'left',
		},
		{
			label: 'Full Name',
			key: 'full_name',
			width: 3,
			align: 'left',
		},
	]
})
</script>
