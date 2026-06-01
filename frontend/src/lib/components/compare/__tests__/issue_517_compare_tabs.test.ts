// TDD RED — Issue #517: Compare-Hub: Detail-Seite als 6-Tab-Hub
//
// Spec: docs/specs/modules/issue_517_compare_hub.md
//
// Source-Inspection-Tests: prüfen Soll-Zustand nach Implementation.
//
// RED-Erwartung (vor Implementation):
//   AC-1: FAIL — CompareTabs.svelte existiert nicht
//   AC-2: FAIL — CompareTabs.svelte enthält nicht alle 6 Tab-Values + Segmented
//   AC-3: FAIL — CompareTabs.svelte enthält kein Übersicht-Tab-Monitoring mit ?tab=-Links
//   AC-4: FAIL — CompareTabs.svelte enthält kein CompareLocationRow + location_ids
//   AC-5: FAIL — CompareTabs.svelte enthält kein CompareIdealRow + ideal_ranges
//   AC-6: FAIL — CompareTabs.svelte enthält kein CHANNEL_COLS mit 4 Kanälen
//   AC-7: FAIL — CompareTabs.svelte enthält kein Versand-Tab mit empfaenger + hour_from
//   AC-8: FAIL — CompareTabs.svelte enthält keinen Vorschau-Placeholder
//   AC-9: FAIL — CompareDetail.svelte enthält nicht alle 5 Pflicht-Strings
//   AC-10: FAIL — +page.svelte enthält nicht searchParams.get('tab') und initialTab
//   AC-Guard: FAIL (oder bereits grün) — +page.svelte importiert NICHT CompareIdealRow/LayoutRow
//   AC-Mobile: FAIL — CompareTabs.svelte enthält kein Mobile-CSS (overflow-x, white-space)
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/compare/__tests__/issue_517_compare_tabs.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const COMPARE_DIR = dirname(fileURLToPath(import.meta.url)) + '/..';
const ROUTES_COMPARE_ID = join(
	COMPARE_DIR,
	'..', '..', '..', 'routes', 'compare', '[id]'
);

const COMPARE_TABS = join(COMPARE_DIR, 'CompareTabs.svelte');
const COMPARE_DETAIL = join(COMPARE_DIR, 'CompareDetail.svelte');
const PAGE_SVELTE = join(ROUTES_COMPARE_ID, '+page.svelte');

// ── AC-1: CompareTabs.svelte existiert ───────────────────────────────────────

describe('AC-1: CompareTabs.svelte existiert', () => {
	test('CompareTabs.svelte ist vorhanden', () => {
		assert.ok(
			existsSync(COMPARE_TABS),
			'CompareTabs.svelte fehlt — muss neu erstellt werden (§1 der Spec)'
		);
	});
});

// ── AC-2: Alle 6 Tab-Values + Segmented-Import ───────────────────────────────

describe('AC-2: CompareTabs.svelte enthält alle 6 Tab-Values und Segmented', () => {
	let src: string;

	test('CompareTabs.svelte ist lesbar', () => {
		assert.ok(existsSync(COMPARE_TABS), 'CompareTabs.svelte fehlt');
		src = readFileSync(COMPARE_TABS, 'utf-8');
	});

	for (const tabValue of ['uebersicht', 'orte', 'idealwerte', 'layout', 'versand', 'vorschau']) {
		test(`Tab-Value '${tabValue}' vorhanden`, () => {
			if (!src) src = readFileSync(COMPARE_TABS, 'utf-8');
			assert.ok(
				src.includes(tabValue),
				`CompareTabs.svelte enthält nicht '${tabValue}' — Tab-Definition fehlt`
			);
		});
	}

	test("Import von 'Segmented' vorhanden", () => {
		if (!src) src = readFileSync(COMPARE_TABS, 'utf-8');
		assert.ok(
			src.includes('Segmented'),
			"CompareTabs.svelte importiert 'Segmented' nicht — Tab-Leiste fehlt"
		);
	});

	for (const label of ['Übersicht', 'Orte', 'Idealwerte', 'Layout', 'Versand', 'Vorschau']) {
		test(`Tab-Label '${label}' vorhanden`, () => {
			if (!src) src = readFileSync(COMPARE_TABS, 'utf-8');
			assert.ok(
				src.includes(label),
				`CompareTabs.svelte enthält nicht Label '${label}'`
			);
		});
	}
});

