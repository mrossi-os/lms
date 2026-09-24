<template>
	<SettingsList
		:title="__(label)"
		:description="__(description)"
		:columns="columns"
		:rows="memberList"
		:loading="Boolean(members.loading)"
		:has-next-page="hasNextPage"
		v-model:search="search"
		searchable
		:search-label="__('Search members')"
		empty-name="Users"
		empty-icon="lucide-user"
		@new="openNewMember"
		@load-more="fetchMembers()"
		@row-click="(member) => openEditMember(member as Member)"
	>
		<template #header-bottom>
			<Select
				v-model="currentRole"
				class="w-40"
				:aria-label="__('Filter by role')"
				:options="roleOptions"
			/>
		</template>
		<!-- OSLMS-CUSTOM: the member cell opens the profile (row click opens the edit form); role badges translated, custom roles such as Valutatore included -->
		<template #cell="{ column, row }">
			<div
				v-if="column.key === 'member'"
				class="flex min-w-0 cursor-pointer items-center"
				@click.stop="openProfile(row.username)"
			>
				<Avatar
					:image="row.user_image"
					:label="row.full_name"
					size="xl"
					class="me-3 shrink-0"
				/>
				<div class="flex min-w-0 flex-col">
					<span class="truncate text-p-base text-ink-gray-8">
						{{ row.full_name }}
					</span>
					<span class="truncate text-p-sm text-ink-gray-5">
						{{ row.name }}
					</span>
				</div>
			</div>
			<template v-else-if="column.key === 'roles'">
				<Badge
					v-for="badge in roleBadges(row as Member)"
					:key="badge.label"
					theme="gray"
					class="me-2 last:me-0"
				>
					{{ badge.label }}
				</Badge>
			</template>
			<Dropdown
				v-else-if="column.type === 'actions'"
				:options="column.options(row)"
				:button="{
					icon: 'lucide-more-horizontal',
					variant: 'ghost',
					label: column.ariaLabel
						? column.ariaLabel(row)
						: __('More options'),
				}"
				placement="right"
			/>
		</template>
	</SettingsList>

	<Dialog
		v-model:open="showDeleteDialog"
		:title="
			memberToDelete ? __('Delete {0}?').format(memberToDelete.full_name) : ''
		"
		:message="
			__('This permanently deletes the user account and cannot be undone.')
		"
		size="sm"
		:actions="[
			{
				label: __('Delete'),
				theme: 'red',
				variant: 'solid',
				onClick: confirmDelete,
			},
			{
				label: __('Cancel'),
				onClick: () => {
					showDeleteDialog = false
				},
			},
		]"
	/>
</template>
<script setup lang="ts">
import {
	Avatar,
	Badge,
	call,
	createResource,
	Dialog,
	Dropdown,
	Select,
	toast,
} from 'frappe-ui'
import { useRouter } from 'vue-router'
import { ref, watch } from 'vue'
import type { SettingsListColumn } from '@/types'
import { SETTINGS_PAGE_LENGTH } from '@/composables/useSettingsListResource'
import { openFormRoute } from '@/composables/useFormRoute'
import { membersRevision } from '@/stores/members'
import SettingsList from '@/components/Layouts/SettingsList.vue'
import { cleanError } from '@/utils'

type Member = {
	username: string
	full_name: string
	name: string
	roles?: string[]
	user_image?: string
}

const router = useRouter()
const show = defineModel('show')
const search = ref('')
const currentRole = ref('All')
const start = ref(0)

const roleOptions = [
	{ label: __('All'), value: 'All' },
	{ label: __('Student'), value: 'LMS Student' },
	{ label: __('Instructor'), value: 'Course Creator' },
	{ label: __('Moderator'), value: 'Moderator' },
	{ label: __('Evaluator'), value: 'Batch Evaluator' },
]

const memberList = ref<Member[]>([])
const hasNextPage = ref(false)

const showDeleteDialog = ref(false)
const memberToDelete = ref<Member | null>(null)

defineProps({
	label: {
		type: String,
		required: true,
	},
	description: {
		type: String,
		default: '',
	},
})

