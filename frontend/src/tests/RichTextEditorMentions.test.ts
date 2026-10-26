/**
 * RichTextEditor: mentions that load after the editor reach the @ menu.
 *
 * frappe-ui's Editor reads `extensions` once at setup. The discussion composer
 * renders the editor with an empty mention list and fills it when the user list
 * arrives, so the items must be a getter, not a copy taken at setup (with the
 * copy the @ menu stayed empty for every role).
 */
import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

const { configure } = vi.hoisted(() => ({
	configure: vi.fn((options) => ({ name: 'richTextKit', options })),
}))

vi.mock('frappe-ui', () => ({
	useFileUpload: () => ({ upload: vi.fn() }),
}))
vi.mock('frappe-ui/editor', () => {
	const stub = { template: '<div />' }
	return {
		Editor: { template: '<div><slot /></div>' },
		EditorContent: stub,
		EditorFixedMenu: stub,
		RichTextKit: { configure },
		AlignCenter: {},
		AlignLeft: {},
		AlignRight: {},
		Blockquote: {},
		Bold: {},
		BulletList: {},
		FontColor: {},
		HeadingGroup: {},
		HorizontalRule: {},
		InlineCode: {},
		InsertIframe: {},
		InsertImage: {},
		InsertLink: {},
		InsertTable: {},
		InsertVideo: {},
		Italic: {},
		OrderedList: {},
		Redo: {},
		Separator: {},
		Strike: {},
		Undo: {},
	}
})

import RichTextEditor from '@/components/RichTextEditor.vue'

function mentionOption() {
	return configure.mock.calls.at(-1)?.[0].mention
}

describe('RichTextEditor mentions', () => {
	it('serves a mention list that arrives after the editor is created', async () => {
		configure.mockClear()
		const wrapper = mount(RichTextEditor, { props: { mentions: [] } })

		const mention = mentionOption()
		expect(typeof mention.items).toBe('function')
		expect(mention.items()).toEqual([])

		await wrapper.setProps({
			mentions: [{ value: 'val@x.it', label: 'Val' }],
		})

		// The editor is not rebuilt: the same getter now returns the new list.
		expect(configure).toHaveBeenCalledTimes(1)
		expect(mention.items()).toEqual([{ id: 'val@x.it', label: 'Val' }])
	})

	it('leaves mentions off when no list is given', () => {
		configure.mockClear()
		mount(RichTextEditor)
		expect(mentionOption()).toBe(false)
	})
})
