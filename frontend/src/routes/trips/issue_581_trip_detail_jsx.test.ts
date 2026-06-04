// TDD RED — Issue #581: Trip-Detail 1:1 nach screen-trip-detail.jsx
//
// Spec: docs/specs/modules/issue_581_trip_detail_jsx.md
//
// Source-Inspection-Tests: prüfen, dass NEUE Muster vorhanden und
// ALTE Muster entfernt sind. VOR der Implementierung SCHEITERN sie (RED).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/routes/trips/issue_581_trip_detail_jsx.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

// import.meta.url = .../frontend/src/routes/trips/file.ts
// ../../.. → frontend/
const FRONTEND = fileURLToPath(new URL('../../..', import.meta.url));
const SRC = join(FRONTEND, 'src');

function readSrc(relPath: string): string {
	return readFileSync(join(SRC, relPath), 'utf-8');
}

function existsSrc(relPath: string): boolean {
	return existsSync(join(SRC, relPath));
}

// ─────────────────────────────────────────────────────────────
// AC-9 + AC-10: View-Page Layout — kein danger-zone, TopoBg, kein max-w-5xl
// ─────────────────────────────────────────────────────────────

describe('AC-9/AC-10: +page.svelte Layout', () => {
	const PAGE = 'routes/trips/[id]/+page.svelte';

	test('AC-9: kein data-testid="danger-zone" in der View-Page', () => {
		const src = readSrc(PAGE);
		assert.ok(
			!src.includes('danger-zone'),
			'+page.svelte darf kein data-testid="danger-zone" mehr enthalten — Danger-Zone ist entfernt'
		);
	});

	test('AC-10: TopoBg ist in +page.svelte eingebunden', () => {
		const src = readSrc(PAGE);
		assert.ok(
			src.includes('TopoBg'),
			'+page.svelte muss TopoBg importieren und verwenden (opacity={0.14})'
		);
	});

	test('AC-10: max-w-5xl ist aus dem <main>-Element entfernt', () => {
		const src = readSrc(PAGE);
		assert.ok(
			!src.includes('max-w-5xl'),
			'+page.svelte darf max-w-5xl nicht mehr im Haupt-Wrapper haben'
		);
	});
});

// ─────────────────────────────────────────────────────────────
// AC-1: Breadcrumb-Bar mit Aktions-Buttons oben in View-Page
// ─────────────────────────────────────────────────────────────

describe('AC-1: View-Page Breadcrumb-Bar', () => {
	const PAGE = 'routes/trips/[id]/+page.svelte';

	test('AC-1: breadcrumb-bar testid vorhanden', () => {
		const src = readSrc(PAGE);
		assert.ok(
			src.includes('trip-detail-breadcrumb-bar') || src.includes('breadcrumb-bar'),
			'+page.svelte muss ein Element mit data-testid="trip-detail-breadcrumb-bar" enthalten'
		);
	});

	test('AC-1: "Test-Briefing senden" Button ist in der Breadcrumb-Bar (nicht nur im TripHeader)', () => {
		const src = readSrc(PAGE);
		assert.ok(
			src.includes('Test-Briefing senden'),
			'+page.svelte muss den Button "Test-Briefing senden" direkt in der Breadcrumb-Bar haben'
		);
	});

	test('AC-1: "Pausieren" Button ist in der Breadcrumb-Bar', () => {
		const src = readSrc(PAGE);
		assert.ok(
			src.includes('Pausieren'),
			'+page.svelte muss den Button "Pausieren" in der Breadcrumb-Bar haben'
		);
	});

	test('AC-1: "Archivieren" Button ist in der Breadcrumb-Bar', () => {
		const src = readSrc(PAGE);
		assert.ok(
			src.includes('Archivieren'),
			'+page.svelte muss den Button "Archivieren" in der Breadcrumb-Bar haben'
		);
	});
});

// ─────────────────────────────────────────────────────────────
// AC-2: TripHeader Hero — H1 fontSize 38, Eyebrow "Trip ·"
// ─────────────────────────────────────────────────────────────

