// Common contract for realtime transports. Subclasses implement connect()
// and close(); the base wires the callback plumbing so the composable is
// transport-agnostic.
export class RealtimeTransport {
	constructor(descriptor) {
		this.descriptor = descriptor
		this._transcriptCbs = []
		this._stateCbs = []
	}

	onTranscript(cb) {
		this._transcriptCbs.push(cb)
	}

	onState(cb) {
		this._stateCbs.push(cb)
	}

	// `text` is the CUMULATIVE text of the current turn (not a delta), so the UI
	// can simply replace the active bubble. `final` marks the turn's end: streamed
	// transports (Gemini) emit many non-final updates then one final; one-shot
	// transports (OpenAI) emit a single final per turn.
	_emitTranscript(role, text, final = true) {
		if (!text) return
		for (const cb of this._transcriptCbs) cb({ role, text, final })
	}

	_emitState(state) {
		for (const cb of this._stateCbs) cb(state)
	}

	// eslint-disable-next-line no-unused-vars
	async connect(mediaStream) {
		throw new Error('connect() not implemented')
	}

	close() {
		throw new Error('close() not implemented')
	}
}
