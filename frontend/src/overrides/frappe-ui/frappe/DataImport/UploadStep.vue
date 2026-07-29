<!--
  Fork of frappe-ui/frappe/DataImport/UploadStep.vue.

  The original hardcodes CSV as the only accepted upload format, with no prop to
  configure it, while our Data Import override reads .csv, .xlsx and .xls alike;
  and, like every component of this page, it ships hardcoded English labels.
  Only these things differ from upstream — keep it that way, it makes re-syncing
  after a frappe-ui bump a small diff:
    1. `accept` on the file input lists ACCEPTED_EXTENSIONS
    2. `uploadFile` validates the extension instead of `file.type`
    3. every user-visible string goes through __()
    4. relative imports are prefixed with the `frappe-ui-original` alias (defined
       in vite.config.js), since they do not resolve from src/overrides

  Re-diff this file against node_modules after every frappe-ui upgrade.
-->
<template>
    <div class="text-base h-full flex flex-col w-[85%] lg:w-[700px] mx-auto pt-12 space-y-8">
        <div class="flex flex-col space-y-1 text-ink-gray-7">
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-2 text-xl font-semibold text-ink-gray-9">
                    <span>
                        {{ __('Choose Import') }}
                    </span>
                    <Badge v-if="data?.status" :theme="getBadgeColor(data?.status)">
                        {{ __(data?.status) }}
                    </Badge>
                </div>
                <Button
                    variant="solid"
                    @click="saveImport"
                    :disabled="disableContinueButton"
                >
                    {{ __('Continue') }}
                </Button>
            </div>
            <div class="leading-5">
                {{ __('Import data into your system using CSV files or Google Sheets.') }}
            </div>
        </div>

        <div class="space-y-4">
            <div
                v-if="showFileSelector && !importFile"
                @dragover.prevent
                @drop.prevent="(e) =>  uploadFile(e)"
                class="h-[300px] flex items-center justify-center bg-surface-gray-1 border border-dashed border-outline-gray-3 rounded-md">
                <div v-if="showFileSelector && !uploading" class="w-4/5 lg:w-2/5 text-center">
                    <FeatherIcon name="upload-cloud" class="size-6 stroke-1.5 text-ink-gray-6 mx-auto mb-2.5" />
                    <input
                        ref="fileInput"
                        type="file"
                        :accept="ACCEPTED_EXTENSIONS.join(',')"
                        class="hidden"
                        @change="(e) => uploadFile(e)"
                    />
                    <div class="leading-5 text-ink-gray-9">
                        {{ __('Drag and drop a CSV or Excel file, or upload from your') }}
                        <span @click="openFileSelector" class="cursor-pointer font-semibold hover:underline">{{ __('Device') }}</span>
                        {{ __('or') }}
                        <span @click="openSheetSelector" class="cursor-pointer font-semibold hover:underline">
                            {{ __('Google Sheet') }}
                        </span>
                    </div>
                </div>
                <div v-else-if="showFileSelector && uploading" class="w-4/5 lg:w-2/5 bg-surface-base border rounded-md p-2">
                    <div class="space-y-2">
                        <div class="font-medium">
                            {{ uploadingdFile.name }}
                        </div>
                        <div class="text-ink-gray-6">
                            {{ convertToKB(uploaded) }} {{ __('of') }} {{ convertToKB(total) }}
                        </div>
                    </div>
                    <div class="w-full bg-surface-gray-1 h-1 rounded-full mt-3">
                        <div
                            class="bg-surface-gray-10 h-1 rounded-full transition-all duration-500 ease-in-out"
                            :style="`width: ${uploadProgress}%`"
                        ></div>
                    </div>
                </div>
            </div>
            <div v-else-if="importFile" class="h-[300px] flex items-center justify-center bg-surface-gray-1 border border-dashed border-outline-gray-3 rounded-md">
                <div class="w-4/5 lg:w-2/5 bg-surface-base border rounded-md p-2 flex items-center justify-between items-center">
                    <div class="space-y-2">
                        <div class="font-medium leading-5 text-ink-gray-9">
                            {{ importFile.file_name || importFile.split("/").pop() }}
                        </div>
                        <div v-if="importFile.file_size" class="text-ink-gray-6">
                            {{ convertToKB(importFile.file_size) }}
                        </div>
                    </div>
                    <FeatherIcon
                        name="trash-2"
                        class="size-4 stroke-1.5 text-ink-red-6 cursor-pointer"
                        @click="deleteFile"
                    />
                </div>
            </div>

            <div v-else-if="showSheetSelector" class="flex flex-col h-[300px] p-4 border border-dashed border-outline-gray-3 rounded-md">
                <div class="flex items-center space-x-2 text-ink-gray-7">
                    <FeatherIcon name="chevron-left" class="size-4 cursor-pointer" @click="backToFileSelector" />
                    <div>
                        {{ __('Google Sheet') }}
                    </div>
                </div>
                <div class="flex-1 flex flex-col items-center justify-center w-[95%] lg:w-[400px] mx-auto space-y-3">
                    <input
                        v-model="googleSheet"
                        type="text"
                        class="w-full border border-outline-gray-2 rounded-md px-2.5 text-base"
                        :placeholder="__('Add Google Sheets Link')"
                    />
                    <div class="text-ink-gray-5">
                        {{ __('Make sure the link is publically accessible to fetch the data.') }}
                    </div>
                </div>
            </div>

            <div class="flex justify-end">
                <Dropdown
                    :options="[
                        {
                            label: __('Mandatory Fields'),
                            onClick() {
                                exportTemplate('mandatory')
                            },
                        },
                        {
                            label: __('All Fields'),
                            onClick() {
                                exportTemplate('all')
                            },
                        },
                        {
                            label: __('Custom Template'),
                            onClick() {
                                showTemplateModal = true
                            },
                        }
                    ]"
                >
                    <template v-slot="{ open }">
                        <Button variant="ghost">
                            <template #prefix>
                                <FeatherIcon name="download" class="size-4 stroke-1.5" />
                            </template>
                            {{ __('Download CSV Template') }}
                            <template #suffix>
                                <FeatherIcon name="chevron-down" :class="[
                                    'w-4 h-4 stroke-1.5 ml-1 transform transition-transform',
                                    open ? 'rotate-180' : '',
                                ]" />
                            </template>
                        </Button>
                    </template>
                </Dropdown>
            </div>
        </div>

        <TemplateModal
            v-if="props.doctype || props.data?.reference_doctype"
            v-model="showTemplateModal"
            :doctype="props.doctype || props.data?.reference_doctype as string"
        />
    </div>
