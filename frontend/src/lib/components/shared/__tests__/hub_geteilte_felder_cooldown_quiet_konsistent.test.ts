// TDD RED (Regressionswächter) — Issue #2727 (Epic #2345, DoD-1): compareWizardState ablösen.
// Spec: docs/specs/modules/feat_2727_compare_wizardstate_abloesen.md — AC-14 (Variante A)
//
// Cooldown und Ruhezeiten (`alertCooldownMinutes`, `alertQuietFrom`, `alertQuietTo`) sind im
// Ortsvergleich-Hub sowohl im Versand- als auch im Alarme-Reiter sichtbar. Beide Reiter werden aus
// EINEM Feldsatz versorgt (`versandPropsAus(f)`, `alarmePropsAus(f)`): eine Änderung im einen ist im
// anderen sichtbar, und umgekehrt — sie können nicht auseinanderlaufend gespeichert werden.
//   * Versand → Alarme: der Versand-Organismus schreibt diese drei Felder nur über seine
//     Rollback-Senke `onVersandFeldSetzen` (versandPropsAus.ts, Klasse C).
//   * Alarme → Versand: Gesten-Rückrufe `onCooldownChange` / `onQuietHoursChange`.
// Die Adapter liefern Momentaufnahmen — nach jeder Änderung werden BEIDE neu gelesen.
// Zusätzlich (Wirkort Hub, AST): CompareTabs übergibt `versandPropsAus(…)` und `alarmePropsAus(…)`
// DENSELBEN Bezeichner — sonst (Variante A', je Reiter ein Satz) liefe der Wert auseinander, ohne
// dass der Adapter-Test es sähe.
//
// Warum heute rot: `compareFeldsatzStandard` fehlt (VERTRAG FEHLT). Fachlich Regressionswächter:
// die Adapter sind heute schon konsistent, der Umbau auf den lokalen Feldsatz darf daran nichts ändern.
// Der AST-Test ist heute grün (der Hub nutzt schon ein gemeinsames Objekt) und bleibt Wächter.
//
// Ausführen (aus frontend/):
//   node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/shared/__tests__/hub_geteilte_felder_cooldown_quiet_konsistent.test.ts

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { versandPropsAus } from '../../compare/versandPropsAus.ts';
import { alarmePropsAus } from '../../compare/alarmePropsAus.ts';
import { neuerFeldsatz } from './compareFeldsatzPruefstand.ts';
import { buendelAus, fetchMitschnitt, vergleichEditor, zustellungsGeste } from './compareNeuEditorPruefstand.ts';

// #2795 S3b Teilschritt 1b: im Hub ersetzt der neue Reiter Zustellung (EIN Speicherer fuer
// Briefing und Alarme, Stand direkt aus dem Preset) beide Adapter. #3333 (D2 von #3307): auch im Anlegen
// (CompareNewEditor) steht statt des Versand-Adapters der Reiter Zustellung; er schreibt Cooldown und
// Stille Stunden in DENSELBEN Feldsatz, aus dem der Reiter Alarme liest — dort gilt die Zusicherung
// „ein Feldsatz fuer beide“ weiter, jetzt am echten Editor gemessen.
let netz: ReturnType<typeof fetchMitschnitt>;
beforeEach(() => {
	netz = fetchMitschnitt('cmp-neu');
});
afterEach(() => {
	netz.abbauen();
});

describe('AC-14: Cooldown/Ruhezeit — Versand und Alarme zeigen denselben Wert', () => {
	test('Ausgangslage: beide Reiter zeigen den Standard „nicht gesetzt"', () => {
		const f = neuerFeldsatz();
		assert.equal(versandPropsAus(f).alertCooldownMinutes, undefined);
		assert.equal(alarmePropsAus(f).cooldownMinutes, undefined);
		assert.equal(alarmePropsAus(f).quietFrom, undefined);
	});

	test('Versand → Alarme: Cooldown und Ruhezeit über die Versand-Senke sind im Alarme-Reiter sichtbar', () => {
		const f = neuerFeldsatz();
		const versand = versandPropsAus(f);
		versand.onVersandFeldSetzen('alertCooldownMinutes', 90);
		versand.onVersandFeldSetzen('alertQuietFrom', '22:00');
		versand.onVersandFeldSetzen('alertQuietTo', '06:30');
		const alarme = alarmePropsAus(f);
		assert.equal(alarme.cooldownMinutes, 90);
		assert.equal(alarme.quietFrom, '22:00');
		assert.equal(alarme.quietTo, '06:30');
	});

	test('Alarme → Versand: Gesten im Alarme-Reiter sind im Versand-Reiter sichtbar', () => {
		const f = neuerFeldsatz();
		const alarme = alarmePropsAus(f);
		alarme.onCooldownChange(45);
		alarme.onQuietHoursChange('23:00', '05:00');
		const versand = versandPropsAus(f);
		assert.equal(versand.alertCooldownMinutes, 45);
		assert.equal(versand.alertQuietFrom, '23:00');
		assert.equal(versand.alertQuietTo, '05:00');
	});

	test('Hin und zurück: die letzte Änderung gewinnt in BEIDEN Reitern (kein Auseinanderlaufen)', () => {
		const f = neuerFeldsatz();
		versandPropsAus(f).onVersandFeldSetzen('alertCooldownMinutes', 30);
		alarmePropsAus(f).onCooldownChange(120);
		assert.equal(versandPropsAus(f).alertCooldownMinutes, 120);
		assert.equal(alarmePropsAus(f).cooldownMinutes, 120);
		alarmePropsAus(f).onCooldownChange(undefined);
		assert.equal(versandPropsAus(f).alertCooldownMinutes, undefined, 'Löschen im Alarme-Reiter kommt im Versand nicht an');
	});
});

describe('AC-14 (Wirkort Anlegen, #3333): Reiter Zustellung und Reiter Alarme teilen DENSELBEN Feldsatz', () => {
	test('Cooldown und Stille Stunden aus dem Reiter Zustellung kommen im Buendel des Reiters Alarme und im POST an', async () => {
		const e = await vergleichEditor({
			stateOverride: { activeTab: 'zustellung', isMobileViewport: false, metrikenVisited: true, zustellungVisited: true, name: 'AC-14', pickedIds: ['loc-a', 'loc-b'] }
		});
		zustellungsGeste(e, (st) => ({ ...st, cooldown: 45, stilleAn: true, stilleVon: '23:00', stilleBis: '05:00' }));
		const alarme = buendelAus(e, 'AlarmeTab');
		assert.equal(alarme.cooldownMinutes, 45, 'Reiter Alarme liest einen anderen Feldsatz als der Reiter Zustellung schreibt');
		assert.equal(alarme.quietFrom, '23:00');
		assert.equal(alarme.quietTo, '05:00');
		await e.u.handleActivate();
		const b = netz.presetPosts()[0]?.koerper as Record<string, unknown>;
		assert.equal(b.alert_cooldown_minutes, 45);
		assert.equal(b.alert_quiet_from, '23:00');
		assert.equal(b.alert_quiet_to, '05:00');
	});
});
