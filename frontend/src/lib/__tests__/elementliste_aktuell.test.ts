// TDD RED — Issue #2913 (Epic #2791): Elementliste aus dem Mockup (Fassung 4, #3122).
// Spec: docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md — AC-9 bis AC-12.
// Fassung 4 (ADR-0124): Die Karte „Inhalt je Kanal und Fläche“ mit ihren Kanal-Segmenten ist durch die
// Tabelle „Was steht wo“ ersetzt (Abschnitt was-steht-wo). Kanal-Segmente gibt es nicht mehr, `segment` ist immer null.
//
// Läuft OHNE Browser im CI-Job `frontend-test`. Geprüft wird das echte, eingecheckte Artefakt
// `docs/context/einstellungen_neu/elementliste.json` gegen das echte Mockup und den echten
// i18n-Katalog. Den Generator-Lauf mit Browser (zwei Läufe, stabile IDs) prüft
// e2e/elementliste-generator.mockup.spec.ts (Config playwright.elementliste.mockup.config.ts).
//
// Vertrag des Generator-Moduls `scripts/elementliste_aus_mockup.ts` (vom Developer umzusetzen):
//   mockupHash(inhalt: string | Buffer): string               — 'sha256:<hex>' über die Datei-Bytes
//   pruefeHashAktuell(mockupPfad, jsonPfad): { ok: boolean; erwartet: string; ist: string }
//   ladeKatalog(messagesDir): { de: Record<string,string>; en: Record<string,string> }  (flache Schlüssel)
//   ermittleEn(textDe, katalog): { i18n_key: string|null; text_en: string|null; muster: string|null; luecke: boolean }
//   erzeugeElementliste({ mockupPfad, messagesDir }): Promise<Elementliste>   (Playwright, file://)
//   Playwright wird erst innerhalb von erzeugeElementliste geladen (dynamischer Import), damit
//   dieser Test ohne Browser und ohne Root-node_modules importieren kann.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --experimental-test-module-mocks --test src/lib/__tests__/elementliste_aktuell.test.ts
import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync, mkdtempSync, writeFileSync, copyFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
	mockupHash,
	pruefeHashAktuell,
	ladeKatalog,
	ermittleEn
} from '../../../../scripts/elementliste_aus_mockup.ts';

const REPO = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..', '..');
const MOCKUP = join(REPO, 'docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html');
const LISTE = join(REPO, 'docs/context/einstellungen_neu/elementliste.json');
const MESSAGES = join(REPO, 'frontend/src/lib/i18n/messages');

type Element = {
	id: string;
	ctx: string;
	reiter: string;
	zustand: string;
	segment: string | null;
	abschnitt: string;
	ordnung: number;
	rolle: string;
	text_de: string;
	muster: string | null;
	i18n_key: string | null;
	text_en: string | null;
	luecke: boolean;
};

function liste(): { mockup_hash: string; elemente: Element[] } {
	return JSON.parse(readFileSync(LISTE, 'utf8'));
}

// Soll unabhängig vom Generator festgehalten (Spec AC-9) — sonst prüfte der Test sich selbst.
const ZUSTAENDE = ['normal', 'laedt', 'fehler', 'luecken'];
const SOLL: Array<{ ctx: string; reiter: string; zustand: string; segment: string | null }> = [];
for (const ctx of ['trip', 'orte']) {
	for (const zustand of ZUSTAENDE) {
		SOLL.push({ ctx, reiter: 'wetter', zustand, segment: null });
		SOLL.push({ ctx, reiter: ctx === 'trip' ? 'etappen' : 'orte', zustand, segment: null });
		SOLL.push({ ctx, reiter: 'zustellung', zustand, segment: null });
	}
}
// Die Tabelle „Was steht wo“ rendert das Mockup im Reiter WETTER (viewWetter ruft wasStehtWo auf,
// mockup-hub-fassung4.html) und nur in den Zuständen normal und Konto mit Lücken — bei lädt/Ladefehler
// zeigt viewWetter nur Skelett bzw. Fehlerbox, die Karte gibt es dort nicht.
const TABELLE = 'was-steht-wo';
const TABELLE_ZUSTAENDE = ['normal', 'luecken'];