describe('AC-2: TripHeader Hero-Typo', () => {
	const HEADER = 'lib/components/trip-detail/TripHeader.svelte';

	test('AC-2: H1 hat font-size 38px (direkt oder via token)', () => {
		const src = readSrc(HEADER);
		assert.ok(
			src.includes('38') && (src.includes('font-size') || src.includes('fontSize')),
			'TripHeader.svelte H1 muss font-size: 38px enthalten'
		);
	});

	test('AC-2: Hero-Padding ist 26px 40px', () => {
		const src = readSrc(HEADER);
		assert.ok(
			src.includes('26px') && src.includes('40px'),
			'TripHeader.svelte muss padding 26px 40px für den Hero-Bereich enthalten'
		);
	});

	test('AC-2: Eyebrow enthält "Trip ·" als Muster', () => {
		const src = readSrc(HEADER);
		assert.ok(
			src.includes('Trip ·') || src.includes("Trip ·"),
			'TripHeader.svelte Eyebrow muss "Trip · {region}" enthalten'
		);
	});
});

// ─────────────────────────────────────────────────────────────
// AC-3: HubOverview.svelte — neue Übersichts-Komponente existiert
// ─────────────────────────────────────────────────────────────

describe('AC-3: HubOverview.svelte Existenz und Struktur', () => {
	const HUB = 'lib/components/trip-detail/HubOverview.svelte';

	test('AC-3: HubOverview.svelte existiert', () => {
		assert.ok(
			existsSrc(HUB),
			'HubOverview.svelte muss unter lib/components/trip-detail/ existieren'
		);
	});

	test('AC-3: HubOverview hat data-testid="hub-overview"', () => {
		if (!existsSrc(HUB)) return; // früher exit wenn noch nicht erstellt
		const src = readSrc(HUB);
		assert.ok(
			src.includes('hub-overview'),
			'HubOverview.svelte muss data-testid="hub-overview" enthalten'
		);
	});

	test('AC-3: HubOverview bindet FullProfile ein', () => {
		if (!existsSrc(HUB)) return;
		const src = readSrc(HUB);
		assert.ok(
			src.includes('FullProfile'),
			'HubOverview.svelte muss FullProfile einbinden (Höhenprofil linke Spalte)'
		);
	});

	test('AC-3: HubOverview bindet TripStageRow ein', () => {
		if (!existsSrc(HUB)) return;
		const src = readSrc(HUB);
		assert.ok(
			src.includes('TripStageRow'),
			'HubOverview.svelte muss TripStageRow einbinden'
		);
	});

	test('AC-3: HubOverview hat 2-Spalten-Grid (1fr 380px)', () => {
		if (!existsSrc(HUB)) return;
		const src = readSrc(HUB);
		assert.ok(
			src.includes('380px'),
			'HubOverview.svelte muss grid-template-columns: "1fr 380px" enthalten'
		);
	});

	test('AC-3: View-Page TripTabs verwendet HubOverview statt TripOverview', () => {
		const tabs = readSrc('lib/components/trip-detail/TripTabs.svelte');
		assert.ok(
			tabs.includes('HubOverview'),
			'TripTabs.svelte muss HubOverview im Übersicht-Tab einbinden (statt TripOverview)'
		);
	});
});

// ─────────────────────────────────────────────────────────────
// AC-4: TripStageRow.svelte — Risiko-Pill-Mapping
// ─────────────────────────────────────────────────────────────