// No frappe-ui `cache` key on purpose: makeParams closes over this component's
// refs, and createResource hands back the FIRST instance for a key without
// rebinding those closures, so a remounted panel would inherit a resource still
// writing into the unmounted one's state. The member forms announce saves
// through `membersRevision` instead (see stores/members.ts).
const members = createResource({
	url: 'lms.lms.api.get_members',
	makeParams: () => ({
		search: search.value,
		start: start.value,
		role: currentRole.value,
	}),
	auto: false,
})

// createResource carries no request sequence and aborts nothing, so two calls
// in flight both resolve and both append: a role change mid-request would show
// one filter's page under another's, and over-advance `start` past rows nobody
// ever saw. Each call takes a token and a superseded response is dropped.
let requestToken = 0

const fetchMembers = async () => {
	const token = ++requestToken
	const data = (await members.reload()) as Member[] | null
	if (token !== requestToken || !data) return
	memberList.value = memberList.value.concat(data)
	// Paged by what the server actually returned, not by the constant. An
	// exact-equality check hides Load More outright the moment the two
	// disagree, and stepping `start` by the constant would then skip rows.
	start.value = start.value + data.length
	hasNextPage.value = data.length >= SETTINGS_PAGE_LENGTH
}

// The search goes to the server with start reset, so a match past the first
// page is reachable without pressing Load More first.
const refreshMembers = () => {
	memberList.value = []
	start.value = 0
	return fetchMembers()
}

watch([search, currentRole], () => {
	refreshMembers()
})

// A member form saved while this panel is still mounted behind it (the desktop
// dialog) has no other way to reach the list. On a phone the panel unmounts, so
// the fresh mount's own first fetch already covers it.
watch(membersRevision, () => {
	refreshMembers()
})

refreshMembers()

const openProfile = (username: string) => {
	show.value = false
	router.push({ name: 'Profile', params: { username } })
}

// OSLMS-CUSTOM: every role get_members returns gets a badge (including the
// custom per-batch Valutatore role); labels are English source strings,
// translated where rendered, and unknown roles show their own name.
const getRole = (role: string) => {
	const map: Record<string, string> = {
		'LMS Student': 'Student',
		'Course Creator': 'Instructor',
		Moderator: 'Moderator',
		'Batch Evaluator': 'Evaluator',
		Valutatore: 'Valutatore',
	}
	return map[role] || role
}

const roleBadges = (member: Member) =>
	(member.roles || []).map((role) => ({ label: __(getRole(role)) }))

// The settings dialog is deliberately left open behind these: opening a member
// form is not a "leave settings" action the way openProfile() is, and the form
// renders as a second dialog on top, the way the delete confirmation below
// already stacks.
const openEditMember = (member: Member) => {
	openFormRoute(router, {
		name: 'MemberForm',
		params: { memberID: member.name },
	})
}

const openNewMember = () => {
	openFormRoute(router, { name: 'MemberForm', params: { memberID: 'new' } })
}

const openDeleteDialog = (member: Member) => {
	memberToDelete.value = member
	showDeleteDialog.value = true
}

const columns: SettingsListColumn[] = [
	{
		key: 'member',
		label: __('User'),
		type: 'stacked',
		primary: (row) => row.full_name,
		secondary: (row) => row.name,
		avatar: (row) => ({ image: row.user_image, label: row.full_name }),
	},
	{
		key: 'roles',
		label: __('Roles'),
		type: 'badge',
		badges: (row) =>
			roleBadges(row as Member).map((badge) => ({
				...badge,
				theme: 'gray' as const,
			})),
	},
	{
		key: 'actions',
		type: 'actions',
		ariaLabel: (row) => __('Actions for {0}').format(row.full_name),
		options: (row) => [
			{
				label: __('Edit member'),
				onClick: () => openEditMember(row as Member),
			},
			{
				label: __('Delete user'),
				theme: 'red',
				onClick: () => openDeleteDialog(row as Member),
			},
		],
	},
]

const confirmDelete = async (close: () => void) => {
	if (!memberToDelete.value) return
	try {
		await call('lms.lms.api.delete_member', { user: memberToDelete.value.name })
		showDeleteDialog.value = false
		memberToDelete.value = null
		refreshMembers()
		toast.success(__('User deleted'))
	} catch (err: any) {
		toast.error(cleanError(err.messages?.[0]) || err)
	}
	close?.()
}
</script>
