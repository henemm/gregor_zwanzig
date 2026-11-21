// TDD RED — Issue #2969 (Epic #2913): Reiter Übersicht in der Elementliste.
// Spec: docs/specs/modules/feat_2969_elementliste_uebersicht.md (AC-1 bis AC-5).
// doc-compliance-test — Datentest über elementliste.json und elementliste_besitzer.json; das Verhalten
// des Abgleichs (AC-5) prüft die echte Funktion findeZusaetzliche mit den echten Daten (keine Mocks).
//
//   cd frontend && npm test -- src/lib/__tests__/elementliste_uebersicht_2969.test.ts

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import * as logik from '../../../e2e/elementliste_abgleich_logik.ts';
import type { ListenElement } from '../../../e2e/elementliste_abgleich_logik.ts';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '../../..');
const KONTEXT = path.resolve(FRONTEND, '..', 'docs/context/einstellungen_neu');
const LISTE = path.join(KONTEXT, 'elementliste.json');
const BESITZER = path.join(KONTEXT, 'elementliste_besitzer.json');
const SPEC = 'docs/specs/modules/feat_2969_elementliste_uebersicht.md';

function katalog(lang: 'de' | 'en'): Record<string, string> {
	const dir = path.join(FRONTEND, 'src/lib/i18n/messages', lang);
	const out: Record<string, string> = {};
	for (const f of readdirSync(dir).filter((n) => n.endsWith('.json'))) Object.assign(out, JSON.parse(readFileSync(path.join(dir, f), 'utf8')));
	return out;
}
const DE = katalog('de');
const EN = katalog('en');

type Eintrag = ListenElement & { id: string; ctx: string; reiter: string; zustand: string; abschnitt: string; i18n_key: string | null; text_de: string; text_en: string | null; luecke: boolean };
const liste = (): { mockup_hash: string; elemente: Eintrag[] } => JSON.parse(readFileSync(LISTE, 'utf8'));
const uebersicht = () => liste().elemente.filter((e) => e.reiter === 'uebersicht');

type Ausnahme = { ctx?: string; reiter?: string; text?: string; muster?: string; grund: string; spec: string };
const ausnahmen = (): Ausnahme[] => logik.leseAusnahmen(readFileSync(BESITZER, 'utf8')) as Ausnahme[];