</template>
<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import type {
	DataImports,
	DataImport,
	DocField,
	DocType,
} from 'frappe-ui-original/frappe/DataImport/types'
import {
	Badge,
	Button,
	Dropdown,
	FeatherIcon,
	FileUploadHandler,
	toast,
} from 'frappe-ui'
import {
	fieldsToIgnore,
	getChildTableName,
	getBadgeColor,
} from 'frappe-ui-original/frappe/DataImport/dataImport'
// Our fork, not the original: the override plugin never re-routes imports
// made from inside src/overrides, so it has to be named explicitly.
import TemplateModal from '@/overrides/frappe-ui/frappe/DataImport/TemplateModal.vue'

const ACCEPTED_EXTENSIONS = ['.csv', '.xlsx', '.xls']

const hasAcceptedExtension = (name: string) =>
    ACCEPTED_EXTENSIONS.some((extension) => name.toLowerCase().endsWith(extension))

const emit = defineEmits(['updateStep'])
const importFile = ref<any | null>(null)
const googleSheet = ref<string>('')
const uploading = ref(false)
const uploadingdFile = ref<any | null>(null)
const uploaded = ref(0)
const total = ref(0)
const showTemplateModal = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
const showFileSelector = ref(true)
const showSheetSelector = ref(false)
const showLibrarySelector = ref(false)
const router = useRouter()

const props = defineProps<{
    dataImports: DataImports
    doctype?: string
    fields: any
    data: DataImport | null
}>()

const uploadProgress = computed(() => {
    if (total.value === 0) return 0
    return Math.floor((uploaded.value / total.value) * 100)
})

const extractFile = (e: Event): File | null => {
    const inputFiles = (e.target as HTMLInputElement)?.files
    const dt = (e as DragEvent).dataTransfer?.files

    return inputFiles?.[0] || dt?.[0] || null
}

const uploadFile = (e: Event) => {
    const file = extractFile(e)
    if (!file) return;

    // Check the extension, not `file.type`: the MIME type is decided by the OS,
    // and a .csv is reported as application/vnd.ms-excel wherever Excel is the
    // registered handler — which made the original reject valid CSV files too.
    if (!hasAcceptedExtension(file.name)) {
        toast.error(__('Please upload a .csv, .xlsx or .xls file.'))
        console.error('Please upload a .csv, .xlsx or .xls file.')
        return;
    }

    uploadingdFile.value = file
    const uploader = new FileUploadHandler()

    uploader.on("start", () => {
        uploading.value = true
    })

    uploader.on("progress", (data: { uploaded: number, total: number }) => {
        uploaded.value = data.uploaded
        total.value = data.total
    })

    uploader.on("error", (error: any) => {
        uploading.value = false
        toast.error(error)
        console.error('File upload error:', error)
    })

    uploader.on("finish", () => {
        uploading.value = false
    })
    uploader.upload(file, {}).then((data => {
        importFile.value = data
    })).catch(error => {
        console.error('File upload error:', error)
    })
}

const saveImport = () => {
    if (props.data?.name) {
        updateImport()
    } else {
        createImport()
    }
}

const createImport = () => {
    props.dataImports.insert.submit({
        reference_doctype: props.doctype!,
        import_type: "Insert New Records",
        mute_emails: true,
        status: 'Pending',
        google_sheets_url: googleSheet.value.trim(),
        import_file: importFile.value?.file_url,
    }, {
        onSuccess(data: DataImport) {
            router.replace({
                name: 'DataImport',
                params: {
                    importName: data.name
                },
                query: {
                    step: 'map'
                }
            })
        },
        onError(error: any) {
            toast.error(error.messages?.[0] || error)
            console.error('Error creating data import:', error)
        }
    })
}

