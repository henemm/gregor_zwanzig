// Issue #2659 (i18n F10, Epic #2644) — AC-1..AC-4, AC-6, AC-7: Ortsvergleich-Hub,
// Orte-Reiter, transponierte Uebersicht (Stundenverlauf), Anlegen und Kleinbausteine
// sprechen die Sprache des angemeldeten Nutzers. Echte SSR-Renders (svelte/server,
// Pruefstand f10Pruefstand.ts):
//   * AC-6: Deutsch ist byte-gleich (Leerraum normalisiert) zur Ausgabe VOR der
//     Umstellung (tests/golden/f10_vergleich_flaechen/*.de.html, funktionen.de.txt),
//   * AC-1: Hub englisch, Namen unveraendert, Aktionen wortgleich zum Trip-Hub,
//   * AC-2: Helfer in beiden Sprachen, Plural exakt,
//   * AC-3: Orte-Reiter/-Schritt/Neuer Ort englisch; Nutzlast nur Ort-IDs, sprachgleich,
//   * AC-4: zwei Nutzer (en/de) durch den ECHTEN Layout- und Vergleichs-Loader und den
//     echten Kopf-Speicherweg der Seite; ersetzt ist nur die Netzgrenze,
//   * AC-7: Stundenverlauf: label_en aus dem Register, ohne label_en deutsch, col_label bleibt.
// Jeder en-Fall rendert zuerst de und schaltet dann OHNE Neuladen auf en.
// Englische und deutsche Texte sind als feste Literale verankert (f10KatalogAnker.ts).
// Spec: docs/specs/modules/i18n_f10_vergleich_flaechen_2659.md
//
//   cd frontend && npm test -- src/lib/components/compare/__tests__/vergleich_hub_sprache.test.ts

import { test, describe, before, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import { register } from 'node:module';
import * as P from './f10Pruefstand.ts';
import { F10_ANKER } from './f10KatalogAnker.ts';
import { umgebungFuer, type Knoten } from '../../shared/__tests__/svelteInstanzPruefstand.ts';

const { locale, trFor, trnFor } = P;
const base = pathToFileURL(P.FRONTEND + '/').href;
register(pathToFileURL(path.join(P.FRONTEND, 'src/routes/admin/__tests__/server-load-resolve.hooks.mjs')).href, base);
const layoutLoad = (await import(pathToFileURL(path.join(P.FRONTEND, 'src/routes/+layout.server.ts')).href)).load;
const vergleichLoad = (await import(pathToFileURL(path.join(P.FRONTEND, 'src/routes/compare/[id]/+page.server.ts')).href)).load;
const SEITE = path.join(P.FRONTEND, 'src/routes/compare/[id]/+page.svelte');
const TABS = path.join(P.CMP, 'CompareTabs.svelte');
const MSG = path.join(P.FRONTEND, 'src', 'lib', 'i18n', 'messages');

before(() => {
	// Die de-Golden sind der Ist-Stand VOR der Umstellung und werden nie neu geschrieben;
	// nur die en-Ansicht (Review-Hilfe, nicht verglichen) wird aktualisiert.
	if (process.env.GZ_GOLDEN_SCHREIBEN === 'en') P.schreibeGolden('en');
});
afterEach(() => locale.set('de'));

// Einzige Normalisierung: jede Leerraumfolge wird EIN Leerzeichen. Sonst byte-gleich.
const leerraum = (s: string) => s.replace(/\s+/g, ' ');
const sichtbar = (html: string) =>
	leerraum(html.replace(/<style[\s\S]*?<\/style>/g, ' ').replace(/<(?:"[^"]*"|'[^']*'|[^'">])*>/g, ' ').replace(/&amp;/g, '&')).trim();
const hat = (text: string, teil: string) => assert.ok(text.includes(teil), `fehlt: „${teil}"\nin: ${text.slice(0, 2500)}`);
const hatNicht = (text: string, teil: string) => assert.ok(!text.includes(teil), `steht noch: „${teil}"`);
const en = (k: string, p?: Record<string, string | number>) => trFor('en', k, p);

/** Erst de rendern, dann OHNE Neuladen auf en schalten. */
function deDannEn<T>(f: () => T): { de: T; en: T } {
	locale.set('de');
	const de = f();
	locale.set('en');
	const enW = f();
	return { de, en: enW };
}