// ── AC-3: Übersicht-Tab mit Monitoring-Streifen und Bearbeiten-Links ─────────

describe('AC-3: Übersicht-Tab — Monitoring-Streifen + Edit-Links', () => {
	let src: string;
	function getSrc() {
		if (!src) src = existsSync(COMPARE_TABS) ? readFileSync(COMPARE_TABS, 'utf-8') : '';
		return src;
	}

	test("'Nächster Versand' im Übersicht-Tab", () => {
		assert.ok(
			getSrc().includes('Nächster Versand'),
			"CompareTabs.svelte enthält nicht 'Nächster Versand' — Monitoring-Streifen fehlt"
		);
	});

	test("'Zuletzt' im Übersicht-Tab", () => {
		assert.ok(
			getSrc().includes('Zuletzt'),
			"CompareTabs.svelte enthält nicht 'Zuletzt' — Monitoring-Streifen fehlt"
		);
	});

	for (const tabLink of ['?tab=orte', '?tab=idealwerte', '?tab=layout', '?tab=versand']) {
		test(`Bearbeiten-Link '${tabLink}' vorhanden`, () => {
			assert.ok(
				getSrc().includes(tabLink),
				`CompareTabs.svelte enthält nicht '${tabLink}' — Edit-Link aus Übersicht fehlt`
			);
		});
	}
});

// ── AC-4: Orte-Tab — CompareLocationRow + location_ids + elevation_m ─────────

describe('AC-4: Orte-Tab — CompareLocationRow, location_ids, elevation_m', () => {
	let src: string;
	function getSrc() {
		if (!src) src = existsSync(COMPARE_TABS) ? readFileSync(COMPARE_TABS, 'utf-8') : '';
		return src;
	}

	test("'CompareLocationRow' importiert und verwendet", () => {
		assert.ok(
			getSrc().includes('CompareLocationRow'),
			"CompareTabs.svelte enthält nicht 'CompareLocationRow' — Orte-Tab fehlt"
		);
	});

	test("'location_ids' referenziert", () => {
		assert.ok(
			getSrc().includes('location_ids'),
			"CompareTabs.svelte enthält nicht 'location_ids' — Orts-Auflösung fehlt"
		);
	});

	test("'elevation_m' referenziert", () => {
		assert.ok(
			getSrc().includes('elevation_m'),
			"CompareTabs.svelte enthält nicht 'elevation_m' — Höhenangabe fehlt"
		);
	});
});

// ── AC-5: Idealwerte-Tab — CompareIdealRow + ideal_ranges + Leerstate ────────

describe('AC-5: Idealwerte-Tab — CompareIdealRow, ideal_ranges, Leerstate', () => {
	let src: string;
	function getSrc() {
		if (!src) src = existsSync(COMPARE_TABS) ? readFileSync(COMPARE_TABS, 'utf-8') : '';
		return src;
	}

	test("'CompareIdealRow' importiert und verwendet", () => {
		assert.ok(
			getSrc().includes('CompareIdealRow'),
			"CompareTabs.svelte enthält nicht 'CompareIdealRow' — Idealwerte-Tab fehlt"
		);
	});

	test("'ideal_ranges' referenziert", () => {
		assert.ok(
			getSrc().includes('ideal_ranges'),
			"CompareTabs.svelte enthält nicht 'ideal_ranges' — Idealwerte-Daten fehlen"
		);
	});

	test("'Keine Idealwerte konfiguriert' als Leerstate", () => {
		assert.ok(
			getSrc().includes('Keine Idealwerte konfiguriert'),
			"CompareTabs.svelte enthält nicht Leerstate-Text 'Keine Idealwerte konfiguriert'"
		);
	});
});

// ── AC-6: Layout-Tab — CompareLayoutRow + CHANNEL_COLS mit 4 Kanälen ─────────

