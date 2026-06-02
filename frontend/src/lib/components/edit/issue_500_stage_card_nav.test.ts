// Issue #500 — Etappen-Kacheln anklickbar + Edit-Seite erreichbar
//
// Spec: docs/specs/modules/issue_500_stage_card_nav.md
// Abgedeckte ACs: AC-1, AC-2, AC-3, AC-4
//
// Source-Inspection-Tests (kein DOM-Rendering, keine Mocks).
// Methodik: node:test + readFileSync/existsSync — prüft Datei-Invarianten.
//
// Ausführen:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/edit/issue_500_stage_card_nav.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));

const PAGE_SERVER = join(here, '..', '..', '..', 'routes', 'trips', '[id]', 'edit', '+page.server.ts');
const STAGE_CARD = join(here, '..', 'trip-detail', 'waypoints', 'StageCard.svelte');
const ETAPPEN_STRIP = join(here, '..', 'trip-detail', 'waypoints', 'EtappenStrip.svelte');
const ISSUE_407_SPEC = join(here, '..', '..', '..', '..', 'e2e', 'issue-407-waypoint-editor-screen.spec.ts');

// ────────────────────────────────────────────────────────────────────────────
// AC-1: +page.server.ts liefert Trip-Daten statt 301-Redirect
// ────────────────────────────────────────────────────────────────────────────

describe('#500 AC-1: Edit-Seite ohne Redirect erreichbar', () => {
	test('AC-1a: +page.server.ts enthält keinen 301-Redirect mehr', () => {
		const src = readFileSync(PAGE_SERVER, 'utf-8');
		assert.ok(
			!src.includes('redirect(301'),
			'+page.server.ts darf keinen redirect(301, ...) mehr enthalten — ' +
				'die Edit-Seite muss direkt die TripEditView laden (Issue #500 AC-1)'
		);
	});

	test('AC-1b: +page.server.ts lädt den Trip über die API', () => {
		const src = readFileSync(PAGE_SERVER, 'utf-8');
		assert.ok(
			src.includes('/api/trips/') && src.includes('return { trip }'),
			'+page.server.ts muss den Trip via fetch("/api/trips/...") laden und { trip } zurückgeben ' +
				'(Issue #500 AC-1)'
		);
	});

	test('AC-1c: +page.server.ts leitet Session-Cookie weiter', () => {
		const src = readFileSync(PAGE_SERVER, 'utf-8');
		assert.ok(
			src.includes('gz_session') && src.includes('cookies.get'),
			'+page.server.ts muss das gz_session-Cookie an den API-Aufruf weitergeben ' +
				'(Issue #500 AC-1, Auth-Invariante)'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// AC-2: StageCard zeigt cursor-pointer + Hover-Feedback wenn onclick gesetzt
// ────────────────────────────────────────────────────────────────────────────

describe('#500 AC-2: StageCard cursor-pointer und Hover-Effekt', () => {
	test('AC-2a: StageCard hat eine .stage-card--clickable CSS-Klasse mit cursor: pointer', () => {
		const src = readFileSync(STAGE_CARD, 'utf-8');
		assert.ok(
			src.includes('stage-card--clickable') && src.includes('cursor: pointer'),
			'StageCard.svelte muss .stage-card--clickable mit cursor: pointer definieren ' +
				'(Issue #500 AC-2 — aktuell nur cursor: default für alle Kacheln)'
		);
	});

	test('AC-2b: StageCard bindet stage-card--clickable an das onclick-Prop', () => {
		const src = readFileSync(STAGE_CARD, 'utf-8');
		assert.ok(
			src.includes('class:stage-card--clickable={!!onclick}') ||
				src.includes("class:stage-card--clickable={onclick !== undefined}") ||
				src.includes('class:stage-card--clickable={Boolean(onclick)}'),
			'StageCard.svelte muss .stage-card--clickable nur setzen wenn onclick definiert ist ' +
				'(Issue #500 AC-2 — bedingte Klasse)'
		);
	});

	test('AC-2c: StageCard .stage-card--clickable hat einen :hover-Zustand', () => {
		const src = readFileSync(STAGE_CARD, 'utf-8');
		assert.ok(
			src.includes('stage-card--clickable:hover') ||
				src.includes('.stage-card--clickable:hover'),
			'StageCard.svelte muss einen :hover-Stil für .stage-card--clickable definieren ' +
				'(Issue #500 AC-2 — sichtbares Hover-Feedback)'
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// AC-3: EtappenStrip verdrahtet onclick → StageCard aktiviert Etappe
// ────────────────────────────────────────────────────────────────────────────

describe('#500 AC-3: Klick auf Kachel aktiviert Etappe', () => {
	test('AC-3a: EtappenStrip übergibt onclick an StageCard', () => {
		const src = readFileSync(ETAPPEN_STRIP, 'utf-8');
		assert.ok(
			src.includes('onclick={makeStageActivateHandler(') ||
				src.includes('onclick={makeStageActivate('),
			'EtappenStrip.svelte muss onclick={makeStageActivateHandler(...)} an StageCard weitergeben ' +
				'(Issue #500 AC-3 — Klick-Verdrahtung)'
		);
	});

	test('AC-3b: StageCard wendet stage-card--clickable auf den normalen UND Pause-Zweig an', () => {
		const src = readFileSync(STAGE_CARD, 'utf-8');
		// Beide divs (normal stage + pause) müssen die bedingte Klasse haben
		const occurrences = (src.match(/class:stage-card--clickable/g) ?? []).length;
		assert.ok(
			occurrences >= 2,
			`StageCard.svelte muss class:stage-card--clickable in BEIDEN Zweigen (normal + Pause) setzen — ` +
				`gefunden: ${occurrences}×, erwartet: ≥2 (Issue #500 AC-3)`
		);
	});
});

// ────────────────────────────────────────────────────────────────────────────
// AC-4: issue-407 Skip-Tests klar als verworfene Architektur dokumentiert
// ────────────────────────────────────────────────────────────────────────────

describe('#500 AC-4: issue-407 Skip-Tests historisch dokumentiert', () => {
	test('AC-4a: issue-407 Kommentar erklärt verworfene Architektur', () => {
		const src = readFileSync(ISSUE_407_SPEC, 'utf-8');
		assert.ok(
			src.includes('verworfene Architektur') || src.includes('verworfenen Architektur'),
			'issue-407-waypoint-editor-screen.spec.ts muss im Kommentar "verworfene Architektur" erwähnen ' +
				'(Issue #500 AC-4 — historische Dokumentation der abgelehnten WaypointEditorPage-Lösung)'
		);
	});

	test('AC-4b: issue-407 Kommentar verbietet Aktivierung der Tests', () => {
		const src = readFileSync(ISSUE_407_SPEC, 'utf-8');
		assert.ok(
			src.includes('NICHT aktivieren') || src.includes('nicht aktivieren'),
			'issue-407-waypoint-editor-screen.spec.ts muss im Kommentar "NICHT aktivieren" enthalten ' +
				'(Issue #500 AC-4 — verhindert versehentliche Reaktivierung)'
		);
	});
});
