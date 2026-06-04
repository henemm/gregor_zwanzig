// TDD RED: Issue #411 (Desktop Stats-Strip) + #413 (Mobile Filter-Pills + Quickactions)
//
// Spec:  docs/specs/modules/issue_411_413_trips_stats_mobile.md
// Route: /trips  →  frontend/src/routes/trips/+page.svelte
//
// Source-Inspection-Tests (analog zu issue_402.test.ts):
// Liest die echte +page.svelte und prüft, ob beide Issues korrekt umgesetzt wurden.
//
// RED: Gegen den aktuellen Stand schlagen alle AC-Tests fehl (Stats-Strip zeigt
// noch Pausiert/Archiviert, keine Filter-Pills, kein expandedCardId, kein tripStatus-Import).
//
// Ausführung:
//   cd frontend && node --experimental-strip-types --test src/routes/trips/issue_411_413.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

const TRIPS_DIR = dirname(fileURLToPath(import.meta.url));
const PAGE_SVELTE = join(TRIPS_DIR, '+page.svelte');

function readPage(): string {
	return readFileSync(PAGE_SVELTE, 'utf-8');
}

function namedImportsFrom(src: string, modulePath: string): string[] {
	const escaped = modulePath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
	const re = new RegExp(`import\\s*\\{([^}]*)\\}\\s*from\\s*['"]${escaped}['"]`, 'g');
	const names: string[] = [];
	let m: RegExpExecArray | null;
	while ((m = re.exec(src))) {
		for (const part of m[1].split(',')) {
			const name = part.trim().replace(/^type\s+/, '').split(/\s+as\s+/)[0].trim();
			if (name) names.push(name);
		}
	}
	return names;
}

// ── #411: Import-Änderungen ──────────────────────────────────────────────────

test('#411 AC-1: tripStatus wird aus $lib/utils/tripStatus importiert', () => {
	const src = readPage();
	const imports = namedImportsFrom(src, '$lib/utils/tripStatus');
	assert.ok(
		imports.includes('tripStatus'),
		`tripStatus nicht importiert (gefunden: ${imports.join(', ') || 'keine'})`
	);
});

test('#411 AC-1: HomeTripStatus wird aus $lib/utils/tripStatus importiert', () => {
	const src = readPage();
	assert.ok(src.includes('HomeTripStatus'), 'HomeTripStatus nicht importiert');
});

test('#411 AC-1: Stat wird NICHT mehr aus molecules importiert', () => {
	const src = readPage();
	const molecules = namedImportsFrom(src, '$lib/components/molecules');
	assert.ok(
		!molecules.includes('Stat'),
		`Stat noch aus molecules importiert — soll durch Inline-HTML ersetzt werden`
	);
});

// ── #411: Stats-Strip Kategorien ─────────────────────────────────────────────

test('#411 AC-1: Stats-Strip hat Kategorie "Abgeschlossen"', () => {
	const src = readPage();
	assert.ok(src.includes('Abgeschlossen'), 'Kategorie "Abgeschlossen" nicht im Stats-Strip');
});

test('#411 AC-3: Stats-Strip hat Kategorie "Drafts"', () => {
	const src = readPage();
	assert.ok(src.includes('Drafts'), 'Kategorie "Drafts" nicht im Stats-Strip');
});

test('#411 AC-1: Stats-Strip enthält NICHT mehr "Pausiert"', () => {
	const src = readPage();
	assert.ok(
		!src.includes("'Pausiert'") && !src.includes('"Pausiert"'),
		'Kategorie "Pausiert" noch im Stats-Strip — muss durch "Abgeschlossen" ersetzt werden'
	);
});

test('#411 AC-1: Stats-Strip enthält NICHT mehr "Archiviert"', () => {
	const src = readPage();
	assert.ok(
		!src.includes("'Archiviert'") && !src.includes('"Archiviert"'),
		'Kategorie "Archiviert" noch im Stats-Strip — muss durch "Drafts" ersetzt werden'
	);
});

test('#411 AC-2/AC-3: Stats-Strip verwendet HomeTripStatus-Werte (aktiv/geplant/fertig/draft)', () => {
	const src = readPage();
	for (const status of ["'aktiv'", "'geplant'", "'fertig'", "'draft'"]) {
		assert.ok(
			src.includes(status),
			`HomeTripStatus-Wert ${status} nicht gefunden — Stats-Strip nutzt noch nicht tripStatus()`
		);
	}
});

