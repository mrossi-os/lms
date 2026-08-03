<template>
	<LayoutHeader>
		<template #left-header>
			<Breadcrumbs :items="breadcrumbs" />
		</template>
		<template #right-header>
			<Dropdown
				v-if="canCreateBatch()"
				:options="[
					{
						label: __('New Batch'),
						icon: 'users',
						onClick() {
							showBatchModal = true
						},
					},
					{
						label: __('Import Batch'),
						icon: 'upload',
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
	</LayoutHeader>
	<div class="flex min-h-0 flex-1 flex-col p-5 pb-10">
		<div
			class="mb-5 flex flex-col justify-between space-y-4 lg:flex-row lg:items-center lg:space-y-0"
		>
			<div class="text-xl-semibold text-ink-gray-9">
				{{ __('All Batches') }}
			</div>
			<div
				class="flex flex-col space-y-3 lg:flex-row lg:items-center lg:gap-x-4 lg:space-y-0"
			>
				<TabButtons
					v-if="user.data && !is_student"
					:buttons="batchTabs"
					v-model="currentTab"
					class="w-fit"
				/>
				<div class="grid grid-cols-2 gap-2">
					<FormControl
						v-model="title"
						:placeholder="__('Search')"
						type="text"
						class="min-w-40"
						@update:modelValue="updateBatches()"
					>
						<template #prefix>
							<span class="lucide-search size-4 text-ink-gray-5" />
						</template>
					</FormControl>
					<ClearableCombobox
						v-if="categories.length"
						v-model="currentCategory"
						:options="categoryOptions"
						:placeholder="__('Category')"
						@update:modelValue="updateBatches()"
					/>
				</div>
			</div>
		</div>
		<SkeletonLoader
			v-if="batches.list.loading && !batches.data"
			variant="cards"
			:count="8"
		/>
		<div
			v-else-if="batches.data?.length"
			class="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
		>
			<router-link
				v-for="batch in batches.data"
				:to="{ name: 'BatchDetail', params: { batchName: batch.name } }"
			>
				<BatchCard :batch="batch" />
			</router-link>
		</div>
		<div v-else-if="!batches.list.loading" class="flex-1">
			<EmptyStateLayout name="Batches" icon="lucide-users" />
		</div>

		<div
			v-if="!batches.list.loading && batches.hasNextPage"
			class="mt-5 flex justify-center"
		>
			<Button @click="batches.next()">
				{{ __('Load More') }}
			</Button>
		</div>
	</div>
	<NewBatchModal
		v-if="showBatchModal"
		v-model="showBatchModal"
		:batches="batches"
	/>
</template>
<script setup>
import {
	Breadcrumbs,
	Button,
	createListResource,
	Dropdown,
	FormControl,
	TabButtons,
	usePageMeta,
} from 'frappe-ui'
import ClearableCombobox from '@/components/Controls/ClearableCombobox.vue'
import { computed, inject, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { sessionStore } from '@/stores/session'
import { useLocalStorage } from '@/utils/composables'
import { searchLikeFilter } from '@/utils'
import BatchCard from '@/pages/Batches/components/BatchCard.vue'
import SkeletonLoader from '@/components/SkeletonLoader.vue'
import EmptyStateLayout from '@/components/Layouts/EmptyStateLayout.vue'
import LayoutHeader from '@/components/Layouts/LayoutHeader.vue'
import NewBatchModal from '@/pages/Batches/components/NewBatchModal.vue'

const user = inject('$user')
const dayjs = inject('$dayjs')
const { brand } = sessionStore()
const start = ref(0)
const pageLength = ref(20)
const categories = ref([])
const currentCategory = ref(null)
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
	certification.value = queries.get('certification') || false
}

const batches = createListResource({
	doctype: 'LMS Batch',
	url: 'lms.lms.utils.get_batches',
	cache: ['batches', user.data?.name],
	pageLength: pageLength.value,
	start: start.value,
})

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
	if (currentCategory.value && currentCategory.value !== ALL_CATEGORIES) {
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
	orderBy.value = 'start_date'
	if (!user.data) {
		return
	}
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
