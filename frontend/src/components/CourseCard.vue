<template>
	<div
		v-if="course.title"
		class="flex flex-col h-full rounded-md overflow-auto text-ink-gray-9 card"
		style="min-height: 350px"
	>
		<div
			class="w-[100%] h-[168px] bg-cover bg-center bg-no-repeat rounded-t-md"
			:style="
				course.image
					? { backgroundImage: `url('${encodeURI(course.image)}')` }
					: {
							backgroundImage: gradientColor,
							backgroundBlendMode: 'screen',
						}
			"
		>
			<div
				v-if="!course.image"
				class="flex items-center justify-center text-ink-gray-9 flex-1 font-extrabold my-auto px-5 text-center leading-6 h-full"
				:class="
					course.title.length > 32
						? 'text-lg'
						: course.title.length > 20
							? 'text-xl'
							: 'text-2xl'
				"
			>
				{{ course.title }}
			</div>
		</div>
		<div class="flex flex-col flex-auto p-4 rounded-b-md">
			<div class="flex items-center justify-start mb-2 gap-4">
				<div v-if="course.lessons">
					<Tooltip :text="__('Lessons')">
						<span class="flex items-center">
							<BookOpen class="h-4 w-4 stroke-2 mr-1" />
							{{ course.lessons }}
						</span>
					</Tooltip>
				</div>

				<div v-if="formattedDuration">
					<Tooltip :text="__('Duration')">
						<span class="flex items-center">
							<Clock class="h-4 w-4 stroke-2 mr-1" />
							{{ formattedDuration }}
						</span>
					</Tooltip>
				</div>

				<div v-if="course.enable_certification">
					<Tooltip :text="__('Certification available')">
						<span class="flex items-center">
							<Award class="h-4 w-4 stroke-2" />
						</span>
					</Tooltip>
				</div>
			</div>

			<div
				v-if="course.image"
				class="font-semibold leading-6"
				:class="course.title.length > 32 ? 'text-lg' : 'text-xl'"
			>
				{{ course.title }}
			</div>

			<CourseTagBadges v-if="course.tags" :tags="course.tags" class="my-1" />

			<div class="short-introduction text-sm">
				{{ course.short_introduction }}
			</div>

			<ProgressBar
				v-if="user && course.membership"
				:progress="course.membership.progress"
			/>

			<div v-if="user && course.membership" class="text-sm mt-2 mb-4">
				{{ Math.ceil(course.membership.progress) }}% {{ __('completed') }}
			</div>
		</div>
	</div>
</template>

<script setup>
import { BookOpen, Clock, Award } from 'lucide-vue-next'
import { sessionStore } from '@/stores/session'
import { Tooltip } from 'frappe-ui'
import { theme } from '@/utils/theme'
import { computed } from 'vue'
import ProgressBar from '@/components/ProgressBar.vue'
import CourseTagBadges from '@/oslms/components/CourseTagBadges.vue'
import colors from '@/utils/frappe-ui-colors.json'

const { user } = sessionStore()

const props = defineProps({
	course: {
		type: Object,
		default: null,
	},
})

// Converte i minuti totali in formato leggibile: "1h 30m", "2h", "45m"
const formattedDuration = computed(() => {
	const total = props.course.total_minutes
	if (!total) return null
	const hours = Math.floor(total / 60)
	const minutes = total % 60
	if (hours > 0 && minutes > 0) return `${hours}h ${minutes}m`
	if (hours > 0) return `${hours}h`
	return `${minutes}m`
})

const gradientColor = computed(() => {
	let themeMode = theme.value === 'dark' ? 'darkMode' : 'lightMode'
	let color = props.course.card_gradient?.toLowerCase() || 'blue'
	let colorMap = colors[themeMode][color]
	return `linear-gradient(to top right, black, ${colorMap[400]})`
})
</script>

<style>
.course-card-pills {
	background: #ffffff;
	margin-left: 0;
	margin-right: 0.5rem;
	padding: 3.5px 8px;
	font-size: 11px;
	text-align: center;
	letter-spacing: 0.011em;
	text-transform: uppercase;
	font-weight: 600;
	width: fit-content;
}

.avatar-group {
	display: inline-flex;
	align-items: center;
}

.avatar-group .avatar {
	transition: margin 0.1s ease-in-out;
}

.avatar-group.overlap .avatar + .avatar {
	margin-inline-start: calc(-8px);
}

.short-introduction {
	display: -webkit-box;
	-webkit-line-clamp: 2;
	-webkit-box-orient: vertical;
	text-overflow: ellipsis;
	width: 100%;
	overflow: hidden;
	margin: 0.25rem 0 1.25rem;
	line-height: 1.5;
}
</style>
