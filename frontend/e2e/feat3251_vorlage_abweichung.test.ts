// Issue #3251 (Epic #2913): Abweichungszustand der Vorlagenkarte in Elementliste und Abgleich (Option B).
// Spec: docs/specs/modules/feat_3251_abweichungszustand_vorlage.md (AC-1, AC-2, AC-4; Test Plan).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test e2e/feat3251_vorlage_abweichung.test.ts
//
// Geprüft werden Daten, die der Abgleich-Lauf liest bzw. die der Generator erzeugt:
//   - die ERZEUGTE Elementliste (docs/context/einstellungen_neu/elementliste.json) muss den Script-Abschnitt
//     `vorlage-abweichung` (Reiter Wetter, Zustand normal, ctx trip und orte) mit den Soll-Einträgen führen;
//     Sollwerte DE/EN kommen aus dem Katalog (wetter.vorlage.abweichungen.one, wetter.vorlage.zuruecksetzen);
//   - die Abgleich-Logik ordnet den Abschnitt dem Prüf-Datensatz `mit_abweichung` zu;
//   - die Besitzerliste führt die pauschalen Ausnahmen aus #3205 für die Zurücksetzen-Zeile nicht mehr.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as L from './elementliste_abgleich_logik.ts';
import * as G from '../../scripts/elementliste_aus_mockup.ts';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..', '..');
const lese = (rel: string) => JSON.parse(readFileSync(join(REPO, rel), 'utf-8'));

type Eintrag = {
	id: string;
	ctx: string;
	reiter: string;
	zustand: string;
	abschnitt: string;
	ordnung: number;
	rolle: string;
	text_de: string;
	muster: string | null;
	i18n_key: string | null;
	text_en: string | null;
};

const LISTE: { elemente: Eintrag[] } = lese('docs/context/einstellungen_neu/elementliste.json');
const KAT_DE: Record<string, string> = lese('frontend/src/lib/i18n/messages/de/wetter.json');
const KAT_EN: Record<string, string> = lese('frontend/src/lib/i18n/messages/en/wetter.json');
const BESITZER: { ausnahmen: Array<Record<string, string | undefined>> } = lese(
	'docs/context/einstellungen_neu/elementliste_besitzer.json',
);

const ABSCHNITT = 'vorlage-abweichung';
const ABW_DE = KAT_DE['wetter.vorlage.abweichungen.one'];
const ABW_EN = KAT_EN['wetter.vorlage.abweichungen.one'];
const RESET_DE = KAT_DE['wetter.vorlage.zuruecksetzen'];
const RESET_EN = KAT_EN['wetter.vorlage.zuruecksetzen'];
/** Aktive Vorlage des Mockup-Normalzustands je Kontext (Abschnitt `vorlage`, Picker-Knopf). */
const VORLAGE: Record<string, string> = { trip: 'Alpen-Trekking', orte: 'Allgemein' };

const abschnitt = (ctx: string): Eintrag[] =>
	LISTE.elemente
		.filter((e) => e.ctx === ctx && e.reiter === 'wetter' && e.zustand === 'normal' && e.abschnitt === ABSCHNITT)
		.sort((a, b) => a.ordnung - b.ordnung);

describe('#3251 Vorbedingung: Katalog-Sollwerte vorhanden', () => {
	test('DE/EN-Texte für Abweichungszahl und Zurücksetzen-Zeile stehen im Katalog', () => {
		assert.equal(ABW_DE, '1 Abweichung');
		assert.equal(ABW_EN, '1 change');
		assert.ok(RESET_DE?.includes('{vorlage}'), 'wetter.vorlage.zuruecksetzen (de) fehlt');
		assert.ok(RESET_EN?.includes('{vorlage}'), 'wetter.vorlage.zuruecksetzen (en) fehlt');
	});
});

