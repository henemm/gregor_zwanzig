// Issue #2658 (i18n F9, Epic #2644) — AC-3: das Anlegen eines Trips (/trips/new,
// TripNewEditor) und der Etappen-Editor (EditStagesPanelNew samt Datums-/Startzeit-
// Feld) stehen fuer englischsprachige Nutzer auf Englisch: Reiter, Hinweise,
// Schaltflaechen, Fehlermeldungen; der Wochentag im Datumsfeld ist `Wed`/`Thu`
// (fmtWeekday), deutsch weiter `Mi`/`Do`. Eingegebene Namen bleiben unveraendert,
// die gespeicherte Nutzlast ist in beiden Sprachen gleich aufgebaut.
// Echte SSR-Renders ueber den F9-Pruefstand (trip-detail/__tests__/f9Pruefstand.ts);
// jeder en-Fall rendert zuerst de und schaltet dann OHNE Neuladen auf en.
// Spec: docs/specs/modules/i18n_f9_trip_flaechen_2658.md
//
//   cd frontend && npm test -- src/lib/components/trip-new/__tests__/trip_anlegen_sprache.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import * as P from '../../trip-detail/__tests__/f9Pruefstand.ts';
import { F9_ANKER } from '../../trip-detail/__tests__/f9KatalogAnker.ts';

const { locale } = P;
afterEach(() => locale.set('de'));

const sichtbar = (html: string) =>
	html.replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<(?:"[^"]*"|'[^']*'|[^'">])*>/g, ' ').replace(/&amp;/g, '&').replace(/\s+/g, ' ').trim();
const hat = (text: string, teil: string) => assert.ok(text.includes(teil), `fehlt: „${teil}"\nin: ${text.slice(0, 2500)}`);
const hatNicht = (text: string, teil: string) => assert.ok(!text.includes(teil), `steht noch: „${teil}"`);
function deDannEn<T>(f: () => T): { de: T; en: T } {
	locale.set('de');
	const de = f();
	locale.set('en');
	const en = f();
	return { de, en };
}

/** Paket-Anker (Anlegen + Etappen-Editor), deren deutsche Festteile im en-Render nicht mehr stehen duerfen. */
const PRUEF = ['trip.anlegen.', 'trip.kaskade.', 'trip.etappen_editor.', 'trip.datum', 'trip.trip_start', 'trip.startzeit', 'trip.etappe_loeschen', 'trip.etappe_entfernen', 'trip.plus_etappe', 'trip.aktivitaet.', 'trip.wegpunkt.', 'trip.keine_wegpunkte', 'trip.wegpunkte'];
/** Daten der Fixture bzw. Beispielnamen (z.B. „Karnischer Höhenweg") sind keine Paket-Texte. */
const DATEN = ['trip.anlegen.name_beispiel', 'trip.anlegen.region_beispiel', 'trip.anlegen.etappe_beispiel', 'trip.wegpunkt.typ.'];
function deutscheReste(text: string): string[] {
	const reste: string[] = [];
	for (const [k, de, en] of F9_ANKER) {
		if (de === en || !PRUEF.some((p) => k === p || (p.endsWith('.') && k.startsWith(p))) || DATEN.some((d) => k === d || (d.endsWith('.') && k.startsWith(d)))) continue;
		const enTeile = new Set(en.split(/<[a-z0-9_]+>/).map((s) => s.trim()));
		for (const teil of de.split(/<[a-z0-9_]+>/).map((s) => s.trim())) {
			if ((teil.match(/[A-Za-zÄÖÜäöüß]/g) ?? []).length < 5 || enTeile.has(teil)) continue;
			if (text.includes(teil)) reste.push(`${k}: ${teil}`);
		}
	}
	return reste;
}
const alle = (fall: string) => P.ANLEGE_FAELLE[fall].map(P.anlegenRendern).join('\n');

