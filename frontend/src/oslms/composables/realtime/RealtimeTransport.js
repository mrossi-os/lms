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

	_emitTranscript(role, text) {
		if (!text) return
		for (const cb of this._transcriptCbs) cb({ role, text })
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