describe('#3251 AC-1: Elementliste führt den Abschnitt vorlage-abweichung', () => {
	for (const ctx of ['trip', 'orte']) {
		test(`${ctx}: Abschnitt vorhanden`, () => {
			assert.ok(abschnitt(ctx).length > 0, `Abschnitt „${ABSCHNITT}“ (${ctx}, Wetter, normal) fehlt in der Elementliste`);
		});

		// Fix-Loop 1 (F001): live sind Auswahlpfeil „▾“ und Stand eigene Textblöcke (VorlageKarte.svelte); der
		// Soll-Eintrag führt den Stand ohne Pfeil. Fix-Loop 2 (F001): die Zahl hängt live am Prüf-Datensatz mit
		// Abweichung (gemessen 21.11.: Trip „14 Abweichungen“, Orte „8 Abweichungen“), darum Zahl als Platzhalter
		// in der Mehrzahl-Form des Katalogs; text_de bleibt der Mockup-Text.
		test(`${ctx}: Picker-Stand „${ABW_DE}“ ohne Auswahlpfeil, Zahl als Platzhalter (Katalog .other)`, () => {
			const picker = abschnitt(ctx).find((e) => e.text_de.includes(ABW_DE));
			assert.ok(picker, `„${ABW_DE}“ fehlt im Abschnitt „${ABSCHNITT}“ (${ctx})`);
			assert.equal(picker.text_de, ABW_DE);
			assert.equal(picker.i18n_key, 'wetter.vorlage.abweichungen.other');
			assert.equal(picker.muster, KAT_DE['wetter.vorlage.abweichungen.other']);
			assert.equal(picker.text_en, KAT_EN['wetter.vorlage.abweichungen.other']);
		});

		test(`${ctx}: Abgleich-Erwartung passt auf den live gemessenen Stand (DE und EN), nicht auf fremden Text`, () => {
			const picker = abschnitt(ctx).find((e) => e.text_de === ABW_DE)!;
			const de = L.erwartung(picker as unknown as L.ListenElement, 'de')!;
			const en = L.erwartung(picker as unknown as L.ListenElement, 'en')!;
			for (const ist of ['14 Abweichungen', '8 Abweichungen']) assert.ok(de.test(ist), `DE passt nicht auf „${ist}“`);
			for (const ist of ['14 changes', '8 changes']) assert.ok(en.test(ist), `EN passt nicht auf „${ist}“`);
			for (const fremd of ['unverändert', 'Als eigene Vorlage speichern', '▾']) assert.ok(!de.test(fremd), `DE passt auf „${fremd}“`);
			assert.ok(!en.test('unchanged'));
		});

		test(`${ctx}: Zurücksetzen-Zeile auf „${VORLAGE[ctx]}“ mit Katalog-Schlüssel und EN-Sollwert`, () => {
			const soll = RESET_DE.replace('{vorlage}', VORLAGE[ctx]);
			const zeile = abschnitt(ctx).find((e) => e.text_de === soll);
			assert.ok(zeile, `Zurücksetzen-Zeile „${soll}“ fehlt im Abschnitt „${ABSCHNITT}“ (${ctx})`);
			assert.equal(zeile.i18n_key, 'wetter.vorlage.zuruecksetzen');
			assert.equal(zeile.muster, RESET_DE);
			assert.equal(zeile.text_en, RESET_EN);
		});
	}

	test('Normalzustand: Orte „▾ unverändert“ ohne Zurücksetzen-Zeile; Trip „▾ 1 Abweichung“ mit Zurücksetzen (#3419 AC-6)', () => {
		// #3419 (AC-6): der Seed-Trip weicht wie das Soll-Bild in Bewölkung von „Alpen-Trekking“ ab; live zeigt die
		// Vorlagenkarte dann Stand und Zurücksetzen-Zeile (VorlageKarte.svelte, abweichungen > 0).
		const normal = (ctx: string) =>
			LISTE.elemente.filter((e) => e.ctx === ctx && e.reiter === 'wetter' && e.zustand === 'normal' && e.abschnitt === 'vorlage');
		assert.ok(normal('orte').some((e) => e.text_de === '▾ unverändert'), '„▾ unverändert“ fehlt (orte)');
		assert.ok(!normal('orte').some((e) => e.i18n_key === 'wetter.vorlage.zuruecksetzen'), 'Zurücksetzen-Zeile im Normalzustand (orte)');
		assert.ok(normal('trip').some((e) => e.text_de === '▾ 1 Abweichung'), '„▾ 1 Abweichung“ fehlt (trip)');
		assert.ok(normal('trip').some((e) => e.i18n_key === 'wetter.vorlage.zuruecksetzen'), 'Zurücksetzen-Zeile fehlt (trip)');
	});
});

