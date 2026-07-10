import { RealtimeTransport } from './RealtimeTransport'

// Gemini Live over WebSocket (BidiGenerateContentConstrained). The ephemeral
// token authorizes the connection; persona/voice/model/transcription are locked
// into the token server-side, so the client only opens the stream and moves
// audio. Unlike the WebRTC transport (where the browser handles the media
// natively), here we must do the audio ourselves:
//   - mic  -> resample to 16 kHz, PCM16 mono, base64, realtimeInput frames
//   - model -> serverContent.modelTurn inlineData is PCM 24 kHz; decode + play
// Final transcript frames map to {role, text}. Session resumption is handled by
// persisting the handle from SessionResumptionUpdate.
const INPUT_SAMPLE_RATE = 16000 // Gemini expects 16 kHz PCM input
const OUTPUT_SAMPLE_RATE = 24000 // Gemini emits 24 kHz PCM output
const MIC_FRAME_SIZE = 2048 // ScriptProcessor buffer (~128 ms at 16 kHz)

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
			// Persona, voice, modalities and transcription are locked into the
			// ephemeral token server-side; the client cannot change them and no
			// longer receives them. We only open the stream: the model must still
			// be named (Gemini wants the `models/<id>` form) and we optionally
			// restore the session-resumption handle, which stays client-managed.
			ws.send(
				JSON.stringify({
					setup: {
						model: this._qualifiedModel(extra.model),
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
			// NOTE: we do NOT emit 'connected' here — the session is only usable
			// once Gemini acknowledges the setup (setupComplete). Emitting early
			// would hide a setup rejection behind a brief 'connected' flash.
		}
		ws.onmessage = (e) => {
			this._onFrame(e.data).catch(() => {})
		}
		ws.onerror = (e) => {
			console.error('[realtime] websocket error', e)
			this._emitState('error')
		}
		ws.onclose = (e) => {
			// close() nulls this handler before an intentional close, so if we
			// land here the server closed the socket unexpectedly. Code 1000 is a
			// clean end; anything else (setup rejected, auth, policy) is an error
			// and must NOT be treated as a normal end (which would jump to debrief).
			console.error(
				`[realtime] websocket closed code=${e.code} reason=${e.reason || '(none)'}`,
			)
			this._emitState(e.code === 1000 ? 'closed' : 'error')
		}
	}

	_qualifiedModel(model) {
		if (!model) return model
		return model.startsWith('models/') ? model : `models/${model}`
	}

	async _onFrame(data) {
		const text = typeof data === 'string' ? data : await data.text()
		let frame
		try {
			frame = JSON.parse(text)
		} catch {
			return
		}
		// Setup acknowledged: only now is the session usable. Emit 'connected',
		// start streaming mic, and kick off the opening turn. Gemini stays silent
		// after setup until it receives client content, so we send an empty
		// turn-complete signal: it prompts the model to speak first from its
		// (server-locked) system instruction WITHOUT injecting a user turn, so
		// nothing leaks into the transcript (built only from audio in/out
		// transcription frames).
		if (frame.setupComplete) {
			this._emitState('connected')
			this._startMicPump()
			this._sendGreetingTrigger()
			return
		}
		const sc = frame.serverContent || {}
		// Barge-in: drop queued model audio AND close the partial model turn so
		// what was said so far is persisted as one message.
		if (sc.interrupted) {
			this._flushPlayback()
			this._finalizeTurn('assistant')
		}
		// Transcription streams in chunks. Accumulate per turn so the UI shows one
		// growing bubble (and the backend stores one Turn) instead of N fragments.
		if (sc.inputTranscription?.text) {
			this._userBuf = (this._userBuf || '') + sc.inputTranscription.text
			this._emitTranscript('user', this._userBuf, false)
		}
		if (sc.outputTranscription?.text) {
			// The first model chunk means the user finished speaking: close theirs.
			this._finalizeTurn('user')
			this._modelBuf = (this._modelBuf || '') + sc.outputTranscription.text
			this._emitTranscript('assistant', this._modelBuf, false)
		}
		// End of the model's turn: finalize both buffers (user is usually already
		// closed; the call is a no-op when the buffer is empty).
		if (sc.turnComplete || sc.generationComplete) {
			this._finalizeTurn('user')
			this._finalizeTurn('assistant')
		}
		// Model audio: PCM 24 kHz mono chunks in modelTurn.parts[].inlineData.
		for (const part of sc.modelTurn?.parts || []) {
			const inline = part.inlineData
			if (inline?.data && (inline.mimeType || '').startsWith('audio/pcm')) {
				this._enqueuePlayback(this._base64ToFloat32(inline.data))
			}
		}
		if (frame.sessionResumptionUpdate?.newHandle) {
			this.descriptor.extra.resumption_handle =
				frame.sessionResumptionUpdate.newHandle
		}
	}

	_finalizeTurn(role) {
		const buffer = role === 'user' ? this._userBuf : this._modelBuf
		if (buffer) this._emitTranscript(role, buffer, true)
		if (role === 'user') this._userBuf = ''
		else this._modelBuf = ''
	}

	_sendGreetingTrigger() {
		// turnComplete with no `turns` = "user turn is over, your move" without
		// adding any user content. Mirrors the OpenAI response.create kickoff.
		if (this._ws?.readyState === WebSocket.OPEN) {
			this._ws.send(JSON.stringify({ clientContent: { turnComplete: true } }))
		}
	}

	// ---- mic capture (browser mic -> 16 kHz PCM16 -> base64 -> Gemini) ----

	_startMicPump() {
		if (!this._mediaStream || this._inCtx) return
		const AudioCtx = window.AudioContext || window.webkitAudioContext
		// Requesting a 16 kHz context makes the MediaStreamSource resample the
		// mic (usually 48 kHz) down to what Gemini wants, so no manual resampling.
		const ctx = new AudioCtx({ sampleRate: INPUT_SAMPLE_RATE })
		this._inCtx = ctx
		if (ctx.state === 'suspended') ctx.resume()
		const source = ctx.createMediaStreamSource(this._mediaStream)
		// ScriptProcessorNode is deprecated but avoids shipping a separate
		// AudioWorklet module; fine for a single mono capture stream.
		const processor = ctx.createScriptProcessor(MIC_FRAME_SIZE, 1, 1)
		processor.onaudioprocess = (e) => {
			this.sendAudio(this._floatTo16BitPcmBase64(e.inputBuffer.getChannelData(0)))
		}
		source.connect(processor)
		// Must connect to destination for onaudioprocess to fire; we never write
		// the output buffer, so this emits silence (no mic echo).
		processor.connect(ctx.destination)
		this._micSource = source
		this._micProcessor = processor
	}

	sendAudio(base64Pcm) {
		if (this._ws?.readyState === WebSocket.OPEN) {
			this._ws.send(
				JSON.stringify({
					realtimeInput: {
						audio: {
							data: base64Pcm,
							mimeType: `audio/pcm;rate=${INPUT_SAMPLE_RATE}`,
						},
					},
				}),
			)
		}
	}

	// ---- model playback (Gemini 24 kHz PCM -> scheduled AudioBuffers) ----

	_enqueuePlayback(float32) {
		if (!float32.length) return
		if (!this._outCtx) {
			const AudioCtx = window.AudioContext || window.webkitAudioContext
			this._outCtx = new AudioCtx()
			this._playHead = 0
			this._playSources = new Set()
		}
		const ctx = this._outCtx
		if (ctx.state === 'suspended') ctx.resume()
		// The buffer declares its own 24 kHz rate; the context resamples to its
		// own rate on playback, so this is correct even if the context is 48 kHz.
		const buffer = ctx.createBuffer(1, float32.length, OUTPUT_SAMPLE_RATE)
		buffer.getChannelData(0).set(float32)
		const src = ctx.createBufferSource()
		src.buffer = buffer
		src.connect(ctx.destination)
		// Schedule chunks back-to-back to avoid gaps/overlap.
		const startAt = Math.max(ctx.currentTime, this._playHead)
		src.start(startAt)
		this._playHead = startAt + buffer.duration
		this._playSources.add(src)
		src.onended = () => this._playSources?.delete(src)
	}

	_flushPlayback() {
		if (this._playSources) {
			for (const src of this._playSources) {
				try {
					src.stop()
				} catch {
					// already stopped/ended
				}
			}
			this._playSources.clear()
		}
		this._playHead = this._outCtx ? this._outCtx.currentTime : 0
	}

	// ---- PCM <-> base64 helpers (little-endian 16-bit, as Gemini uses) ----

	_floatTo16BitPcmBase64(float32) {
		const view = new DataView(new ArrayBuffer(float32.length * 2))
		for (let i = 0; i < float32.length; i++) {
			const s = Math.max(-1, Math.min(1, float32[i]))
			view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
		}
		const bytes = new Uint8Array(view.buffer)
		let binary = ''
		for (let i = 0; i < bytes.length; i++)
			binary += String.fromCharCode(bytes[i])
		return btoa(binary)
	}

	_base64ToFloat32(base64) {
		const binary = atob(base64)
		const bytes = new Uint8Array(binary.length)
		for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
		const view = new DataView(bytes.buffer)
		const out = new Float32Array(bytes.length >> 1)
		for (let i = 0; i < out.length; i++) out[i] = view.getInt16(i * 2, true) / 0x8000
		return out
	}

	close() {
		// Tear down mic capture.
		if (this._micProcessor) {
			this._micProcessor.onaudioprocess = null
			try {
				this._micProcessor.disconnect()
			} catch {
				// ignore
			}
			this._micProcessor = null
		}
		if (this._micSource) {
			try {
				this._micSource.disconnect()
			} catch {
				// ignore
			}
			this._micSource = null
		}
		if (this._inCtx) {
			try {
				this._inCtx.close()
			} catch {
				// ignore
			}
			this._inCtx = null
		}
		// Tear down playback.
		this._flushPlayback()
		if (this._outCtx) {
			try {
				this._outCtx.close()
			} catch {
				// ignore
			}
			this._outCtx = null
		}
		// Tear down the socket (mic tracks themselves are stopped by the caller).
		if (this._ws) {
			this._ws.onclose = null
			this._ws.onerror = null
			this._ws.close()
		}
		this._emitState('closed')
	}
}
