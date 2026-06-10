// TDD RED — Issue #699: Doppelter Pfad im Trip-Header.
//
// Spec: docs/specs/modules/issue_699_doppelter_pfad_header.md
//
// Bug: TripHeader.svelte rendert eine ZWEITE Breadcrumb ("MEINE TRIPS › …")
// direkt unter der korrekten oberen Breadcrumb aus +page.svelte. Zusätzlich
// zeigt die Eyebrow das falsche Format "Trip · {region}" statt
// "{REGION} · {DATUMSBEREICH}".
//
// Soll:
//   Trips / KHW 403                          ← obere Breadcrumb (+page.svelte, bleibt)
//   KARNISCHE ALPEN · 03.06. – 14.06.2026    ← Eyebrow: REGION · DATUMSBEREICH
//   Karnischer Höhenweg 403                  ← H1
//
// Test-Pattern: Das Frontend nutzt `node --experimental-strip-types --test`,
// das KEINE `.svelte`-Imports laden kann. Daher Source-Inspection wie in
// `TripHeader.spacing.test.ts`. Der echte Verhaltensnachweis folgt via
// Playwright/staging-validator gegen Staging.
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test \
//     src/lib/components/trip-detail/TripHeader.issue699.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const COMPONENT = join(here, 'TripHeader.svelte');
const source = readFileSync(COMPONENT, 'utf8');

describe('AC-1: keine zweite Breadcrumb mehr im TripHeader', () => {
	test('Der String "MEINE TRIPS" kommt nicht mehr vor', () => {
		assert.ok(
			!source.includes('MEINE TRIPS'),
			'TripHeader.svelte darf die zweite Breadcrumb "MEINE TRIPS › …" nicht mehr enthalten — ' +
				'die obere Breadcrumb-Bar kommt aus +page.svelte.'
		);
	});

	test('kein data-testid="trip-detail-breadcrumb" (innere nav) mehr', () => {
		assert.ok(
			!source.includes('data-testid="trip-detail-breadcrumb"'),
			'TripHeader.svelte darf die innere <nav data-testid="trip-detail-breadcrumb"> nicht mehr enthalten.'
		);
	});
});

describe('AC-3-follow-up: Meta-Zeile zeigt KEIN Datum mehr (nur Strecke + Höhenmeter)', () => {
	// PO-Entscheidung: Datum nur einmal — in der Eyebrow. Die Meta-Zeile
	// (data-testid="trip-detail-meta") darf dateRange nicht mehr rendern.
	const lines = source.split('\n');
	// Den meta-line-Block isolieren: von "meta-line" bis zur schließenden </div>
	const metaStart = lines.findIndex((l) => l.includes('meta-line'));
	const metaEnd = lines.findIndex((l, i) => i > metaStart && l.includes('</div>'));
	const metaBlock = lines.slice(metaStart, metaEnd + 1).join('\n');

	test('meta-line-Block enthält dateRange nicht mehr', () => {
		assert.ok(metaStart >= 0, 'meta-line-Block nicht gefunden');
		assert.ok(
			!metaBlock.includes('dateRange'),
			`Meta-Zeile darf dateRange nicht mehr rendern — Datum steht nur noch in der Eyebrow.\n` +
				`Gefunden: ${JSON.stringify(metaBlock.trim())}`
		);
	});

	test('meta-line-Block enthält kein {#if dateRange} mehr', () => {
		assert.ok(metaStart >= 0, 'meta-line-Block nicht gefunden');
		assert.ok(
			!metaBlock.includes('{#if dateRange}'),
			`Meta-Zeile darf keinen {#if dateRange}-Block mehr enthalten.\n` +
				`Gefunden: ${JSON.stringify(metaBlock.trim())}`
		);
	});

	test('eyebrowText-Derived nutzt dateRange weiterhin (kein verwaister Import)', () => {
		// dateRange muss im eyebrowText-Kontext weiterhin vorkommen —
		// weder die Variable noch formatDateRange dürfen verwaist sein.
		assert.ok(
			source.includes('eyebrowText') && source.includes('dateRange'),
			'eyebrowText muss dateRange weiterhin referenzieren.'
		);
	});
});

describe('AC-2: Eyebrow zeigt REGION · DATUMSBEREICH', () => {
	test('kein "Trip ·"-Präfix mehr in der Eyebrow', () => {
		assert.ok(
			!source.includes('Trip ·'),
			'TripHeader.svelte Eyebrow darf das alte Format "Trip · {region}" nicht mehr enthalten.'
		);
	});

	test('Eyebrow rendert region zusammen mit dem Datumsbereich (dateRange)', () => {
		// Die Eyebrow-Region-Zeile muss sowohl trip.region als auch den
		// Datumsbereich (dateRange via formatDateRange) anzeigen.
		assert.ok(
			source.includes('trip.region'),
			'TripHeader.svelte Eyebrow muss trip.region rendern.'
		);
		assert.ok(
			source.includes('dateRange'),
			'TripHeader.svelte Eyebrow muss den Datumsbereich (dateRange) rendern.'
		);
	});
});