describe('AC-6: Layout-Tab — CompareLayoutRow, CHANNEL_COLS, Kanal-Constraints', () => {
	let src: string;
	function getSrc() {
		if (!src) src = existsSync(COMPARE_TABS) ? readFileSync(COMPARE_TABS, 'utf-8') : '';
		return src;
	}

	test("'CompareLayoutRow' importiert und verwendet", () => {
		assert.ok(
			getSrc().includes('CompareLayoutRow'),
			"CompareTabs.svelte enthält nicht 'CompareLayoutRow' — Layout-Tab fehlt"
		);
	});

	test("'CHANNEL_COLS' definiert", () => {
		assert.ok(
			getSrc().includes('CHANNEL_COLS'),
			"CompareTabs.svelte enthält nicht 'CHANNEL_COLS' — Kanal-Constraints fehlen"
		);
	});

	// Constraints: email 99 (∞), telegram 8, signal 6, sms 0
	for (const [channel, cols] of [['email', '99'], ['telegram', '8'], ['signal', '6'], ['sms', '0']] as const) {
		test(`Kanal '${channel}' mit Spaltenwert ${cols} definiert`, () => {
			const s = getSrc();
			assert.ok(
				s.includes(channel) && s.includes(String(cols)),
				`CompareTabs.svelte enthält nicht Kanal '${channel}' mit cols=${cols}`
			);
		});
	}
});

// ── AC-7: Versand-Tab — presetScheduleLabel, hour_from, empfaenger, draft-Hint

describe('AC-7: Versand-Tab — Zeitplan, Zeitfenster, Empfänger, Draft-Hinweis', () => {
	let src: string;
	function getSrc() {
		if (!src) src = existsSync(COMPARE_TABS) ? readFileSync(COMPARE_TABS, 'utf-8') : '';
		return src;
	}

	test("'presetScheduleLabel' aufgerufen", () => {
		assert.ok(
			getSrc().includes('presetScheduleLabel'),
			"CompareTabs.svelte enthält nicht 'presetScheduleLabel' — Zeitplan-Anzeige fehlt"
		);
	});

	test("'hour_from' referenziert", () => {
		assert.ok(
			getSrc().includes('hour_from'),
			"CompareTabs.svelte enthält nicht 'hour_from' — Zeitfenster fehlt"
		);
	});

	test("'hour_to' referenziert", () => {
		assert.ok(
			getSrc().includes('hour_to'),
			"CompareTabs.svelte enthält nicht 'hour_to' — Zeitfenster fehlt"
		);
	});

	test("'empfaenger' referenziert (Empfänger-Pills)", () => {
		assert.ok(
			getSrc().includes('empfaenger'),
			"CompareTabs.svelte enthält nicht 'empfaenger' — Empfänger-Anzeige fehlt"
		);
	});

	test("'Noch nicht aktiv' als Draft-Hinweis", () => {
		assert.ok(
			getSrc().includes('Noch nicht aktiv'),
			"CompareTabs.svelte enthält nicht 'Noch nicht aktiv' — Draft-Hinweis fehlt"
		);
	});
});

// ── AC-8: Vorschau-Tab — statischer Placeholder ───────────────────────────────

describe('AC-8: Vorschau-Tab — CompareEmail-Placeholder', () => {
	let src: string;
	function getSrc() {
		if (!src) src = existsSync(COMPARE_TABS) ? readFileSync(COMPARE_TABS, 'utf-8') : '';
		return src;
	}

	test("Placeholder-Text 'CompareEmail implementiert ist' vorhanden", () => {
		assert.ok(
			getSrc().includes('CompareEmail implementiert ist'),
			"CompareTabs.svelte enthält nicht den Vorschau-Placeholder-Text"
		);
	});

	test("Hinweis 'Postfach gelesen' vorhanden", () => {
		assert.ok(
			getSrc().includes('Postfach gelesen'),
			"CompareTabs.svelte enthält nicht den Hinweis 'Postfach gelesen'"
		);
	});

	test("Button 'Test-Briefing senden' vorhanden", () => {
		assert.ok(
			getSrc().includes('Test-Briefing senden'),
			"CompareTabs.svelte enthält nicht den Button 'Test-Briefing senden'"
		);
	});
});

// ── AC-9: URL-Sync — history.replaceState + searchParams.set ─────────────────

describe('AC-9: URL-Sync via history.replaceState + searchParams', () => {
	let src: string;
	function getSrc() {
		if (!src) src = existsSync(COMPARE_TABS) ? readFileSync(COMPARE_TABS, 'utf-8') : '';
		return src;
	}

	test("'history.replaceState' vorhanden", () => {
		assert.ok(
			getSrc().includes('history.replaceState'),
			"CompareTabs.svelte enthält nicht 'history.replaceState' — URL-Sync fehlt"
		);
	});

	test("'searchParams.set' vorhanden", () => {
		assert.ok(
			getSrc().includes('searchParams.set'),
			"CompareTabs.svelte enthält nicht 'searchParams.set' — ?tab=-Schreiben fehlt"
		);
	});
});

