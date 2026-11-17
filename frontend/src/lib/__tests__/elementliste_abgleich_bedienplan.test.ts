// Issue #2966 (Epic #2913): Bedienplan für Script-Zustände im Reiter Wetter, Schreib-Tripwire und
// Abräumen der Besitzer-Einträge `#2966`. Spec: docs/specs/modules/feat_2966_abgleich_haken.md
// (AC-6, AC-7, AC-10). Reine Logik aus frontend/e2e/elementliste_abgleich_logik.ts, geprüft mit der
// echten Elementliste und der echten Besitzer-Datei.
//
//   cd frontend && npm test -- src/lib/__tests__/elementliste_abgleich_bedienplan.test.ts
//
// Vertrag `bedienPlan(abschnitt, lage)`:
//   lage = { ctx: 'trip' | 'orte', briefing: string[] (Metrik-IDs im Briefing des Prüf-Datensatzes),
//            vorlagen: string[] (System-Vorlagen-IDs), aktiveVorlage: string }
//   Ergebnis:
//     { art: 'ohne_bedienung' }                        Abschnitt braucht keinen Bedienschritt
//     { art: 'plan', schritte: Schritt[] }             Schritt = { aktion: 'klick' | 'lesen' | 'schliessen', testid?: string, taste?: string }
//     { art: 'nicht_herstellbar', grund: string }      echter, nicht leerer Grund
// Vertrag `schreibBefund(anfragen)`: anfragen = { method, url }[] während der Bedienung;
//   null, wenn keine schreibende Anfrage (PUT/POST/PATCH/DELETE) dabei war, sonst ein Befund-Text.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as L from '../../../e2e/elementliste_abgleich_logik.ts';

const FRONTEND = join(fileURLToPath(new URL('.', import.meta.url)), '..', '..', '..');
const DOCS = join(FRONTEND, '..', 'docs', 'context', 'einstellungen_neu');
const LISTE: L.ListenElement[] = JSON.parse(readFileSync(join(DOCS, 'elementliste.json'), 'utf8')).elemente;
const BESITZER_TEXT = readFileSync(join(DOCS, 'elementliste_besitzer.json'), 'utf8');

type Schritt = { aktion: string; testid?: string; taste?: string };
type PlanErgebnis = { art: 'ohne_bedienung' } | { art: 'plan'; schritte: Schritt[] } | { art: 'nicht_herstellbar'; grund: string };
type Lage = { ctx: string; briefing: string[]; vorlagen: string[]; aktiveVorlage: string };

function plan(abschnitt: string, lage: Lage): PlanErgebnis {
	const f = (L as Record<string, unknown>).bedienPlan;
	assert.equal(typeof f, 'function', 'bedienPlan fehlt in elementliste_abgleich_logik.ts');
	return (f as (a: string, l: Lage) => PlanErgebnis)(abschnitt, lage);
}
function befund(anfragen: { method: string; url: string }[]): string | null {
	const f = (L as Record<string, unknown>).schreibBefund;
	assert.equal(typeof f, 'function', 'schreibBefund fehlt in elementliste_abgleich_logik.ts');
	return (f as (a: { method: string; url: string }[]) => string | null)(anfragen);
}

const WETTER = LISTE.filter((e) => e.reiter === 'wetter');
const ALLE_METRIKEN = [...new Set(WETTER.map((e) => e.abschnitt).filter((a) => a.startsWith('grenzen-')).map((a) => a.slice('grenzen-'.length)))];
const lage = (ctx: string, extra: Partial<Lage> = {}): Lage => ({ ctx, briefing: ALLE_METRIKEN, vorlagen: ['standard', 'alpin'], aktiveVorlage: 'standard', ...extra });
const aktionen = (p: PlanErgebnis) => (p.art === 'plan' ? p.schritte.map((s) => s.aktion) : []);
const istPlan = (p: PlanErgebnis): p is { art: 'plan'; schritte: Schritt[] } => p.art === 'plan';
const ERLAUBT = new Set(['klick', 'lesen', 'schliessen']);