describe('#3251 AC-2: Abgleich ordnet vorlage-abweichung dem Datensatz mit_abweichung zu', () => {
	test('datensatzFuerAbschnitt("vorlage-abweichung") === "mit_abweichung"', () => {
		assert.equal(L.datensatzFuerAbschnitt(ABSCHNITT), 'mit_abweichung');
	});

	test('grenzen-* bleibt mit_abweichung, übrige Abschnitte ohne_abweichung', () => {
		assert.equal(L.datensatzFuerAbschnitt('grenzen-wind'), 'mit_abweichung');
		for (const a of ['vorlage', 'vorlage-auswahl', 'vorlage-bestaetigung', 'vorlage-speichern', 'metriken', 'normal']) {
			assert.equal(L.datensatzFuerAbschnitt(a), 'ohne_abweichung', `Abschnitt ${a}`);
		}
	});

	test('SCRIPT_ABSCHNITT erkennt vorlage-abweichung als Script-Zustand', () => {
		assert.ok(L.SCRIPT_ABSCHNITT.test(ABSCHNITT));
	});

	// Fix-Loop 1 (F002): die App hat keinen eigenen Haken; der Abschnitt wird in der Vorlagenkarte gelesen.
	test('abschnittHaken: vorlage-abweichung liest im App-Haken „vorlage“, andere Abschnitte unverändert', () => {
		assert.equal(L.abschnittHaken(ABSCHNITT), 'vorlage');
		for (const a of ['vorlage', 'vorlage-auswahl', 'vorlage-bestaetigung', 'grenzen-wind', 'metriken']) {
			assert.equal(L.abschnittHaken(a), a, `Abschnitt ${a}`);
		}
	});

	test('bedienPlan: vorlage-abweichung wird ohne Klick gelesen (Abweichung kommt aus dem Prüf-Datensatz)', () => {
		const plan = L.bedienPlan(ABSCHNITT, { ctx: 'trip', briefing: [], vorlagen: [], aktiveVorlage: 'alpen-trekking' });
		assert.deepEqual(plan, { art: 'plan', schritte: [{ aktion: 'lesen' }] });
	});
});

describe('#3251 AC-4: pauschale Ausnahmen aus #3205 für die Zurücksetzen-Zeile sind gestrichen', () => {
	test('keine Ausnahme mit Muster der Zurücksetzen-Zeile (DE/EN)', () => {
		const rest = BESITZER.ausnahmen.filter(
			(a) =>
				a.spec === 'docs/specs/modules/feat_3205_vorlagen_mockup.md' ||
				a.muster === 'Auf "{vorlage}" zurücksetzen' ||
				a.muster === 'Reset to "{vorlage}"' ||
				a.muster === RESET_DE ||
				a.muster === RESET_EN,
		);
		assert.deepEqual(rest, [], 'Ausnahmen für die Zurücksetzen-Zeile stehen noch in der Besitzerliste');
	});
});

describe('#3251 Fix-Loop 2 (F001): Generator führt die Abweichungszahl als Katalog-Mehrzahl-Muster', () => {
	const katalog = G.ladeKatalog(join(REPO, 'frontend/src/lib/i18n/messages'));
	const einzahl = G.ermittleEn(ABW_DE, katalog);

	test('ermittleEn liefert für „1 Abweichung“ die Einzahl (Ausgangslage)', () => {
		assert.equal(einzahl.i18n_key, 'wetter.vorlage.abweichungen.one');
	});

	test('im Abschnitt vorlage-abweichung: .one → .other, Muster und EN-Soll aus dem Katalog', () => {
		const r = G.abweichungsZahlAlsMuster(ABSCHNITT, einzahl, katalog);
		assert.equal(r.i18n_key, 'wetter.vorlage.abweichungen.other');
		assert.equal(r.muster, KAT_DE['wetter.vorlage.abweichungen.other']);
		assert.equal(r.text_en, KAT_EN['wetter.vorlage.abweichungen.other']);
		assert.equal(r.luecke, false);
	});

	test('andere Abschnitte und Nicht-Einzahl-Schlüssel bleiben unverändert', () => {
		assert.deepEqual(G.abweichungsZahlAlsMuster('vorlage', einzahl, katalog), einzahl);
		const reset = G.ermittleEn('Auf „Allgemein“ zurücksetzen', katalog);
		assert.deepEqual(G.abweichungsZahlAlsMuster(ABSCHNITT, reset, katalog), reset);
	});
});
