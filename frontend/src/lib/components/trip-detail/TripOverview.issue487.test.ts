// TDD RED: Issue #487 — TripOverview: 4-Karten-2×2-Dashboard
//
// Spec: docs/specs/modules/issue_487_trip_detail_overview_cards.md
//
// Aktuelle Implementierung (Issue #409) zeigt FullProfile + StageList +
// rechte Preview-Karten. Das neue Design will 4 DetailCard-Kacheln im
// 2×2-Grid. Diese Tests schlagen auf der alten Implementierung fehl.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/TripOverview.issue487.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT = join(here, 'TripOverview.svelte');
const source = readFileSync(COMPONENT, 'utf8');

// ─────────────────────────────────────────────────────────────
// AC-1: Die Komponente nutzt DetailCard (nicht die alten Preview-Karten)
// ─────────────────────────────────────────────────────────────

describe('AC-1: DetailCard-Import und Struktur', () => {
	test('importiert DetailCard', () => {
		assert.ok(
			source.includes('DetailCard'),
			'TripOverview muss DetailCard importieren und verwenden'
		);
	});

	test('bindet NICHT mehr FullProfile ein', () => {
		assert.ok(
			!source.includes('FullProfile'),
			'TripOverview darf FullProfile nicht mehr einbinden (wurde durch 4-Card-Grid ersetzt)'
		);
	});

	test('bindet NICHT mehr StageList ein', () => {
		assert.ok(
			!source.includes('StageList'),
			'TripOverview darf StageList nicht mehr einbinden (wurde durch 4-Card-Grid ersetzt)'
		);
	});

	test('bindet NICHT mehr BriefingPreviewCard ein', () => {
		assert.ok(
			!source.includes('BriefingPreviewCard'),
			'TripOverview darf BriefingPreviewCard nicht mehr einbinden'
		);
	});

	test('enthält genau 4 DetailCard-Instanzen', () => {
		// Zähle <DetailCard … über mehrere Zeilen
		const matches = source.match(/<DetailCard/g);
		assert.ok(matches, 'Keine <DetailCard>-Instanzen gefunden');
		assert.strictEqual(
			matches!.length,
			4,
			`Erwartet 4 DetailCard-Instanzen, gefunden: ${matches!.length}`
		);
	});
});

// ─────────────────────────────────────────────────────────────
// AC-1: Korrekte testid-Attribute für alle 4 Karten
// ─────────────────────────────────────────────────────────────

describe('AC-1: testid-Attribute der 4 Karten', () => {
	test('card-reports vorhanden', () => {
		assert.ok(
			source.includes('card-reports'),
			'Karte "Was geht raus" braucht testid="card-reports"'
		);
	});

	test('card-alerts vorhanden', () => {
		assert.ok(
			source.includes('card-alerts'),
			'Karte "Alarm-Schwellen" braucht testid="card-alerts"'
		);
	});

	test('card-stages vorhanden', () => {
		assert.ok(
			source.includes('card-stages'),
			'Karte "Route & Etappen" braucht testid="card-stages"'
		);
	});

	test('card-schedule vorhanden', () => {
		assert.ok(
			source.includes('card-schedule'),
			'Karte "Datenstand" braucht testid="card-schedule"'
		);
	});
});

// ─────────────────────────────────────────────────────────────
// AC-5: Jede Karte verlinkt auf den richtigen Tab-Hash
// ─────────────────────────────────────────────────────────────

describe('AC-5: Action-Links zu Tab-Hashes', () => {
	test('Reports-Karte verlinkt auf ?tab=briefings (Bug #533 — Issue #516 Konsistenz)', () => {
		assert.ok(
			source.includes('?tab=briefings'),
			'Karte "Was geht raus" muss ?tab=briefings verwenden (nicht #briefings)'
		);
	});

	test('Alerts-Karte verlinkt auf ?tab=alerts (Bug #502 — Issue #516 Konsistenz)', () => {
		assert.ok(
			source.includes('?tab=alerts'),
			'Karte "Wachhund-Schwellen" muss ?tab=alerts verwenden (nicht #alerts)'
		);
	});

	test('Stages-Karte verlinkt auf /trips/[id]/edit (Issue #503)', () => {
		// Issue #503 AC-1: "Etappen öffnen" navigiert nicht mehr zum #stages-Tab,
		// sondern direkt in den Wegpunkt-Editor /trips/{trip.id}/edit.
		const hasEditLink =
			source.includes('/trips/${trip.id}/edit') ||
			source.includes('/trips/{trip.id}/edit') ||
			/\/trips\/\$\{[a-zA-Z_.]+\}\/edit/.test(source);
		assert.ok(
			hasEditLink,
			'Karte "Route & Etappen" muss auf /trips/{trip.id}/edit verlinken (Issue #503 AC-1)'
		);
	});

	test('Datenstand-Karte verlinkt auf ?tab=preview (Bug #533 — Issue #516 Konsistenz)', () => {
		assert.ok(
			source.includes('?tab=preview'),
			'Karte "Datenstand" muss ?tab=preview verwenden (nicht #preview)'
		);
	});
});

// ─────────────────────────────────────────────────────────────
// AC-2/AC-3/AC-4: Korrekte Datenquellen
// ─────────────────────────────────────────────────────────────

describe('AC-2/3/4: Richtige Utilities genutzt', () => {
	test('nutzt getReportSchedule für Reports/Datenstand-Karten', () => {
		assert.ok(
			source.includes('getReportSchedule'),
			'TripOverview muss getReportSchedule(trip) für Briefing-Daten verwenden'
		);
	});

	test('nutzt computeTripStats für Route & Etappen-Karte', () => {
		assert.ok(
			source.includes('computeTripStats'),
			'TripOverview muss computeTripStats(trip) für Etappen-Statistiken verwenden'
		);
	});

	test('nutzt alert_rules für Alarm-Schwellen-Karte', () => {
		assert.ok(
			source.includes('alert_rules'),
			'TripOverview muss trip.alert_rules für die Alarmregeln-Karte verwenden'
		);
	});

	test('AC-6: hat Fallback für leeres alert_rules', () => {
		// Nullsafe: (trip.alert_rules ?? []) oder trip?.alert_rules?.filter
		const hasNullsafe =
			source.includes('alert_rules ?? []') ||
			source.includes('alert_rules?.') ||
			source.includes("alert_rules || []");
		assert.ok(
			hasNullsafe,
			'alert_rules muss null-safe behandelt werden (trip.alert_rules ?? [] oder ?.)'
		);
	});
});

// ─────────────────────────────────────────────────────────────
// Layout: 2×2-Grid vorhanden
// ─────────────────────────────────────────────────────────────

describe('Layout: overview-grid', () => {
	test('enthält CSS-Klasse overview-grid', () => {
		assert.ok(
			source.includes('overview-grid'),
			'TripOverview braucht eine .overview-grid-CSS-Klasse für das 2×2-Layout'
		);
	});

	test('CSS-Grid ist 2-spaltig', () => {
		const hasTwoColumns =
			source.includes('1fr 1fr') ||
			source.includes('repeat(2') ||
			source.includes('grid-template-columns');
		assert.ok(hasTwoColumns, 'overview-grid muss ein 2-spaltiges CSS-Grid verwenden');
	});
});
