// Issue #3204 (Epic #2913): Anzeige-Metriken Tages-Tief/-Hoch (Gehzeit) im Mockup Fassung 4.
// Spec: docs/specs/modules/feat_3204_anzeige_metriken_mockup.md (AC-1, AC-2, AC-3, AC-4; Test Plan
// „Elementlisten-Test“ und „Reihenfolge-Test“).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks --test e2e/feat3204_elementliste_anzeige_metriken.test.ts
//
// Geprüft wird die ERZEUGTE Elementliste (docs/context/einstellungen_neu/elementliste.json), nicht der
// Mockup-Quelltext: Sie entsteht deterministisch per scripts/elementliste_aus_mockup.ts aus dem gerenderten
// Mockup, und elementliste_aktuell.test.ts bindet sie per Prüfsumme an den aktuellen Mockup-Stand. Was hier
// steht, zeigt das Mockup also wirklich an (Gruppe, Reihenfolge, Zeilentexte).
//
// Erwartete Werte kommen aus den Katalogen (Metrik-Namen aus dem Server-Katalog-Schnappschuss
// daten/metrik_namen.json, Nur-Anzeige-Texte wetter.json), nicht aus einer Kopie: Mockup und App müssen
// dieselben Wörter zeigen. #3383 S1: die Frontend-Schlüssel wertebereiche.symbolzeile.* entfielen mit der Waise
// wertebereicheAnzeige.ts; live steht der Zeilenname aus dem Server-Katalog (label_de/label_en).

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, '..', '..');
const MSG = join(REPO, 'frontend/src/lib/i18n/messages');

type Eintrag = {
	id: string;
	ctx: string;
	reiter: string;
	zustand: string;
	abschnitt: string;
	ordnung: number;
	rolle: string;
	text_de: string;
	i18n_key: string | null;
	text_en: string | null;
};

const LISTE: { elemente: Eintrag[] } = JSON.parse(readFileSync(join(REPO, 'docs/context/einstellungen_neu/elementliste.json'), 'utf-8'));
const kat = (sprache: 'de' | 'en', bereich: string): Record<string, string> =>
	JSON.parse(readFileSync(join(MSG, sprache, `${bereich}.json`), 'utf-8'));
const WT_DE = kat('de', 'wetter');
const WT_EN = kat('en', 'wetter');
const METRIK_NAMEN: { namen: { id: string; de: string; en: string }[] } = JSON.parse(
	readFileSync(join(REPO, 'docs/context/einstellungen_neu/daten/metrik_namen.json'), 'utf-8')
);

const NEU = ['temperature_day_low', 'temperature_day_high'] as const;
const nameDe = (id: string) => METRIK_NAMEN.namen.find((n) => n.id === id)?.de;
const nameEn = (id: string) => METRIK_NAMEN.namen.find((n) => n.id === id)?.en;

/** Untertitel wie im Mockup: `[Einheit, Hinweis].join(' · ')`, Hinweis = Nur-Anzeige-Hinweis des Katalogs. */
const UNTERTITEL = `°C · ${WT_DE['wetter.untertitel.nur_anzeige']}`;
const MITTE = WT_DE['wetter.zeile.nur_anzeige'];
/** Mockup-Wortlaut des Erklärsatzes (mockup-hub-fassung4.html, why() für Nur-Anzeige-Zeilen). */
const ERKLAER_MOCKUP = 'Nur Anzeige: keine Ampel und kein Alarm. Roh oder Einfach stellst du unten unter „Was steht wo“ ein.';

/** Zeilen der Metrikliste eines Kontexts im Normalzustand, in Dokumentreihenfolge. */
const metriken = (ctx: string, zustand = 'normal'): Eintrag[] =>
	LISTE.elemente
		.filter((e) => e.ctx === ctx && e.reiter === 'wetter' && e.zustand === zustand && e.abschnitt === 'metriken')
		.sort((a, b) => a.ordnung - b.ordnung);

/** Die Einträge einer Metrik-Zeile: ab dem Namen bis vor den nächsten Entfernen-Knopf bzw. die nächste Gruppe. */
function zeile(liste: Eintrag[], name: string): Eintrag[] {
	const i = liste.findIndex((e) => e.rolle === 'text' && e.text_de === name);
	assert.ok(i >= 0, `Metrik-Zeile „${name}“ fehlt in der Elementliste (Trip, Reiter Wetter, Metriken). Mockup TRIP_METRICS ergänzen und Elementliste neu erzeugen.`);
	const rest = liste.slice(i + 1);
	const ende = rest.findIndex((e) => e.i18n_key === 'wetter.zeile.entfernen' || e.rolle === 'beschriftung' || e.rolle === 'chip');
	return ende < 0 ? rest : rest.slice(0, ende);
}

