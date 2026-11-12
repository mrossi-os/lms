<template>
	<div class="space-y-5">
		<section class="space-y-4 rounded-md border card">
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
				<Link
					v-model="filters.user"
					doctype="User"
					:label="__('Student')"
					:placeholder="__('All students')"
					variant="outline"
				/>
				<Link
					v-model="filters.course"
					doctype="LMS Course"
					:label="__('Course')"
					:placeholder="__('All courses')"
					variant="outline"
				/>
				<FormControl
					v-model="filters.event_type"
					type="select"
					:options="eventOptions"
					:label="__('Event')"
					variant="outline"
				/>
				<FormControl
					v-model="filters.from_date"
					type="date"
					:placeholder="__('Select date')"
					:label="__('From')"
					variant="outline"
				/>
				<FormControl
					v-model="filters.to_date"
					type="date"
					:placeholder="__('Select date')"
					:label="__('To')"
					variant="outline"
				/>
			</div>
			<div class="flex flex-wrap justify-end gap-2">
				<Button variant="ghost" @click="clear">
					{{ __('Clear filters') }}
				</Button>
				<Button variant="solid" :loading="loading" @click="search">
					{{ __('Search') }}
				</Button>
			</div>
		</section>

		<!-- Student summary -->
		<section
			v-if="summary"
			class="space-y-4 rounded-md border card"
		>
			<div class="flex flex-wrap items-baseline justify-between gap-2">
				<h2 class="text-base font-semibold text-ink-gray-9">
					{{ summary.full_name }}
				</h2>
				<div class="flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-gray-6">
					<span
						>{{ __('Lesson visits') }}:
						<b class="text-ink-gray-9">{{ summary.totals.visits }}</b></span
					>
					<span
						>{{ __('Presence') }}:
						<b class="text-ink-gray-9">{{
							formatHM(summary.totals.presence_seconds)
						}}</b></span
					>
					<span
						>{{ __('Active Time') }}:
						<b class="text-ink-gray-9">{{
							formatHM(summary.totals.active_seconds)
						}}</b></span
					>
					<span v-if="summary.totals.video_seconds"
						>{{ __('Video time') }}:
						<b class="text-ink-gray-9">{{
							formatHM(summary.totals.video_seconds)
						}}</b></span
					>
				</div>
			</div>

			<div>
				<h3 class="mb-2 text-sm font-semibold text-ink-gray-8">
					{{ __('Time per lesson') }}
				</h3>
				<div v-if="!summary.lessons.length" class="text-sm text-ink-gray-5">
					{{ __('No lesson visits in this period') }}
				</div>
				<div v-else class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="text-left text-ink-gray-5">
								<th class="py-1.5 pr-3 font-medium">{{ __('Course') }}</th>
								<th class="py-1.5 pr-3 font-medium">{{ __('Lesson') }}</th>
								<th class="py-1.5 pr-3 font-medium">{{ __('Visits') }}</th>
								<th class="py-1.5 pr-3 font-medium">{{ __('Presence') }}</th>
								<th class="py-1.5 pr-3 font-medium">{{ __('Active Time') }}</th>
								<th class="py-1.5 pr-3 font-medium">{{ __('Video time') }}</th>
								<th class="py-1.5 font-medium">{{ __('Last visit') }}</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="row in summary.lessons"
								:key="row.course + row.lesson"
								class="border-t border-outline-gray-1"
							>
								<td class="py-1.5 pr-3 text-ink-gray-7">{{ row.course_title }}</td>
								<td class="py-1.5 pr-3 text-ink-gray-8">{{ row.lesson_title }}</td>
								<td class="py-1.5 pr-3">{{ row.visits }}</td>
								<td class="py-1.5 pr-3">{{ formatHM(row.presence_seconds) }}</td>
								<td class="py-1.5 pr-3">{{ formatHM(row.active_seconds) }}</td>
								<td class="py-1.5 pr-3">{{ formatHM(row.video_seconds) }}</td>
								<td class="py-1.5 text-ink-gray-6">{{ formatDateTime(row.last_at) }}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			<div v-if="summary.days.length">
				<h3 class="mb-2 text-sm font-semibold text-ink-gray-8">
					{{ __('Summary per day') }}
				</h3>
				<div class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="text-left text-ink-gray-5">
								<th class="py-1.5 pr-3 font-medium">{{ __('Date') }}</th>
								<th class="py-1.5 pr-3 font-medium">{{ __('First entry') }}</th>
								<th class="py-1.5 pr-3 font-medium">{{ __('Last signal') }}</th>
								<th class="py-1.5 pr-3 font-medium">{{ __('Lessons') }}</th>
								<th class="py-1.5 pr-3 font-medium">{{ __('Presence') }}</th>
								<th class="py-1.5 pr-3 font-medium">{{ __('Active Time') }}</th>
								<th class="py-1.5 font-medium">{{ __('Video time') }}</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="day in summary.days"
								:key="day.date"
								class="border-t border-outline-gray-1"
							>
								<td class="py-1.5 pr-3 text-ink-gray-8">{{ formatDate(day.date) }}</td>
								<td class="py-1.5 pr-3">{{ formatTime(day.first_at) }}</td>
								<td class="py-1.5 pr-3">{{ formatTime(day.last_at) }}</td>
								<td class="py-1.5 pr-3">{{ day.lessons }}</td>
								<td class="py-1.5 pr-3">{{ formatHM(day.presence_seconds) }}</td>
								<td class="py-1.5 pr-3">{{ formatHM(day.active_seconds) }}</td>
								<td class="py-1.5">{{ formatHM(day.video_seconds) }}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			<div
				v-if="summary.simulations.length || summary.tutor_questions.length"
				class="grid grid-cols-1 gap-4 sm:grid-cols-2"
			>
				<div v-if="summary.simulations.length">
					<h3 class="mb-2 text-sm font-semibold text-ink-gray-8">
						{{ __('AI simulations') }}
					</h3>
					<ul class="space-y-1 text-sm">
						<li
							v-for="sim in summary.simulations"
							:key="sim.name"
							class="text-ink-gray-7"
						>
							{{ formatDateTime(sim.started_at) }} · {{ sim.scenario_title }} ·
							{{ __(sim.status) }}
							<template v-if="sim.session_seconds">
								· {{ formatHM(sim.session_seconds) }}</template
							>
						</li>
					</ul>
				</div>
				<div v-if="summary.tutor_questions.length">
					<h3 class="mb-2 text-sm font-semibold text-ink-gray-8">
						{{ __('Questions to the AI tutor') }}
					</h3>
					<ul class="space-y-1 text-sm">
						<li
							v-for="(question, index) in summary.tutor_questions"
							:key="index"
							class="text-ink-gray-7"
						>
							{{ formatDateTime(question.creation) }} ·
							{{ question.lesson_title || question.course_title }}
						</li>
					</ul>
				</div>
			</div>
		</section>

		<!-- Timeline -->
		<section class="space-y-3 rounded-md border card">
			<h2 class="text-base font-semibold text-ink-gray-9">
				{{ __('Events') }}
			</h2>
			<div
				v-if="!events.length"
				class="py-6 text-center text-sm text-ink-gray-5"
			>
				{{ loading ? __('Loading...') : __('No events found') }}
			</div>
			<div v-else class="overflow-x-auto">
				<table class="w-full text-sm">
					<thead>
						<tr class="text-left text-ink-gray-5">
							<th class="py-1.5 pr-3 font-medium">{{ __('Date and time') }}</th>
							<th class="py-1.5 pr-3 font-medium">{{ __('Event') }}</th>
							<th class="py-1.5 pr-3 font-medium">{{ __('Student') }}</th>
							<th class="py-1.5 pr-3 font-medium">{{ __('Where') }}</th>
							<th class="py-1.5 pr-3 font-medium">{{ __('Details') }}</th>
							<th class="py-1.5 font-medium">{{ __('Device') }}</th>
						</tr>
					</thead>
					<tbody>
						<tr
							v-for="event in events"
							:key="event.name"
							class="border-t border-outline-gray-1 align-top"
						>
							<td class="whitespace-nowrap py-1.5 pr-3 text-ink-gray-6">
								{{ formatDateTime(event.timestamp) }}
							</td>
							<td class="py-1.5 pr-3 text-ink-gray-9">{{ event.event_label }}</td>
							<td class="py-1.5 pr-3 text-ink-gray-7">
								{{ event.redacted ? __('Erased') : event.full_name }}
							</td>
							<td class="py-1.5 pr-3 text-ink-gray-7">
								{{ event.course_title || event.batch_title }}
								<div v-if="event.lesson_title" class="text-ink-gray-5">
									{{ event.lesson_title }}
								</div>
							</td>
							<td class="py-1.5 pr-3 text-ink-gray-6">{{ describeEvent(event) }}</td>
							<td class="py-1.5 text-ink-gray-6">
								{{ event.device_label }}
								<div v-if="event.ip_address" class="text-ink-gray-5">
									{{ event.ip_address }}
								</div>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
			<div v-if="hasMore" class="flex justify-center">
				<Button :loading="loading" @click="loadMore">
					{{ __('Load more') }}
				</Button>
			</div>
		</section>
	</div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Button, FormControl, call, toast } from 'frappe-ui'