describe('#2966 AC-6: bedienPlan — Grenzen-Dialog je Metrik', () => {
	for (const ctx of ['trip', 'orte']) {
		test(`${ctx}: grenzen-wind mit Wind im Briefing ⇒ klick (Ändern) · lesen · schliessen (Fertig)`, () => {
			const p = plan('grenzen-wind', lage(ctx));
			assert.ok(istPlan(p), `erwartet Plan, bekam ${JSON.stringify(p)}`);
			assert.deepEqual(aktionen(p), ['klick', 'lesen', 'schliessen']);
			assert.equal(p.schritte[0].testid, 'wetter-grenzen-aendern-wind');
			assert.equal(p.schritte[2].testid, 'wetter-grenzen-aendern-wind', 'schließen über denselben Knopf („Fertig“)');
		});
	}
	test('Metrik nicht im Briefing des Prüf-Datensatzes ⇒ nicht_herstellbar mit echtem Grund (Metrik-ID genannt)', () => {
		const p = plan('grenzen-uv_index', lage('trip', { briefing: ['wind', 'gust'] }));
		assert.equal(p.art, 'nicht_herstellbar');
		const grund = (p as { grund: string }).grund;
		assert.ok(grund.trim().length > 0, 'Grund ist leer');
		assert.match(grund, /uv_index/);
		assert.match(grund, /nicht im Briefing/);
	});
	test('der Plan hängt an der Metrik: grenzen-thunder öffnet thunder, nicht wind', () => {
		const p = plan('grenzen-thunder', lage('orte'));
		assert.ok(istPlan(p));
		assert.equal(p.schritte[0].testid, 'wetter-grenzen-aendern-thunder');
	});
});

describe('#2966 AC-6: bedienPlan — Vorlage-Dialoge (nichts wird übernommen oder gespeichert)', () => {
	test('vorlage-auswahl ⇒ Picker öffnen, lesen, schließen; keine Option geklickt', () => {
		const p = plan('vorlage-auswahl', lage('trip'));
		assert.ok(istPlan(p), JSON.stringify(p));
		assert.deepEqual(aktionen(p), ['klick', 'lesen', 'schliessen']);
		assert.equal(p.schritte[0].testid, 'wetter-vorlage-picker');
		assert.ok(!p.schritte.some((s) => /wetter-vorlage-option-|wetter-vorlage-eigene-/.test(s.testid ?? '')), 'Auswahl darf keine Vorlage anklicken');
	});
	test('vorlage-bestaetigung ⇒ Picker, eine ANDERE Systemvorlage, lesen, Abbrechen; nie Übernehmen', () => {
		const p = plan('vorlage-bestaetigung', lage('orte'));
		assert.ok(istPlan(p), JSON.stringify(p));
		assert.deepEqual(aktionen(p), ['klick', 'klick', 'lesen', 'schliessen']);
		assert.equal(p.schritte[0].testid, 'wetter-vorlage-picker');
		assert.equal(p.schritte[1].testid, 'wetter-vorlage-option-alpin', 'muss eine nicht aktive Systemvorlage wählen');
		assert.equal(p.schritte[3].testid, 'wetter-vorlage-wechsel-abbrechen');
		assert.ok(!p.schritte.some((s) => s.testid === 'wetter-vorlage-wechsel-uebernehmen'), 'Übernehmen ist verboten');
	});
	test('vorlage-bestaetigung ohne andere Systemvorlage ⇒ nicht_herstellbar mit Grund', () => {
		const p = plan('vorlage-bestaetigung', lage('trip', { vorlagen: ['standard'] }));
		assert.equal(p.art, 'nicht_herstellbar');
		assert.ok((p as { grund: string }).grund.trim().length > 0);
	});
	test('vorlage-speichern ⇒ „Als eigene Vorlage speichern“ öffnen, lesen, schließen; nie absenden', () => {
		const p = plan('vorlage-speichern', lage('trip'));
		assert.ok(istPlan(p), JSON.stringify(p));
		assert.deepEqual(aktionen(p), ['klick', 'lesen', 'schliessen']);
		assert.equal(p.schritte[0].testid, 'wetter-vorlage-als-eigene');
		assert.ok(!p.schritte.some((s) => s.testid === 'save-preset-submit'), 'Speichern-Dialog darf hier nicht abgesendet werden');
	});
	test('vorlage-speichern-fehler ⇒ öffnen, LEER absenden, lesen, schließen; kein Namensfeld befüllt', () => {
		const p = plan('vorlage-speichern-fehler', lage('orte'));
		assert.ok(istPlan(p), JSON.stringify(p));
		assert.deepEqual(aktionen(p), ['klick', 'klick', 'lesen', 'schliessen']);
		assert.equal(p.schritte[0].testid, 'wetter-vorlage-als-eigene');
		assert.equal(p.schritte[1].testid, 'save-preset-submit');
		assert.ok(p.schritte.every((s) => ERLAUBT.has(s.aktion)), 'nur klick/lesen/schliessen, kein Eintippen');
	});
});