/** Deutsche Festteile (>= 5 Buchstaben) der F10-Anker, die im englischen Text stehen. */
function deutscheReste(text: string, ausnahmen: string[] = []): string[] {
	const reste: string[] = [];
	for (const [k, de, enW] of F10_ANKER) {
		if (de === enW || ausnahmen.some((a) => k === a || (a.endsWith('.') && k.startsWith(a)))) continue;
		const enTeile = new Set(enW.split(/<[a-z0-9_]+>/).map((s) => s.trim()));
		for (const teil of de.split(/<[a-z0-9_]+>/).map((s) => s.trim())) {
			if ((teil.match(/[A-Za-zÄÖÜäöüß]/g) ?? []).length < 5 || enTeile.has(teil)) continue;
			const esc = teil.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
			if (new RegExp(`(?<![A-Za-zÄÖÜäöüß])${esc}(?![A-Za-zÄÖÜäöüß])`).test(text)) reste.push(`${k}: ${teil}`);
		}
	}
	return reste;
}
/** Deutsche Woerter, die im englischen Render DATEN sind bzw. anderen Paketen gehoeren. */
const NAMEN = ['Skitouren Tirol', 'Gletscher Herbst', 'Hintertux', 'Kaunertal', 'Obergurgl', 'Sölden', 'Zillertal', 'Tirol'];

describe('AC-6: Deutsch byte-gleich zum Ist-Stand vor der Umstellung (Golden golden-de)', () => {
	const FAELLE = P.htmlFaelle();
	for (const fall of Object.keys(FAELLE)) {
		test(`${fall}.de.html`, () => {
			const golden = readFileSync(path.join(P.GOLDEN_DIR, `${fall}.de.html`), 'utf-8');
			const { de } = deDannEn(() => FAELLE[fall]());
			locale.set('de');
			assert.equal(leerraum(FAELLE[fall]() + '\n'), leerraum(golden));
			assert.equal(leerraum(de + '\n'), leerraum(golden));
		});
	}
	test('funktionen.de.txt: Helfer, Aktivierungs-Karte, Uebersicht-Modell unveraendert (byte-gleich)', () => {
		const golden = readFileSync(path.join(P.GOLDEN_DIR, 'funktionen.de.txt'), 'utf-8');
		locale.set('en');
		P.funktionsTabelle();
		locale.set('de');
		assert.equal(P.funktionsTabelle() + '\n', golden);
	});
	test('Messaufbau: Golden enthaelt die deutschen Texte der Flaechen', () => {
		const alle = [...Object.keys(FAELLE).map((f) => `${f}.de.html`), 'funktionen.de.txt'].map((f) => readFileSync(path.join(P.GOLDEN_DIR, f), 'utf-8')).join('');
		for (const s of ['Läuft automatisch', 'Läuft autom.', 'Verglichene Orte', 'Ort hinzufügen', 'Nächster Versand', 'Zuletzt raus', '3 Kandidaten', 'Bearbeiten →', 'Orts-Vergleiche', 'Laufzeit überschritten', 'Setup abschließen', 'Stundenverlauf', 'Erscheint nur in der E-Mail.', 'Neuer Ort', 'Erkannt · Vorschau', 'min. 2 erforderlich', 'viel — Empfehlung 3–5', 'Eckdaten', 'noch 1 Ort nötig', 'noch 2 Orte nötig', 'erst Vergleich benennen', 'Gesperrt — erst Vergleich benennen', 'Keine weiteren gespeicherten Orte verfügbar.', 'Status-Änderung fehlgeschlagen', 'Täglich 7–9 Uhr', 'vor 1 Woche', 'vor 2 Wochen', 'Neuer Auto-Report'])
			assert.ok(alle.includes(s), s);
	});
	test('Messaufbau: jeder deutsche Anker-Text (Festteile) steht im Golden oder in der Funktionstabelle', () => {
		const alle = leerraum([...Object.keys(FAELLE).map((f) => `${f}.de.html`), 'funktionen.de.txt'].map((f) => readFileSync(path.join(P.GOLDEN_DIR, f), 'utf-8')).join(' ')).replace(/&amp;/g, '&');
		// Nicht im golden-de-Zustand erreichbar (nur Fehler-/Grenzfaelle), im Bestand je Datei nachgewiesen.
		const UNERREICHT = new Set(['vergleich.relativ.diese_woche', 'vergleich.hub.archivieren_fehler', 'vergleich.hub.reaktivieren_fehler', 'vergleich.hub.delete_fehler', 'vergleich.hub.delete_titel', 'listen.dialog.unwiderruflich', 'vergleich.hub.nicht_gefunden', 'vergleich.orte.format_unbekannt', 'vergleich.orte.fehler_hinzufuegen', 'vergleich.gruppe.neu', 'vergleich.gruppe.beispiel', 'vergleich.gruppe.standard_profil', 'vergleich.gruppe.kein_profil', 'vergleich.gruppe.legt_an', 'vergleich.gruppe.fehler', 'vergleich.neu.bereit_titel', 'vergleich.neu.bereit_zeile.one', 'vergleich.neu.bereit_zeile.other', 'vergleich.neu.bereit_text', 'vergleich.neu.alarme_zum_aktivieren_punkt', 'vergleich.neu.tab_gesperrt', 'vergleich.neu.ort_waehlen', 'vergleich.neu.kopie', 'vergleich.relativ.wochen.one', 'vergleich.orte.manuell', 'vergleich.orte.breitengrad', 'vergleich.orte.laengengrad', 'vergleich.orte.hinzufuegen', 'vergleich.hub.test_gesendet', 'vergleich.aktivierung.aktivieren', 'vergleich.orte.viel_kurz']);
		const fehlt: string[] = [];
		for (const [k, de] of F10_ANKER) {
			if (UNERREICHT.has(k)) continue;
			for (const teil of de.split(/<[a-z0-9_]+>/).map((s) => s.trim()))
				if ((teil.match(/[A-Za-zÄÖÜäöüß]/g) ?? []).length >= 2 && !alle.includes(teil)) fehlt.push(`${k}: ${teil}`);
		}
		assert.deepEqual(fehlt, []);
	});
});

