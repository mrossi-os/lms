<template>
	<!-- OSLMS-CUSTOM: a profile that fails to load shows NotFound when the user does not exist (DoesNotExistError) and NoPermission for any other error, instead of upstream's NotFound for every error -->
	<NoPermission v-if="!$user.data" />
	<div v-else-if="profile.data">
		<PageHeader :breadcrumbs="breadcrumbs">
			<template #actions>
				<HeaderButton
					v-if="isSessionUser()"
					variant="ghost"
					:label="__('Refresh session')"
					icon="lucide-refresh-ccw"
					@click="reloadUser()"
				/>
			</template>
		</PageHeader>
		<!-- OSLMS-CUSTOM: cover image and its Edit button removed, empty spacer kept -->
		<div class="group relative h-[130px] w-full"></div>
		<div class="mx-auto -mt-10 md:-mt-4 max-w-4xl translate-x-0 px-5">
			<div class="flex flex-col md:flex-row items-center">
				<div>
					<div class="relative">
						<img
							v-if="profile.data.user_image"
							:src="safeUrl(profile.data.user_image)"
							:alt="profile.data.full_name"
							class="object-cover h-[100px] w-[100px] rounded-full border-4 border-white object-cover"
						/>
						<div
							v-else
							class="flex items-center justify-center h-[100px] w-[100px] rounded-full border-4 border-white bg-surface-gray-2 text-4xl-semibold text-ink-gray-7"
						>
							{{ profile.data.full_name.charAt(0).toUpperCase() }}
						</div>
						<Tooltip
							v-if="profile.data.open_to"
							:text="
								profile.data.open_to === 'Work'
									? __('Open to Work')
									: __('Hiring')
							"
							placement="right"
						>
							<div
								class="absolute bottom-3 end-1 p-0.5 bg-surface-base rounded-full"
							>
								<div
									class="rounded-full w-fit"
									:class="
										profile.data.open_to === 'Work'
											? 'bg-surface-green-7 text-ink-green-1'
											: 'bg-surface-violet-7 text-ink-violet-1'
									"
								>
									<span class="lucide-badge-check size-5" />
								</div>
							</div>
						</Tooltip>
					</div>
				</div>
				<div class="ms-6 mt-5">
					<h1 class="text-4xl-semibold text-ink-gray-9">
						{{ profile.data.full_name }}
					</h1>
					<div class="text-base text-ink-gray-7 mt-1">
						{{ profile.data.headline }}
					</div>
					<div class="flex items-center gap-x-4 mt-2">
						<a
							v-if="profile.data.twitter"
							:href="safeUrl(profile.data.twitter)"
							v-external
							:aria-label="__('Twitter')"
						>
							<Twitter class="size-4 text-ink-gray-5 cursor-pointer" />
						</a>
						<a
							v-if="profile.data.linkedin"
							:href="safeUrl(profile.data.linkedin)"
							v-external
							:aria-label="__('LinkedIn')"
						>
							<Linkedin class="size-4 text-ink-gray-5 cursor-pointer" />
						</a>
						<a
							v-if="profile.data.github"
							:href="safeUrl(profile.data.github)"
							v-external
							:aria-label="__('GitHub')"
						>
							<Github class="size-4 text-ink-gray-5 cursor-pointer" />
						</a>
					</div>
				</div>
				<Button
					v-if="isSessionUser() && !readOnlyMode"
					class="mt-3 sm:mt-0 md:ms-auto"
					@click="editProfile()"
				>
					<template #prefix>
						<span class="lucide-edit size-4 text-ink-gray-7" />
					</template>
					{{ __('Edit Profile') }}
				</Button>
			</div>

			<div class="mb-4 mt-10">
				<!-- OSLMS-CUSTOM: tab bar hidden for students, who only have the Certificates tab -->
				<TabButtons
					v-if="!$user.data?.is_student"
					:class="
						isMobile
							? 'flex w-full [&>div]:w-full [&_button]:min-w-0 [&_button]:grow [&_button>span]:w-full'
							: 'inline-block'
					"
					:options="getTabButtons()"
					v-model="activeTab"
				/>
			</div>
			<router-view :profile="profile" :key="profile.data?.name" />
		</div>
	</div>
	<NotFound v-else-if="profile.error?.exc_type === 'DoesNotExistError'" />
	<NoPermission v-else-if="profile.error" />
	<NotFound v-else-if="profile.fetched && !profile.data" />
