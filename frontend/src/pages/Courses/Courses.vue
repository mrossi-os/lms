<template>
	<LayoutHeader>
		<template #left-header>
			<Breadcrumbs :items="breadcrumbs" />
		</template>
		<template #right-header>
			<Dropdown
				placement="right"
				side="bottom"
				v-if="canCreateCourse()"
				:options="courseMenu"
			>
				<template v-slot="{ open }">
					<Button variant="solid">
						<template #prefix>
							<span class="lucide-plus size-4" />
						</template>
						{{ __('Createsssss') }}
						<template #suffix>
							<span
								:class="[
									'lucide-chevron-down ms-1 size-4 transform transition-transform',
									open ? 'rotate-180' : '',
								]"
							/>
						</template>
					</Button>
				</template>
			</Dropdown>
		</template>
	</LayoutHeader>
	<div class="flex min-h-0 flex-1 flex-col p-5 pb-10">
		<div
			class="mb-5 flex flex-col justify-between space-y-4 lg:flex-row lg:items-center lg:space-y-0"
		>
			<div class="text-xl-semibold text-ink-gray-9">
				{{ __('All Courses') }}
			</div>
			<div
				class="flex flex-col space-y-4 lg:flex-row lg:items-center lg:gap-x-4 lg:space-y-0"
			>
				<TabButtons
					v-if="courseTabs.length > 1"
					:buttons="courseTabs"
					v-model="currentTab"
					class="w-fit"
				/>

				<FormControl
					v-model="title"
					:placeholder="__('Search')"
					type="text"
					class="w-full lg:w-40"
					@update:modelValue="updateCourses()"
				>
					<template #prefix>
						<span class="lucide-search size-4 text-ink-gray-5" />
					</template>
				</FormControl>

				<ClearableCombobox
					v-if="categoryOptions.length"
					v-model="currentCategory"
					:options="categoryOptions"
					:placeholder="__('Category')"
					@update:modelValue="updateCourses()"
					class="w-full lg:w-40"
				/>

				<Tooltip :text="__('Only show courses that offer a certificate')">
					<FormControl
						type="checkbox"
						v-model="certification"
						:label="__('Certification')"
						@change="updateCourses()"
					/>
				</Tooltip>
			</div>
		</div>
		<SkeletonLoader
			v-if="courses.list.loading && !courses.data"
			variant="cards"
			:count="8"
		/>
		<div
			v-else-if="courses.data?.length"
			class="grid grid-cols-1 gap-8 md:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4"
		>
			<router-link
				v-for="course in courses.data"
				:to="{ name: 'CourseDetail', params: { courseName: course.name } }"
			>
				<CourseCard :course="course" />
			</router-link>
		</div>
		<div v-else-if="!courses.list.loading" class="flex-1">
			<EmptyStateLayout name="Courses" icon="lucide-book-open" />
		</div>
		<div
			v-if="!courses.list.loading && courses.hasNextPage"
			class="flex justify-center mt-5"
		>
			<Button @click="courses.next()">
				{{ __('Load More') }}
			</Button>
		</div>
	</div>
	<NewCourseModal
		v-if="showCourseModal"
		v-model="showCourseModal"
		:courses="courses"
	/>

	<CourseImportModal
		v-if="showCourseImportModal"
		v-model="showCourseImportModal"
	/>
</template>
<script setup>
import {
	Breadcrumbs,
	Button,
	call,
	createListResource,
	createResource,
	Dropdown,
	FormControl,
	TabButtons,
	Tooltip,
	usePageMeta,
} from 'frappe-ui'
import ClearableCombobox from '@/components/Controls/ClearableCombobox.vue'
import { computed, inject, onMounted, provide, ref, watch } from 'vue'
import { sessionStore } from '@/stores/session'
import { canCreateCourse, searchLikeFilter } from '@/utils'
import { useLocalStorage } from '@/utils/composables'
import CourseCard from '@/components/CourseCard.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyStateLayout from '@/components/Layouts/EmptyStateLayout.vue'
import LayoutHeader from '@/components/Layouts/LayoutHeader.vue'
import { useRouter } from 'vue-router'
import NewCourseModal from '@/pages/Courses/NewCourseModal.vue'
import CourseImportModal from '@/pages/Courses/CourseImportModal.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')
const start = ref(0)
const pageLength = ref(30)
const currentCategory = ref(null)
const title = ref('')
const certification = ref(false)
const filters = ref({})
// Persist the selected tab so it survives leaving and returning to the list.
const currentTab = useLocalStorage('lms_courses_tab', 'live')
const { brand } = sessionStore()
const courseCount = ref(0)
const router = useRouter()
const showCourseModal = ref(false)
const showCourseImportModal = ref(false)