// ---------------------------------------------------------------- AC-12
describe('AC-12: Hash-Check Mockup ↔ elementliste.json (ohne Browser)', () => {
	test('Hash in der JSON entspricht dem SHA-256 der Mockup-Datei', () => {
		const soll = 'sha256:' + createHash('sha256').update(readFileSync(MOCKUP)).digest('hex');
		assert.equal(liste().mockup_hash, soll, 'Mockup geändert? → Generator neu laufen lassen');
		assert.equal(mockupHash(readFileSync(MOCKUP)), soll);
	});

	test('pruefeHashAktuell: Original grün, veränderte Kopie rot', () => {
		assert.equal(pruefeHashAktuell(MOCKUP, LISTE).ok, true);
		const dir = mkdtempSync(join(tmpdir(), 'elementliste-hash-'));
		try {
			const kopie = join(dir, 'mockup.html');
			copyFileSync(MOCKUP, kopie);
			writeFileSync(kopie, readFileSync(kopie, 'utf8').replace('Zustellung', 'Zustelung'));
			const r = pruefeHashAktuell(kopie, LISTE);
			assert.equal(r.ok, false);
			assert.notEqual(r.erwartet, r.ist);
		} finally {
			rmSync(dir, { recursive: true, force: true });
		}
	});
});

// ---------------------------------------------------------------- AC-9
describe('AC-9: alle Kombinationen Kontext × Zustand × Reiter, Tabelle „Was steht wo“, ohne Mockup-Rahmen', () => {
	test('jede Soll-Kombination hat mindestens ein Element', () => {
		const el = liste().elemente;
		const fehlend = SOLL.filter(
			(k) =>
				!el.some(
					(e) => e.ctx === k.ctx && e.reiter === k.reiter && e.zustand === k.zustand && (e.segment ?? null) === k.segment
				)
		);
		assert.deepEqual(fehlend, [], `fehlende Kombinationen: ${fehlend.length}`);
	});

	test('kein Eintrag trägt ein Kanal-Segment, die ersetzte Karte „Inhalt je Kanal und Fläche“ ist weg (ADR-0124)', () => {
		for (const e of liste().elemente) {
			assert.equal(e.segment ?? null, null, `${e.id}: Kanal-Segment gibt es seit Fassung 4 nicht mehr`);
			assert.notEqual(e.abschnitt, 'kanal-inhalt', `${e.id}: Abschnitt der ersetzten Karte`);
			assert.ok(!e.text_de.includes('Inhalt je Kanal'), `${e.id}: Text der ersetzten Karte`);
		}
	});

	test('Tabelle „Was steht wo“: nur im Wetter-Reiter, nur normal und Konto mit Lücken, für Trip und Orte', () => {
		const tab = liste().elemente.filter((e) => e.abschnitt === TABELLE);
		for (const e of tab) {
			assert.equal(e.reiter, 'wetter', `${e.id}: Tabelle außerhalb des Wetter-Reiters`);
			assert.ok(TABELLE_ZUSTAENDE.includes(e.zustand), `${e.id}: Tabelle im Zustand ${e.zustand}`);
		}
		for (const ctx of ['trip', 'orte']) {
			for (const zustand of TABELLE_ZUSTAENDE) {
				const texte = tab.filter((e) => e.ctx === ctx && e.zustand === zustand).map((e) => e.text_de);
				for (const soll of ['Was steht wo', 'Amtliche Warnungen', 'Ganze Blöcke ein- und ausschalten', 'Einstellungen je Kanal']) {
					assert.ok(texte.includes(soll), `${ctx}/${zustand}: „${soll}“ fehlt in der Tabelle`);
				}
				assert.ok(texte.some((t) => t.startsWith('SMS-Beispiel:')), `${ctx}/${zustand}: SMS-Beispielzeile fehlt`);
			}
		}
	});

	test('Stellen der Tabelle: E-Mail, Telegram, SMS und 3-Tages-Ausblick überall; Stundenverlauf nur bei Orte', () => {
		const tab = liste().elemente.filter((e) => e.abschnitt === TABELLE && e.zustand === 'normal');
		const texte = (ctx: string) => tab.filter((e) => e.ctx === ctx).map((e) => e.text_de);
		for (const ctx of ['trip', 'orte']) {
			for (const stelle of ['E-Mail', 'Telegram', 'SMS', '3-Tages-Ausblick']) {
				assert.ok(texte(ctx).includes(stelle), `${ctx}: Spalte ${stelle} fehlt`);
			}
			assert.ok(texte(ctx).includes('Temperatur in E-Mail'), `${ctx}: Haken „Temperatur in E-Mail“ fehlt`);
			assert.ok(texte(ctx).includes('Temperatur im 3-Tages-Ausblick'), `${ctx}: Haken im Ausblick fehlt`);
			// Roh/Einfach je Stelle nur bei Metriken mit zwei Formen (ADR-0124 Nr. 5): Wind ja, Temperatur nein.
			assert.ok(texte(ctx).some((t) => t.startsWith('Darstellung Wind in E-Mail:')), `${ctx}: Umschalter Wind fehlt`);
			assert.ok(!texte(ctx).some((t) => t.startsWith('Darstellung Temperatur')), `${ctx}: Umschalter bei Temperatur`);
			// SMS und Premium-SMS haben keine Wahl.
			assert.ok(!texte(ctx).some((t) => /^Darstellung .* in SMS:/.test(t)), `${ctx}: Umschalter in der SMS-Spalte`);
		}
		assert.ok(texte('orte').includes('Stundenverlauf') && texte('orte').includes('Temperatur im Stundenverlauf'));
		assert.ok(texte('orte').includes('kein Stundenwert'), 'Sonnenstunden sind im Stundenverlauf gesperrt');
		assert.ok(!texte('trip').some((t) => t.includes('Stundenverlauf')), 'Trip hat keine Spalte Stundenverlauf');
	});

	test('keine Texte aus .frame, data-fb oder .tag', () => {
		const texte = liste().elemente.map((e) => e.text_de);
		for (const rahmen of ['Mockup · Fassung 4', 'Orte · 3 Orte', 'Orte · 1 Ort', 'neu markiert', 'Konto mit Lücken', 'Neue Punkte markieren', 'Kopf & Test schicken', 'Sonstiges']) {
			assert.ok(!texte.some((t) => t.includes(rahmen)), `Rahmen-/Feedbacktext in der Liste: ${rahmen}`);
		}
		const lade = liste().elemente.filter((e) => e.text_de.startsWith('Lade Metriken'));
		assert.ok(lade.length > 0, 'Ladezustand fehlt');
		for (const e of lade) assert.doesNotMatch(e.text_de, /\bW1\b/, '.tag-Kürzel muss entfernt sein');
		for (const t of texte) assert.doesNotMatch(t, /\s(?:[A-Z]\d{1,2})$/, `Tag-Kürzel am Textende: ${t}`);
	});

	test('beide Kontexte und alle vier Kanäle sind vertreten (Kanal-Tabelle im Reiter Zustellung)', () => {
		const el = liste().elemente;
		assert.ok(el.some((e) => e.ctx === 'trip') && el.some((e) => e.ctx === 'orte'));
		assert.deepEqual([...new Set(el.map((e) => e.ctx))].sort(), ['orte', 'trip'], 'der Ein-Ort-Kontext wird nicht gelesen');
		for (const ctx of ['trip', 'orte']) {
			for (const k of ['E-Mail', 'Telegram', 'SMS', 'Premium-SMS']) {
				assert.ok(
					el.some((e) => e.ctx === ctx && e.reiter === 'zustellung' && e.abschnitt === 'kanaele' && e.text_de === k),
					`${ctx}: Kanal ${k} fehlt`
				);
			}
		}
	});
});

