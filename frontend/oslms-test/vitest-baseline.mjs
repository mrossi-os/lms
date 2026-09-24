#!/usr/bin/env node
// OSLMS-CUSTOM: run Vitest and judge the result against a baseline of known
// failures instead of "everything green".
//
// Many upstream tests fail on this fork by design: they assert upstream
// behaviour our customizations change, or their mocks do not know a module
// our grafts import. Editing those upstream test files would turn every
// upstream merge that touches them into a conflict, so they stay as they are
// and are listed, one by one with the reason, in known-failures.json.
//
// The run fails when:
//   - a test fails that is not in the baseline (a real regression), or
//   - a test in the baseline passes (it got fixed: drop it from the list), or
//   - on a full run, a baseline entry matches no test at all (renamed/removed).
//
// Usage: `yarn test` (full run) or `yarn test src/tests/foo.test.ts`.
// Plain Vitest without the baseline: `yarn test:raw`.

import { spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const frontend = join(here, '..')
const baseline = JSON.parse(readFileSync(join(here, 'known-failures.json'), 'utf8'))

// `yarn test --run` is what upstream's workflow calls; `vitest run` already
// runs once, so the flag is dropped rather than passed twice.
const passthrough = process.argv.slice(2).filter((arg) => arg !== '--run')
const isFullRun = !passthrough.some((arg) => !arg.startsWith('-'))

const outDir = mkdtempSync(join(tmpdir(), 'vitest-baseline-'))
const outFile = join(outDir, 'report.json')
const run = spawnSync(
	'npx',
	['vitest', 'run', '--reporter=default', '--reporter=json', `--outputFile=${outFile}`, ...passthrough],
	{ cwd: frontend, stdio: 'inherit' }
)

let report
try {
	report = JSON.parse(readFileSync(outFile, 'utf8'))
} catch {
	console.error('\nvitest-baseline: Vitest produced no JSON report (exit code %s).', run.status)
	process.exit(run.status || 1)
} finally {
	rmSync(outDir, { recursive: true, force: true })
}

// Ids match known-failures.json: "<file> > <describe…> <title>" for a test,
// "<file> [suite]" for a file that fails before running any test.
const failed = new Set()
const passed = new Set()
const ranFiles = new Set()
for (const file of report.testResults) {
	const name = relative(join(frontend, 'src/tests'), file.name)
	ranFiles.add(name)
	if (file.status === 'failed' && file.assertionResults.length === 0) {
		failed.add(`${name} [suite]`)
		continue
	}
	for (const test of file.assertionResults) {
		const id = `${name} > ${[...test.ancestorTitles, test.title].join(' ')}`
		if (test.status === 'failed') failed.add(id)
		else if (test.status === 'passed') passed.add(id)
	}
}

const known = Object.keys(baseline.tests)
const unexpected = [...failed].filter((id) => !(id in baseline.tests))
const fixed = known.filter((id) => passed.has(id))
const stale = isFullRun
	? known.filter((id) => !failed.has(id) && !passed.has(id))
	: known.filter((id) => ranFiles.has(id.split(/ > | \[suite\]/)[0]) && !failed.has(id) && !passed.has(id))

const expected = known.filter((id) => failed.has(id)).length
console.log(`\nvitest-baseline: ${failed.size} failing, ${expected} of them known (known-failures.json).`)

const list = (title, ids) => {
	if (!ids.length) return
	console.log(`\n${title} (${ids.length}):`)
	for (const id of ids) console.log(`  - ${id}`)
}
list('NEW failures, not in the baseline: fix the code, or agree the rule and list it', unexpected)
list('Known failures that now PASS: remove them from known-failures.json', fixed)
list('Baseline entries that match no test (renamed or removed upstream?)', stale)

const ok = !unexpected.length && !fixed.length && !stale.length
console.log(ok ? '\nvitest-baseline: OK' : '\nvitest-baseline: FAILED')
process.exit(ok ? 0 : 1)
