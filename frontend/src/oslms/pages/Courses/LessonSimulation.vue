<template>
    <div class="sticky top-10">
        <div v-if="canLaunchSimulation" class="m-3 p-4 rounded-md border bg-surface-blue-1 border-outline-blue-3">
            <div class="text-sm-medium text-ink-gray-9 mb-1">
                {{ __('Metti in pratica') }}
            </div>
            <div class="text-xs text-ink-gray-5 mb-3">
                {{ __('Avvia una simulazione di vendita per questa lezione.') }}
            </div>
            <Button variant="solid" size="sm" @click="simulationLauncherOpen = true">
                {{ __('Avvia simulazione') }}
            </Button>
        </div>
        <SimulationLauncher v-if="canLaunchSimulation" v-model="simulationLauncherOpen"
            :scenarios="availableSimulations" />
        <div v-if="lesson.data?.name && !hasQuiz" ref="chatBotContainer" :data-ai-tutor="true" class="p-3">
            <ChatBot :courseId="lesson.data?.course" :lessonId="lesson.data?.name" />
        </div>
        <div class="bg-surface-sidebar p-5 border-b m-3 rounded-md">
            <div class="text-xl-semibold text-ink-gray-9">
                {{ lesson.data.course_title }}
            </div>
            <div v-if="user && lesson.data.membership" class="text-sm mt-4 mb-2 text-ink-gray-5">
                {{ Math.ceil(lessonProgress) }}% {{ __('completed') }}
            </div>

            <ProgressBar v-if="user && lesson.data.membership" :progress="lessonProgress" />
        </div>
        <div class="m-3">
            <CourseOutline :courseName="courseName" :key="chapterNumber"
                :getProgress="lesson.data.membership ? true : false" />
        </div>
    </div>
</template>