describe('AC-1: Ortsvergleich-Hub englisch, Namen unveraendert, Aktionen wie im Trip-Hub', () => {
	test('Uebersicht und Seite: Kennzahlen, Karten, Kopf englisch (erst de, dann ohne Neuladen en)', () => {
		const { de, en: e } = deDannEn(() => P.hubUebersichtRendern() + P.hubSeiteRendern());
		for (const s of ['Läuft automatisch', 'Nächster Versand', 'Zuletzt raus', 'Orts-Vergleiche']) hat(sichtbar(de), s);
		// #2837 S1 (ADR-0110): Breadcrumb aus dem geteilten HubKopf — Elternteil im Katalog-Wortlaut,
		// kein Krümel „Hub“, keine Mobil-Eyebrow „Orts-Vergleich · Hub“.
		for (const alt of ['ORTS-VERGLEICHE', 'Orts-Vergleich · Hub']) hatNicht(sichtbar(de), alt);
		const s = sichtbar(e);
		for (const t of ['Runs automatically', 'Runs auto.', 'Draft · not active', 'Next delivery', 'Last sent', 'Channels', 'Email · Telegram', 'Morning 07:00 · Evening 18:00', '3 candidates', '1 candidate', 'Edit →', 'Delivery', 'Not scheduled yet', '2 metrics with a target range', '2 metrics · highlighted, no score', 'Location comparisons', 'End date passed', 'Finish setup', 'Send', 'Sending…', 'Status change failed. Please try again.', '3 locations', '1 location', 'Winter sports', '27 Oct 2026', 'No delivery yet', 'Active', 'Paused'])
			hat(s, t);
		for (const t of ['aria-label="More actions"', 'aria-label="Back to overview"']) hat(e, t);
		// #2837 S1: kein „Hub“-Krümel, keine Versalien im Markup, keine Mobil-Eyebrow.
		for (const t of ['LOCATION COMPARISONS', 'Location comparison · Hub']) hatNicht(s, t);
		// Plural exakt am Wirkort (Orte-Karte): Einzahl ohne „s", Mehrzahl mit.
		assert.match(s, /\b1 candidate(?!s)/);
		hatNicht(s, '1 candidates');
		hatNicht(s, '3 candidate ');
		for (const n of ['Skitouren Tirol', 'Gletscher Herbst', 'Hintertux', 'Kaunertal', 'Obergurgl', 'Tirol']) hat(s, n);
		for (const t of ['Bearbeiten', 'Läuft', 'Kandidaten', 'Zuletzt raus', 'Wintersport', 'Allgemein', 'Sommer-Trekking']) hatNicht(s, t);
		// Der Golden-Zustand „meldung" traegt `sendMsg` als Server-Text (Daten); der Schluessel-Fall
		// steht im Test „Meldungen ohne Server-Text".
		assert.deepEqual(deutscheReste(s, ['vergleich.hub.test_gesendet']), []);
	});
	test('Reiterleiste: Kennungen gleich, Namen englisch wie im Trip-Hub (aktionen.reiter.*)', () => {
		const { en: e } = deDannEn(() => P.hubOrteRendern());
		// #2794 S3a: Reiter Wetter/Zustellung.
		for (const [id, k] of [['uebersicht', 'aktionen.reiter.uebersicht'], ['orte', 'aktionen.reiter.orte'], ['wetter', 'aktionen.reiter.wetter'], ['zustellung', 'aktionen.reiter.zustellung']])
			assert.match(e, new RegExp(`data-testid="compare-detail-tab-${id}"[\\s\\S]{0,400}?${en(k)}`), id);
		hat(e, `aria-label="${en('vergleich.hub.tabs_aria')}"`);
	});
	test('Edit/Delete/Pause tragen im Vergleich denselben Text wie im Trip (gleicher Schluessel)', () => {
		const { en: e } = deDannEn(() => ({ t: P.aktionen.subscriptionActions('trip', 'active', 'hub'), v: P.aktionen.subscriptionActions('vergleich', 'active', 'hub') }));
		assert.deepEqual(e.v, e.t);
		assert.deepEqual((e.v as { label: string }[]).map((a) => a.label), ['Pause', 'Archive', 'Delete']);
		assert.equal(en('aktionen.edit'), 'Edit');
	});
	test('Fehler ohne Server-Text: Seite haelt nur Schluessel/Flag, Text entsteht beim Rendern', () => {
		const { de, en: e } = deDannEn(() => sichtbar(P.seiteRendern('meldung')));
		hat(de, 'Status-Änderung fehlgeschlagen. Bitte versuche es erneut.');
		hat(e, 'Status change failed. Please try again.');
		hatNicht(e, 'Status-Änderung');
	});
	test('Meldungen ohne Server-Text: Schluessel wird beim Rendern aufgeloest (Seite, Orte-Schritt, Neuer Ort)', () => {
		const { de, en: e } = deDannEn(() => P.fehlerFlagsRendern().map(sichtbar));
		const DE = ['Test-Briefing gesendet', 'Archivieren fehlgeschlagen.', 'Format nicht erkannt', 'Fehler beim Speichern'];
		const EN = ['Test briefing sent', 'Archiving failed.', 'Format not recognised', 'Error while saving'];
		DE.forEach((s, i) => hat(de[i], s));
		EN.forEach((s, i) => {
			hat(e[i], s);
			hatNicht(e[i], DE[i]);
		});
	});
	test('Anlegen-Toast (mobil): Sperr-Hinweis aus der Anlege-Kette, beim Rendern aufgeloest', () => {
		const { de, en: e } = deDannEn(() => P.anlegenToastRendern());
		hat(de, 'erst Vergleich benennen');
		hat(e, 'name the comparison first');
		hatNicht(e, 'erst Vergleich benennen');
	});
});