// ---------------------------------------------------------------- AC-10
describe('AC-10: Schema je Eintrag, eindeutige IDs, dynamische Texte als ein Element mit Muster', () => {
	const FELDER = ['id', 'ctx', 'reiter', 'zustand', 'abschnitt', 'ordnung', 'rolle', 'text_de', 'muster', 'i18n_key', 'text_en', 'luecke'];

	test('jeder Eintrag hat alle Felder mit passenden Typen', () => {
		const el = liste().elemente;
		assert.ok(el.length > 100, 'Elementliste ist erstaunlich kurz');
		for (const e of el) {
			for (const f of FELDER) assert.ok(f in e, `${e.id ?? '?'}: Feld ${f} fehlt`);
			assert.equal(typeof e.id, 'string');
			assert.equal(typeof e.ordnung, 'number');
			assert.equal(typeof e.luecke, 'boolean');
			assert.ok(e.text_de.trim().length > 0, `${e.id}: leerer Text`);
			assert.ok(e.muster === null || typeof e.muster === 'string');
		}
	});

	test('IDs sind eindeutig', () => {
		const ids = liste().elemente.map((e) => e.id);
		assert.equal(new Set(ids).size, ids.length);
	});

	test('Reihenfolge: ordnung ist je Kombination und Abschnitt eindeutig', () => {
		const gesehen = new Set<string>();
		for (const e of liste().elemente) {
			const k = [e.ctx, e.reiter, e.zustand, e.segment, e.abschnitt, e.ordnung].join('|');
			assert.ok(!gesehen.has(k), `doppelte ordnung: ${k}`);
			gesehen.add(k);
		}
	});

	test('dynamische Texte: je Kombination und Abschnitt kein Text doppelt, der sich nur in Zahlen unterscheidet', () => {
		const gruppen = new Map<string, Element[]>();
		for (const e of liste().elemente) {
			const k = [e.ctx, e.reiter, e.zustand, e.segment, e.abschnitt, e.text_de.replace(/\d+([.,]\d+)?/g, '#')].join('|');
			gruppen.set(k, [...(gruppen.get(k) ?? []), e]);
		}
		const doppelt = [...gruppen.values()].filter((g) => g.length > 1 && new Set(g.map((e) => e.text_de)).size > 1);
		assert.deepEqual(
			doppelt.map((g) => g.map((e) => e.text_de)),
			[],
			'Werte-Varianten müssen als EIN Element mit muster erscheinen'
		);
	});

	test('es gibt Elemente mit Muster, und jedes Muster enthält einen Platzhalter', () => {
		const mit = liste().elemente.filter((e) => e.muster !== null);
		assert.ok(mit.length > 0, 'keine dynamischen Texte erkannt');
		for (const e of mit) assert.match(e.muster as string, /\{[^}]+\}/, `${e.id}: Muster ohne Platzhalter`);
	});
});

