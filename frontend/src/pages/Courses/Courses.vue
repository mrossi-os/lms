<template>
	<ListPage
		:breadcrumbs="breadcrumbs"
		:title="__('All Courses')"
		:rows="courses.data || []"
		:loading="courses.list.loading || reloading"
		:total-count="courseCount"
		:has-next-page="courses.hasNextPage"
		v-model:page-length="pageLength"
		empty-name="Courses"
		empty-icon="lucide-book-open"
		@load-more="courses.next()"
	>
		<template #actions>
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
						{{ __('Create') }}
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

		<template #filters>
			<!-- OSLMS-CUSTOM: students only have the Enrolled tab, so the switcher is hidden when a single tab is left -->
			<TabButtons
				v-if="courseTabs.length > 1"
				:options="courseTabs"
				v-model="currentTab"
				class="!w-fit shrink-0"
			/>
			<!-- OSLMS-CUSTOM: reload on update:modelValue so the search reads the current value and clearing it clears the filter -->
			<FormControl
				v-model="title"
				:placeholder="__('Search')"
				:aria-label="__('Search')"
				type="text"
				@update:modelValue="updateCourses()"
			>
				<template #prefix>
					<span class="lucide-search size-4 text-ink-gray-5" />
				</template>
			</FormControl>
			<!-- OSLMS-CUSTOM: category options scoped to the active tab; hidden when the tab has no categories -->
			<ClearableCombobox
				v-if="categoryOptions.length"
				v-model="currentCategory"
				:options="categoryOptions"
				:placeholder="__('Category')"
				@update:modelValue="updateCourses()"
			/>
			<ToggleFilter
				:modelValue="certification"
				:label="__('Certification')"
				:mobileLabel="__('Certification available')"
				:tooltip="__('Only show courses that offer a certificate')"
				@update:modelValue="setCertification"
			/>
		</template>

		<template #card="{ row }">
			<router-link
				:to="{ name: 'CourseDetail', params: { courseName: row.name } }"
			>
				<CourseCard :course="row" />
			</router-link>
		</template>
	</ListPage>

	<router-view />
</template>
<script setup>
import {
	Button,
	createListResource,
	createResource,
	Dropdown,
	FormControl,
	TabButtons,
	usePageMeta,
} from 'frappe-ui'
import ClearableCombobox from '@/components/Controls/ClearableCombobox.vue'
import ToggleFilter from '@/components/Controls/ToggleFilter.vue'
import ListPage from '@/components/Layouts/ListPage.vue'
import { computed, inject, onMounted, provide, ref, watch } from 'vue'
import { sessionStore } from '@/stores/session'
import { canCreateCourse, searchLikeFilter } from '@/utils'
import { useLocalStorage } from '@/utils/composables'
import CourseCard from '@/components/CourseCard.vue'
import { useRouter } from 'vue-router'
import { openFormRoute } from '@/composables/useFormRoute'

const user = inject('$user')
const dayjs = inject('$dayjs')
const start = ref(0)
const currentCategory = ref(null)
const title = ref('')
const certification = ref(false)

const setCertification = (value) => {
	certification.value = value
	updateCourses()
}
const filters = ref({})
// OSLMS-CUSTOM: persisted tab selection
// Persist the selected tab so it survives leaving and returning to the list.
const currentTab = useLocalStorage('lms_courses_tab', 'live')
const { brand } = sessionStore()
const router = useRouter()

// OSLMS-CUSTOM: LMS OS Tag colors provided to CourseCard's CourseTagBadges
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
	// OSLMS-CUSTOM: students always land on the Enrolled tab
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
})

const setFiltersFromQuery = () => {
	let queries = new URLSearchParams(location.search)
	title.value = queries.get('title') || ''
	currentCategory.value = queries.get('category') || null
	// `|| false` would keep the raw string, so ?certification=false read as on.
	certification.value = queries.get('certification') === 'true'
	const tab = queries.get('tab')
	// OSLMS-CUSTOM: ignore a ?tab= the user is not allowed to see
	// Only honor tabs the current user is actually allowed to see, so a stale
	// or crafted ?tab= can't push a student onto a hidden tab.
	if (tab && courseTabs.value.some((t) => t.value === tab)) {
		currentTab.value = tab
	}
	// Compatibility shim: ?newCourse=1 was this page's ad-hoc deep link before
	// /courses/new existed. BatchCourseModal.vue:27 still emits it, as may
	// bookmarks and anything outside the SPA, so forward it rather than drop it.
	// replace(), so the query-param URL is not left behind as an entry the user
	// can go Back to and re-open the form from.
	if (queries.get('newCourse') == '1') {
		router.replace({ name: 'NewCourse' })
	}
}