describe('AC-2: Compare-Helfer in Deutsch und Englisch (Eingabe -> Ausgabe)', () => {
	const H = P.helfer;
	const p = (x: Record<string, unknown>) => P.vergleichAktiv(x);
	const fall = (iso: string) => P.mitUhr(() => H.relativeLastSent(iso));
	const TABELLE: [string, () => string, string, string][] = [
		['presetScheduleLabel daily 7–9', () => H.presetScheduleLabel(p({ hour_from: 7, hour_to: 9 })), 'Täglich 7–9 Uhr', 'Daily 7–9'],
		['presetScheduleLabel weekly', () => H.presetScheduleLabel(p({ schedule: 'weekly' })), 'Wöchentlich', 'Weekly'],
		['presetScheduleLabel manual', () => H.presetScheduleLabel(p({ schedule: 'manual' })), 'Manuell', 'Manual'],
		['presetTileScheduleLabel daily', () => H.presetTileScheduleLabel(p({})), 'tägl. 07', 'daily 07'],
		['presetTileScheduleLabel weekly Mo', () => H.presetTileScheduleLabel(p({ schedule: 'weekly', weekday: 0 })), 'Montag', 'Monday'],
		['presetTileScheduleLabel weekly So', () => H.presetTileScheduleLabel(p({ schedule: 'weekly', weekday: 6 })), 'Sonntag', 'Sunday'],
		['presetTileScheduleLabel manual', () => H.presetTileScheduleLabel(p({ schedule: 'manual' })), 'manuell', 'manual'],
		['presetLocationsLabel 3', () => H.presetLocationsLabel(p({})), '3 Orte', '3 locations'],
		['presetLocationsLabel 1', () => H.presetLocationsLabel(p({ location_ids: ['l-hx'] })), '1 Ort', '1 location'],
		['relativeLastSent heute', () => fall('2026-10-29T06:00:00'), 'heute', 'today'],
		['relativeLastSent gestern', () => fall('2026-10-28T06:00:00'), 'gestern', 'yesterday'],
		['relativeLastSent Montag', () => fall('2026-10-26T06:00:00'), 'Montag', 'Monday'],
		['relativeLastSent 1 Woche', () => fall('2026-10-22T06:00:00'), 'vor 1 Woche', '1 week ago'],
		['relativeLastSent 2 Wochen', () => fall('2026-10-15T06:00:00'), 'vor 2 Wochen', '2 weeks ago'],
		['formatLastSent leer', () => H.formatLastSent(null), 'Noch kein Versand', 'No delivery yet'],
		['formatLastSent Datum', () => H.formatLastSent('2026-10-27T05:00:00Z'), '27.10.2026', '27 Oct 2026'],
		['formatNextSend null', () => H.formatNextSend(null), 'manuell', 'manual'],
		['formatNextSend Datum', () => H.formatNextSend(new Date('2026-10-30T07:05:00')), '30.10. 07:05', 'Fri 30 Oct 07:05'],
		['presetProfileLabel wintersport', () => H.presetProfileLabel('wintersport'), 'Wintersport', 'Winter sports'],
		['presetBriefingTimesLabel', () => H.presetBriefingTimesLabel(p({})), 'Morgen 07:00 · Abend 18:00', 'Morning 07:00 · Evening 18:00']
	];
	for (const [name, f, de, enW] of TABELLE) {
		test(name, () => {
			const r = deDannEn(f);
			assert.equal(r.de, de);
			assert.equal(r.en, enW);
		});
	}
	test('Status-Pille und Aktivierungs-Karte je Sprache', () => {
		const { de, en: e } = deDannEn(() => sichtbar(P.bausteineRendern()) + ' ' + JSON.stringify(['active', 'paused', 'draft'].map((s) => P.persistenz.hubActivationBanner(s))));
		// #2837 S1b: die Status-Pille ist das geteilte StatusSchild (Texte aus trip.status.*, vormals listen.status.*).
		for (const s of ['Aktiv', 'Pausiert', 'Entwurf', 'Neuer Auto-Report', 'Aktivieren', 'Pausieren']) hat(de, s);
		for (const s of ['Active', 'Paused', 'Draft', 'New auto report', 'Activate', '"Pause"', 'Runs automatically — with no end date until you pause it.']) hat(e, s);
		for (const s of ['aktiv"', 'pausiert', 'Aktivieren', 'Pausieren']) hatNicht(e, s);
	});
});

