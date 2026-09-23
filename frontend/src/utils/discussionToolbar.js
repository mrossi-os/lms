// Toolbar items hidden in the Discussions editor. The RichTextEditor fixed
// toolbar always includes the "Embed" (iframe) button: excluding it keeps
// learners from embedding iframes in batch discussions.
import { InsertIframe } from 'frappe-ui/editor'

export const discussionExcludedItems = [InsertIframe]
