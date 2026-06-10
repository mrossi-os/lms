<template>
	<div
		class="flex flex-col border rounded-md h-full text-ink-gray-7 hover:border-outline-gray-3 p-3 card"
		:class="{ 'cursor-pointer': clickable }"
		@click="$emit('card-click', cls)"
	>
		<div v-if="$slots.actions" class="absolute top-2 right-2" @click.stop>
			<slot name="actions" />
		</div>
		<div class="font-semibold text-ink-gray-9 mb-1 pr-8">
			{{ cls.title }}
		</div>
		<div class="short-introduction">
			{{ cls.description }}
		</div>
		<div class="mt-auto space-y-3">
			<div class="flex items-center gap-x-2">
				<Calendar class="w-4 h-4 stroke-1.5" />
				<span>
					{{ dayjs(cls.date).format('DD MMMM YYYY') }}
				</span>
			</div>
			<div class="flex items-center gap-x-2">
				<Clock class="w-4 h-4 stroke-1.5" />
				<span>
					{{ dayjs(getClassStart(cls)).format('hh:mm A') }} -
					{{ dayjs(getClassEnd(cls)).format('hh:mm A') }}
				</span>
			</div>
			<div
				v-if="isAdmin && canModeratorAccessClass(cls)"
				class="flex items-center gap-x-2 text-ink-gray-9 mt-auto"
				@click.stop
			>
				<button
					type="button"
					@click="startClass(cls)"
					:disabled="startLiveClass.loading"
					class="w-full cursor-pointer inline-flex items-center justify-center gap-2 transition-colors focus:outline-none text-ink-gray-8 bg-surface-gray-2 hover:bg-surface-gray-3 active:bg-surface-gray-4 focus-visible:ring focus-visible:ring-outline-gray-3 h-7 text-base px-2 rounded disabled:opacity-50 disabled:cursor-not-allowed"
				>
					<Monitor class="h-4 w-4 stroke-1.5" />
					{{ hasHostStarted(cls) ? __('Open') : __('Start') }}
				</button>
			</div>
			<div
				v-else-if="canStudentJoin(cls)"
				class="flex items-center gap-x-2 text-ink-gray-9 mt-auto"
			>
				<a
					:href="cls.join_url"
					target="_blank"
					@click.stop
					class="w-full cursor-pointer inline-flex items-center justify-center gap-2 transition-colors focus:outline-none text-ink-gray-8 bg-surface-gray-2 hover:bg-surface-gray-3 active:bg-surface-gray-4 focus-visible:ring focus-visible:ring-outline-gray-3 h-7 text-base px-2 rounded"
				>
					<Video class="h-4 w-4 stroke-1.5" />
					{{ __('Join') }}
				</a>
			</div>
			<Tooltip
				v-else-if="showStudentJoinDisabled(cls)"
				:text="__('Waiting for the host to start the class')"
				placement="right"
			>
				<div class="flex items-center gap-x-2 mt-auto" @click.stop>
					<button
						type="button"
						disabled
						class="w-full inline-flex items-center justify-center gap-2 text-ink-gray-5 bg-surface-gray-2 h-7 text-base px-2 rounded opacity-60 cursor-not-allowed"
					>
						<Video class="h-4 w-4 stroke-1.5" />
						{{ __('Join') }}
					</button>
				</div>
			</Tooltip>
			<Tooltip
				v-else-if="hasClassEnded(cls)"
				:text="__('This class has ended')"
				placement="right"
			>
				<div class="flex items-center gap-x-2 text-ink-amber-3 w-fit">
					<Info class="w-4 h-4 stroke-1.5" />
					<span>
						{{ __('Ended') }}
					</span>
				</div>
			</Tooltip>
		</div>
	</div>
</template>
<script setup>
import { createResource, Tooltip, toast } from 'frappe-ui'
import { Calendar, Clock, Info, Monitor, Video } from 'lucide-vue-next'
import { inject } from 'vue'

const JOIN_WINDOW_MINUTES_BEFORE = 15

const dayjs = inject('$dayjs')

const props = defineProps({
	cls: {
		type: Object,
		required: true,
	},
	// Whether the current user can start/open the class (moderator / evaluator).
	isAdmin: {
		type: Boolean,
		default: false,
	},
	// Whether the card itself is clickable (used by the batch tab for attendance).
	clickable: {
		type: Boolean,
		default: false,
	},
})

const emit = defineEmits(['card-click', 'started'])

const getClassStart = (cls) => {
	return new Date(`${cls.date}T${cls.time}`)
}

const getClassEnd = (cls) => {
	const classStart = getClassStart(cls)
	return new Date(classStart.getTime() + cls.duration * 60000)
}

const hasClassEnded = (cls) => {
	const classEnd = getClassEnd(cls)
	const now = new Date()
	return now > classEnd
}

const isWithinJoinWindow = (cls) => {
	const now = new Date()
	const start = getClassStart(cls)
	const end = getClassEnd(cls)
	const windowOpen = new Date(
		start.getTime() - JOIN_WINDOW_MINUTES_BEFORE * 60000,
	)
	return now >= windowOpen && now <= end
}

const hasHostStarted = (cls) => Boolean(cls.started_at)

const canStudentJoin = (cls) =>
	isWithinJoinWindow(cls) && hasHostStarted(cls) && Boolean(cls.join_url)

const showStudentJoinDisabled = (cls) =>
	isWithinJoinWindow(cls) &&
	!hasHostStarted(cls) &&
	!hasClassEnded(cls) &&
	Boolean(cls.join_url)

const canModeratorAccessClass = (cls) => {
	if (hasClassEnded(cls)) return false
	if (cls.date !== dayjs().format('YYYY-MM-DD')) return false
	return true
}

const startLiveClass = createResource({
	url: 'os_lms.os_lms.api.start_live_class',
})

const startClass = (cls) => {
	const fallbackUrl = cls.start_url || cls.join_url
	startLiveClass.submit(
		{ name: cls.name },
		{
			onSuccess(data) {
				const url = data?.start_url || fallbackUrl
				if (url) window.open(url, '_blank', 'noopener')
				emit('started', cls)
			},
			onError(err) {
				toast.error(err.messages?.[0] || err)
				if (fallbackUrl) window.open(fallbackUrl, '_blank', 'noopener')
			},
		},
	)
}
</script>