describe('AC-3: Orte-Reiter, Orte-Schritt, Neuer Ort englisch; Nutzlast nur Ort-IDs', () => {
	test('Orte-Reiter: Kopf, Hinweis, Leerfall, Hinzufuegen-Panel englisch; Reihenfolge der Orte gleich', () => {
		const { de, en: e } = deDannEn(() => P.hubOrteRendern());
		const s = sichtbar(e);
		for (const t of ['Compared locations', 'Order = columns in the briefing · drag to sort', 'drag to sort', 'No locations selected yet.', 'Add location', 'Other · 1', 'No other saved locations available.']) hat(s, t);
		for (const t of ['title="Remove"', 'aria-label="Compared locations, order"']) hat(e, t);
		const reihe = (h: string) => [...h.matchAll(/data-loc-id="([^"]+)"/g)].map((m) => m[1]);
		assert.deepEqual(reihe(e), reihe(de));
		assert.ok(reihe(e).length > 0, 'Messaufbau');
		assert.deepEqual(deutscheReste(s), []);
	});
	test('Orte-Schritt und Neuer Ort: Hinweise, Platzhalter, Schaltflaechen englisch; Koordinaten gleich', () => {
		const { de, en: e } = deDannEn(() => P.orteSchrittRendern() + P.ortNeuRendern());
		const s = sichtbar(e);
		for (const t of ['Add new location', 'Smart import · URL from Komoot/Google Maps or coordinates', 'Resolve', 'In comparison · 2', 'min. 2 required', 'many — 3–5 recommended', 'good', 'No locations yet.', 'add on the left or pick below', '… or choose from saved locations', 'No saved locations yet.', 'No locations chosen yet.', 'Choose a location from the library', 'Detected', '＋ Add to comparison', 'Adding…', 'Other · 2', 'Module 1 · Add location', 'New location', 'Detected · preview', 'Source', 'Elevation (DEM)', '3250 m a.s.l.', 'Time zone', 'Country/region', 'Naming', 'Group (optional)', 'Meteorological lens (activity profile)', 'Cancel', 'Save location', 'Saving…', 'detected · komoot', 'General', 'Summer trekking'])
			hat(s, t);
		for (const t of ['placeholder="Komoot URL, Google Maps or coordinates"', 'placeholder="Location name"', 'placeholder="Komoot link, Google Maps URL or coordinates…"', 'aria-label="Close"']) hat(e, t);
		for (const k of ['47.0789, 11.6856', '47.07890°N · 11.68560°E']) {
			hat(sichtbar(de), k);
			hat(s, k);
		}
		assert.deepEqual(deutscheReste(s, ['vergleich.ort.name_beispiel']), []);
	});
	test('Hinzufuegen, Entfernen, Sortieren: PUT-Nutzlast nur `location_ids`, in en und de identisch', async () => {
		async function lauf(lang: 'de' | 'en') {
			locale.set(lang);
			const puts: unknown[] = [];
			const api = { put: async (_u: string, body: Record<string, unknown>) => (puts.push(body), { ...P.vergleichAktiv(), ...body }), get: async () => [] };
			const ctl: Knoten = { setSaving: () => {}, setSaved: () => {}, setError: () => {}, flush: async () => {}, imWiederholen: false, state: 'idle' };
			const { u } = await umgebungFuer(TABS, { preset: P.vergleichAktiv(), locations: P.ORTE, saveController: ctl, api, extractMessage: String });
			u.currentPreset = P.vergleichAktiv();
			await u.addLocationToCompare('l-sf');
			await u.removeLocation('l-ka');
			await u.handleOrteDndReorder(['l-ob', 'l-hx', 'l-sf']);
			return puts;
		}
		const de = await lauf('de');
		const enW = await lauf('en');
		assert.deepEqual(enW, de);
		assert.deepEqual(de, [{ location_ids: ['l-hx', 'l-ka', 'l-ob', 'l-sf'] }, { location_ids: ['l-hx', 'l-ob', 'l-sf'] }, { location_ids: ['l-ob', 'l-hx', 'l-sf'] }]);
	});
});