describe('AC-4: TripStageRow.svelte — Risk-Pill', () => {
	const ROW = 'lib/components/trip-detail/TripStageRow.svelte';

	test('AC-4: TripStageRow.svelte existiert', () => {
		assert.ok(
			existsSrc(ROW),
			'TripStageRow.svelte muss unter lib/components/trip-detail/ existieren'
		);
	});

	test('AC-4: TripStageRow importiert Pill-Atom', () => {
		if (!existsSrc(ROW)) return;
		const src = readSrc(ROW);
		assert.ok(src.includes('Pill'), 'TripStageRow.svelte muss Pill importieren und verwenden');
	});

	test('AC-4: TripStageRow hat Risiko-Label für risk=high', () => {
		if (!existsSrc(ROW)) return;
		const src = readSrc(ROW);
		assert.ok(src.includes('Risiko'), 'TripStageRow.svelte muss Label "Risiko" für risk=high enthalten');
	});

	test('AC-4: TripStageRow hat Achten-Label für risk=med', () => {
		if (!existsSrc(ROW)) return;
		const src = readSrc(ROW);
		assert.ok(src.includes('Achten'), 'TripStageRow.svelte muss Label "Achten" für risk=med enthalten');
	});

	test('AC-4: TripStageRow hat 4-Spalten-Grid', () => {
		if (!existsSrc(ROW)) return;
		const src = readSrc(ROW);
		assert.ok(
			src.includes('60px') && src.includes('280px'),
			'TripStageRow.svelte muss grid-template-columns: "60px 1fr 280px 100px" enthalten'
		);
	});
});

// ─────────────────────────────────────────────────────────────
// AC-5: HubSchedule.svelte — 4 Schedule-Cards
// ─────────────────────────────────────────────────────────────

describe('AC-5: HubSchedule.svelte — Briefing-Zeitplan-Tab', () => {
	const SCHED = 'lib/components/trip-detail/HubSchedule.svelte';

	test('AC-5: HubSchedule.svelte existiert', () => {
		assert.ok(
			existsSrc(SCHED),
			'HubSchedule.svelte muss unter lib/components/trip-detail/ existieren'
		);
	});

	test('AC-5: HubSchedule hat data-testid="hub-schedule"', () => {
		if (!existsSrc(SCHED)) return;
		const src = readSrc(SCHED);
		assert.ok(src.includes('hub-schedule'), 'HubSchedule.svelte muss data-testid="hub-schedule" enthalten');
	});

	test('AC-5: HubSchedule hat 4 Schedule-Card-Einträge', () => {
		if (!existsSrc(SCHED)) return;
		const src = readSrc(SCHED);
		const morgen = src.includes('Morgen');
		const abend = src.includes('Abend');
		const alert = src.includes('Alert');
		const trend = src.includes('Trend') || src.includes('Mehrtages');
		assert.ok(
			morgen && abend && alert && trend,
			'HubSchedule.svelte muss alle 4 Briefing-Typen enthalten: Morgen, Abend, Alert, Mehrtages-Trend'
		);
	});

	test('AC-5: HubSchedule bindet Switch ein', () => {
		if (!existsSrc(SCHED)) return;
		const src = readSrc(SCHED);
		assert.ok(src.includes('Switch'), 'HubSchedule.svelte muss Switch-Atom für Toggles einbinden');
	});

	test('AC-5: TripTabs verwendet HubSchedule für den Briefing-Zeitplan-Tab', () => {
		const tabs = readSrc('lib/components/trip-detail/TripTabs.svelte');
		assert.ok(
			tabs.includes('HubSchedule'),
			'TripTabs.svelte muss HubSchedule für den briefings-Tab einbinden'
		);
	});
});

// ─────────────────────────────────────────────────────────────
// AC-6: TripEditView.svelte — Breadcrumb, Hero, Stats-Karte
// ─────────────────────────────────────────────────────────────

describe('AC-6: TripEditView.svelte — Layout und Stats-Karte', () => {
	const EDIT = 'lib/components/edit/TripEditView.svelte';

	test('AC-6: max-w-5xl ist aus TripEditView entfernt', () => {
		const src = readSrc(EDIT);
		assert.ok(
			!src.includes('max-w-5xl'),
			'TripEditView.svelte darf max-w-5xl nicht mehr enthalten'
		);
	});

	test('AC-6: Breadcrumb zeigt "Bearbeiten" als drittes Segment', () => {
		const src = readSrc(EDIT);
		assert.ok(
			src.includes('Bearbeiten'),
			'TripEditView.svelte Breadcrumb muss "Bearbeiten" als drittes Segment enthalten'
		);
	});

	test('AC-6: Stats-Karte enthält GESAMT-Label', () => {
		const src = readSrc(EDIT);
		assert.ok(
			src.includes('GESAMT'),
			'TripEditView.svelte Stats-Karte muss "GESAMT"-Header enthalten'
		);
	});

	test('AC-6: Stats-Karte enthält ZEITRAUM-Label', () => {
		const src = readSrc(EDIT);
		assert.ok(
			src.includes('ZEITRAUM'),
			'TripEditView.svelte Stats-Karte muss "ZEITRAUM"-Header enthalten'
		);
	});
});

