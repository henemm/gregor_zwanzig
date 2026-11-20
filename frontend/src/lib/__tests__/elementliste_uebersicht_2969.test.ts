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
const ALT_ANZAHL = 2646;
const ALT_SHA = '0afd879c0de88cdfff286c1cc3b609bcb5474efd26be028c41e18ae736304f3d';
const MOCKUP_HASH = 'sha256:d1fcdf63fb3b9fdc166f537f89af5e0f66992b62541b78176fc2504a491edb40';

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