describe('AC-7: Groessennamen im Alarme-Reiter des Vergleichs (Register-Ergaenzung)', () => {
	test('mitRegisterNamen + registerAusKatalog: unalertable Groessen englisch, ohne label_en deutsch', async () => {
		const L = await import(pathToFileURL(path.join(P.KOMP, 'shared/corridor-editor/compareMetricCatalogLoader.ts')).href);
		const A = await import(pathToFileURL(path.join(P.KOMP, 'shared/alarme-tab/activeAlertMetricsFromCatalog.ts')).href);
		const register = L.registerAusKatalog({ a: [P.REGISTER.temperature, P.REGISTER.cloud_total], b: [P.REGISTER.sunshine], kaputt: null });
		assert.deepEqual(Object.keys(register).sort(), ['cloud_total', 'sunshine', 'temperature']);
		const katalog = L.mitRegisterNamen(P.VERGLEICHS_KATALOG, register);
		const keys = ['cloud_avg_pct', 'sunny_hours_h'];
		assert.deepEqual(A.deriveUnalertableSelectedMetricNames(keys, katalog, 'en'), ['Bewölkung', 'Sunshine hours']);
		assert.deepEqual(A.deriveUnalertableSelectedMetricNames(keys, katalog, 'de'), ['Bewölkung', 'Sonnenstunden']);
		// Daten bleiben: Kennungen und deutscher Name unveraendert, nur label_en ergaenzt.
		assert.deepEqual(katalog.map((e: { metric: string; label: string }) => [e.metric, e.label]), P.VERGLEICHS_KATALOG.map((e) => [e.metric, e.label]));
	});
	test('Vorlage (?from=): Vorschlagsname in der Sprache des Nutzers', async () => {
		// #2727: reine Funktion ueber dem Standard-Feldsatz (wie der Anlege-Editor beim Start).
		const { feldsatzAusVorlage } = await import(pathToFileURL(path.join(P.KOMP, 'compare-new/compareNewVorlage.ts')).href);
		const { compareFeldsatzStandard } = await import(pathToFileURL(path.join(P.CMP, 'compareEditorSave.ts')).href);
		const name = () => ({ ...compareFeldsatzStandard(), ...feldsatzAusVorlage(P.vergleichAktiv(), P.ORTE) }).name;
		const r = deDannEn(name);
		assert.equal(r.de, 'Skitouren Tirol (Kopie)');
		assert.equal(r.en, 'Skitouren Tirol (copy)');
	});
});