test('#411 AC-1 (superseded by #580): <Stat>-Atom für Stats-Bar vorhanden', () => {
	// Issue #580 kehrt die #411-Anforderung um: Stat-Atoms sind jetzt canonical per #578/#580.
	// Stat-Atom mit layout="inline" muss vorhanden sein (siehe issue_580.test.ts AC-1b).
	const src = readPage();
	assert.ok(src.includes('<Stat'), '<Stat>-Atom fehlt — Stats-Bar muss Stat-Atoms nutzen (superseded #411 by #580)');
});

// ── #413: Mobile Filter-Pills ─────────────────────────────────────────────────

test('#413 AC-4: Pill wird aus $lib/components/atoms importiert', () => {
	const src = readPage();
	const atoms = namedImportsFrom(src, '$lib/components/atoms');
	assert.ok(
		atoms.includes('Pill'),
		`Pill nicht aus atoms importiert (gefunden: ${atoms.join(', ') || 'keine'})`
	);
});

test('#413 AC-4: mobileFilter State-Variable existiert', () => {
	const src = readPage();
	assert.ok(src.includes('mobileFilter'), 'State-Variable mobileFilter nicht vorhanden');
});

test('#413 AC-5: mobileFiltered derived-Variable existiert', () => {
	const src = readPage();
	assert.ok(src.includes('mobileFiltered'), 'Derived-Variable mobileFiltered nicht vorhanden');
});

test('#413 AC-4: Filter-Leiste enthält alle 4 Pill-Labels', () => {
	const src = readPage();
	for (const label of ['Alle', 'Aktiv', 'Geplant', 'Fertig']) {
		assert.ok(
			src.includes(`'${label}'`) || src.includes(`"${label}"`),
			`Filter-Label "${label}" nicht im Quellcode gefunden`
		);
	}
});

test('#413 AC-4: Mobile Card-Stack nutzt mobileFiltered statt filteredTrips', () => {
	const src = readPage();
	// Im Mobile-Abschnitt muss mobileFiltered im each-Block stehen
	assert.ok(
		src.includes('mobileFiltered'),
		'mobileFiltered nicht im Mobile Card-Stack verwendet'
	);
	// Sanity: trip-card-stack data-testid muss noch vorhanden sein
	assert.ok(
		src.includes('data-testid="trip-card-stack"'),
		'data-testid="trip-card-stack" fehlt — Mobile Card-Stack entfernt'
	);
});

// ── #413: Mobile Quickactions ─────────────────────────────────────────────────

test('#413 AC-7: expandedCardId State-Variable existiert', () => {
	const src = readPage();
	assert.ok(src.includes('expandedCardId'), 'State-Variable expandedCardId nicht vorhanden');
});

test('#413 AC-8: Quickaction "Briefing senden" existiert', () => {
	const src = readPage();
	assert.ok(src.includes('Briefing senden'), 'Quickaction-Text "Briefing senden" nicht gefunden');
});

test('#413 AC-8: Quickactions navigieren zu #preview und #alerts', () => {
	const src = readPage();
	assert.ok(src.includes('#preview'), 'Deeplink #preview für Briefing-senden fehlt');
	assert.ok(src.includes('#alerts'), 'Deeplink #alerts für Alerts-Button fehlt');
});

test('#413 AC-9: Bottom-Sheet (sheetTrip) bleibt erhalten', () => {
	const src = readPage();
	assert.ok(src.includes('sheetTrip'), 'sheetTrip State fehlt — Bottom-Sheet wurde entfernt');
});

test('#413 AC-10: trip.region wird in der Karte gerendert', () => {
	const src = readPage();
	assert.ok(src.includes('trip.region'), 'trip.region nicht in mobiler Karte gerendert');
});

test('#413 AC-8: SendIcon wird importiert', () => {
	const src = readPage();
	assert.ok(src.includes('SendIcon'), 'SendIcon nicht importiert — fehlt für Briefing-senden-Button');
});

test('#413 AC-8: ExternalLinkIcon wird importiert', () => {
	const src = readPage();
	assert.ok(src.includes('ExternalLinkIcon'), 'ExternalLinkIcon nicht importiert — fehlt für Vorschau-Button');
});