</template>
<script setup>
import {
	Button,
	call,
	createResource,
	TabButtons,
	Tooltip,
	toast,
	usePageMeta,
} from 'frappe-ui'
import { computed, inject, watch, ref, onMounted, watchEffect } from 'vue'
import PageHeader from '@/components/Layouts/PageHeader.vue'
import HeaderButton from '@/components/HeaderButton.vue'
import { sessionStore } from '@/stores/session'
import { Github, Linkedin, Twitter } from 'lucide-vue-next'
import { useRoute, useRouter } from 'vue-router'
import { convertToTitleCase } from '@/utils'
import { useScreenSize } from '@/utils/composables'
import UserAvatar from '@/components/UserAvatar.vue'
import NoPermission from '@/components/NoPermission.vue'
import NotFound from '@/pages/NotFound.vue'
import EditCoverImage from '@/components/Modals/EditCoverImage.vue'
import { openFormRoute } from '@/composables/useFormRoute'
import { safeUrl } from '@/utils/safeUrl'

const { user, brand } = sessionStore()
const $user = inject('$user')
const route = useRoute()
const router = useRouter()
const activeTab = ref('')
const readOnlyMode = window.read_only_mode
const { isMobile } = useScreenSize()

const props = defineProps({
	username: {
		type: String,
		required: true,
	},
})

onMounted(() => {
	if ($user.data) profile.reload()
	setActiveTab()
})

const profile = createResource({
	url: 'lms.lms.api.get_profile_details',
	makeParams() {
		return {
			username: props.username,
		}
	},
})

const coverImage = createResource({
	url: 'frappe.client.set_value',
	makeParams(values) {
		return {
			doctype: 'User',
			name: profile.data?.name,
			fieldname: 'cover_image',
			value: values.url,
		}
	},
	onSuccess() {
		profile.reload()
	},
})

const setActiveTab = () => {
	let fragments = route.path.split('/')
	let sections = ['certificates', 'roles', 'slots', 'schedule']
	sections.forEach((section) => {
		if (fragments.includes(section)) {
			activeTab.value = convertToTitleCase(section)
		}
	})
	// OSLMS-CUSTOM: About tab removed, Certificates is the default tab
	if (!activeTab.value) activeTab.value = 'Certificates'
}

// The edit form is a child route, not a tab, and `edit` matches none of the tab
// segments — so setActiveTab lands on About and this effect would push the About
// tab straight over a deep link to the form before it ever renders.
watchEffect(() => {
	if (!activeTab.value || route.name === 'ProfileEditForm') return
	let target = {
		About: { name: 'ProfileAbout' },
		Certificates: { name: 'ProfileCertificates' },
		Roles: { name: 'ProfileRoles' },
		Slots: { name: 'ProfileEvaluator' },
		Schedule: { name: 'ProfileEvaluationSchedule' },
	}[activeTab.value]
	router.push(target)
})

watch(
	() => props.username,
	() => {
		profile.reload()
	},
)

const editProfile = () => {
	openFormRoute(router, {
		name: 'ProfileEditForm',
		params: { username: props.username },
	})
}

const isSessionUser = () => {
	return $user.data?.name === profile.data?.name
}

const currentUserHasHigherAccess = () => {
	return $user.data?.is_evaluator || $user.data?.is_moderator
}

const isEvaluatorOrModerator = () => {
	return (
		profile.data?.roles?.includes('Batch Evaluator') ||
		profile.data?.roles?.includes('Moderator')
	)
}

const getTabButtons = () => {
	// OSLMS-CUSTOM: About tab removed
	let buttons = [{ label: __('Certificates'), value: 'Certificates' }]
	if ($user.data?.is_moderator) {
		buttons.push({ label: __('Roles'), value: 'Roles' })
	}

	// OSLMS-CUSTOM: Slots and Schedule tabs hidden (commented out)
	// if (currentUserHasHigherAccess() && isEvaluatorOrModerator()) {
	// 	buttons.push({ label: __('Slots'), value: 'Slots' })
	// 	buttons.push({ label: __('Schedule'), value: 'Schedule' })
	// }
	return buttons
}

const reloadUser = () => {
	call('frappe.sessions.clear')
		.then(() => {
			$user.reload().then(() => {
				profile.reload()
				toast.success(__('Session refreshed successfully'))
			})
		})
		.catch((err) => {
			toast.error(__('Failed to refresh session'))
			console.error(err)
		})
}

const breadcrumbs = computed(() => {
	let crumbs = [
		{
			label: __('People'),
		},
		{
			label: profile.data?.full_name,
			route: {
				name: 'Profile',
				params: {
					username: user.doc?.username,
				},
			},
		},
	]
	return crumbs
})

usePageMeta(() => {
	return {
		title: profile.data?.full_name,
		icon: brand.favicon,
	}
})
</script>