describe('AC-7: Stundenverlauf (transponierte Uebersicht): Name aus dem Register, col_label unveraendert', () => {
	test('mit Register: label_en englisch, ohne label_en deutsch; Kurzform bleibt', () => {
		const { de, en: e } = deDannEn(() => P.stundenverlaufRendern());
		const zweiter = (h: string) => sichtbar(h.split('\n')[1]);
		hat(zweiter(e), 'Temperature');
		hat(zweiter(e), 'Sunshine hours');
		hat(zweiter(e), 'Bewölkung'); // kein label_en im Register
		hat(zweiter(e), 'Hourly view');
		hat(zweiter(e), 'Appears only in the email.');
		hat(zweiter(de), 'Temperatur');
		hat(zweiter(de), 'Sonnenstunden');
		hatNicht(zweiter(e), 'Temperatur ');
		for (const c of P.COL_LABELS.slice(0, 3)) {
			const zaehle = (h: string) => (h.match(new RegExp(`>${c}<`, 'g')) ?? []).length;
			assert.equal(zaehle(e), zaehle(de), c);
		}
	});
	test('ohne Register (nicht geladen): die Namen der Vergleichs-Antwort bleiben, keine Leerstellen', () => {
		const { en: e } = deDannEn(() => sichtbar(P.stundenverlaufRendern().split('\n')[0]));
		for (const n of ['Temperatur', 'Wind', 'Bewölkung', 'Sonnenstunden']) hat(e, n);
	});
	// #2880: mobil MField mit Hinweis rechts (vorher handgeschriebenes „Region (optional)")
	test('Anlegen: Profil-Metriknamen und Profile englisch (metricLabel/Katalog)', () => {
		const { en: e } = deDannEn(() => sichtbar(P.ANLEGE_FAELLE.anlegen_vergleich.map(P.anlegenRendern).join('\n')));
		for (const s of ['General', 'Winter sports', 'Hiking', 'Summer trekking', 'Basics', 'Comparison name', 'Activity profile', 'Add locations →', '⊘ Name missing', 'Location comparisons', 'New comparison', 'Enter name', 'Cancel', 'Activate briefing', 'Region optional · max 60', 'No name yet', 'Nothing set up yet']) hat(e, s);
		// #2837 S2 (AC-3): der mobile Zurück-Pfeil trägt den Elternteil „Location comparisons"
		// (vorher „Comparisons") — je Render Desktop-Pfad UND mobiler Zurück-Pfeil.
		assert.ok((e.match(/Location comparisons/g) ?? []).length >= 2 * P.ANLEGE_FAELLE.anlegen_vergleich.length, 'mobiler Zurück-Pfeil ohne Elternteil „Location comparisons"');
		assert.deepEqual(deutscheReste(e), []);
	});
	test('Anlegen Orte/weiter: Reiter, Fortschritt, Schaltflaechen englisch; Plural exakt', () => {
		const { en: e } = deDannEn(() => sichtbar([...P.ANLEGE_FAELLE.anlegen_orte, ...P.ANLEGE_FAELLE.anlegen_weiter].map(P.anlegenRendern).join('\n')));
		// #2794 S3a: kein eigener Wertebereiche-Schritt mehr, Fortschritt mit 4 Abschnitten.
		for (const s of ['1 more location needed', '2 more locations needed', '⊘ select at least 2 locations', 'Weather metrics →', 'Set up delivery →', '1 / 4 sections set up', 'Set up alerts to activate']) hat(e, s);
		assert.deepEqual(deutscheReste(e), []);
	});
});

/** Netzgrenze: fetch je Sitzungs-Cookie (gz_session) -> Antworten des jeweiligen Nutzers. */
const API: Record<string, Record<string, unknown>> = {
	A: { '/api/auth/profile': { id: 'anna', language: 'en' }, '/api/compare/presets/anna-v': P.vergleichAktiv({ id: 'anna-v', name: 'Anna Tirol' }), '/api/locations': P.ORTE },
	B: { '/api/auth/profile': { id: 'bert', language: 'de' }, '/api/compare/presets/bert-v': P.vergleichPausiert(), '/api/locations': P.ORTE }
};
async function mitApi<T>(lauf: () => Promise<T>): Promise<T> {
	const echt = globalThis.fetch;
	globalThis.fetch = (async (u: string, init?: { headers?: Record<string, string> }) => {
		const sitzung = /gz_session=([^;]+)/.exec(init?.headers?.Cookie ?? '')?.[1] ?? '';
		const daten = API[sitzung]?.[new URL(String(u)).pathname];
		return new Response(JSON.stringify(daten ?? null), { status: daten === undefined ? 404 : 200, headers: { ETag: '"1"' } });
	}) as unknown as typeof fetch;
	try {
		return await lauf();
	} finally {
		globalThis.fetch = echt;
	}
}
const cookies = (s: string) => ({ get: (n: string) => (n === 'gz_session' ? s : undefined) });

