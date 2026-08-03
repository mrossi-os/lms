<template>
	<div
		class="text-sm text-ink-gray-9 absolute bg-surface-elevation-2 border rounded-md z-10 w-44"
		:style="{
			display: top > 0 ? 'block' : 'none',
			top: top + 'px',
			insetInlineStart: left + 'px',
		}"
	>
		<div class="space-y-2 py-2">
			<div class="text-xs-medium text-ink-gray-5 px-3">
				{{ __('Highlight') }}
			</div>
			<div class="">
				<div
					v-for="color in colors"
					class="flex items-center gap-x-2 px-3 py-2 cursor-pointer hover:bg-surface-gray-2"
					@click="saveHighLight(color)"
				>
					<span
						class="size-3 rounded-full"
						:style="{
							backgroundColor: getColor(color.toLowerCase(), 400),
						}"
					></span>
					<span>
						{{ __(color) }}
					</span>
				</div>
			</div>
		</div>
		<div class="border-t">
			<div
				@click="addToNotes()"
				class="flex items-center gap-x-2 hover:bg-surface-gray-2 cursor-pointer rounded-b-md py-2 px-3"
			>
				<span class="lucide-notepad-text size-3" />
				<span>
					{{ __('Add to Notes') }}
				</span>
			</div>
			<div
				v-if="highlightExists()"
				@click="deleteHighlight"
				class="flex items-center gap-x-2 hover:bg-surface-gray-2 cursor-pointer rounded-b-md py-2 px-3"
			>
				<span class="lucide-trash-2 size-3" />
				<span>
					{{ __('Remove Highlight') }}
				</span>
			</div>
		</div>
	</div>
</template>
<script setup lang="ts">
import { computed, inject, ref, watch } from 'vue'
import type { Note, Notes } from '@/components/Notes/types'
import {
	blockQuotesClick,
	getColor,
	getRangeOffset,
	highlightText,
	removeHighlight,
} from '@/utils'

const user = inject<any>('$user')
const show = defineModel()
const notes = defineModel<Notes>('notes')
const top = ref(0)
const left = ref(0)
const currentSelection = ref<Selection | null>(null)
const selectedText = ref('')
const selectionOffset = ref<number | null>(null)
const emit = defineEmits<{
	(e: 'updateNotes'): void
}>()

const props = defineProps<{
	lesson: string
}>()

watch(show, () => {
	if (!show.value) {
		return resetMenuPosition()
	}

	currentSelection.value = window.getSelection()
	if (!currentSelection.value?.toString()) {
		return resetMenuPosition()
	}

	updateMenuPosition()
})

const updateMenuPosition = () => {
	const range = currentSelection.value?.rangeCount
		? currentSelection.value.getRangeAt(0)
		: null
	if (!range) return

	// Range.toString() rather than Selection.toString(): the latter can insert
	// newlines at block boundaries, which would desync the text from the offset.
	selectedText.value = range.toString()
	selectionOffset.value = getRangeOffset(range)

	const rect = range.getBoundingClientRect()
	if (!rect) return

	const offsetY = window.scrollY
	const offsetX = window.scrollX

	top.value = Math.floor(rect.top + offsetY - 40)
	left.value = Math.floor(rect.right + offsetX + 10)
}

const resetMenuPosition = () => {
	top.value = 0
	left.value = 0
}

const colors = computed(() => {
	return ['Red', 'Blue', 'Green', 'Yellow', 'Purple']
})

// Match on the offset too, otherwise a second highlight of the same word would
// resolve to the first note and delete the wrong one. Notes saved before the
// offset existed carry 0 and can only be matched on their text.
const noteForSelection = () => {
	return notes.value?.data?.find((note: Note) => {
		if (note.highlighted_text !== selectedText.value) return false
		if (selectionOffset.value === null || !note.text_offset) return true
		return note.text_offset === selectionOffset.value
	})
}

const highlightExists = () => {
	return Boolean(noteForSelection())
}

const saveHighLight = (color: string) => {
	if (!selectedText.value) return

	const offset = selectionOffset.value
	notes.value?.insert.submit(
		{
			lesson: props.lesson,
			member: user?.data?.name,
			highlighted_text: selectedText.value,
			text_offset: offset ?? 0,
			color: color,
			name: '',
		},
		{
			onSuccess(data: Note) {
				highlightText({ ...data, text_offset: offset ?? 0 })
				resetStates()
				emit('updateNotes')
			},
			onError(err: any) {
				console.error('Error saving highlight:', err)
				resetStates()
			},
		}
	)
}

const deleteHighlight = () => {
	const notesToDelete = noteForSelection()
	if (!notesToDelete) return
	notes.value?.delete.submit(notesToDelete.name, {
		onSuccess() {
			resetStates()
			removeHighlight(notesToDelete.name)
		},
		onError(err: any) {
			console.error('Error deleting highlight:', err)
			resetStates()
		},
	})
}

const addToNotes = () => {
	if (!selectedText.value) return
	let noteToUpdate = notes.value?.data.find((note: Note) => {
		return !note.highlighted_text && note.note !== ''
	})
	if (!noteToUpdate) {
		createNote()
	} else {
		updateNote(noteToUpdate)
	}
}

const createNote = () => {
	notes.value?.insert.submit(
		{
			lesson: props.lesson,
			member: user?.data?.name,
			note: `<blockquote><p>${selectedText.value}</p></blockquote><br>`,
			color: 'Yellow',
			name: '',
		},
		{
			onSuccess(data: Note) {
				emit('updateNotes')
				setTimeout(() => {
					scrollToText(selectedText.value)
					blockQuotesClick()
					resetStates()
				}, 100)
			},
			onError(err: any) {
				console.error('Error creating note:', err)
				resetStates()
			},
		}
	)
}

const updateNote = (noteToUpdate: Note) => {
	notes.value?.setValue.submit(
		{
			name: noteToUpdate.name,
			note: `${noteToUpdate.note}\n\n<blockquote><p>${selectedText.value}</p></blockquote><br>`,
		},
		{
			onSuccess(data: Note) {
				emit('updateNotes')
				setTimeout(() => {
					scrollToText(selectedText.value)
					blockQuotesClick()
					resetStates()
				}, 100)
			},
			onError(err: any) {
				console.error('Error updating note:', err)
				resetStates()
			},
		}
	)
}

const scrollToText = (text: string) => {
	const elements = document.querySelectorAll('blockquote p')
	Array.from(elements).forEach((el) => {
		const element = el as HTMLElement
		if (element.textContent?.toLowerCase().includes(text.toLowerCase())) {
			element.scrollIntoView({ behavior: 'smooth', block: 'center' })
		}
	})
}

const resetStates = () => {
	selectedText.value = ''
	selectionOffset.value = null
	show.value = false
	resetMenuPosition()
}
</script>
