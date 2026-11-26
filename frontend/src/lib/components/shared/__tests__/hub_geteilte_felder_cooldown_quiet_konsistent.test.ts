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
import { buendelAus, fetchMitschnitt, vergleichEditor, zustellungsGeste } from './compareNeuEditorPruefstand.ts';
import { derivedNeu } from './standardwerteEditorPruefstand.ts';

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

// #3384 S4: Block „AC-14: Cooldown/Ruhezeit — Versand und Alarme zeigen denselben Wert“ (Adapter-Ebene
// über versandPropsAus) mit der Waise versandPropsAus.ts gelöscht; die Zusicherung „ein Feldsatz für
// beide Reiter“ misst der Block unten am echten Editor, in beiden Richtungen: Zustellung → Alarme und
// (#3385 AC-4, Finding F002 aus #3384) Alarme → Zustellung, dort nur auf dem Schreibweg zum Speichern
// (Prop `preset` des Reiters Zustellung und POST der Aktivierung).

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

	// #3385 AC-4 (F002 aus #3384): Rückrichtung. Der Reiter Alarme schreibt über die Rückrufe seines
	// Bündels; gemessen wird nur, was der Editor dem Reiter Zustellung übergibt und was er speichert.
	const anlegen = () =>
		vergleichEditor({
			stateOverride: { activeTab: 'zustellung', isMobileViewport: false, metrikenVisited: true, zustellungVisited: true, name: 'AC-4', pickedIds: ['loc-a', 'loc-b'] }
		});
	type Editor = Awaited<ReturnType<typeof anlegen>>;
	/** Geste im Reiter Alarme über den echten Rückruf seines Bündels; danach rechnet der Prüfstand die
	 *  `$derived`-Werte neu (wie Svelte nach der Zustandsänderung), dann wird gemessen. */
	const cooldown = (e: Editor, m: number | undefined) => {
		(buendelAus(e, 'AlarmeTab').onCooldownChange as (m: number | undefined) => void)(m);
		derivedNeu(e);
	};
	const stille = (e: Editor, von: string | undefined, bis: string | undefined) => {
		(buendelAus(e, 'AlarmeTab').onQuietHoursChange as (v?: string, b?: string) => void)(von, bis);
		derivedNeu(e);
	};
	const postKoerper = async (e: Editor) => {
		await e.u.handleActivate();
		const posts = netz.presetPosts();
		assert.equal(posts.length, 1, 'genau ein POST der Aktivierung erwartet');
		return posts[0].koerper as Record<string, unknown>;
	};

	test('#3385 AC-4: Cooldown 60 aus dem Reiter Alarme steht im Prop preset des Reiters Zustellung und im POST', async () => {
		const e = await anlegen();
		cooldown(e, 60);
		assert.equal(buendelAus(e, 'ZustellungTab', 'preset').alert_cooldown_minutes, 60, 'Prop preset trägt den Cooldown aus dem Reiter Alarme nicht');
		assert.equal((await postKoerper(e)).alert_cooldown_minutes, 60);
	});

	test('#3385 AC-4: Cooldown 60 und danach gelöscht: weder Prop preset noch POST enthalten 60', async () => {
		const e = await anlegen();
		cooldown(e, 60);
		assert.equal(buendelAus(e, 'ZustellungTab', 'preset').alert_cooldown_minutes, 60);
		cooldown(e, undefined);
		assert.notEqual(buendelAus(e, 'ZustellungTab', 'preset').alert_cooldown_minutes, 60, 'gelöschter Cooldown steht noch im Prop preset');
		assert.notEqual((await postKoerper(e)).alert_cooldown_minutes, 60, 'gelöschter Cooldown steht noch im POST');
	});

	test('#3385 AC-4: Stille Stunden 22:00–06:00 aus dem Reiter Alarme stehen im Prop preset und im POST', async () => {
		const e = await anlegen();
		stille(e, '22:00', '06:00');
		const p = buendelAus(e, 'ZustellungTab', 'preset');
		assert.equal(p.alert_quiet_from, '22:00', 'Prop preset trägt die Stillen Stunden aus dem Reiter Alarme nicht');
		assert.equal(p.alert_quiet_to, '06:00');
		const b = await postKoerper(e);
		assert.equal(b.alert_quiet_from, '22:00');
		assert.equal(b.alert_quiet_to, '06:00');
	});

	test('#3385 AC-4: Stille Stunden gesetzt und danach gelöscht: weder Prop preset noch POST enthalten sie', async () => {
		const e = await anlegen();
		stille(e, '22:00', '06:00');
		assert.equal(buendelAus(e, 'ZustellungTab', 'preset').alert_quiet_from, '22:00');
		stille(e, undefined, undefined);
		const p = buendelAus(e, 'ZustellungTab', 'preset');
		assert.notEqual(p.alert_quiet_from, '22:00', 'gelöschte Stille Stunden stehen noch im Prop preset');
		assert.notEqual(p.alert_quiet_to, '06:00');
		const b = await postKoerper(e);
		assert.notEqual(b.alert_quiet_from, '22:00', 'gelöschte Stille Stunden stehen noch im POST');
		assert.notEqual(b.alert_quiet_to, '06:00');
	});
});