describe('AC-4: zwei Nutzer, zwei Sprachen, eigener Vergleich, sprachunabhaengige Nutzlast', () => {
	async function sichtFuer(sitzung: 'A' | 'B', id: string, fremdeId: string) {
		const locals = { userId: sitzung, lang: 'de' as 'de' | 'en' };
		const { daten, fremd } = await mitApi(async () => {
			await layoutLoad({ locals, cookies: cookies(sitzung) } as never);
			const daten = await vergleichLoad({ params: { id }, locals, cookies: cookies(sitzung) } as never);
			const fremd = await vergleichLoad({ params: { id: fremdeId }, locals, cookies: cookies(sitzung) } as never).then(
				() => null,
				(e: { status?: number; body?: { message?: string } }) => e
			);
			return { daten, fremd };
		});
		locale.set(locals.lang);
		const seite = sichtbar(P.seiteRendern('ruhe', daten.preset, daten.locations));
		// Echter Kopf-Speicherweg der Seite (onSaveField -> baueSpeicherung -> PUT), Netz ersetzt.
		const rumpf: unknown[] = [];
		const api = { put: async (_p: string, body: unknown) => (rumpf.push(body), { ...daten.preset, ...(body as object) }) };
		const ctl = { setSaving: () => {}, setSaved: () => {}, markPristine: () => {}, setError: () => {}, imWiederholen: false, state: 'idle' };
		const { u } = await umgebungFuer(SEITE, { data: daten, api, hubSaveCtl: ctl }, { jsAlsTs: true });
		u.api = api;
		await u.onSaveField('name', `${daten.preset.name} 2`, () => {});
		return { lang: locals.lang, seite, fremd, rumpf, preset: daten.preset };
	}

	test('A englisch, B deutsch; jeder nur eigener Vergleich (fremder 404 in eigener Sprache); Nutzlast ohne Anzeigetexte', async () => {
		locale.set('de');
		const a = await sichtFuer('A', 'anna-v', 'bert-v');
		const b = await sichtFuer('B', 'bert-v', 'anna-v');
		assert.equal(a.lang, 'en');
		assert.equal(b.lang, 'de');
		assert.equal(a.fremd?.status, 404, 'A liest den Vergleich von B');
		assert.equal(b.fremd?.status, 404, 'B liest den Vergleich von A');
		assert.equal(a.fremd?.body?.message, 'Location comparison not found');
		assert.equal(b.fremd?.body?.message, 'Orts-Vergleich nicht gefunden');
		hat(a.seite, 'Anna Tirol');
		hat(a.seite, 'Runs automatically');
		hat(a.seite, 'Overview');
		hatNicht(a.seite, 'Gletscher Herbst');
		hat(b.seite, 'Gletscher Herbst');
		hat(b.seite, 'Pausiert');
		hat(b.seite, 'Übersicht');
		hatNicht(b.seite, 'Anna Tirol');
		assert.deepEqual(a.rumpf, [{ name: 'Anna Tirol 2' }]);
		assert.deepEqual(b.rumpf, [{ name: 'Gletscher Herbst 2' }]);
		assert.deepEqual(Object.keys(a.rumpf[0] as object), Object.keys(b.rumpf[0] as object));
		for (const wort of ['Overview', 'Übersicht', 'Locations', 'Orte', 'label']) hatNicht(JSON.stringify(a.rumpf), wort);
		// Gespeicherte Daten bleiben unveraendert (kein Anzeigetext im Vergleich selbst).
		assert.deepEqual(a.preset, API.A['/api/compare/presets/anna-v']);
	});
});

describe('Anker: jeder F10-Katalogwert ist als festes de/en-Literal verankert', () => {
	const params = (literal: string) => Object.fromEntries([...literal.matchAll(/<([a-z0-9_]+)>/g)].map((m) => [m[1], `<${m[1]}>`]));
	for (const [k, de, enW] of F10_ANKER) {
		test(k, () => {
			assert.equal(trFor('de', k, params(de)), de, `de ${k}`);
			assert.equal(trFor('en', k, params(enW)), enW, `en ${k}`);
		});
	}
	test('statischer Gegencheck: vergleich.json = vergleich.anlegen.* (F9) + F10-Anker; aktionen.uebersicht.* verankert', () => {
		const anker = (p: string) => F10_ANKER.map(([k]) => k).filter((k) => k.startsWith(p));
		for (const lang of ['de', 'en']) {
			const lies = (b: string) => Object.keys(JSON.parse(readFileSync(path.join(MSG, lang, `${b}.json`), 'utf-8')));
			assert.deepEqual(lies('vergleich').filter((k) => !k.startsWith('vergleich.anlegen.')).sort(), anker('vergleich.').sort(), `${lang}: vergleich.json`);
			assert.deepEqual(lies('aktionen').filter((k) => k.startsWith('aktionen.uebersicht.')).sort(), anker('aktionen.uebersicht.').sort(), `${lang}: aktionen.uebersicht.*`);
		}
		assert.equal(new Set(F10_ANKER.map(([k]) => k)).size, F10_ANKER.length, 'doppelte Anker');
	});
	test('Plural exakt: Kandidaten, Wochen, fehlende Orte, Bereit-Zeile', () => {
		assert.equal(trnFor('en', 'vergleich.hub.kandidaten', 1), '1 candidate');
		assert.equal(trnFor('en', 'vergleich.hub.kandidaten', 3), '3 candidates');
		assert.equal(trnFor('de', 'vergleich.hub.kandidaten', 1), '1 Kandidaten');
		assert.equal(trnFor('de', 'vergleich.relativ.wochen', 1), 'vor 1 Woche');
		assert.equal(trnFor('en', 'vergleich.relativ.wochen', 1), '1 week ago');
		assert.equal(trnFor('de', 'vergleich.neu.noch_orte', 1), 'noch 1 Ort nötig');
		assert.equal(trnFor('de', 'vergleich.neu.noch_orte', 2), 'noch 2 Orte nötig');
		assert.equal(trnFor('en', 'vergleich.neu.bereit_zeile', 1, { name: 'X' }), '“X” · 1 location');
		assert.equal(trnFor('de', 'vergleich.neu.bereit_zeile', 1, { name: 'X' }), '„X" · 1 Orte');
	});
});