describe('AC-3: /trips/new englisch (Desktop und mobil)', () => {
	test('Route-Schritt: Kopf, Reiter, Felder, Platzhalter, Pflicht-Hinweise, Aktivitaeten', () => {
		const { de, en } = deDannEn(() => alle('anlegen_route'));
		hat(sichtbar(de), 'Neue Trip anlegen');
		const s = sichtbar(en);
		for (const t of ['Create new trip', 'No name yet', 'Nothing set up yet', 'Route', 'Stages & GPX', 'Check waypoints', 'Weather metrics', 'Target ranges', 'Alerts', 'optional', 'Trip basics', 'Trip name', 'Region', 'optional · max 50', 'Start date', 'Stage 1 starts on 1 Jul — each following stage +1 day.', 'Activity type', 'Hiking (default)', 'Alpine trekking', 'Hiking', 'Ski touring trips', 'Mountaineering', 'Via ferrata', 'Bike (20 km/h)', 'You upload GPX files in the next step — one file per stage.', '⊘ Trip name missing', '⊘ Start date missing', 'Create stages →', 'Set up alerts to save', 'Save trip', 'Enter trip name', 'New trip', 'Trips'])
			hat(s, t);
		for (const t of ['title="Locked — trip name + start date first"', 'placeholder="e.g. Karnischer Höhenweg 2026"', 'placeholder="e.g. Karnische Alpen"']) hat(en, t);
		assert.deepEqual(deutscheReste(s), []);
	});

	test('Etappen-Schritt: Spaltenkoepfe, Datum `1 Jul`, Plural ohne GPX, Knoepfe; Etappen-Name unveraendert', () => {
		const { de, en } = deDannEn(() => alle('anlegen_etappen'));
		hat(sichtbar(de), '01.07.');
		const s = sichtbar(en);
		for (const t of ['Stages', 'Name stages & upload a GPX file per stage', '0 / 2 GPX loaded', 'Start: 1 Jul', 'Stage name', 'Date', 'GPX file', '1 Jul', '2 Jul', 'Upload GPX', '+ Add stage', '⊘ 2 stages without a GPX file — waypoints are calculated automatically after the upload.', '⊘ 1 stage without a GPX file', 'Check waypoints →', '3 stages', '0/3 GPX', 'Name stage 2 …', '3 more GPX needed', 'Calenzana'])
			hat(s, t);
		hat(en, 'placeholder="Name stage 2 …"');
		hat(en, 'aria-label="Remove stage"');
		hat(en, 'value="Calenzana"');
		hatNicht(s, '01.07.');
		assert.deepEqual(deutscheReste(s), []);
	});

	test('Wegpunkte- und Alarme-Schritt: Hinweise und Weiter-Knoepfe englisch', () => {
		const { en } = deDannEn(() => alle('anlegen_weiter'));
		const s = sichtbar(en);
		for (const t of ['Waypoints calculated from GPX — optional check', 'Waypoints are weather divides — points where elevation, aspect or terrain changes. You can rename, move or add to them. You can also skip this step.', 'Skip →', 'Accept waypoints →', 'Skip', 'Set target ranges →', 'Set up alerts →', 'Waypoints calculated automatically. Adjust names or skip.', 'Save trip', 'Save'])
			hat(s, t);
		assert.deepEqual(deutscheReste(s), []);
	});

	test('Anlege-Fehler: Rueckfall-Meldung wird beim Rendern aufgeloest (nicht eingefroren)', () => {
		// Ein Speicherfehler ohne Server-Text wird als Flag gehalten: derselbe Zustand
		// zeigt nach dem Sprachwechsel die englische Meldung.
		const html = (P as unknown as { anlegenFehlerRendern: () => string }).anlegenFehlerRendern;
		assert.equal(typeof html, 'function', 'Pruefstand: anlegenFehlerRendern fehlt');
		const { de, en } = deDannEn(() => sichtbar(html()));
		hat(de, '⚠ Fehler beim Speichern');
		hat(en, '⚠ Error while saving');
	});
});