const tagResource = createResource({
	url: 'frappe.client.get_list',
	method: 'POST',
	params: {
		doctype: 'LMS OS Tag',
		fields: ['tag_name', 'color'],
		limit_page_length: 0,
	},
	auto: true,
})

const tagColorMap = computed(() => {
	if (!tagResource.data) return new Map()
	return new Map(tagResource.data.map((t) => [t.tag_name, t.color]))
})

provide('tagColorMap', tagColorMap)

onMounted(() => {
	// Students only have the "Enrolled" tab, so always land them there
	// regardless of any previously persisted value.
	if (user.data?.is_student) {
		currentTab.value = 'enrolled'
	}
	// Fall back to the first available tab if the persisted value isn't valid
	// for this user's role (e.g. role changed since it was stored).
	const validTabs = courseTabs.value.map((tab) => tab.value)
	if (!validTabs.includes(currentTab.value)) {
		currentTab.value = validTabs[0] || 'live'
	}
	setFiltersFromQuery()
	updateCourses()
	reloadCategories()
	getCourseCount()
})

const setFiltersFromQuery = () => {
	let queries = new URLSearchParams(location.search)
	title.value = queries.get('title') || ''
	currentCategory.value = queries.get('category') || null
	certification.value = queries.get('certification') || false
	const tab = queries.get('tab')
	// Only honor tabs the current user is actually allowed to see, so a stale
	// or crafted ?tab= can't push a student onto a hidden tab.
	if (tab && courseTabs.value.some((t) => t.value === tab)) {
		currentTab.value = tab
	}
	if (queries.get('newCourse') == '1') {
		showCourseModal.value = true
	}
}

const courses = createListResource({
	doctype: 'LMS Course',
	url: 'lms.lms.utils.get_courses',
	cache: ['courses', user.data?.name],
	pageLength: pageLength.value,
	start: start.value,
})

// get_course_categories returns plain { label, value } options, not doctype
// documents, so use a plain resource: createListResource's document machinery
// (name-keyed dataMap + offline doc cache) can leave `data` empty here. No
// persisted cache, so the list always loads fresh. Loaded on demand (not auto)
// because the option set is scoped to the active tab's filters.
const categories = createResource({
	url: 'lms.lms.utils.get_course_categories',
})

// Real category options (the backend always prepends an empty "clear" sentinel,
// which the ClearableCombobox provides on its own). Empty when the current tab
// has no categorized courses, so the combobox stays hidden instead of showing
// an empty dropdown.
const categoryOptions = computed(
	() => categories.data?.filter((c) => c.value) || [],
)

// The category set depends on the active tab (Enrolled, Created, ...), so
// refetch it with the current tab filters. The backend ignores the narrowing
// filters (picked category, search text, certification), so the list stays
// stable as those change and only needs reloading when the tab changes.
const reloadCategories = () => {
	categories.reload({ filters: filters.value })
}

const getCourseCount = () => {
	if (!user.data) return
	if (!user.data.is_moderator) return
	call('frappe.client.get_count', {
		doctype: 'LMS Course',
	}).then((data) => {
		courseCount.value = data
	})
}

const updateCourses = () => {
	updateFilters()
	courses.update({
		filters: filters.value,
	})
	courses.reload()
}

const updateFilters = () => {
	updateCategoryFilter()
	updateTitleFilter()
	updateCertificationFilter()
	updateTabFilter()
	updateStudentFilter()
	setQueryParams()
}

