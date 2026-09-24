<template>
	<FormShell
		:title="isNew ? __('Create Program') : __('Edit Program')"
		size="2xl"
		@close="close"
	>
		<template #header-action>
			<Badge theme="orange" v-if="dirty">
				{{ __('Not Saved') }}
			</Badge>
		</template>
		<template #default>
			<div v-if="!canManageProgram" class="p-4 text-base text-ink-gray-6">
				{{ __('You are not permitted to manage programs.') }}
			</div>
			<div v-else data-testid="program-fields" class="text-base">
				<div class="grid grid-cols-1 md:grid-cols-2 gap-5 pb-5">
					<!-- OSLMS-CUSTOM: Title bound to program.title; a changed title renames the program on save -->
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
				<!-- OSLMS-CUSTOM: rich program description editor (os_lms description field) -->
				<div class="pb-5 col-span-2">
					<div class="mb-1.5 text-sm text-ink-gray-5">
						{{ __('Description') }}
					</div>
					<TextEditor
						:content="program.description"
						@change="
							(val: string) => {
								program.description = val
								dirty = true
							}
						"
						:editable="true"
						:fixedMenu="true"
						editorClass="prose-sm max-w-none border-b border-x border-outline-elevation-2 bg-surface-gray-2 rounded-b-md py-1 px-2 min-h-[7rem]"
					/>
				</div>

				<div class="pb-5">
					<div class="flex items-center justify-between mt-5 mb-4">
						<div class="text-lg-semibold text-ink-gray-9">
							{{ __('Courses') }}
						</div>
						<!-- OSLMS-CUSTOM: the add-course dialog adds several courses at once -->
						<Button @click="openForm()">
							<template #prefix>
								<span class="lucide-plus size-4" />
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
						:rowKey="'course'"
					>
						<ListHeader
							class="mb-2 grid items-center gap-x-4 rounded bg-surface-gray-2 p-2"
						>
							<ListHeaderItem
								:item="item"
								v-for="item in courseColumns"
								:key="item.key"
							/>
						</ListHeader>
						<ListRows>
							<Draggable
								:list="program.program_courses"
								:item-key="'course'"
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
										:label="__('Delete')"
										@click="
											remove(selections, unselectAll, 'program_courses', 'course')
										"
									>
										<template #icon>
											<span class="lucide-trash-2 size-4" />
										</template>
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
						<div class="text-lg-semibold text-ink-gray-9">
							{{ __('Members') }}
						</div>

						<div class="flex gap-x-2">
							<Button
								v-if="program.program_members?.length > 0"
								@click="showProgressDialog = true"
							>
								<template #prefix>
									<span class="lucide-trending-up size-4" />
								</template>
								{{ __('Progress Summary') }}
							</Button>
							<!-- OSLMS-CUSTOM: add several members at once, or pick them from a batch ("Add Group") -->
							<Button @click="openMemberForm('direct')">
								<template #prefix>
									<span class="lucide-plus size-4" />
								</template>
								{{ __('Add Member') }}
							</Button>
							<Button @click="openMemberForm('batch')">
								<template #prefix>
									<span class="lucide-plus size-4" />
								</template>
								{{ __('Add Group') }}
							</Button>
						</div>
					</div>
					<ResponsiveListView
						v-if="program.program_members?.length > 0"
						:columns="memberColumns"
						:rows="program.program_members"
						row-key="member"
						:options="{ selectable: true, selectionText }"
					>
						<template #selection-actions="{ unselectAll, selections }">
							<Button
								variant="ghost"
								:label="__('Delete')"
								@click="
									remove(selections, unselectAll, 'program_members', 'member')
								"
							>
								<template #icon>
									<span class="lucide-trash-2 size-4" />
								</template>
							</Button>
						</template>
					</ResponsiveListView>
					<div v-else class="text-ink-gray-7">
						{{ __('No members added yet.') }}
					</div>
				</div>
			</div>
			<!--
				Courses only: members get their own dialogs (showMemberDialog and
				showBatchDialog). This one used to serve both, switching on a
				`currentForm` ref that a refactor removed while leaving the reads
				behind — so it always took the member branch, titled itself "Enroll
				Member", ran addMembers, and rendered no field at all.
			-->
			<Dialog
				v-model:open="showFormDialog"
				:title="__('Add Course to Program')"
				:actions="[
					{
						label: __('Add'),
						variant: 'solid',
						onClick: ({ close }: { close: () => void }) => addCourses(close),
					},
				]"
			>
				<template #default>
					<div @click.stop>
						<!-- OSLMS-CUSTOM: multi-course picker that excludes courses already in the program -->
						<!--
							MultiSelect, like the members field below: it binds an array,
							supports :exclude and exposes cachedOptions — the three things
							addCourses and this dialog rely on. A refactor swapped it for
							the single-value Link bound to an undeclared `course` ref, so
							selectedCourses stayed empty and adding always failed with
							"select at least one course", while :exclude was silently
							ignored.
						-->
						<MultiSelect
							v-model="selectedCourses"
							doctype="LMS Course"
							:label="__('Courses')"
							ref="multiSelectRef"
							:exclude="
								(program.program_courses || []).map((c: any) => c.course)
							"
						/>
					</div>
				</template>
			</Dialog>
			<!-- OSLMS-CUSTOM: dialogs to add members directly or from a batch -->
			<Dialog
				v-model:open="showMemberDialog"
				size="lg"
				:title="__('Add Members')"
				:actions="[
					{
						label: __('Add'),
						variant: 'solid',
						onClick: ({ close }: { close: () => void }) => addMembers(close),
					},
				]"
			>
				<template #default>
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

			<Dialog
				v-model:open="showBatchDialog"
				size="lg"
				:title="__('Add Members from Batch')"
				:actions="[
					{
						label: __('Add'),
						variant: 'solid',
						onClick: ({ close }: { close: () => void }) =>
							addMembersFromBatch(close),
					},
				]"
			>
				<template #default>
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
				:programName="programId"
				:programMembers="program.program_members || []"
			/>
		</template>
		<template #actions>
			<div v-if="canManageProgram" class="flex items-center justify-end gap-2">
				<HeaderButton
					v-if="!isNew"
					data-testid="program-delete"
					:label="__('Delete program')"
					icon="lucide-trash-2"
					variant="outline"
					theme="red"
					@click="deleteProgram()"
				/>
				<HeaderButton
					data-testid="program-save"
					:label="__('Save')"
					variant="solid"
					@click="saveProgram()"
				/>
			</div>
		</template>
	</FormShell>
