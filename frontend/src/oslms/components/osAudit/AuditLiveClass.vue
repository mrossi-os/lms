<template>
	<div class="rounded border border-outline-gray-2 p-3">
		<div class="flex flex-wrap items-baseline justify-between gap-2">
			<div class="font-medium text-ink-gray-9">{{ live.title }}</div>
			<div class="text-sm text-ink-gray-6">
				{{ formatDate(live.date) }} {{ formatClock(live.time) }}
				· {{ live.batch_title }}
				<template v-if="live.provider">· {{ live.provider }}</template>
			</div>
		</div>
		<div
			class="mt-1 flex flex-wrap items-center justify-between gap-2 text-sm text-ink-gray-6"
		>
			<div>
				{{ __('Teacher') }}: {{ live.teacher_name || live.host_name || '—' }}
			</div>
			<div v-if="live.provider" class="flex flex-wrap items-center gap-2">
				<Badge
					:theme="readStatusTheme(live.read_status)"
					:label="live.read_status_label || __('Not read yet')"
				/>
				<span v-if="live.read_at" class="text-p-xs text-ink-gray-5">
					{{ formatDateTime(live.read_at) }}
				</span>
				<Button
					v-if="canRereadLive(live)"
					size="sm"
					variant="subtle"
					:loading="rereading"
					@click="reread"
				>
					{{ __('Read attendance again') }}
				</Button>
			</div>
		</div>
		<p v-if="live.read_error" class="mt-1 text-p-sm text-ink-red-4">
			{{ live.read_error }}
		</p>

		<div
			v-if="!live.participants.length && !live.unmatched.length"
			class="mt-2 text-sm text-ink-gray-5"
		>
			{{ __('No attendance recorded') }}
		</div>
		<div v-if="live.participants.length" class="mt-2 overflow-x-auto">
			<table class="w-full text-sm">
				<thead>
					<tr class="text-left text-ink-gray-5">
						<th class="py-1 pr-3 font-medium">{{ __('Participant') }}</th>
						<th class="py-1 pr-3 font-medium">
							{{ __('Joined from the platform') }}
						</th>
						<th class="py-1 pr-3 font-medium">{{ __('Entry') }}</th>
						<th class="py-1 pr-3 font-medium">{{ __('Exit') }}</th>
						<th class="py-1 pr-3 font-medium">{{ __('Duration') }}</th>
						<th class="py-1 font-medium">{{ __('Matched by') }}</th>
					</tr>
				</thead>
				<tbody>
					<tr
						v-for="person in live.participants"
						:key="person.user"
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
							<div
								v-if="person.names.length"
								class="text-p-xs text-ink-gray-5"
							>
								{{ __('At the provider') }}: {{ person.names.join(', ') }}
							</div>
						</td>
						<td class="py-1 pr-3">
							{{
								formatTime(person.joined_from_platform || person.started_at) ||
								'—'
							}}
						</td>
						<td class="py-1 pr-3">{{ formatTime(person.joined_at) || '—' }}</td>
						<td class="py-1 pr-3">{{ formatTime(person.left_at) || '—' }}</td>
						<td class="py-1 pr-3">
							{{
								person.duration_seconds === null
									? '—'
									: formatHM(person.duration_seconds)
							}}
							<span
								v-if="person.segments > 1"
								class="text-p-xs text-ink-gray-5"
							>
								({{ __('{0} segments').format(person.segments) }})
							</span>
						</td>
						<td class="py-1 text-ink-gray-6">
							{{ person.matched_label || '—' }}
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<div v-if="live.unmatched.length" class="mt-3 space-y-2">
			<div class="text-sm font-medium text-ink-gray-8">
				{{ __('Unmatched participants') }} ({{ live.unmatched.length }})
			</div>
			<p class="text-p-xs text-ink-gray-5">
				{{
					__(
						'The provider reported them with a name or email that does not belong to anyone in this class. Match each one to a person, or mark them as an external guest.',
					)
				}}
			</p>
			<div
				v-for="person in live.unmatched"
				:key="person.row"
				class="flex flex-wrap items-end gap-2 border-t border-outline-gray-1 pt-2"
			>
				<div class="min-w-[12rem] flex-1 text-sm">
					<div class="text-ink-gray-8">
						{{ person.display_name || __('No name') }}
					</div>
					<div class="text-p-xs text-ink-gray-5">
						{{ person.email || __('No email') }} ·
						{{ formatTime(person.joined_at) }}–{{ formatTime(person.left_at) }}
						· {{ formatHM(person.duration_seconds) }}
					</div>
				</div>
				<FormControl
					v-model="choice[person.row]"
					type="select"
					class="min-w-[14rem]"
					:placeholder="__('Choose a person')"
					:options="peopleOptions"
				/>
				<Button
					size="sm"
					variant="solid"
					:disabled="!choice[person.row]"
					:loading="saving === person.row"
					@click="match(person.row)"
				>
					{{ __('Match') }}
				</Button>
				<Button
					size="sm"
					variant="subtle"
					:loading="saving === person.row + ':guest'"
					@click="match(person.row, true)"
				>
					{{ __('External guest') }}
				</Button>
			</div>
		</div>

		<details v-if="live.guests.length" class="mt-3 text-sm text-ink-gray-6">
			<summary class="cursor-pointer">
				{{ __('External guests') }} ({{ live.guests.length }})
			</summary>
			<div
				v-for="person in live.guests"
				:key="person.row"
				class="mt-1 flex flex-wrap items-center gap-2"
			>
				<span>
					{{ person.display_name || __('No name') }} ·
					{{ formatTime(person.joined_at) }}–{{ formatTime(person.left_at) }}
					· {{ formatHM(person.duration_seconds) }}
				</span>
				<Button size="sm" variant="ghost" @click="undoGuest(person.row)">
					{{ __('Match to a person') }}
				</Button>
			</div>
		</details>
	</div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { Badge, Button, FormControl, call, toast } from 'frappe-ui'
