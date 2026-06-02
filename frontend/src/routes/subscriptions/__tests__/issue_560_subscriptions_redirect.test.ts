// TDD RED — Issue #560: /subscriptions Legacy-Seite bereinigen
//
// Spec: docs/specs/modules/issue_560_subscriptions_redirect.md
//
// Source-Inspection-Tests (node:test, kein DOM-Rendering).
// Prüft: Redirect-Datei, Link auf account-Seite, keine Legacy-Page-Datei.
//
// RED-Erwartung (vor Implementation):
//   - AC-2: account/+page.svelte hat noch href="/subscriptions" → Test FAIL
//   - AC-3: subscriptions/+page.svelte existiert noch → Test FAIL
//   - AC-1: subscriptions/+page.server.ts hat redirect(301,'/compare') → Test PASS (bereits erledigt)
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/routes/subscriptions/__tests__/issue_560_subscriptions_redirect.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const REDIRECT_SERVER = resolve('src/routes/subscriptions/+page.server.ts');
const LEGACY_PAGE     = resolve('src/routes/subscriptions/+page.svelte');
const ACCOUNT_PAGE    = resolve('src/routes/account/+page.svelte');

// ── §1 AC-1: Redirect ist implementiert ──────────────────────────────────────

test('AC-1: +page.server.ts redirectet auf /compare (301)', () => {
	assert.ok(existsSync(REDIRECT_SERVER), '+page.server.ts muss existieren');
	const src = readFileSync(REDIRECT_SERVER, 'utf-8');
	assert.match(
		src,
		/redirect\s*\(\s*301\s*,\s*['"]\/compare['"]/,
		'+page.server.ts muss redirect(301, "/compare") enthalten'
	);
});

// ── §2 AC-2: account/+page.svelte zeigt auf /compare ─────────────────────────

test('AC-2: account/+page.svelte hat keinen Link mehr auf /subscriptions', () => {
	const src = readFileSync(ACCOUNT_PAGE, 'utf-8');
	assert.doesNotMatch(
		src,
		/href=["']\/subscriptions["']/,
		'account/+page.svelte darf keinen href="/subscriptions" mehr haben — muss auf /compare zeigen'
	);
});

test('AC-2b: account/+page.svelte zeigt "Aktive Abos"-Link auf /compare', () => {
	const src = readFileSync(ACCOUNT_PAGE, 'utf-8');
	// Prüft ob irgendwo in der Nähe von data.subscriptions.filter ein /compare-Link existiert
	assert.match(
		src,
		/href=["']\/compare["'][^>]*>[\s\S]{0,200}data\.subscriptions|data\.subscriptions[\s\S]{0,200}href=["']\/compare["']/,
		'account/+page.svelte muss den Abo-Zähler mit href="/compare" verknüpfen'
	);
});

// ── §3 AC-3: Legacy-Seitendatei ist gelöscht ─────────────────────────────────

test('AC-3: subscriptions/+page.svelte existiert nicht mehr (totes Code entfernt)', () => {
	assert.ok(
		!existsSync(LEGACY_PAGE),
		'subscriptions/+page.svelte muss gelöscht sein — sie wird durch +page.server.ts-Redirect nie gerendert'
	);
});
