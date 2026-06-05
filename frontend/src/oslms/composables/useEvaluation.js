/**
 * Composable that owns evaluation triggering, polling, and realtime hookup.
 *
 * Exposes three "start" methods (quick, deep, production) plus a poll-until-
 * complete helper and a realtime subscription utility.
 */
import { inject, onUnmounted, ref } from 'vue'
import { createResource, toast } from 'frappe-ui'

const REALTIME_EVENT = 'simulation:eval_complete'

export function useEvaluation() {
	const socket = inject('$socket', null)
	const lastError = ref(null)

	const _runResource = (url) =>
		createResource({
			url,
			method: 'POST',
			onError(e) {
				lastError.value = e?.messages?.[0] || e?.message || String(e)
				toast.error(lastError.value)
			},
		})

	const simulationTestRes = _runResource(
		'os_lms.os_lms.ai.simulations.eval.api.run_simulation_test',
	)
	const prodRes = _runResource(
		'os_lms.os_lms.ai.simulations.eval.api.run_production_evaluation',
	)

	async function runSimulationTest(scenario, studentProfile, numVariants = 1) {
		const out = await simulationTestRes.submit({
			scenario,
			student_profile: studentProfile,
			num_variants: numVariants,
		})
		return out?.eval_id
	}
	async function runProductionEvaluation(sessionId) {
		const out = await prodRes.submit({ session_id: sessionId })
		return out?.eval_id
	}

	const statusRes = createResource({
		url: 'os_lms.os_lms.ai.simulations.eval.api.get_evaluation_status',
	})

	function pollUntilComplete(evalId, { intervalMs = 2000, timeoutMs = 90_000 } = {}) {
		return new Promise((resolve, reject) => {
			const startedAt = Date.now()
			const tick = async () => {
				try {
					const status = await statusRes.submit({ eval_id: evalId })
					if (status.status === 'complete' || status.status === 'failed') {
						resolve(status)
						return
					}
				} catch (e) {
					reject(e)
					return
				}
				if (Date.now() - startedAt > timeoutMs) {
					reject(new Error('poll_timeout'))
					return
				}
				setTimeout(tick, intervalMs)
			}
			tick()
		})
	}

	function subscribeToCompletion({ filter, onComplete }) {
		if (!socket) return () => {}
		const handler = (payload) => {
			if (filter && !filter(payload)) return
			onComplete(payload)
		}
		socket.on(REALTIME_EVENT, handler)
		const off = () => socket.off(REALTIME_EVENT, handler)
		onUnmounted(off)
		return off
	}

	const resultRes = createResource({
		url: 'os_lms.os_lms.ai.simulations.eval.api.get_evaluation_result',
	})
	function loadResult(evalId) {
		return resultRes.submit({ eval_id: evalId })
	}

	return {
		runSimulationTest,
		runProductionEvaluation,
		pollUntilComplete,
		subscribeToCompletion,
		loadResult,
		lastError,
	}
}