const courses = createListResource({
	doctype: 'LMS Course',
	url: 'lms.lms.utils.get_courses',
	cache: ['courses', user.data?.name],
	pageLength: 24,
	start: start.value,
})

// The tabs filter on `enrolled`, `created` and `live`, which are not fields,
// so `frappe.client.get_count` cannot answer this; only the endpoint that
// resolves them can. Without it the footer can say how many rows it has but
// not how many there are.
const courseCountResource = createResource({
	url: 'lms.lms.utils.get_course_count',
	makeParams: () => ({ filters: filters.value }),
	onError: (error) => {
		console.error(error)
	},
})

const courseCount = computed(() => courseCountResource.data ?? null)

const getCourseCount = () => {
	// Same sequencing hazard as the list: nothing orders the responses, so a
	// slow count for filters the user has left would overwrite the current one.
	courseCountResource.abort()
	courseCountResource.submit()
}

// `list.loading` goes false mid-request: the aborted fetch's tail resolves
// after the new reload() has started and clears the flag for it, so the empty
// state flashes until the reload lands.
const reloading = ref(false)

const reloadCourses = async () => {
	reloading.value = true
	try {
		await courses.reload()
	} finally {
		reloading.value = false
	}
}

const pageLength = computed({
	get: () => courses.pageLength,
	set: (value) => {
		// reload() refetches only the rows already loaded when start > 0, so
		// without rewinding to the first page a bigger page size changes nothing.
		courses.update({ pageLength: value, start: 0 })
		reloadCourses()
	},
})

// OSLMS-CUSTOM: tab-scoped category options loaded with a plain resource
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

const updateCourses = () => {
	updateFilters()
	// createResource keeps no request sequence: every response assigns
	// `data`, so a slow fetch for filters the user has already left repaints
	// the list with the wrong courses seconds later. Cancel it first: an
	// aborted fetch is swallowed and never reaches the list.
	courses.list.abort()
	courses.update({
		filters: filters.value,
	})
	reloadCourses()
	getCourseCount()
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
	// OSLMS-CUSTOM: search words matched independently
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

// OSLMS-CUSTOM: no published=1 filter for students on the Upcoming tab (batch access to unpublished courses)
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

	// Carry the existing state forward rather than replacing it with `{}`. This
	// page hosts form child routes whose open/close semantics hang off a marker
	// in history.state, and that marker only survives a reload through
	// window.history. `{}` also being truthy means vue-router never re-seeds its
	// own `position` key after such a reload, so every later pop delta is NaN.
	history.replaceState(history.state, '', `${location.pathname}${queryString}`)
}

watch(currentTab, () => {
	// OSLMS-CUSTOM: clear the category and refetch the tab-scoped options
	// Each tab has its own category set, so a selection made on another tab no
	// longer applies; clear it before refetching the tab-scoped options.
	currentCategory.value = null
	updateCourses()
	reloadCategories()
})

const courseTabs = computed(() => {
	// OSLMS-CUSTOM: students see only the Enrolled tab
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

// OSLMS-CUSTOM: file-based course import hidden from Gestore (System Managers keep it)
// A "Gestore" may only create courses manually, so the file-based entries
// (Data Import tool, ZIP) are hidden for them. System Managers keep them —
// including the Administrator, who implicitly holds every role and would
// otherwise lose the import too.
const canImportCourse = computed(() => {
	const roles = user.data?.roles || []
	if (!roles.includes('Gestore')) return true
	return !!user.data?.is_system_manager
})

const courseMenu = computed(() => {
	const menu = [
		{
			label: __('New Course'),
			icon: 'lucide-book-open',
			onClick() {
				// openFormRoute, not a bare router.push: it stamps the history
				// entry so the form's own close() pops it instead of replacing.
				openFormRoute(router, { name: 'NewCourse' })
			},
		},
	]

	// OSLMS-CUSTOM: file-based course import hidden from Gestore
	if (!canImportCourse.value) return menu

	menu.push(
		{
			label: __('Import via Data Import Tool'),
			icon: 'lucide-upload',
			onClick() {
				router.push({
					name: 'NewDataImport',
					params: { doctype: 'LMS Course' },
				})
			},
		},
		{
			label: __('Import via ZIP'),
			icon: 'lucide-folder-plus',
			onClick() {
				openFormRoute(router, { name: 'CourseImport' })
			},
		},
	)

	return menu
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