</template>
<script setup lang="ts">
import {
	Badge,
	Button,
	call,
	createListResource,
	createResource,
	Dialog,
	FormControl,
	ListView,
	ListHeader,
	ListHeaderItem,
	ListRows,
	ListRow,
	TextEditor,
	toast,
} from 'frappe-ui'
// OSLMS-CUSTOM: translatable selection banner (os_lms override imported directly)
import ListSelectBanner from '@/overrides/frappe-ui/src/components/ListView/ListSelectBanner.vue'
import { computed, inject, ref, watch, getCurrentInstance } from 'vue'

import { Program } from '@/types'
import { sanitizeOnWrite } from '@/utils/sanitizeOnWrite'
import { sanitizeRichHTML } from '@/utils/sanitizeRichHTML'
import FormShell from '@/components/FormShell.vue'
import HeaderButton from '@/components/HeaderButton.vue'
import { useFormRoute } from '@/composables/useFormRoute'
import Link from '@/components/Controls/Link.vue'
import ResponsiveListView from '@/components/ResponsiveListView.vue'
import Draggable from 'vuedraggable'
import ProgramProgressSummary from '@/components/Programs/ProgramProgressSummary.vue'
import { submitResource } from '@/utils/resource'
// OSLMS-CUSTOM: multi-value picker for courses and members
import MultiSelect from '@/components/Controls/MultiSelect.vue'