// ---------------------------------------------------------------- AC-11
describe('AC-11: EN aus dem Katalog — exakter Treffer, Muster, sonst Lücke (nie erfunden)', () => {
	const katalog = ladeKatalog(MESSAGES);

	test('Katalog ist flach und zweisprachig geladen', () => {
		assert.equal(katalog.de['aktionen.reiter.zustellung'], 'Zustellung');
		assert.equal(katalog.en['aktionen.reiter.zustellung'], 'Delivery');
	});

	test('exakter Treffer: EN-Wert desselben Schlüssels', () => {
		const r = ermittleEn('Zustellung', katalog);
		assert.equal(r.luecke, false);
		assert.ok(r.i18n_key && katalog.de[r.i18n_key] === 'Zustellung', `Schlüssel ${r.i18n_key}`);
		assert.equal(r.text_en, katalog.en[r.i18n_key as string]);
		assert.equal(r.text_en, 'Delivery');
	});

	test('Musterabgleich: Platzhalter-Text aus dem Katalog liefert das EN-Muster (Platzhalter bleiben, #2913 C5)', () => {
		const r = ermittleEn('Etappe T3 auswählen', katalog);
		assert.equal(r.luecke, false);
		assert.equal(r.i18n_key, 'trip.profil.etappe_waehlen');
		assert.equal(r.muster, 'Etappe {code} auswählen');
		assert.equal(r.text_en, 'Select stage {code}');
	});

	test('kein Treffer: luecke = true, kein erfundenes EN', () => {
		const r = ermittleEn('Ersetzt den bisherigen „Mehrtages-Trend“. Vorbelegung: nur abends.', katalog);
		assert.equal(r.luecke, true);
		assert.equal(r.text_en, null);
		assert.equal(r.i18n_key, null);
	});

	test('in der erzeugten Liste: Lücke ⇔ kein EN; Treffer ⇔ Schlüssel im Katalog', () => {
		for (const e of liste().elemente) {
			if (e.luecke) {
				assert.equal(e.text_en, null, `${e.id}: Lücke mit EN-Text`);
			} else if ((e as { sprachneutral?: boolean }).sprachneutral) {
				// #2968 Regel c: sprachneutral ⇒ kein Schlüssel, EN = DE-Muster (Zahlen als {zahl}).
				assert.equal(e.i18n_key, null, e.id);
				assert.equal(e.text_en, e.text_de.replace(/\d+([.,]\d+)?/g, '{zahl}'), e.id);
			} else if (e.i18n_key === null) {
				// #2968 Regel b: Segmente ohne einzelnen Schlüssel, EN = Segment-EN mit „ · “ verbunden.
				assert.ok(e.text_en && (e.text_en.includes(' · ') || e.text_en.startsWith('· ')), `${e.id}: Treffer ohne Schlüssel und ohne Segmente`);
			} else {
				assert.ok(e.i18n_key && e.i18n_key in katalog.en, `${e.id}: Schlüssel ${e.i18n_key} fehlt im EN-Katalog`);
				assert.ok(e.text_en && e.text_en.length > 0);
			}
		}
	});

	test('der Reitername „Zustellung“ ist in der Liste kein Lückenposten', () => {
		const z = liste().elemente.filter((e) => e.text_de === 'Zustellung');
		assert.ok(z.length > 0);
		for (const e of z) assert.equal(e.text_en, 'Delivery');
	});
});
