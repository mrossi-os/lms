<template>
    <section v-if="doc" class="space-y-5">
        <div>
            <div class="card p-4 space-y-4">
                <Switch size="sm" v-model="doc.hero_enabled" :label="__('Hero nella pagina corso')" :description="__(
                    'Mostra una sezione in alto con titolo, introduzione e media dedicato.',
                )
                    " @change="markDirty()" />
                <template v-if="doc.hero_enabled">
                    <FormControl v-model="doc.hero_media_type" type="select" :label="__('Tipo media hero')" :options="[
                        { label: __('Video'), value: 'Video' },
                        { label: __('Image'), value: 'Image' },
                    ]" @change="markDirty()" />
                    <FormControl v-model="doc.hero_media_url" :label="__('URL media hero')" :description="__(
                        'Link YouTube/Vimeo, file caricato o URL immagine pubblico.',
                    )
                        " @input="markDirty()" />
                    <FilePicker v-model="heroMediaFile" :label="__('Oppure scegli un file caricato')"
                        :placeholder="__('Cerca un file immagine o video...')"
                        :allowedExtensions="HERO_MEDIA_EXTENSIONS" @update:fileUrl="onHeroMediaFileUrl" />
                </template>
            </div>
        </div>
        <FeatureSectionEditor :modelValue="doc" @dirty="markDirty()" />
    </section>
</template>

<script setup lang="ts">
import {
    FormControl,
} from 'frappe-ui'
import FilePicker from '@/components/Controls/FilePicker.vue'
import FeatureSectionEditor from '@/oslms/components/FeatureSectionEditor.vue'
import { computed, inject, ref } from 'vue'
import type { CourseFormContext } from '@/types/api'

const HERO_MEDIA_EXTENSIONS = [
    'mp4',
    'webm',
    'ogg',
    'ogv',
    'mov',
    'm4v',
    'png',
    'jpg',
    'jpeg',
    'gif',
    'webp',
    'svg',
]

const { resource, markDirty } = inject<CourseFormContext>('courseForm')!
const doc = computed(() => resource.doc)
const heroMediaFile = ref('')


const onHeroMediaFileUrl = (url: string | null) => {
    if (!url || !doc) return
    doc.hero_media_url = url
    markDirty()
}
</script>
