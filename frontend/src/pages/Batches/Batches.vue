<template>
	<ListPage
		:breadcrumbs="breadcrumbs"
		:title="__('All Batches')"
		:rows="batches.data || []"
		:loading="batches.list.loading"
		:has-next-page="batches.hasNextPage"
		v-model:page-length="pageLength"
		empty-name="Batches"
		empty-icon="lucide-users"
		@load-more="batches.next()"
	>
		<template #actions>
			<Dropdown
				v-if="canCreateBatch()"
				:options="[
					{
						label: __('New Batch'),
						icon: 'lucide-users',
						onClick() {
							showBatchModal = true
						},
					},
					{
						label: __('Import Batch'),
						icon: 'lucide-upload',
						onClick() {
							router.push({
								name: 'NewDataImport',
								params: { doctype: 'LMS Batch' },
							})
						},
					},
				]"
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

		<template #tabs>
			<!-- OSLMS-CUSTOM: students get no tab bar; their batch list is pinned to Enrolled -->
			<TabButtons
				v-if="user.data && !is_student"
				:options="batchTabs"
				v-model="currentTab"
				class="w-fit"
			/>
		</template>

		<template #filters>
			<!-- OSLMS-CUSTOM: search matches words independently and reloads on update:modelValue -->
			<FormControl
				v-model="title"
				:placeholder="__('Search')"
				:aria-label="__('Search')"
				type="text"
				class="w-full sm:min-w-40"
				@update:modelValue="updateBatches()"
			>
				<template #prefix>
					<span class="lucide-search size-4 text-ink-gray-5" />
				</template>
			</FormControl>
			<!-- OSLMS-CUSTOM: category options start with an "All" entry that clears the filter -->
			<ClearableCombobox
				v-if="categories.length"
				v-model="currentCategory"
				:options="categoryOptions"
				:placeholder="__('Category')"
				class="w-full sm:w-auto"
				@update:modelValue="updateBatches()"
			/>
		</template>

		<!-- OSLMS-CUSTOM: upstream "Certification" filter checkbox removed (still reachable via ?certification=true) -->
		<!-- The upstream #toggles slot (ToggleFilter) is omitted on purpose: ListPageHeader
		     renders the toggle strip only when the slot exists. -->

		<template #card="{ row }">
			<router-link
				:to="{ name: 'BatchDetail', params: { batchName: row.name } }"
			>
				<BatchCard :batch="row" />
			</router-link>
		</template>
	</ListPage>

	<NewBatchModal
		v-if="showBatchModal"
		v-model="showBatchModal"
		:batches="batches"
	/>
</template>
<script setup>
import {
	Button,
	createListResource,
	Dropdown,
	FormControl,
	TabButtons,
	usePageMeta,
} from 'frappe-ui'
import ClearableCombobox from '@/components/Controls/ClearableCombobox.vue'
import ToggleFilter from '@/components/Controls/ToggleFilter.vue'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { sessionStore } from '@/stores/session'
import { useLocalStorage } from '@/utils/composables'
import { searchLikeFilter } from '@/utils'
import BatchCard from '@/pages/Batches/components/BatchCard.vue'
import ListPage from '@/components/Layouts/ListPage.vue'
import NewBatchModal from '@/pages/Batches/components/NewBatchModal.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')
const { brand } = sessionStore()
const start = ref(0)
const categories = ref([])
const currentCategory = ref(null)
// OSLMS-CUSTOM: All sentinel lets the user clear the category filter
// Sentinel for the "All" category option. There's otherwise no way to clear a
// selected category from the dropdown, so selecting "All" resets the filter and
// shows every batch, with or without a category.
const ALL_CATEGORIES = '__all__'
const categoryOptions = computed(() => [
	{ label: __('All'), value: ALL_CATEGORIES },
	...categories.value.filter((c) => c.value),
])
const title = ref('')
const certification = ref(false)
const filters = ref({})
const is_student = computed(() => user.data?.is_student)
// OSLMS-CUSTOM: role-based default tab (Valutatore falls back to All)
// Managers default to the "Upcoming" tab; students to "Enrolled". Other roles
// (e.g. a scoped Valutatore) don't get those tabs, so they default to "All".
const isListManager = computed(
	() =>
		user.data?.is_moderator ||
		user.data?.is_instructor ||
		user.data?.is_evaluator,
)
const defaultTab = is_student.value
	? 'enrolled'
	: isListManager.value
		? 'upcoming'
		: 'all'
// OSLMS-CUSTOM: selected tab persisted per browser, never for students
// Persist the selected tab so it survives leaving and returning to the list.
// Students are deliberately kept out of that: they have no tab bar (see the
// TabButtons v-if) and always see their own batches, while `lms_batches_tab` is
// a per-browser key — an "all" left there by another user of the same browser
// would strand them on an empty list (updateStudentFilter narrows it to future
// published batches) with no visible tab to switch back.
const currentTab = is_student.value
	? ref('enrolled')
	: useLocalStorage('lms_batches_tab', defaultTab)
const orderBy = ref('start_date')
const readOnlyMode = window.read_only_mode
const router = useRouter()
const showBatchModal = ref(false)

onMounted(() => {
	// OSLMS-CUSTOM: discard a persisted tab not valid for the current role
	// Fall back to the default tab if the persisted value isn't available for
	// this user's role (e.g. role changed since it was stored).
	const validTabs = batchTabs.value.map((tab) => tab.value)
	if (!validTabs.includes(currentTab.value)) {
		currentTab.value = defaultTab
	}
	setFiltersFromQuery()
	updateBatches()
	categories.value = [
		{
			label: '',
			value: null,
		},
	]
})

