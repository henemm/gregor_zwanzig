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
// #3251: Abschnitt vorlage-abweichung (21.11.; vorher bb07d0b7…10e8904, Mockup-Hash unverändert, Anzahl 2752).
// Der Generator wählt im Reiter Wetter (Zustand normal) eine Metrik ab (devs>0) und liest Picker-Zahl und
// Zurücksetzen-Zeile. Liste neu erzeugt: genau 4 neue Einträge (Trip/Orte je „1 Abweichung“, Stand ohne
// Auswahlpfeil wie live, und „Auf „{vorlage}“ zurücksetzen“); alle übrigen Einträge byte-gleich, keine ID
// entfallen (Diff je ID geprüft). Anzahl 2756.
const ALT_ANZAHL_3251 = 2756;
// #3251 Fix-Loop 2 (21.11.; vorher 7d0365c3…3c8a4): die zwei Einträge „1 Abweichung“ führen die Zahl als
// Katalog-Mehrzahl-Muster („{count} Abweichungen“ / „{count} changes“, Schlüssel .other), weil der Prüf-Datensatz
// live 14 bzw. 8 Abweichungen zeigt. ID, text_de und alle übrigen Einträge byte-gleich (Diff je ID geprüft).
// #3258: Legende „Kürzel erklärt“ (22.11.; vorher e31b8c1d…cadac10d5, Mockup-Hash c2347e08…30d8e6be, Anzahl
// 2756). Mockup Fassung 4 zeigt unter der SMS-Beispielzeile den Aufklapper „Kürzel erklärt“ wie live (je aktiver
// SMS-Metrik Kürzel und Bedeutung, dann die festen Einträge aus wetter.wsw.legende.*, bei Orten O1); der
// Generator liest Kürzel (dt, sprachneutral) und Bedeutung (dd; EN aus wetter.wsw.legende.*, sonst aus dem
// Server-Katalog-Schnappschuss daten/kuerzel_bedeutung.json, Fix-Loop 1 F002: keine EN-Lücke in der Legende).
// Liste neu erzeugt: 184 neue Einträge, nur Abschnitt was-steht-wo im Reiter Wetter (Trip 55, Orte 37, je Zustand
// normal/luecken); die folgenden Einträge desselben Abschnitts ändern nur ordnung. Keine ID entfallen, alle
// übrigen Einträge byte-gleich (Diff je ID geprüft).
// #3154: Abnahme-Abgleich „Was steht wo“ (22.11.; vorher 95e04d79…0a269b12a5, Mockup-Hash c347e818…9503cdb972,
// Anzahl 2940). Mockup Fassung 4 an freigegebene Entscheidungen angeglichen: die sechs Fensterzeilen sind in
// E-Mail und 3-Tages-Ausblick gesperrt mit Grund („keine eigene Spalte“, „kein Tageswert“) statt Haken,
// Gewitter-Einfach nur in der E-Mail (dort nur der Ampelpunkt ohne Text, wie live), Regenwahrscheinlichkeit mit
// Roh/Einfach-Knopf (Spec #3122 Teil A Nr. 4), Orte-SMS als Token-Zeile (ADR-0125) ohne „+N“ und ohne
// „Dafür steht …“, gekürzte SMS-Zellen nur mit Marke, Zeichenzahl als eigenes Element, Ausblick-Schalter vor dem
// Titel (Titel aria-hidden wie live). Generator: Beispieltexte (Rolle beispiel) als Muster {wert}, je Zelle ein
// Element; EN-Metriknamen aus daten/metrik_namen.json; SMS-Kürzungshinweis als Regel g (E1–E4). Liste neu
// erzeugt: im Abschnitt was-steht-wo (Trip/Orte, je Zustand normal/luecken) 180 IDs entfallen und 174 neu
// (Haken → Sperr-Grund, Beispiele mit Rolle beispiel, Darstellungs-Knöpfe Regenwahrscheinlichkeit, Orte-SMS/
// Hinweis), 294 ändern nur ordnung, 10 Inhalt (EN der Zeilennamen); außerhalb von was-steht-wo ändern genau 10
// Einträge im Abschnitt metriken (Zeilennamen Regenwahrscheinlichkeit, Tiefe Wolken, UV-Index, Bewölkung je
// Zustand) nur EN (Lücke → Server-EN). Alle übrigen Einträge byte-gleich (Diff je ID geprüft).
const ALT_ANZAHL = ALT_ANZAHL_3251 + 184 - 180 + 174;
// #3276: 6 Einträge „Stundenverlauf“ (was-steht-wo, orte) ändern nur i18n_key vergleich.stundenverlauf.titel →
// wetter.wsw.bloecke.stundenverlauf (alter Schlüssel mit der Compare-Stundenverlauf-Steuerung entfernt; EN gleich).
// #3297/#3020: 12 Einträge (was-steht-wo, trip/orte) ändern nur i18n_key layout.ausblick.titel →
// wetter.wsw.bloecke.ausblick bzw. layout.mail_inhalt.ausfuehrlich/kompakt → wetter.wsw.kanal.ausfuehrlich/kompakt
// (alte Schlüssel mit OutlookLayoutControls/MailInhaltCard entfernt; DE/EN gleich).
// #3383 S1 (26.11.; vorher d0b10d3c…af728e3f50): Liste mit dem Generator neu erzeugt, Mockup-Hash und Anzahl
// gleich, keine ID entfallen, Reihenfolge gleich (Diff je ID geprüft). Nur i18n_key ändert sich, weil Schlüssel
// der gelöschten Waisen entfielen: 28 Einträge wertebereiche.symbolzeile.* → null (metriken/was-steht-wo, EN
// unverändert aus daten/metrik_namen.json), 8 trip.about.kanal → zustellung.spalte.kanal (DE/EN gleich), 4
// „Eigene“ wertebereiche.preset.eigene → wetter.vorlage.eigene (EN „Custom“ → „Your own“, der Wortlaut der App).
// Dazu 20 „Telegram“ wetter.wsw.spalte.telegram → level.zeile.telegram (DE/EN gleich): Altstand ohne S1-Bezug,
// der Schlüssel level.zeile.telegram (funktionen.json, #3319) sortiert davor und fehlte in der vorigen Erzeugung.
// #3385 S3 (26.11.; vorher 1a6ffdba…83de02666): Liste mit dem Generator neu erzeugt, Mockup-Hash und Anzahl
// gleich, keine ID entfallen, Reihenfolge gleich. Nur i18n_key ändert sich, weil die versand.laufzeit.*-Schlüssel
// der gelöschten Waisen entfielen: 20 Einträge „Laufzeit“/„Etappen öffnen →“/„Bis auf Weiteres“/„Bis Datum“
// versand.laufzeit.* → zustellung.laufzeit.* (DE/EN gleich).
// #3020 R2 (26.11.; vorher 2e9246ec…0e73ce): Liste mit dem Generator neu erzeugt, Mockup-Hash und Anzahl gleich,
// keine ID entfallen, Reihenfolge gleich. Nur i18n_key ändert sich, weil wertebereiche.kategorie.* mit
// BucketSectionOff/MetricOffShelf entfiel: 24 Einträge „Temperatur“/„Wind“ (metriken/was-steht-wo, trip und orte)
// wertebereiche.kategorie.temperature/wind → wetter.gruppe.temperature/wind (DE/EN gleich).
// #3419 (26.11.; vorher a532b75c…e1d661084290, Mockup-Hash fbb04f54…657cf5ab13a31e267eb00882ad7e6496ec6, Anzahl
// 2934): Mockup Fassung 4 an den Live-Stand der Karte „Was steht wo“ angeglichen (Temperatur in SMS gesperrt „kein
// Kürzel“ mit Bereichs-Token, SMS-Zeile in Live-Form „E1 …“, Legende Tiefst/Höchst zusammengeführt #3284, Trip-Blöcke
// Kurz-Zusammenfassung und Großwetterlage #3036, E-Mail-Format auch bei Orten #3059, Ausblick-Beschriftungen
// Morgen-/Abend-Briefing, Orte-SMS-Temperatur „D{tief}/{hoch}“, Trip-Vorlage „▾ 1 Abweichung“ mit Zurücksetzen).
// Liste neu erzeugt: 24 IDs entfallen, 46 neu, 4 Inhalt (Zeichenzahl der SMS-Zeile), 154 nur ordnung — alles nur in
// den Abschnitten was-steht-wo und vorlage (trip/orte, je Zustand normal/luecken). Diff je ID geprüft.
// #3419 Fix-Loop: Generator nimmt Wetter-Symbole (Emoji) als Beispielwert einer Zelle auf („🌥️“, Tiefe Wolken in
// E-Mail, trip normal/luecken): +2 Einträge, nur ordnung im Abschnitt was-steht-wo verschoben.
// #3442 (Kebab-Rückfragen, 27.11.; vorher 3c90a598…4af2c22ae): Liste mit dem Generator neu erzeugt, Mockup-Hash gleich.
// 8 IDs entfallen: die K14-Anmerkung „Pausieren, Archivieren, Löschen“ (#kebabMenu .dis) ist kein UI-Text (Generator
// überspringt sie wie die Übersicht-Notiz). Sonst nur Katalogfelder: kebab-bestaetigung-* (32) bekommen
// aktionen.kebab.* samt text_en/muster {name} statt Lücke, kebab-menue (16) aktionen.kebab.menue_*, test-menue (14)
// schließt EN-Lücken aus test_schicken.* (#3440), kanaele (8) „Briefing“ → test_schicken.briefing (DE/EN gleich).
const ALT_ANZAHL_3419 = ALT_ANZAHL - 24 + 46 + 2 - 8;
// #3441 (Test-Alarm): im Abschnitt test-menue tragen die 16 Zeilen „Test-Alarm“ und ihr Untertitel (alle Kontexte
// und Zustände) jetzt i18n_key, text_en und luecke false. Keine ID neu oder entfallen, Anzahl gleich, sonst byte-gleich.
// #3241 (Metrik-Zeile EN, 28.11.; vorher a227cb93…0d75c1): im Abschnitt metriken tragen 12 Zeilen („mm · Summe“,
// „m · Minimum“, „°C · Tageshöchst · Tagestief“, „· grün: bis 6“) jetzt wetter.hinweis.* bzw. wetter.gruen.bis mit
// text_en; keine ID neu oder entfallen, Anzahl gleich, sonst byte-gleich (Diff je ID geprüft).
const ALT_SHA = 'cc2a199914234e62eee9e2e4a347a116edac67aae669bec0e1648ac8748571fa';
const MOCKUP_HASH = 'sha256:946e69c0f185fc66133b3b8c820d87b61ef3a3f52834f621c1c76505c7f81a0b';

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
	assert.equal(rest.length, ALT_ANZAHL_3419);
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