// OSLMS-CUSTOM: the os_lms description field is not on the upstream type
type ProgramWithDescription = Program & { description?: string }

const showFormDialog = ref(false)
const selectedCourses = ref<string[]>([])
const showProgressDialog = ref(false)
const dirty = ref(false)
const showMemberDialog = ref(false)
const showBatchDialog = ref(false)
const selectedBatch = ref<string>('')
const selectedMembers = ref<string[]>([])
const batchMembersList = ref<any[]>([])
const multiSelectRef = ref<any>(null)
const user = inject<any>('$user')

const app = getCurrentInstance()
const { $dialog } = app!.appContext.config.globalProperties

const props = withDefaults(
	defineProps<{
		programName?: string | null
	}>(),
	{
		programName: 'new',
	}
)

// The parent list refetches through its own updatePrograms(), which drives the
// `reloading` flag and the footer count as well (Programs.vue:175-187). A bare
// resource reload from here would skip both and bring back the flash of empty
// state, so signal the parent instead of reaching into its resource.
const emit = defineEmits<{ saved: [] }>()

const { close, saveAndReplace } = useFormRoute({ name: 'Programs' })

// R3: `withDefaults` only fills an *undefined* prop, so the `null` this form
// used to be handed by the parent (Programs.vue's `currentProgram` ref) slipped
// straight through and every `=== 'new'` comparison below took the EDIT branch
// before a program had been chosen. The route param is always a string now, but
// the sentinel is still normalised in exactly one place rather than eight.
const programId = computed(() => props.programName || 'new')
const isNew = computed(() => programId.value === 'new')

// Copied from Programs.vue:268-275, which gates both the Create button and the
// card that opens an existing program. A URL goes through neither. This is a UX
// gate, not an authorization boundary — the server's DocPerms on LMS Program
// are; this only spares an unentitled user a form that could never save.
const canManageProgram = computed(() => {
	// Cast because Window has no read_only_mode declaration; same shape as
	// NewBatchForm.vue:190.
	if ((window as Window & { read_only_mode?: boolean }).read_only_mode)
		return false
	return Boolean(user.data?.is_moderator || user.data?.is_instructor)
})

const program = ref<ProgramWithDescription>({
	name: '',
	title: '',
	description: '',
	published: false,
	enforce_course_order: false,
	program_courses: [],
	program_members: [],
})

// This form owns its LMS Program resource instead of the parent's list resource
// (`cache: ['program']`). Deliberately a DIFFERENT cache key: reusing the
// parent's would hand back its cached instance and make insert.onSuccess refetch
// it behind the page's back, which is exactly the bare reload the `saved` emit
// exists to avoid.
const programs = createListResource({
	doctype: 'LMS Program',
	cache: ['programForm'],
	auto: false,
})

// OSLMS-CUSTOM: load the whole LMS Program document (child tables included) instead of per-child list resources
// It also seeds the scalar fields (title, description, flags): a routed form has
// no parent list to copy them from, and on a cold deep link seeding nothing
// would let a Save post an empty program back over the real record.
const programDoc = createResource({
	url: 'frappe.client.get',
	makeParams() {
		return {
			doctype: 'LMS Program',
			name: programId.value,
		}
	},
	onSuccess(data: any) {
		program.value.name = data.name
		program.value.title = data.title || data.name
		program.value.description = data.description || ''
		program.value.published = Boolean(data.published)
		program.value.enforce_course_order = Boolean(data.enforce_course_order)
		program.value.program_courses = (data.program_courses || [])
			.slice()
			.sort((a: any, b: any) => (a.idx || 0) - (b.idx || 0))
			.map((c: any) => ({
				course: c.course,
				course_title: c.course_title,
				name: c.name,
				idx: c.idx,
			}))
		program.value.program_members = (data.program_members || []).map(
			(m: any) => ({
				member: m.member,
				full_name: m.full_name,
				progress: m.progress,
				name: m.name,
			})
		)
		dirty.value = false
	},
	onError(err: any) {
		toast.warning(__(err.messages?.[0] || err))
	},
})

