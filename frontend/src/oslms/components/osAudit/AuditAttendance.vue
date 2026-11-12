<template>
	<div class="space-y-5">
		<section class="space-y-4 rounded-md border card">
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
				<Link
					v-model="filters.course"
					doctype="LMS Course"
					:label="__('Course')"
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
			<div class="flex justify-end">
				<Button
					variant="solid"
					:loading="loading"
					:disabled="!filters.course"
					@click="load"
				>
					{{ __('Show attendance') }}
				</Button>
			</div>
		</section>

		<template v-if="data">
			<section class="space-y-3 rounded-md border card">
				<div class="flex flex-wrap items-baseline justify-between gap-2">
					<h2 class="text-base font-semibold text-ink-gray-9">
						{{ data.course_title }}
					</h2>
					<div class="flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-gray-6">
						<span
							>{{ __('Planned hours') }}:
							<b class="text-ink-gray-9">{{
								data.planned_hours || __('Not set')
							}}</b></span
						>
						<span
							>{{ __('Minimum attendance %') }}:
							<b class="text-ink-gray-9">{{
								data.min_attendance_percent || __('Not set')
							}}</b></span
						>
						<span
							>{{ __('Time that counts') }}:
							<b class="text-ink-gray-9">{{ __(data.counted_time) }}</b></span
						>
					</div>
				</div>
				<p v-if="!data.in_scope" class="text-p-sm text-ink-amber-3">
					{{
						__(
							'This course is not in the audit scope: no new activity is recorded for it.',
						)
					}}
				</p>
				<div
					v-if="!data.students.length"
					class="py-4 text-center text-sm text-ink-gray-5"
				>
					{{ __('No students') }}
				</div>
				<div v-else class="overflow-x-auto">
					<table class="w-full text-sm">
						<thead>
							<tr class="text-left text-ink-gray-5">
								<th class="py-1.5 pr-3 font-medium">{{ __('Student') }}</th>
								<th class="py-1.5 pr-3 font-medium">{{ __('Visits') }}</th>
								<th class="py-1.5 pr-3 font-medium">{{ __('Presence') }}</th>
								<th class="py-1.5 pr-3 font-medium">{{ __('Active Time') }}</th>
								<th class="py-1.5 pr-3 font-medium">{{ __('Attendance') }}</th>
								<th class="py-1.5 font-medium">{{ __('Last signal') }}</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="student in data.students"
								:key="student.user"
								class="border-t border-outline-gray-1"
							>
								<td class="py-1.5 pr-3 text-ink-gray-8">
									{{ student.full_name }}
									<div class="text-ink-gray-5">{{ student.user }}</div>
								</td>
								<td class="py-1.5 pr-3">{{ student.visits }}</td>
								<td class="py-1.5 pr-3">{{ formatHM(student.presence_seconds) }}</td>
								<td class="py-1.5 pr-3">{{ formatHM(student.active_seconds) }}</td>
								<td class="py-1.5 pr-3">
									<Badge
										v-if="student.percent !== null"
										:theme="student.below_threshold ? 'red' : 'green'"
										:label="formatPercent(student.percent)"
									/>
									<span v-else class="text-ink-gray-5">—</span>
								</td>
								<td class="py-1.5 text-ink-gray-6">{{ formatDateTime(student.last_at) }}</td>
							</tr>
						</tbody>
					</table>
				</div>
				<p v-if="belowCount" class="text-p-sm text-ink-red-3">
					{{ __('{0} students below the minimum attendance').format(belowCount) }}
				</p>
			</section>

			<section class="space-y-3 rounded-md border card">
				<h2 class="text-base font-semibold text-ink-gray-9">
					{{ __('Live classes') }}
				</h2>
				<p class="text-p-sm text-ink-gray-6">
					{{
						__(
							'Joining from the platform is recorded by the audit. Entry and exit come from Zoom or Google Meet, when they report them.',
						)
					}}
				</p>
				<div
					v-if="!data.live_classes.length"
					class="py-4 text-center text-sm text-ink-gray-5"
				>
					{{ __('No live classes for this course in this period') }}
				</div>
				<div
					v-for="live in data.live_classes"
					:key="live.name"
					class="rounded border border-outline-gray-2 p-3"
				>
					<div class="flex flex-wrap items-baseline justify-between gap-2">
						<div class="font-medium text-ink-gray-9">{{ live.title }}</div>
						<div class="text-sm text-ink-gray-6">
							{{ formatDate(live.date) }} {{ formatClock(live.time) }}
							· {{ live.batch_title }} · {{ live.provider }}
						</div>
					</div>
					<div class="mt-1 text-sm text-ink-gray-6">
						{{ __('Teacher') }}: {{ live.host_name || '—' }}
					</div>
					<div
						v-if="!live.participants.length"
						class="mt-2 text-sm text-ink-gray-5"
					>
						{{ __('No attendance recorded') }}
					</div>
					<div v-else class="mt-2 overflow-x-auto">
						<table class="w-full text-sm">
							<thead>
								<tr class="text-left text-ink-gray-5">
									<th class="py-1 pr-3 font-medium">{{ __('Participant') }}</th>
									<th class="py-1 pr-3 font-medium">{{ __('Joined from the platform') }}</th>
									<th class="py-1 pr-3 font-medium">{{ __('Entry') }}</th>
									<th class="py-1 pr-3 font-medium">{{ __('Exit') }}</th>
									<th class="py-1 font-medium">{{ __('Duration') }}</th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="person in live.participants"
									:key="person.user || person.full_name"
									class="border-t border-outline-gray-1"
								>
									<td class="py-1 pr-3 text-ink-gray-8">
										{{ person.full_name }}
										<Badge
											v-if="person.is_host"
											theme="blue"
											:label="__('Teacher')"
											class="ml-1"
										/>
									</td>
									<td class="py-1 pr-3">{{ formatTime(person.joined_from_platform) || '—' }}</td>
									<td class="py-1 pr-3">{{ formatTime(person.joined_at) || '—' }}</td>
									<td class="py-1 pr-3">{{ formatTime(person.left_at) || '—' }}</td>
									<td class="py-1">
										{{
											person.duration_seconds === null
												? '—'
												: formatHM(person.duration_seconds)
										}}
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>
			</section>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { Badge, Button, FormControl, call, toast } from 'frappe-ui'
import Link from '@/oslms/components/Controls/Link.vue'
import {
	AUDIT_API,
	formatClock,
	formatDate,
	formatDateTime,
	formatHM,
	formatPercent,
	formatTime,
} from './format'

const filters = reactive({ course: '', from_date: '', to_date: '' })
const data = ref<any>(null)
const loading = ref(false)

const belowCount = computed(
	() => (data.value?.students || []).filter((s: any) => s.below_threshold).length,
)

async function load() {
	if (!filters.course) return
	loading.value = true
	try {
		data.value = await call(`${AUDIT_API}.get_attendance`, {
			course: filters.course,
			from_date: filters.from_date || undefined,
			to_date: filters.to_date || undefined,
		})
	} catch (error: any) {
		toast.error(error?.messages?.[0] || __('Could not load the attendance'))
	} finally {
		loading.value = false
	}
}
</script>