describe('#2966 AC-6: bedienPlan — nie still übergangen', () => {
	test('Abschnitte ohne Bedienung (Kopf, laden, warnung, metriken) ⇒ ohne_bedienung', () => {
		for (const a of ['abschnittskopf', 'laden', 'warnung', 'metriken', 'vorlage']) {
			assert.deepEqual(plan(a, lage('trip')), { art: 'ohne_bedienung' }, a);
		}
	});
	test('unbekannter Script-Abschnitt ⇒ nicht_herstellbar mit Grund, nie ohne_bedienung', () => {
		for (const a of ['kebab-etwas', 'test-menue', 'vorlage-speichern-unbekannt', 'grenzen-']) {
			const p = plan(a, lage('trip'));
			assert.equal(p.art, 'nicht_herstellbar', `${a}: ${JSON.stringify(p)}`);
			assert.ok((p as { grund: string }).grund.trim().length > 0, `${a}: Grund leer`);
		}
	});
	test('jeder Abschnitt der Elementliste: Plan mit genau einem „lesen“, ohne_bedienung nur außerhalb SCRIPT_ABSCHNITT, sonst Grund', () => {
		const paare = [...new Set(LISTE.map((e) => `${e.ctx}\u0000${e.abschnitt}`))].map((s) => s.split('\u0000'));
		for (const [ctx, a] of paare) {
			const p = plan(a, lage(ctx));
			if (p.art === 'plan') {
				assert.equal(aktionen(p).filter((x) => x === 'lesen').length, 1, `${ctx}/${a}: genau ein Lese-Schritt`);
				assert.ok(p.schritte.every((s) => ERLAUBT.has(s.aktion)), `${ctx}/${a}: unbekannte Aktion`);
				assert.ok(p.schritte.filter((s) => s.aktion !== 'lesen').every((s) => (s.testid ?? s.taste ?? '').length > 0), `${ctx}/${a}: Schritt ohne Ziel`);
			} else if (p.art === 'ohne_bedienung') {
				assert.ok(!L.SCRIPT_ABSCHNITT.test(a), `${ctx}/${a}: Script-Abschnitt still ohne Bedienung`);
			} else {
				assert.ok(p.grund.trim().length > 0, `${ctx}/${a}: Grund leer`);
			}
		}
	});
	test('mit allen Metriken im Briefing ist jeder Wetter-Script-Abschnitt herstellbar (Plan)', () => {
		const script = [...new Set(WETTER.filter((e) => L.SCRIPT_ABSCHNITT.test(e.abschnitt)).map((e) => `${e.ctx}\u0000${e.abschnitt}`))].map((s) => s.split('\u0000'));
		assert.ok(script.length >= 25, `zu wenige Script-Abschnitte im Reiter Wetter: ${script.length}`);
		for (const [ctx, a] of script) assert.equal(plan(a, lage(ctx)).art, 'plan', `${ctx}/${a}`);
	});
});

describe('#2966 AC-7: Schreib-Tripwire', () => {
	test('nur lesende Anfragen ⇒ kein Befund', () => {
		assert.equal(befund([]), null);
		assert.equal(befund([{ method: 'GET', url: '/api/metrics' }, { method: 'HEAD', url: '/api/x' }, { method: 'OPTIONS', url: '/api/y' }]), null);
	});
	for (const method of ['PUT', 'POST', 'PATCH', 'DELETE', 'post']) {
		test(`${method} während der Bedienung ⇒ Befund nennt Methode und Pfad`, () => {
			const b = befund([{ method: 'GET', url: '/api/metrics' }, { method, url: '/api/metric-presets' }]);
			assert.ok(b && b.trim().length > 0, 'kein Befund');
			assert.match(b!, new RegExp(method, 'i'));
			assert.match(b!, /\/api\/metric-presets/);
		});
	}
});

describe('#2966 AC-10: Besitzer-Einträge #2966 abgeräumt, Restabweichungen neu zugeordnet', () => {
	test('elementliste_besitzer.json ist gültig und enthält keinen Verweis #2966 mehr', () => {
		const besitzer = L.leseBesitzer(BESITZER_TEXT, LISTE);
		const rest = besitzer.filter((b) => b.verweis.trim() === '#2966');
		assert.deepEqual(rest.map((b) => ('abschnitt' in b ? `${b.ctx}/${b.abschnitt}` : b.art)), [], 'Besitzer #2966 noch vorhanden');
	});
});