// ── AC-Pflicht-Strings: CompareDetail.svelte Thin-Shell ──────────────────────

describe('AC-Pflicht-Strings: CompareDetail.svelte enthält alle 5 Pflicht-Strings', () => {
	let src: string;
	function getSrc() {
		if (!src) src = existsSync(COMPARE_DETAIL) ? readFileSync(COMPARE_DETAIL, 'utf-8') : '';
		return src;
	}

	for (const requiredString of [
		'Nächster Versand',
		'Zuletzt',
		'empfaenger',
		'location_ids',
		'elevation_m',
	]) {
		test(`Pflicht-String '${requiredString}' in CompareDetail.svelte`, () => {
			assert.ok(
				existsSync(COMPARE_DETAIL),
				'CompareDetail.svelte fehlt'
			);
			assert.ok(
				getSrc().includes(requiredString),
				`CompareDetail.svelte enthält nicht '${requiredString}' — Pflicht-String für bestehende Tests fehlt`
			);
		});
	}

	test("CompareDetail.svelte delegiert an 'CompareTabs'", () => {
		assert.ok(
			getSrc().includes('CompareTabs'),
			"CompareDetail.svelte enthält nicht 'CompareTabs' — Delegation fehlt"
		);
	});
});

// ── AC-10: +page.svelte — searchParams.get('tab') + initialTab ───────────────

describe('AC-10: +page.svelte liest ?tab= und gibt initialTab weiter', () => {
	let src: string;
	function getSrc() {
		if (!src) src = existsSync(PAGE_SVELTE) ? readFileSync(PAGE_SVELTE, 'utf-8') : '';
		return src;
	}

	test("+page.svelte enthält searchParams.get('tab')", () => {
		assert.ok(
			existsSync(PAGE_SVELTE),
			'+page.svelte fehlt'
		);
		assert.ok(
			getSrc().includes("searchParams.get('tab')") || getSrc().includes('searchParams.get("tab")'),
			"+page.svelte liest searchParams.get('tab') nicht — ?tab=-Parameter wird nicht verarbeitet"
		);
	});

	test("+page.svelte enthält 'initialTab'", () => {
		assert.ok(
			getSrc().includes('initialTab'),
			"+page.svelte enthält nicht 'initialTab' — initialTab-Prop wird nicht übergeben"
		);
	});
});

// ── AC-Guard: +page.svelte importiert NICHT CompareIdealRow / CompareLayoutRow

describe('AC-Guard: +page.svelte importiert NICHT CompareIdealRow oder CompareLayoutRow', () => {
	let src: string;
	function getSrc() {
		if (!src) src = existsSync(PAGE_SVELTE) ? readFileSync(PAGE_SVELTE, 'utf-8') : '';
		return src;
	}

	test("+page.svelte enthält NICHT 'CompareIdealRow'", () => {
		assert.ok(
			existsSync(PAGE_SVELTE),
			'+page.svelte fehlt'
		);
		assert.ok(
			!getSrc().includes('CompareIdealRow'),
			"+page.svelte importiert 'CompareIdealRow' — verletzt AC-9 (darf nur in CompareTabs.svelte sein)"
		);
	});

	test("+page.svelte enthält NICHT 'CompareLayoutRow'", () => {
		assert.ok(
			!getSrc().includes('CompareLayoutRow'),
			"+page.svelte importiert 'CompareLayoutRow' — verletzt AC-9 (darf nur in CompareTabs.svelte sein)"
		);
	});
});

// ── AC-Mobile: CompareTabs.svelte enthält Mobile-CSS ─────────────────────────

describe('AC-Mobile: CompareTabs.svelte enthält scrollbare Pill-Tabs für Mobile (<900px)', () => {
	let src: string;
	function getSrc() {
		if (!src) src = existsSync(COMPARE_TABS) ? readFileSync(COMPARE_TABS, 'utf-8') : '';
		return src;
	}

	test("'overflow-x' im Style-Block vorhanden", () => {
		assert.ok(
			getSrc().includes('overflow-x'),
			"CompareTabs.svelte enthält nicht 'overflow-x' — Mobile-Scrollbar-CSS fehlt"
		);
	});

	test("'white-space' (nowrap) im Style-Block vorhanden", () => {
		assert.ok(
			getSrc().includes('white-space'),
			"CompareTabs.svelte enthält nicht 'white-space' — Mobile-Nowrap-CSS fehlt"
		);
	});
});
