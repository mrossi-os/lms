import { RealtimeTransport } from './RealtimeTransport'

// Gemini Live over WebSocket (BidiGenerateContent). The ephemeral token
// authorizes the connection; the first frame is the setup (persona + voice +
// transcription). Final transcript frames map to {role, text}. Session
// resumption is handled by persisting the handle from SessionResumptionUpdate.
export class WebsocketTransport extends RealtimeTransport {
	async connect(mediaStream) {
		this._emitState('connecting')
		const { connect_url, client_secret, extra } = this.descriptor
		const ws = new WebSocket(
			`${connect_url}?access_token=${encodeURIComponent(client_secret)}`,
		)
		this._ws = ws
		this._mediaStream = mediaStream

		ws.onopen = () => {
			ws.send(
				JSON.stringify({
					setup: {
						model: extra.model,
						systemInstruction: {
							parts: [{ text: extra.instructions }],
						},
						generationConfig: {
							responseModalities: ['AUDIO'],
							speechConfig: {
								voiceConfig: {
									prebuiltVoiceConfig: {
										voiceName: extra.voice,
									},
								},
							},
						},
						inputAudioTranscription: {},
						outputAudioTranscription: {},
						...(extra.resumption_handle
							? {
									sessionResumption: {
										handle: extra.resumption_handle,
									},
								}
							: { sessionResumption: {} }),
					},
				}),
			)
			this._emitState('connected')
			this._startMicPump()
		}
		ws.onmessage = (e) => this._onFrame(e.data)
		ws.onerror = () => this._emitState('error')
		ws.onclose = () => this._emitState('closed')
	}

	async _onFrame(data) {
		const text = typeof data === 'string' ? data : await data.text()
		let frame
		try {
			frame = JSON.parse(text)
		} catch {
			return
		}
		const sc = frame.serverContent || {}
		if (sc.inputTranscription?.text)
			this._emitTranscript('user', sc.inputTranscription.text)
		if (sc.outputTranscription?.text)
			this._emitTranscript('assistant', sc.outputTranscription.text)
		if (frame.sessionResumptionUpdate?.newHandle) {
			this.descriptor.extra.resumption_handle =
				frame.sessionResumptionUpdate.newHandle
		}
		// NOTE: audio playback of sc.modelTurn parts (PCM 24kHz) is wired in the
		// VoiceSession component's audio worklet; omitted here to keep the
		// transport focused on signaling + transcripts.
	}

	_startMicPump() {
		// PCM 16kHz capture + realtimeInput frames. Implemented with an
		// AudioWorklet in VoiceSession.vue; the transport exposes sendAudio().
	}

	sendAudio(base64Pcm) {
		this._ws?.send(
			JSON.stringify({
				realtimeInput: {
					audio: {
						data: base64Pcm,
						mimeType: 'audio/pcm;rate=16000',
					},
				},
			}),
		)
	}

	close() {
		this._ws?.close()
		this._emitState('closed')
	}
}