// C3: a directly-mounted route renders blank without `immediate: true`.
watch(
	programId,
	() => {
		if (isNew.value) return
		programDoc.fetch()
	},
	{ immediate: true }
)

// OSLMS-CUSTOM: list the members of the picked batch, minus those already in the program
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
			(d: any) => !existing.includes(d.member)
		)
	} catch (e) {
		console.error('fetch error:', e)
	}
})

const batchEnrollments = createResource({
	url: 'frappe.client.get_list',
	makeParams(values: any) {
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

// OSLMS-CUSTOM: the input is bound to program.title (renamable), so clean that field, not the docname
const validateTitle = () => {
	program.value.title = sanitizeOnWrite(program.value.title.trim())
}

const saveProgram = () => {
	if (!canManageProgram.value) return
	// The full document is PUT back on save: never before it has loaded, or
	// the empty child tables would overwrite the real ones.
	if (!isNew.value && !programDoc.data) return
	validateTitle()
	// OSLMS-CUSTOM: keep the description's rich formatting
	// Rich sanitizer: the allowlist one drops the span/mark/s tags and style
	// attributes the editor uses for text color, highlight and strikethrough.
	program.value.description = sanitizeRichHTML(program.value.description)
	if (isNew.value) createNewProgram()
	else updateProgram()
	dirty.value = false
}

// Saving navigates onward by REPLACING, so the entry this form was opened on is
// consumed and Back reaches the list rather than a stale form.
const afterSave = () => {
	emit('saved')
	saveAndReplace({ name: 'Programs' })
}

const createNewProgram = () => {
	submitResource(
		programs.insert,
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
				toast.success(__('Program created successfully'))
				afterSave()
			},
			onError(err: any) {
				toast.warning(__(err.messages?.[0] || err))
			},
		}
	)
}

// OSLMS-CUSTOM: rename on title change, then save the whole document (child tables included)
const updateProgram = async () => {
	try {
		const newTitle = program.value.title
		const oldName = programId.value

		// A changed title renames the document first (LMS Program is autonamed
		// from its title).
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
				}
			)
			const renameJson = await renameResponse.json()
			if (renameJson.exc) {
				toast.warning(
					renameJson._server_messages
						? JSON.parse(JSON.parse(renameJson._server_messages)[0]).message
						: renameJson.exc
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
			}
		)

		const saveJson = await saveResponse.json()
		if (saveJson.exc) {
			toast.warning(
				saveJson._server_messages
					? JSON.parse(JSON.parse(saveJson._server_messages)[0]).message
					: saveJson.exc
			)
			return
		}

		toast.success(__('Program updated successfully'))
		afterSave()
	} catch (err: any) {
		toast.warning(err.message)
	}
}

const openForm = () => {
	showFormDialog.value = true
	selectedCourses.value = []
}

// OSLMS-CUSTOM: add several courses at once
const addCourses = (close: () => void) => {
	if (!selectedCourses.value.length) {
		toast.warning(__('Please select at least one course'))
		return
	}

	let added = 0
	const availableOptions = multiSelectRef.value?.cachedOptions || []

	selectedCourses.value.forEach((courseValue) => {
		const existingCourse = program.value.program_courses.find(
			(c: any) => c.course === courseValue
		)
		if (!existingCourse) {
			const option = availableOptions.find((o: any) => o.value === courseValue)
			program.value.program_courses.push({
				course: courseValue,
				course_title: option?.label || option?.description || courseValue,
				idx: program.value.program_courses.length + 1,
			} as any)
			added++
		}
	})

	if (added > 0 && !isNew.value) {
		dirty.value = true
	}

	close()
	toast.success(
		added === 1
			? __('1 course added to program successfully')
			: __('{0} courses added to program successfully').format(added)
	)
}

