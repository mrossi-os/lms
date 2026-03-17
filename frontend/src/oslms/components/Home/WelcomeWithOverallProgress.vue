<template>
    <div v-if="sessionStore().user" class="p-4 border rounded-md bg-surface-white">

        <!-- Saluto -->
        <div class="text-lg font-semibold text-ink-gray-9 mb-3">
            {{ __('Salve,') }} {{ user?.data?.full_name || sessionStore().user }}
        </div>

        <!-- Loading -->
        <div v-if="enrollments.loading" class="text-sm text-ink-gray-5">
            {{ __('Caricamento...') }}
        </div>

        <!-- Nessun corso -->
        <div v-else-if="!enrollments.data?.length" class="text-sm text-ink-gray-5">
            {{ __('Nessun corso trovato.') }}
        </div>

        <div v-else>
            <!-- Progresso globale -->
            <div class="flex items-center justify-between mb-1">
                <span class="text-sm text-ink-gray-6">
                    {{ __('Progresso del programma') }}
                </span>
                <span class="text-sm font-semibold text-ink-gray-9">
                    {{ overallProgress }}%
                </span>
            </div>

            <ProgressBar :progress="overallProgress" />

            <div class="text-xs text-ink-gray-5 mt-1.5 mb-4">
                {{ enrollments.data.length }}
                {{ enrollments.data.length === 1 ? __('corso iscritto') : __('corsi iscritti') }}
            </div>

            <!-- Pulsanti azione -->
            <div class="flex items-center gap-2 flex-wrap">

                <!-- Riprendi dove eri rimasto -->
                <router-link v-if="resumeRoute" :to="resumeRoute" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium
					       bg-surface-gray-2 hover:bg-surface-gray-3 text-ink-gray-8 transition-colors">
                    <PlayCircle class="w-4 h-4 stroke-1.5" />
                    {{ __('Riprendi dove eri rimasto') }}
                </router-link>

                <!-- Esplora corso -->
                <router-link v-if="lastActiveCourse"
                    :to="{ name: 'CourseDetail', params: { courseName: lastActiveCourse } }" class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded text-sm font-medium
					       bg-surface-gray-2 hover:bg-surface-gray-3 text-ink-gray-8 transition-colors">
                    <BookOpen class="w-4 h-4 stroke-1.5" />
                    {{ __('Esplora corso') }}
                </router-link>

            </div>
        </div>
    </div>
</template>

<script setup lang="ts">
import { inject, computed, watch } from 'vue'
import { createResource } from 'frappe-ui'
import { sessionStore } from '@/stores/session'
import ProgressBar from '@/components/ProgressBar.vue'
import { PlayCircle, BookOpen } from 'lucide-vue-next'

const user = inject<any>('$user')
const currentUser = sessionStore().user

const enrollments = createResource({
    url: 'frappe.client.get_list',
    auto: true,
    params: {
        doctype: 'LMS Enrollment',
        filters: [['member', '=', currentUser]],
        fields: ['course', 'progress', 'current_lesson'],
        order_by: 'modified desc',
        limit: 0,
    },
})

const overallProgress = computed<number>(() => {
    const data = enrollments.data
    if (!data?.length) return 0
    const total = data.reduce((sum: number, e: any) => sum + (e.progress ?? 0), 0)
    return Math.round(total / data.length)
})


const activeEnrollment = computed(() => {
    const data = enrollments.data
    if (!data?.length) return null
    return data.find((e: any) => e.progress > 0 && e.progress < 100) ?? data[0]
})

const lastActiveCourse = computed(() => activeEnrollment.value?.course ?? null)


const lessonPosition = createResource({
    url: 'os_lms.os_lms.api.get_lesson_position',
})

watch(
    () => activeEnrollment.value?.current_lesson,
    (lessonName: string | null) => {
        if (!lessonName) return
        lessonPosition.fetch({ lesson_name: lessonName })
    },
    { immediate: true }
)

// ─── Route finale per "Riprendi" ──────────────────────────────────────────────
const resumeRoute = computed(() => {
    const pos = lessonPosition.data
    const course = lastActiveCourse.value

    if (!pos || !course) return null

    return {
        name: 'Lesson',
        params: {
            courseName: course,
            chapterNumber: pos.chapter_number,
            lessonNumber: pos.lesson_number,
        },
    }
})
</script>