const updateImport = () => {
    if (!props.data) return;
    props.dataImports.setValue.submit({
        ...props.data,
        google_sheets_url: googleSheet.value.trim(),
        import_file: importFile.value ? importFile.value.file_url : '',
    }, {
        onSuccess(data: DataImport) {
            nextTick(() => {
                if (importFile.value || googleSheet.value.trim().length) {
                    emit('updateStep', 'map', data)
                } else {
                    emit('updateStep', 'upload', data)
                }
            })
        },
        onError(error: any) {
            toast.error(error.messages?.[0] || error, { duration: 1000 })
            console.error('Error updating data import:', error)
        }
    })
}

const exportTemplate = async (type: 'mandatory' | 'all') => {
    let url = getExportURL(type)
    const response = await fetch(url)
    const blob = await response.blob();
    const link = document.createElement('a');

    link.href = URL.createObjectURL(blob);
    link.download = props.doctype + '.csv'
    document.body.appendChild(link);

    link.click();
    document.body.removeChild(link);
}

const getExportURL = (type: 'mandatory' | 'all') => {
    if (!props.doctype && !props.data?.reference_doctype) return ''
    let exportFields = getExportFields(type)

    return `/api/method/frappe.core.doctype.data_import.data_import.download_template
        ?doctype=${encodeURIComponent(props.doctype || props.data?.reference_doctype as string)}
        &export_fields=${encodeURIComponent(JSON.stringify(exportFields))}
        &export_records=blank_template
        &file_type=CSV`
        .replace(/\s+/g, '')
}

const getExportFields = (type: 'mandatory' | 'all') => {
    /* {'Sales Invoice': ['name', 'customer'], 'Sales Invoice Item': ['item_code']} */
    if (type == "mandatory") {
        return getMandatoryFields()
    }
    return getAllFields()
}

const getMandatoryFields = () => {
    let exportableFields: Record<string, string[]> = {}
    let docs = props.fields.data?.docs || []
    let referenceDoctype = props.doctype || props.data?.reference_doctype as string
    let parentDoctype = docs.find((doc: DocType) => doc.name == referenceDoctype)

    let parentFields = parentDoctype.fields.filter((field: DocField) => {
        return !fieldsToIgnore.includes(field.fieldtype) && field.reqd
    }).map((field: DocField) => field.fieldname)
    parentFields.unshift('name')
    exportableFields[referenceDoctype] = parentFields

    let childDoctypes = parentDoctype.fields.filter((field: DocField) => {
        return (field.fieldtype === 'Table' || field.fieldtype === 'Table MultiSelect') && field.reqd
    })

    childDoctypes.forEach((field: DocField) => {
        let childDoctype = docs.find((doc: DocType) => doc.name == field.options)
        if (childDoctype) {
            let childFields = childDoctype.fields.filter((f: DocField) => {
                return !fieldsToIgnore.includes(f.fieldtype) && f.reqd
            }).map((f: DocField) => f.fieldname)
            childFields.unshift('name')
            exportableFields[field.fieldname] = childFields
        }
    })

    return exportableFields
}

const getAllFields = () => {
    let doctypeMap: Record<string, string[]> = {}
    let docs = props.fields.data?.docs || []
    docs.forEach((doc: DocType) => {
        let exportableFields = doc.fields.filter((field: DocField) => {
            return !fieldsToIgnore.includes(field.fieldtype)
        }).map((field: DocField) => field.fieldname)
        exportableFields.unshift('name')
        let doctypeName = doc.name == props.doctype ? doc.name : getChildTableName(doc.name, props.doctype || props.data?.reference_doctype as string, docs)
        doctypeMap[doctypeName] = exportableFields
    })
    return doctypeMap
}

const openFileSelector = () => {
    fileInput.value?.click()
}

const openSheetSelector = () => {
    showFileSelector.value = false
    showLibrarySelector.value = false
    showSheetSelector.value = true
}

const backToFileSelector = () => {
    showFileSelector.value = true
    showLibrarySelector.value = false
    showSheetSelector.value = false
}

const disableContinueButton = computed(() => {
    return !importFile.value && !googleSheet.value.trim().length
})

watch(() => props.data, () => {
    if (props.data) {
        if (props.data.import_file) {
            importFile.value = props.data.import_file
        } else if (props.data.google_sheets_url) {
            openSheetSelector()
            googleSheet.value = props.data.google_sheets_url
        }
    }
}, { immediate: true })

watch([importFile, googleSheet], () => {
    if (!importFile.value || !googleSheet.value.trim().length) {
        updateImport()
    }
})

const deleteFile = () => {
    importFile.value = null
}

const convertToKB = (bytes: number) => {
    return (bytes / 1024).toFixed(2) + ' KB'
}
</script>