describe('AC-3: Etappen-Editor englisch, Wochentag ueber fmtWeekday', () => {
	test('Desktop: Kopf, Datum/Startzeit, Karte, Profil, Wegpunkte, Speichern; Wochentag Wed (de Mi)', () => {
		const { de, en } = deDannEn(() => P.etappenEditorRendern('desktop'));
		hat(sichtbar(de), 'Mi');
		const s = sichtbar(en);
		for (const t of ['Stage · GR20-01', 'Calenzana – Ortu di u Piobbu', 'Waypoints are weather divides — points where elevation, aspect or terrain changes. 2 waypoints were created from the GPX', 'Date · Trip start', 'Wed', 'Start time', 'Map · OpenTopoMap (OSM + SRTM)', 'Topo', 'Elevation profile · synced with map', 'Waypoints', '2 in total', '+ on route', 'Save stages', 'STAGES · DRAG TO SORT', '+ Stage'])
			hat(s, t);
		for (const t of ['title="Rename stage"', 'aria-label="Rename stage"']) hat(en, t);
		hatNicht(s, ' Mi ');
		assert.deepEqual(deutscheReste(s), []);
	});

	test('Kaskaden-Rueckfrage und -Bestaetigung: Plural exakt, Datum englisch', () => {
		const { de, en } = deDannEn(() => sichtbar(P.etappenEditorRendern('kaskade_offen') + ' || ' + P.etappenEditorRendern('kaskade_fertig')));
		hat(de, 'Diese Etappe liegt jetzt am 05.07.2026.');
		hat(de, 'Sollen die 2 folgenden Etappen lückenlos anschließen, ab 06.07.2026?');
		for (const t of ['This stage is now on 5 Jul 2026.', 'Should the 2 following stages follow without a gap, from 6 Jul 2026?', 'Follow without a gap', 'Only this stage', 'Re-dated without gaps', '· the 2 following stages, from 6 Jul 2026.', 'Close', 'Click in the elevation profile to insert a waypoint', 'Saved ✓'])
			hat(en, t);
		assert.deepEqual(deutscheReste(en), []);
	});

	test('Mobil: Hinweis, Liste, Wahl Etappe/Pausentag englisch', () => {
		const { en } = deDannEn(() => sichtbar(P.etappenEditorRendern('mobil')));
		for (const t of ['Map & elevation profile', 'are available on desktop. The full elevation profile stays in the overview tab.', '3 stages · drag to sort', '+ Stage', 'Stage', 'Rest day']) hat(en, t);
		assert.deepEqual(deutscheReste(en), []);
	});

	test('Datumsfeld: Wochentag je Sprache, Trip-Start und Startzeit englisch', () => {
		const { de, en } = deDannEn(() => sichtbar(P.editFelderRendern()));
		for (const t of ['So', 'Mo', 'Di', 'Datum · Trip-Start', '· Trip-Start', 'Startzeit']) hat(de, t);
		for (const t of ['Sun', 'Mon', 'Tue', 'Date · Trip start', '· Trip start', 'Start time', 'Weather profile', 'Custom selection', '1 columns · 1 detail · 2 active', 'Edit in the weather tab →', 'Read-only.', 'Create 2 stages', '2 file(s) selected', 'Drag GPX files here', 'or click to choose', '2 stage(s) loaded', 'Create manually', 'Trip name'])
			hat(en, t);
	});
});

describe('AC-3: eingegebene Namen unveraendert gespeichert, Nutzlast sprachunabhaengig', () => {
	const zustand = () => ({
		name: 'Karnischer Höhenweg 2026',
		region: 'Karnische Alpen',
		startDate: '2026-07-01',
		stages: [{ id: 1, name: 'Sillian → Obstanser See', waypoints: [] }, { id: 2, name: 'Etappe Zwei', waypoints: [] }],
		weatherMetrics: [],
		channels: { email: true, telegram: true, sms: false }
	});
	const ohneIds = (t: Record<string, unknown>) => JSON.parse(JSON.stringify(t, (k, v) => (k === 'id' ? undefined : v)));
	test('buildCreateTripPayload in de und en gleich; Namen byte-gleich zur Eingabe; keine Anzeige-Texte', () => {
		const { de, en } = deDannEn(() => ohneIds(P.neuLogik.buildCreateTripPayload(zustand())));
		assert.deepEqual(en, de);
		assert.equal(en.name, 'Karnischer Höhenweg 2026');
		assert.deepEqual(en.stages.map((s: { name: string }) => s.name), ['Sillian → Obstanser See', 'Etappe Zwei']);
		assert.deepEqual(en.stages.map((s: { date: string }) => s.date), ['2026-07-01', '2026-07-02']);
		for (const w of ['Stage name', 'Trip name', 'New trip', 'Neue Trip', 'Etappe 1', 'Rest day']) hatNicht(JSON.stringify(en), w);
	});
	test('stageDate: de `01.07.` unveraendert, en `1 Jul`', () => {
		assert.equal(P.neuLogik.stageDate('2026-07-01', 0), '01.07.');
		assert.equal(P.neuLogik.stageDate('2026-07-01', 1, 'en'), '2 Jul');
		assert.equal(P.neuLogik.stageDate('2026-07-31', 1, 'de'), '01.08.');
	});
});