describe('#3204 AC-1: Gruppe Temperatur im Mockup (Trip) wie in der App', () => {
	test('Katalog kennt beide Namen (Vorbedingung)', () => {
		for (const id of NEU) {
			assert.ok(nameDe(id), `DE-Name ${id} fehlt in daten/metrik_namen.json`);
			assert.ok(nameEn(id), `EN-Name ${id} fehlt in daten/metrik_namen.json`);
		}
	});

	for (const zustand of ['normal', 'luecken']) {
		test(`Reihenfolge Temperatur, Nacht, Tages-Tief, Tages-Hoch, Gefühlte (Zustand ${zustand})`, () => {
			const liste = metriken('trip', zustand);
			const soll = ['Temperatur', 'Tiefsttemperatur Nacht', nameDe('temperature_day_low'), nameDe('temperature_day_high'), 'Gefühlte Temperatur'];
			const von = liste.findIndex((e) => e.rolle === 'beschriftung' && e.text_de === 'Temperatur');
			const bis = liste.findIndex((e, i) => i > von && e.rolle === 'beschriftung');
			assert.ok(von >= 0 && bis > von, 'Gruppe Temperatur nicht gefunden');
			const ist = liste.slice(von + 1, bis).filter((e) => e.rolle === 'text' && soll.includes(e.text_de)).map((e) => e.text_de);
			assert.deepEqual(ist, soll, 'Gruppe Temperatur im Mockup weicht von der App-Reihenfolge ab');
		});
	}

	test('Namen tragen die englischen Katalognamen (EN-Abgleich)', () => {
		const liste = metriken('trip');
		for (const id of NEU) {
			const e = liste.find((x) => x.rolle === 'text' && x.text_de === nameDe(id));
			assert.ok(e, `„${nameDe(id)}“ fehlt in der Elementliste`);
			assert.equal(e!.text_en, nameEn(id), `EN-Name von ${id}`);
		}
	});
});

describe('#3204 AC-2/AC-3: Nur-Anzeige-Form wie Windrichtung, Erklärsatz wortgleich zum Mockup', () => {
	for (const id of NEU) {
		test(`${id}: Untertitel „${UNTERTITEL}“, Zeilenmitte, Erklärsatz, ohne Grenzen und Alarm-Auswahl`, () => {
			const z = zeile(metriken('trip'), nameDe(id));
			const texte = z.map((e) => e.text_de);
			assert.ok(texte.includes(UNTERTITEL), `Untertitel fehlt: ${JSON.stringify(texte)}`);
			const mitte = z.find((e) => e.text_de === MITTE);
			assert.ok(mitte, `Zeilenmitte „${MITTE}“ fehlt: ${JSON.stringify(texte)}`);
			assert.equal(mitte!.i18n_key, 'wetter.zeile.nur_anzeige');
			assert.ok(!z.some((e) => e.i18n_key === 'wetter.grenzen.aendern'), '„Grenzen ändern“ in einer Nur-Anzeige-Zeile');
			assert.ok(!z.some((e) => e.rolle === 'option'), 'Alarm-Auswahl in einer Nur-Anzeige-Zeile');

			const satz = z.find((e) => e.text_de.startsWith('Nur Anzeige:'));
			assert.ok(satz, `Erklärsatz fehlt: ${JSON.stringify(texte)}`);
			assert.equal(satz!.text_de, ERKLAER_MOCKUP, 'Erklärsatz im Mockup geändert');
			// AC-3: Mockup-Satz und App-Katalog sind wortgleich; der Generator findet ihn dann im Katalog.
			assert.equal(WT_DE['wetter.erklaer.anzeige'], ERKLAER_MOCKUP, 'DE-Katalog wetter.erklaer.anzeige weicht vom Mockup ab');
			assert.equal(satz!.i18n_key, 'wetter.erklaer.anzeige', 'Erklärsatz der Elementliste ohne Katalogschlüssel');
			assert.equal(satz!.text_en, WT_EN['wetter.erklaer.anzeige'], 'EN-Text des Erklärsatzes');
		});
	}
});

describe('#3204 AC-4: Orts-Vergleich bietet Tages-Tief/-Hoch nicht an (ADR-0011)', () => {
	test('keine Zeile, kein Chip, kein Text der Gehzeit-Metriken in Orte', () => {
		const orte = LISTE.elemente.filter((e) => e.ctx === 'orte');
		assert.ok(orte.length > 0, 'Orte-Elemente fehlen');
		for (const id of NEU) {
			const treffer = orte.filter((e) => e.text_de.includes(nameDe(id)));
			assert.deepEqual(treffer.map((e) => e.id), [], `${nameDe(id)} erscheint im Orts-Vergleich`);
		}
	});
});
