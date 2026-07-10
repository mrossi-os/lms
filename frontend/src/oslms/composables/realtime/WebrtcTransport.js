import { RealtimeTransport } from './RealtimeTransport'

// OpenAI Realtime over WebRTC. The ephemeral client_secret authorizes the SDP
// exchange; events arrive on the `oai-events` data channel as JSON. Final
// transcript events are mapped to {role, text}.
const USER_EVENT = 'conversation.item.input_audio_transcription.completed'
const ASSISTANT_EVENT = 'response.output_audio_transcript.done'

export class WebrtcTransport extends RealtimeTransport {
	async connect(mediaStream) {
		this._emitState('connecting')
		const pc = new RTCPeerConnection()
		this._pc = pc

		// Play remote audio.
		this._audioEl = new Audio()
		this._audioEl.autoplay = true
		pc.ontrack = (e) => {
			this._audioEl.srcObject = e.streams[0]
		}

		// Send mic.
		for (const track of mediaStream.getAudioTracks()) {
			pc.addTrack(track, mediaStream)
		}

		// Events channel.
		const dc = pc.createDataChannel('oai-events')
		this._dc = dc
		dc.onmessage = (e) => this._onEvent(e.data)
		// The role-player opens the conversation: with server VAD the model
		// otherwise stays silent until the user speaks. Ask it to speak first
		// as soon as the events channel is ready.
		dc.onopen = () => {
			dc.send(JSON.stringify({ type: 'response.create' }))
		}

		pc.onconnectionstatechange = () => {
			if (pc.connectionState === 'connected') this._emitState('connected')
			if (['failed', 'disconnected'].includes(pc.connectionState))
				this._emitState('error')
			if (pc.connectionState === 'closed') this._emitState('closed')
		}

		const offer = await pc.createOffer()
		await pc.setLocalDescription(offer)

		const url = `${this.descriptor.connect_url}?model=${encodeURIComponent(this.descriptor.model)}`
		const resp = await fetch(url, {
			method: 'POST',
			body: offer.sdp,
			headers: {
				Authorization: `Bearer ${this.descriptor.client_secret}`,
				'Content-Type': 'application/sdp',
			},
		})
		if (!resp.ok) {
			this._emitState('error')
			throw new Error(`SDP exchange failed: ${resp.status}`)
		}
		const answer = { type: 'answer', sdp: await resp.text() }
		await pc.setRemoteDescription(answer)
	}

	_onEvent(raw) {
		let ev
		try {
			ev = JSON.parse(raw)
		} catch {
			return
		}
		if (ev.type === USER_EVENT)
			this._emitTranscript('user', ev.transcript || '')
		else if (ev.type === ASSISTANT_EVENT)
			this._emitTranscript('assistant', ev.transcript || '')
	}

	close() {
		this._dc?.close()
		if (this._pc) {
			this._pc.onconnectionstatechange = null
			this._pc.close()
		}
		if (this._audioEl) this._audioEl.srcObject = null
		this._emitState('closed')
	}
}