// Stand vor #2969: 2646 Einträge, Prüfsumme über JSON.stringify der Einträge (Reihenfolge und Felder).
// #3192 (20.11.): Pin bewusst nachgezogen (vorher b146a7ed…7658946). Die Elementliste wurde neu erzeugt,
// damit die #3111-Dialogtexte (Vorlagen-Auswahl/-Bestätigung/-Speichern) ihr text_en aus dem Katalog tragen:
// 44 Einträge bekamen text_en (luecke true → false), dabei i18n_key/muster der Katalogzuordnung; die
// Unterzeile „N Metriken · …“ nutzt die Mehrzahl-Form (Plural-Wahl im Erzeuger, #3192).
// Anzahl 2646, IDs und Mockup-Hash unverändert.
// #3196 (20.11.): Pin erneut nachgezogen (vorher 8886ab45…57ae28817). Die Katalogschlüssel trip.aktivitaet.*
// entfallen mit den Aktivitäts-Kacheln, neu sind trip.tempo.* (Tempo-Karte). Neu erzeugt: 12 Einträge wechseln
// nur den Schlüssel (Alpen-Trekking/Skitouren → wetter.vorlage.name.*, MTB → trip.tempo.mtb), 16 Lücken der
// Tempo-Karte im Reiter Etappen (Fortbewegung, zu Fuß, Rad, Ski) bekommen Schlüssel und text_en.
// Anzahl 2646, IDs und Mockup-Hash unverändert.
// #3194 (20.11.): Pin erneut nachgezogen (vorher 0afd879c…736304f3d). Regel g „zusammengesetzt“ im EN-Zuordner:
// genau 100 bisherige Lücken der Wetter-Dialogtexte (Grenzen-Titel, Hinweis + abweichend, Bestätigungs-Rumpf)
// bekommen i18n_key, text_en (und bei {vorlage} muster); alle übrigen Einträge byte-gleich (Diff je ID geprüft).
// Anzahl 2646, IDs und Mockup-Hash unverändert.
// #3202 (21.11.): Pin erneut nachgezogen (vorher 9e1449ed…7458fa5d9, Mockup-Hash d1fcdf63…491edb40). Mockup
// Fassung 4 an die PO-Entscheidungen angeglichen (Kanalzeile Telegram „verbunden“ ohne @name, E-Mail ohne
// „+1 Empfänger“), Liste neu erzeugt: genau 14 Einträge der Kanaltabelle (Zustellung, ordnung 8 und 15, je
// Trip/Orte und Zustand) wechseln Text und damit ID; alle übrigen Einträge byte-gleich (Diff geprüft). Anzahl 2646.
// #3203 (21.11.): Pin erneut nachgezogen (vorher 65265ff3…2088d569, Mockup-Hash 112bf2f6…479d18c6). Mockup
// Fassung 4 an den Live-Vorbotensatz angeglichen (PO 21.11.: Tiefe Wolken Trip / Sonnenstunden Orte sind keine
// Vorboten → „Kein Alarm. Die Farbe erscheint nur im Briefing.“), Liste neu erzeugt: genau 4 Einträge (Reiter
// Wetter, metriken, Trip ordnung 106 und Orte ordnung 84, je Zustand normal/luecken) wechseln Text, Schlüssel
// und ID; die Trip-Folgezeile ordnung 112 (gleicher Text, je Zustand) wechselt nur die ID (Vorkommens-Zähler). Alle
// übrigen Einträge byte-gleich (Diff geprüft). Anzahl 2646.
// #3204: zwei Anzeige-Metriken ergänzt (21.11.; vorher 11ce7550…eda1986, Mockup-Hash e8d3efb5…5e8b095, Anzahl
// 2646). Mockup Fassung 4 zeigt Tages-Tief/-Hoch (Gehzeit) im Trip als aktive Nur-Anzeige-Zeilen (Gruppe
// Temperatur nach Tiefsttemperatur Nacht), der Erklärsatz nennt „Was steht wo“. Liste neu erzeugt: je Zustand
// normal/luecken neu Name, Untertitel, Zeilenmitte, Erklärsatz, „kein Alarm“, Entfernen-Knopf und die Zeilen in
// „Was steht wo“ (Name + 4 Haken) beider Metriken; der Zähler „9 von 13 … 3“ wird „9 von 15 … 5“. Orte und alle
// übrigen Einträge unverändert (Diff geprüft). Anzahl 2690.
// #3205: Vorlagen je Art im Mockup (21.11.; vorher 61d486a3…843e329, Mockup-Hash eb4b3442…538f2d1c4, Anzahl
// 2690). Mockup Fassung 4 führt eigene Vorlagen je Art wie die App (PO 08.11./21.11.: Trip und Orts-Vergleich
// getrennt); die Trip-Vorlage „Mallorca Frühling“ steht nur noch in der Trip-Auswahl. Liste neu erzeugt: genau
// 4 Einträge entfallen (Orte, vorlage-auswahl, Zustände normal/luecken, je Name und Unterzeile „eigene · aus
// GR221 gespeichert“); alle übrigen Einträge byte-gleich, Reihenfolge gleich (Diff je ID geprüft). Anzahl 2686.
// #3250: drei gefühlte Anzeige-Metriken ergänzt (21.11.; vorher 5bec7350…6adf371ae3f, Mockup-Hash
// 24f6c2a4…765b1b8, Anzahl 2686). Mockup Fassung 4 zeigt Gefühlte Tiefsttemperatur Nacht, Gefühlte
// Tages-Tiefst-/Höchsttemperatur (Gehzeit) im Trip als aktive Nur-Anzeige-Zeilen (Gruppe Temperatur nach
// Gefühlte Temperatur, Reihenfolge wie _REITER_WETTER). Liste neu erzeugt: 66 neue Einträge, nur Trip/Wetter
// (je Zustand normal/luecken Name, Untertitel, Zeilenmitte, Erklärsatz, „kein Alarm“, Entfernen-Knopf und die
// Zeilen in „Was steht wo“ (Name + 4 Haken)); der Zähler „9 von 15 … 5“ wird „9 von 18 … 8“ (gleiche ID); die
// übrigen Trip/Wetter-Einträge ändern nur ordnung. Orte, Zustellung und alle übrigen Einträge byte-gleich, keine
// ID entfallen (Diff je ID geprüft). Anzahl 2752.
const ALT_ANZAHL = 2752;
const ALT_SHA = 'bb07d0b72a14ccb4450a346d1074c9fd91ef959c9ecc39f4a07f49baf10e8904';
const MOCKUP_HASH = 'sha256:c2347e0876a30710b2d56f6c1561b13668cb48089802558eaeaec0de30d8e6be';

test('AC-1: 16 Übersicht-Einträge (Trip/Orte × 4 Zustände × Titel/Satz), Abschnitt abschnittskopf, DE/EN aus dem Katalog', () => {
	const e = uebersicht();
	assert.equal(e.length, 16, `Übersicht-Einträge: ${e.length}`);
	const fehler: string[] = [];
	for (const ctx of ['trip', 'orte']) {
		for (const zustand of ['normal', 'laedt', 'fehler', 'luecken']) {
			const gruppe = e.filter((x) => x.ctx === ctx && x.zustand === zustand);
			const keys = gruppe.map((x) => x.i18n_key).sort();
			if (JSON.stringify(keys) !== JSON.stringify(['aktionen.reiter.uebersicht', 'bausteine.hub_uebersicht.kopf_erklaer']))
				fehler.push(`${ctx}/${zustand}: Schlüssel ${JSON.stringify(keys)}`);
		}
	}
	for (const x of e) {
		if (x.abschnitt !== 'abschnittskopf') fehler.push(`${x.id}: Abschnitt ${x.abschnitt}`);
		if (x.luecke) fehler.push(`${x.id}: EN-Lücke`);
		if (x.i18n_key && (x.text_de !== DE[x.i18n_key] || x.text_en !== EN[x.i18n_key])) fehler.push(`${x.id}: DE/EN ≠ Katalog`);
	}
	assert.equal(EN['aktionen.reiter.uebersicht'], 'Overview');
	assert.equal(EN['bausteine.hub_uebersicht.kopf_erklaer'], 'Unchanged: status, latest briefings, next delivery.');
	assert.deepEqual(fehler, [], fehler.join('\n'));
});