// ─────────────────────────────────────────────────────────────
// AC-7: TripEditView.svelte — EtappenStrip statt EditStagesPanelNew im Etappen-Tab
// ─────────────────────────────────────────────────────────────

describe('AC-7: TripEditView.svelte — EtappenStrip im Etappen-Tab', () => {
	const EDIT = 'lib/components/edit/TripEditView.svelte';

	test('AC-7: TripEditView importiert EtappenStrip', () => {
		const src = readSrc(EDIT);
		assert.ok(
			src.includes('EtappenStrip'),
			'TripEditView.svelte muss EtappenStrip importieren und im Etappen-Tab einbinden'
		);
	});

	test('AC-7: TripEditView enthält Hinweis-Text über das Bearbeiten via Klick', () => {
		const src = readSrc(EDIT);
		assert.ok(
			src.includes('Klicke auf eine Etappe'),
			'TripEditView.svelte muss den Hinweis-Text "Klicke auf eine Etappe" enthalten'
		);
	});

	test('AC-7: EditStagesPanelNew ist nicht mehr im Etappen-Tab-Zweig', () => {
		const src = readSrc(EDIT);
		// EditStagesPanelNew darf nicht mehr direkt im etappen-Tab gerendert werden
		// Prüfen ob es noch vorhanden ist (wird durch EtappenStrip ersetzt)
		assert.ok(
			!src.includes('EditStagesPanelNew'),
			'TripEditView.svelte darf EditStagesPanelNew nicht mehr einbinden (durch EtappenStrip ersetzt)'
		);
	});
});

// ─────────────────────────────────────────────────────────────
// AC-8: TripEditView.svelte — Separate Badge-Elemente in Tabs
// ─────────────────────────────────────────────────────────────

describe('AC-8: TripEditView.svelte — Tab-Badges als separate Elemente', () => {
	const EDIT = 'lib/components/edit/TripEditView.svelte';

	test('AC-8: Tabs haben keine Inline-Counts wie "Alarmregeln 5" als reinen String', () => {
		const src = readSrc(EDIT);
		// Das alte Muster war: `"Alarmregeln ${alertRules.length}"` als label-String
		assert.ok(
			!src.includes('`Alarmregeln ${') && !src.includes('"Alarmregeln "'),
			'TripEditView.svelte darf Alarmregeln-Count nicht mehr als Inline-String im Tab-Label haben'
		);
	});

	test('AC-8: Edit-Tab-Leiste enthält separate badge-Elemente', () => {
		const src = readSrc(EDIT);
		assert.ok(
			src.includes('edit-tab-badge') || src.includes('tab-badge'),
			'TripEditView.svelte muss separate data-testid-"tab-badge"-Elemente für Tab-Counts enthalten'
		);
	});
});

// ─────────────────────────────────────────────────────────────
// Neue Hilfs-Komponenten existieren
// ─────────────────────────────────────────────────────────────

describe('Neue Hilfs-Komponenten', () => {
	test('MetricsPreview.svelte existiert', () => {
		assert.ok(
			existsSrc('lib/components/trip-detail/MetricsPreview.svelte'),
			'MetricsPreview.svelte muss unter lib/components/trip-detail/ existieren'
		);
	});

	test('ReportLine.svelte existiert', () => {
		assert.ok(
			existsSrc('lib/components/trip-detail/ReportLine.svelte'),
			'ReportLine.svelte muss unter lib/components/trip-detail/ existieren'
		);
	});

	test('ChannelDot.svelte existiert', () => {
		assert.ok(
			existsSrc('lib/components/trip-detail/ChannelDot.svelte'),
			'ChannelDot.svelte muss unter lib/components/trip-detail/ existieren'
		);
	});
});