const setFiltersFromQuery = () => {
	let queries = new URLSearchParams(location.search)
	title.value = queries.get('title') || ''
	currentCategory.value = queries.get('category') || null
	// `|| false` would keep the raw string, so ?certification=false read as on.
	certification.value = queries.get('certification') === 'true'
}

const batches = createListResource({
	doctype: 'LMS Batch',
	url: 'lms.lms.utils.get_batches',
	cache: ['batches', user.data?.name],
	pageLength: 24,
	start: start.value,
})

const pageLength = computed({
	get: () => batches.pageLength,
	set: (value) => {
		// reload() ignores pageLength while start > 0 and refetches the rows
		// already loaded, so a size change after Load More would do nothing.
		batches.update({ pageLength: value, start: 0 })
		batches.reload()
	},
})

const setCertification = (value) => {
	certification.value = value
	updateBatches()
}

const setCategories = (data) => {
	let allCategories = data.map((batch) => batch.category)
	allCategories = allCategories.filter(
		(category, index) => allCategories.indexOf(category) === index && category,
	)
	if (categories.value.length <= allCategories.length) {
		updateCategories(data)
	}
}

const updateBatches = () => {
	updateFilters()
	batches.update({
		filters: filters.value,
		orderBy: orderBy.value,
	})
	batches.reload().then((data) => {
		setCategories(data)
	})
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
	// OSLMS-CUSTOM: All sentinel means no category filter
	if (currentCategory.value && currentCategory.value !== ALL_CATEGORIES) {
		filters.value['category'] = currentCategory.value
	} else {
		delete filters.value['category']
	}
}

const updateTitleFilter = () => {
	// OSLMS-CUSTOM: word-by-word LIKE search
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
	orderBy.value = 'start_date'
	if (!user.data) {
		return
	}
	// OSLMS-CUSTOM: Enrolled tab filters by enrollment for every member, not only students
	if (currentTab.value == 'enrolled') {
		// The "Enrolled" tab is offered to every non-admin user (students AND, e.g.,
		// a Valutatore who is also enrolled). Don't gate the filter on is_student,
		// or those non-student members see all/assigned batches instead of their own.
		filters.value['enrolled'] = 1
		delete filters.value['start_date']
		delete filters.value['end_date']
		delete filters.value['published']
		orderBy.value = 'start_date desc'
	} else if (is_student.value) {
		delete filters.value['enrolled']
	} else {
		// Clear the enrolled filter when leaving the Enrolled tab; otherwise a
		// non-student member (e.g. a Valutatore) keeps filtering by enrollment
		// after switching to All/Upcoming/etc.
		delete filters.value['enrolled']
		delete filters.value['start_date']
		delete filters.value['end_date']
		delete filters.value['published']
		orderBy.value = 'start_date desc'
		if (currentTab.value == 'upcoming') {
			filters.value['start_date'] = ['>=', dayjs().format('YYYY-MM-DD')]
			filters.value['published'] = 1
			orderBy.value = 'start_date'
		} else if (currentTab.value == 'archived') {
			// OSLMS-CUSTOM: archived = batches already ended (end_date), not started
			filters.value['end_date'] = ['<=', dayjs().format('YYYY-MM-DD')]
		} else if (currentTab.value == 'unpublished') {
			filters.value['published'] = 0
		}
	}
}

const updateStudentFilter = () => {
	if (!user.data || (is_student.value && currentTab.value != 'enrolled')) {
		filters.value['start_date'] = ['>=', dayjs().format('YYYY-MM-DD')]
		filters.value['published'] = 1
	}
}

const setQueryParams = () => {
	let queries = new URLSearchParams(location.search)
	let filterKeys = {
		title: title.value,
		// The "All" sentinel means "no category filter" — keep it out of the URL.
		category:
			currentCategory.value === ALL_CATEGORIES ? null : currentCategory.value,
		certification: certification.value,
	}

	Object.keys(filterKeys).forEach((key) => {
		if (filterKeys[key]) {
			queries.set(key, filterKeys[key])
		} else {
			queries.delete(key)
		}
	})

	history.replaceState(
		{},
		'',
		`${location.pathname}${queries.size > 0 ? `?${queries.toString()}` : ''}`,
	)
}

const updateCategories = (data) => {
	data.forEach((batch) => {
		if (
			batch.category &&
			!categories.value.find((category) => category.value === batch.category)
		)
			categories.value.push({
				label: batch.category,
				value: batch.category,
			})
	})
}

watch(currentTab, () => {
	updateBatches()
})

const batchTabs = computed(() => {
	// OSLMS-CUSTOM: Enrolled is the only tab offered to a student
	// A student's tab is pinned to "Enrolled" (see currentTab), so that's the
	// only valid value for them. Mirrors courseTabs on the Courses page.
	if (is_student.value) {
		return [{ label: __('Enrolled'), value: 'enrolled' }]
	}

	let tabs = [
		{
			label: __('All'),
			value: 'all',
		},
	]

	if (
		user.data?.is_moderator ||
		user.data?.is_instructor ||
		user.data?.is_evaluator
	) {
		tabs.push({ label: __('Upcoming'), value: 'upcoming' })
		tabs.push({ label: __('Archived'), value: 'archived' })
		tabs.push({ label: __('Unpublished'), value: 'unpublished' })
	} else if (user.data) {
		tabs.push({ label: __('Enrolled'), value: 'enrolled' })
	}
	return tabs
})

const canCreateBatch = () => {
	if (readOnlyMode) return false
	if (
		user.data?.is_moderator ||
		user.data?.is_instructor ||
		user.data?.is_evaluator
	)
		return true
	return false
}

const breadcrumbs = computed(() => [
	{
		label: __('Batches'),
		route: { name: 'Batches' },
	},
])

usePageMeta(() => {
	return {
		title: __('Batches'),
		icon: brand.favicon,
	}
})
</script>
