// Issue #1756 — AC-7: HTTP 409 ("already_in_progress") zeigt die Backend-
// Detail-Meldung, unterscheidbar von der generischen 5xx-Serverfehler-
// Meldung, OHNE automatischen Retry/Poll.
// Spec: docs/specs/modules/fix_1756_send_idempotenz_lock.md — AC-7.
//
// doc-compliance-test (Quelltext-Pruefung). Grund identisch zu
// pageServerEtagPassthrough.test.ts im selben Ordner: `+page.svelte`
// importiert `$app/state`/`$app/navigation` — virtuelle SvelteKit-Module,
// die node --test (kein vitest/jsdom in diesem Repo) nicht aufloesen kann.
//
// RED-Charakter: Mutations-Waechter, HEUTE BEREITS GRUEN. Laut Spec
// (Implementation Details Punkt 4) faellt ein 409 strukturell bereits in
// den bestehenden generischen 4xx-Zweig (`else if (detail)`), der die
// Backend-Meldung anzeigt -- kein Frontend-Codeaenderung fuer AC-7 noetig.
// Dieser Test ist deshalb bewusst ein Regressions-Waechter, keine
// Bug-Reproduktion: sein Wert liegt darin, ein kuenftiges Refactoring
// (z.B. den 409-Fall versehentlich in den >=500-Zweig verschieben) rot
// werden zu lassen.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', '+page.svelte'), 'utf-8');

function handleTestBriefingBody(): string {
	const start = src.indexOf('async function handleTestBriefing(');
	assert.ok(start >= 0, 'handleTestBriefing() wurde in +page.svelte nicht gefunden');
	const end = src.indexOf('\n\t}\n', start);
	assert.ok(end > start, 'Funktionsende von handleTestBriefing() nicht gefunden');
	return src.slice(start, end);
}

describe('AC-7: 409 "already_in_progress" zeigt die Backend-Meldung, kein Retry', () => {
	test('test_handleTestBriefing_hasDistinctBranchForServerErrorsVs4xxDetail', () => {
		const body = handleTestBriefingBody();
		// Serverfehler-Zweig (>=500): generische Meldung, KEIN roher detail-Text.
		assert.match(
			body,
			/res\.status\s*>=\s*500/,
			'handleTestBriefing() unterscheidet nicht nach res.status >= 500 -- ' +
				'ohne diesen Zweig waere ein 409 nicht von einem 5xx-Serverfehler unterscheidbar'
		);
		// 4xx-Zweig zeigt den Backend-Detail-Text (409 faellt hierher, da 409 < 500).
		assert.match(
			body,
			/else\s+if\s*\(\s*detail\s*\)\s*\{\s*\n?\s*testBriefingMessage\s*=\s*detail\s*;/,
			'handleTestBriefing() setzt testBriefingMessage bei einem 4xx mit detail (z.B. 409) ' +
				'nicht auf den Backend-Detail-Text'
		);
	});

	test('test_handleTestBriefing_500BranchDoesNotShowRawDetail', () => {
		const body = handleTestBriefingBody();
		const serverErrorIdx = body.search(/if\s*\(\s*res\.status\s*>=\s*500\s*\)\s*\{/);
		assert.ok(serverErrorIdx >= 0, '>=500-Zweig nicht gefunden');
		const elseIfIdx = body.indexOf('else if (detail)', serverErrorIdx);
		assert.ok(elseIfIdx > serverErrorIdx, 'else-if(detail)-Zweig nicht NACH dem >=500-Zweig gefunden');
		const serverErrorBranch = body.slice(serverErrorIdx, elseIfIdx);
		assert.doesNotMatch(
			serverErrorBranch,
			/testBriefingMessage\s*=\s*detail\s*;/,
			'Der >=500-Zweig darf den rohen detail-Text NICHT anzeigen -- sonst waere ein ' +
				'409 nicht mehr von einem echten Serverfehler unterscheidbar, faellt ein Refactoring ' +
				'den 409-Fall versehentlich in diesen Zweig'
		);
	});

	test('test_handleTestBriefing_makesExactlyOneFetchCall_noAutoRetry', () => {
		const body = handleTestBriefingBody();
		const fetchCalls = body.match(/\bfetch\(/g) ?? [];
		assert.equal(
			fetchCalls.length,
			1,
			`handleTestBriefing() darf genau EINEN fetch()-Aufruf enthalten (kein automatischer ` +
				`Retry/Poll bei 409), gefunden ${fetchCalls.length}`
		);
	});
});
