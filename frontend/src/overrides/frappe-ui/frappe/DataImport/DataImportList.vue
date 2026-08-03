<template>
    <div class="flex min-h-0 flex-col text-base py-5 w-[90%] lg:w-[700px] mx-auto">
		<div class="flex items-center justify-between">
			<div>
				<div class="text-xl font-semibold mb-1 text-ink-gray-9">
					{{ __('Data Import') }}
				</div>
				<div class="text-ink-gray-6 leading-5">
					{{ __('Import data into your system using CSV files.') }}
				</div>
			</div>
            <Button variant="solid" @click="showModal = true">
                <template #prefix>
                    <FeatherIcon name="plus" class="size-4 stroke-1.5" />
                </template>
                {{ __('Import') }}
            </Button>
		</div>

        <div class="flex items-center space-x-2 my-5">
            <FormControl
                v-model="search"
                :placeholder="__('Search imported files')"
                type="text"
                class="flex-1"
            />
            <FormControl
                v-model="importStatus"
                type="select"
                :options="importOptions"
            />
        </div>

        <div v-if="dataImports.data?.length" class="overflow-y-scroll">
            <div class="divide-y">
                <div class="grid grid-cols-[75%,20%] lg:grid-cols-[85%,20%] items-center text-sm text-ink-gray-5 py-1.5 mx-2 my-0.5 px-1">
                    <div>
                        {{ __('Name') }}
                    </div>
                    <div class="pl-1">
                        {{ __('Status') }}
                    </div>
                </div>
                <div
                    v-for="dataImport in dataImports.data"
                    @click="() => redirectToImport(dataImport.name!)"
                    class="grid grid-cols-[75%,20%] lg:grid-cols-[85%,20%] items-center cursor-pointer py-2.5 px-1 mx-2"
                >
                    <div class="space-y-1">
                        <div class="text-ink-gray-7">
                            {{ __(dataImport.reference_doctype) }}
                        </div>
                        <div class="text-ink-gray-5">
                            {{ dayjs(dataImport.creation).fromNow() }}
                        </div>
                    </div>
                    <Badge :label="__(dataImport.status)" :theme="getBadgeColor(dataImport.status) as BadgeProps['theme']" class="w-fit" />
                </div>
            </div>
            <div class="my-5 flex justify-center">
                <Button v-if="props.dataImports.hasNextPage" @click="props.dataImports.next()">
                    <template #prefix>
                        <FeatherIcon name="refresh-cw" class="size-4 stroke-1.5" />
                    </template>
                    {{ __('Load More') }}
                </Button>
            </div>
        </div>
        <div v-else class="text-sm italic text-ink-gray-5 mt-5">
            {{ __('No data imports found.') }}
        </div>
        <Dialog
            v-model="showModal"
            :options="{
                title: __('New Data Import'),
                actions: [{
                    label: __('Continue'),
                    variant: 'solid',
                    onClick({ close }) {
                        createDataImport(close)
                    }
                }]
            }"
        >
            <template #body-content>
                <div>
                    <Link
                        v-model="doctypeForImport"
                        doctype="DocType"
                        :filters="{
                            'allow_import': 1
                        }"
                        :label="__('Choose a Document Type to import')"
                        :placeholder="__('Select a document type')"
                    />
                </div>
            </template>
        </Dialog>
	</div>
</template>
<script setup lang="ts">
import { Badge, Button, Dialog, FeatherIcon, FormControl, toast } from 'frappe-ui'
import type { BadgeProps } from 'frappe-ui'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type { DataImports, DataImport } from '../../../../../node_modules/frappe-ui/frappe/DataImport/types'
// The SPA's own dayjs, which loads the Italian locale; frappe-ui's has none,
// so `fromNow()` came out in English.
import dayjs from '@/utils/dayjs'
import { getBadgeColor } from '../../../../../node_modules/frappe-ui/frappe/DataImport/dataImport'
import Link from '@/overrides/frappe-ui/frappe/Link/Link.vue'

const search = ref('')
const importStatus = ref('All')
const showModal = ref(false)
const doctypeForImport = ref<string | null>(null)
const emit = defineEmits(['updateStep'])
const router = useRouter()

const props = defineProps<{
    dataImports: DataImports
}>()

const importOptions = computed(() => {
    const options = ["All", "Pending", "Success", "Partial Success", "Error", "Timed Out"]
    return options.map(option => ({ label: __(option), value: option }))
})

watch([search, importStatus], ([newSearch, newStatus]) => {
    props.dataImports.update({
        filters: [
            newSearch ? [['name', 'like', `%${newSearch}%`]] : [],
            newStatus !== 'All' ? [['status', '=', newStatus]] : [],
        ].flat(),
    })
    props.dataImports.reload()
})

const createDataImport = (close: () => void) => {
    props.dataImports.insert.submit({
        reference_doctype: doctypeForImport.value!,
        import_type: 'Insert New Records',
        mute_emails: true,
        status: 'Pending',
    }, {
        onSuccess(data: DataImport) {
            router.replace({
                name: 'DataImport',
                params: {
                    importName: data.name
                },
            })
            close()
        },
        onError(error: any) {
            console.error(error)
            toast.error(error.messages?.[0] || error)
        }
    })
}

const redirectToImport = (importName: string) => {
    router.replace({
        name: 'DataImport',
        params: {
            importName
        },
    })
}
</script>