const addMembers = (close: () => void) => {
	if (!selectedMembers.value.length) {
		toast.warning(__('Please select at least one member'))
		return
	}
	let added = 0
	selectedMembers.value.forEach((memberValue) => {
		const existing = program.value.program_members.find(
			(m: any) => m.member === memberValue
		)
		if (!existing) {
			program.value.program_members.push({ member: memberValue } as any)
			added++
		}
	})
	if (added > 0 && !isNew.value) dirty.value = true
	close()
	toast.success(
		added === 1
			? __('1 member added successfully')
			: __('{0} members added successfully').format(added)
	)
}

// OSLMS-CUSTOM: add members picked from a batch
const addMembersFromBatch = (close: () => void) => {
	if (!selectedMembers.value.length) {
		toast.warning(__('Please select at least one member'))
		return
	}
	let added = 0
	selectedMembers.value.forEach((memberValue) => {
		const existing = program.value.program_members.find(
			(m: any) => m.member === memberValue
		)
		if (!existing) {
			const found = batchMembersList.value.find((m) => m.member === memberValue)
			program.value.program_members.push({
				member: memberValue,
				full_name: found?.member_name || memberValue,
			} as any)
			added++
		}
	})
	if (added > 0 && !isNew.value) dirty.value = true
	close()
	toast.success(
		added === 1
			? __('1 member added successfully')
			: __('{0} members added successfully').format(added)
	)
}

// OSLMS-CUSTOM: reorder the local course list, then persist idx per row for saved programs
const updateOrder = async (e: any) => {
	let sourceIdx = e.from.dataset.idx
	let targetIdx = e.to.dataset.idx

	let courses = program.value.program_courses
	courses.splice(targetIdx, 0, courses.splice(sourceIdx, 1)[0])
	courses.forEach((course: any, index: number) => {
		course.idx = index + 1
	})

	if (isNew.value) {
		dirty.value = true
		return
	}

	for (const course of courses) {
		try {
			await call('frappe.client.set_value', {
				doctype: 'LMS Program Course',
				name: course.name,
				fieldname: { idx: course.idx },
			})
		} catch (err: any) {
			toast.warning(__(err.messages?.[0] || err))
		}
		await wait(100)
	}
}

const wait = (ms: number) => new Promise((res) => setTimeout(res, ms))

// OSLMS-CUSTOM: remove selected rows by their row key (course / member)
const remove = (
	selections: Iterable<string>,
	unselectAll: () => void,
	listField: string,
	rowKey: string
) => {
	const selectionsSet = new Set(selections)
	const list = (program.value as any)[listField]
	if (!Array.isArray(list)) return
	;(program.value as any)[listField] = list.filter(
		(item: any) => !selectionsSet.has(item[rowKey])
	)
	dirty.value = true
	unselectAll()
}

const deleteProgram = () => {
	if (isNew.value) return
	$dialog({
		title: __('Delete Program'),
		message: __(
			'Are you sure you want to delete this program? This action cannot be undone.'
		),
		actions: [
			{
				label: __('Delete'),
				theme: 'red',
				variant: 'solid',
				onClick(closeDialog: () => void) {
					submitResource(programs.delete, programId.value, {
						onSuccess() {
							toast.success(__('Program deleted successfully'))
							emit('saved')
							closeDialog()
							close()
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

// OSLMS-CUSTOM: translated selection banner text
const selectionText = (count: number) =>
	count === 1 ? __('1 row selected') : __('{0} rows selected').format(count)

const courseColumns = computed(() => {
	return [
		{
			label: __('Title'),
			key: isNew.value ? 'course' : 'course_title',
			width: 1,
		},
	]
})

const memberColumns = computed(() => {
	return [
		{
			label: __('Member'),
			key: 'member',
			width: 3,
			align: 'left',
		},
		{
			label: __('Full Name'),
			key: 'full_name',
			width: 3,
			align: 'left',
		},
	]
})
</script>