import {
	LIVE_API,
	canRereadLive,
	formatClock,
	formatDate,
	formatDateTime,
	formatHM,
	formatTime,
	readStatusTheme,
} from './format'

const props = defineProps<{ live: any }>()
const emit = defineEmits<{ (e: 'changed'): void }>()

const choice = reactive<Record<string, string>>({})
const saving = ref<string | null>(null)
const rereading = ref(false)

const peopleOptions = computed(() =>
	(props.live.people || []).map((p: { user: string; full_name: string }) => ({
		label: p.full_name === p.user ? p.user : `${p.full_name} (${p.user})`,
		value: p.user,
	})),
)

async function match(row: string, guest = false) {
	saving.value = guest ? `${row}:guest` : row
	try {
		await call(`${LIVE_API}.match_participant`, {
			row,
			user: guest ? undefined : choice[row],
			guest: guest ? 1 : 0,
		})
		toast.success(guest ? __('Marked as external guest') : __('Participant matched'))
		emit('changed')
	} catch (error: any) {
		toast.error(error?.messages?.[0] || __('Could not save the match'))
	} finally {
		saving.value = null
	}
}

// A guest goes back among the unmatched by matching it: open the picker on it.
function undoGuest(row: string) {
	const person = props.live.guests.find((g: any) => g.row === row)
	if (!person) return
	props.live.guests = props.live.guests.filter((g: any) => g.row !== row)
	props.live.unmatched = [...props.live.unmatched, person]
}

async function reread() {
	rereading.value = true
	try {
		await call(`${LIVE_API}.reread_live_class`, { live_class: props.live.name })
		toast.success(
			__('The attendance will be read again in a few moments: reload to see it.'),
		)
		emit('changed')
	} catch (error: any) {
		toast.error(error?.messages?.[0] || __('Could not read the attendance again'))
	} finally {
		rereading.value = false
	}
}
</script>