import Link from '@/oslms/components/Controls/Link.vue'
import {
	AUDIT_API,
	describeEvent,
	formatDate,
	formatDateTime,
	formatHM,
	formatTime,
} from './format'

const props = defineProps<{ eventTypes: { value: string; label: string }[] }>()

const PAGE_LENGTH = 50

const filters = reactive({
	user: '',
	course: '',
	event_type: '',
	from_date: '',
	to_date: '',
})
const events = ref<any[]>([])
const hasMore = ref(false)
const loading = ref(false)
const summary = ref<any>(null)

const eventOptions = computed(() => [
	{ label: __('All events'), value: '' },
	...props.eventTypes,
])

function params() {
	return Object.fromEntries(
		Object.entries(filters).filter(([, value]) => Boolean(value)),
	)
}

async function fetchEvents(start: number) {
	const data = await call(`${AUDIT_API}.get_log`, {
		...params(),
		start,
		page_length: PAGE_LENGTH,
	})
	events.value = start ? [...events.value, ...data.events] : data.events
	hasMore.value = data.has_more
}

async function search() {
	loading.value = true
	try {
		const { user, course, from_date, to_date } = filters
		const [, studentSummary] = await Promise.all([
			fetchEvents(0),
			user
				? call(`${AUDIT_API}.get_student_summary`, {
						user,
						course: course || undefined,
						from_date: from_date || undefined,
						to_date: to_date || undefined,
					})
				: Promise.resolve(null),
		])
		summary.value = studentSummary
	} catch (error: any) {
		toast.error(error?.messages?.[0] || __('Could not load the events'))
	} finally {
		loading.value = false
	}
}

async function loadMore() {
	loading.value = true
	try {
		await fetchEvents(events.value.length)
	} catch (error: any) {
		toast.error(error?.messages?.[0] || __('Could not load the events'))
	} finally {
		loading.value = false
	}
}

function clear() {
	Object.assign(filters, {
		user: '',
		course: '',
		event_type: '',
		from_date: '',
		to_date: '',
	})
	search()
}

onMounted(search)
</script>
