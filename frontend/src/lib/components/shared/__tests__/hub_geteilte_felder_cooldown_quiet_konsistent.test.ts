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

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';
import { versandPropsAus } from '../../compare/versandPropsAus.ts';
import { alarmePropsAus } from '../../compare/alarmePropsAus.ts';
import { neuerFeldsatz } from './compareFeldsatzPruefstand.ts';
import type { Knoten } from './svelteInstanzPruefstand.ts';

const HUB = join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'compare', 'CompareTabs.svelte');

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

describe('AC-14 (Wirkort Hub): Versand- und Alarme-Adapter bekommen DENSELBEN Feldsatz', () => {
	test('CompareTabs übergibt versandPropsAus(…) und alarmePropsAus(…) denselben Bezeichner', () => {
		const quelle = readFileSync(HUB, 'utf-8');
		const ast: Knoten = parse(quelle, { modern: true });
		const argumente: Record<string, Set<string>> = { versandPropsAus: new Set(), alarmePropsAus: new Set() };
		(function lauf(n: unknown): void {
			if (n === null || typeof n !== 'object') return;
			if (Array.isArray(n)) return n.forEach(lauf);
			const k = n as Knoten;
			if (k.type === 'CallExpression' && k.callee?.type === 'Identifier' && k.callee.name in argumente) {
				const a = k.arguments?.[0];
				argumente[k.callee.name].add(a?.type === 'Identifier' ? a.name : quelle.slice(a?.start, a?.end));
			}
			for (const key of Object.keys(k)) if (key !== 'parent' && key !== 'loc') lauf(k[key]);
		})(ast.fragment);
		assert.equal(argumente.versandPropsAus.size, 1, `Messaufbau: versandPropsAus-Aufrufe im Hub: ${[...argumente.versandPropsAus]}`);
		assert.equal(argumente.alarmePropsAus.size, 1, `Messaufbau: alarmePropsAus-Aufrufe im Hub: ${[...argumente.alarmePropsAus]}`);
		assert.deepEqual([...argumente.versandPropsAus], [...argumente.alarmePropsAus], 'Versand und Alarme lesen aus verschiedenen Feldsätzen (Variante A\')');
	});
});
