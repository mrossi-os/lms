import { WebrtcTransport } from './WebrtcTransport'
import { WebsocketTransport } from './WebsocketTransport'

// Pick a transport strategy from the backend descriptor. The backend already
// decided the provider; the client only honors `transport`.
export function createTransport(descriptor) {
	switch (descriptor.transport) {
		case 'webrtc':
			return new WebrtcTransport(descriptor)
		case 'websocket':
			return new WebsocketTransport(descriptor)
		default:
			throw new Error(
				`Unsupported realtime transport: ${descriptor.transport}`,
			)
	}
}