test('AC-2: Die Mockup-Notiz „Im Mockup nicht ausgearbeitet.“ ist kein Soll-Eintrag', () => {
	const treffer = liste().elemente.filter((x) => /nicht ausgearbeitet/i.test(x.text_de));
	assert.deepEqual(treffer.map((x) => x.id), []);
	assert.ok(uebersicht().length > 0, 'ohne Übersicht-Einträge ist AC-2 nicht aussagekräftig');
});

test('AC-3: Bisherige 2646 Einträge unverändert, Mockup-Hash unverändert', () => {
	const l = liste();
	const rest = l.elemente.filter((x) => x.reiter !== 'uebersicht');
	assert.equal(rest.length, ALT_ANZAHL);
	assert.equal(createHash('sha256').update(JSON.stringify(rest)).digest('hex'), ALT_SHA);
	assert.equal(l.mockup_hash, MOCKUP_HASH);
	assert.ok(uebersicht().length > 0, 'neue Übersicht-Einträge fehlen');
});

test('AC-4: Keine Pauschal-Ausnahme für die Übersicht; Einzel-Ausnahmen je ctx mit Grund und Spec', () => {
	const u = ausnahmen().filter((a) => a.reiter === 'uebersicht');
	const pauschal = u.filter((a) => typeof a.muster === 'string' && /^\s*(\{\w+\}\s*)+$/.test(a.muster));
	assert.deepEqual(pauschal, [], 'Muster nur aus Platzhaltern verdeckt den ganzen Reiter');
	for (const ctx of ['trip', 'orte']) {
		assert.ok(u.some((a) => a.ctx === ctx), `keine Einzel-Ausnahme für ${ctx}/uebersicht`);
	}
	const ohne = u.filter((a) => !a.grund.includes('unverändert') || a.spec !== SPEC);
	assert.deepEqual(ohne, [], `jede Übersicht-Ausnahme braucht Grund („unverändert“) und spec=${SPEC}`);
});

test('AC-5: Gegenrichtung Übersicht — Kopf, Bereichskopf und bekannter Inhalt erklärt, unbekannter Text zusaetzlich', () => {
	const l = liste().elemente as unknown as ListenElement[];
	const aus = ausnahmen();
	for (const ctx of ['trip', 'orte'] as const) {
		const kopf = liste().elemente.find((x) => x.ctx === ctx && x.reiter === 'wetter' && x.zustand === 'normal' && x.abschnitt === 'kopf' && !x.muster);
		assert.ok(kopf, `kein Kopf-Eintrag für ${ctx}`);
		const bekannt = aus.filter((a) => a.ctx === ctx && a.reiter === 'uebersicht' && typeof a.text === 'string').map((a) => a.text as string);
		assert.ok(bekannt.length > 0, `${ctx}: keine Einzel-Ausnahme mit festem Text`);
		const unbekannt = 'Völlig neuer Übersichtstext 2969 ohne Soll';
		for (const sprache of ['de', 'en'] as const) {
			const texte = [
				sprache === 'de' ? kopf.text_de : (kopf.text_en ?? kopf.text_de),
				sprache === 'de' ? DE['aktionen.reiter.uebersicht'] : EN['aktionen.reiter.uebersicht'],
				sprache === 'de' ? DE['bausteine.hub_uebersicht.kopf_erklaer'] : EN['bausteine.hub_uebersicht.kopf_erklaer'],
				...bekannt,
				unbekannt
			];
			const zus = logik.findeZusaetzliche({ ctx, reiter: 'uebersicht', texte }, l, aus, [], sprache);
			const nichtErklaert = zus.map((z) => z.text);
			// Einzel-Ausnahmen sind sprachgebunden über ihren Text; erklärt sein müssen hier Kopf, Bereichskopf und der unbekannte Text gemeldet.
			assert.ok(nichtErklaert.includes(unbekannt), `${ctx}/${sprache}: unbekannter Text nicht als zusaetzlich gemeldet`);
			for (const t of texte.slice(0, 3)) assert.ok(!nichtErklaert.includes(t), `${ctx}/${sprache}: „${t}“ nicht erklärt`);
			for (const t of bekannt) assert.ok(!nichtErklaert.includes(t), `${ctx}/${sprache}: Ausnahme-Text „${t}“ nicht erklärt`);
		}
	}
});