const updateCategoryFilter = () => {
	if (currentCategory.value) {
		filters.value['category'] = currentCategory.value
	} else {
		delete filters.value['category']
	}
}

const updateTitleFilter = () => {
	const titleFilter = searchLikeFilter(title.value)
	if (titleFilter) {
		filters.value['title'] = titleFilter
	} else {
		delete filters.value['title']
	}
}

const updateCertificationFilter = () => {
	if (certification.value) {
		filters.value['certification'] = 1
	} else {
		delete filters.value['certification']
	}
}

const updateTabFilter = () => {
	delete filters.value['live']
	delete filters.value['created']
	delete filters.value['published_on']
	delete filters.value['upcoming']

	if (currentTab.value == 'enrolled' && user.data?.is_student) {
		filters.value['enrolled'] = 1
		delete filters.value['published']
	} else {
		delete filters.value['published']
		delete filters.value['enrolled']

		if (currentTab.value == 'live') {
			filters.value['published'] = 1
			filters.value['upcoming'] = 0
			filters.value['live'] = 1
		} else if (currentTab.value == 'upcoming') {
			filters.value['upcoming'] = 1
		} else if (currentTab.value == 'new') {
			filters.value['published'] = 1
			filters.value['published_on'] = [
				'>=',
				dayjs().add(-3, 'month').format('YYYY-MM-DD'),
			]
		} else if (currentTab.value == 'created') {
			filters.value['created'] = 1
		} else if (currentTab.value == 'unpublished') {
			filters.value['published'] = 0
		}
	}
}

const updateStudentFilter = () => {
	if (
		!user.data ||
		(user.data?.is_student &&
			currentTab.value != 'enrolled' &&
			currentTab.value != 'upcoming')
	) {
		filters.value['published'] = 1
	}
}

const setQueryParams = () => {
	let queries = new URLSearchParams(location.search)
	let filterKeys = {
		title: title.value,
		category: currentCategory.value,
		certification: certification.value,
	}

	Object.keys(filterKeys).forEach((key) => {
		if (filterKeys[key]) {
			queries.set(key, filterKeys[key])
		} else {
			queries.delete(key)
		}
	})

	let queryString = ''
	if (queries.toString()) {
		queryString = `?${queries.toString()}`
	}

	history.replaceState({}, '', `${location.pathname}${queryString}`)
}

watch(currentTab, () => {
	// Each tab has its own category set, so a selection made on another tab no
	// longer applies; clear it before refetching the tab-scoped options.
	currentCategory.value = null
	updateCourses()
	reloadCategories()
})

const courseTabs = computed(() => {
	// Students only see the courses they are enrolled in — the public
	// "Published" and "Upcoming" tabs are hidden for them.
	if (user.data?.is_student) {
		return [{ label: __('Enrolled'), value: 'enrolled' }]
	}

	let tabs = [
		{
			label: __('Published'),
			value: 'live',
		},
		{
			label: __('Upcoming'),
			value: 'upcoming',
		},
	]
	if (
		user.data?.is_moderator ||
		user.data?.is_instructor ||
		user.data?.is_evaluator
	) {
		tabs.push({ label: __('Created'), value: 'created' })
		tabs.push({ label: __('Unpublished'), value: 'unpublished' })
	}
	return tabs
})

const courseMenu = computed(() => {
	return [
		{
			label: __('New Course'),
			icon: 'book-open',
			onClick() {
				showCourseModal.value = true
			},
		},
		{
			label: __('Import via Data Import Tool'),
			icon: 'upload',
			onClick() {
				router.push({
					name: 'NewDataImport',
					params: { doctype: 'LMS Course' },
				})
			},
		},
		{
			label: __('Import via ZIP'),
			icon: 'folder-plus',
			onClick() {
				showCourseImportModal.value = true
			},
		},
	]
})

const breadcrumbs = computed(() => [
	{
		label: __('Courses'),
		route: { name: 'Courses' },
	},
])

usePageMeta(() => {
	return {
		title: __('Courses'),
		icon: brand.favicon,
	}
})
</script>
