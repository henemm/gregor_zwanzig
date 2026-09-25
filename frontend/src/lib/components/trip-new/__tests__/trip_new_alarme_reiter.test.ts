// TDD RED — Issue #2277 Scheibe S1: /trips/new nutzt im Alarme-Reiter den
// geteilten AlarmeTab.svelte (context="route", createMode) statt der
// Alt-Komponente AlertRulesEditor (Regel-Array-Modell, kein Premium-SMS —
// schliesst nebenbei #2229).
//
// Spec: docs/specs/modules/fix_2277_s1_alarme_tab_route.md (AC-1, AC-3, AC-6, AC-7)
//
// Echtes SSR-Rendering der Produktivkomponente ueber die bestehende Harness
// tripNewSsr.ts (Issue #1738) — keine neue Test-Infrastruktur, kein Mock, keine
// Quelltext-Regex fuer die Render-Zusicherungen (AC-1/AC-3/AC-6). AC-7 ist ein
// reiner Abwesenheits-/Strukturwaechter (Spec erlaubt Source-Inspection dafuer
// ausdruecklich).
//
// Ausfuehren:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/trip-new/__tests__/trip_new_alarme_reiter.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { renderTripNew, countTestid, outerHtml, FRONTEND } from './tripNewSsr.ts';

describe('AC-1: Mount-Ersetzung — AlarmeTab statt AlertRulesEditor (schließt #2229)', () => {
	test('Desktop, Tab "alerts": genau 1 alarme-tab, 0 alert-rules-editor, 1 Premium-SMS-Kanalzeile', () => {
		const html = renderTripNew({ activeTab: 'alerts', isMobileViewport: false });
		assert.equal(
			countTestid(html, 'alarme-tab'),
			1,
			'AC-1 FAIL: der Alerts-Tab rendert nicht genau eine AlarmeTab-Instanz.'
		);
		assert.equal(
			countTestid(html, 'alert-rules-editor'),
			0,
			'AC-1 FAIL: der Alt-Mount AlertRulesEditor ist weiterhin im Dokument.'
		);
		assert.equal(
			countTestid(html, 'alert-channel-toggle-premium_sms'),
			1,
			'AC-1 FAIL: keine Premium-SMS-Kanalzeile im Alerts-Tab (Issue #2229).'
		);
	});

	test('Mobile, Tab "alerts": genau 1 alarme-tab, 0 alert-rules-editor, 1 Premium-SMS-Kanalzeile', () => {
		const html = renderTripNew({ activeTab: 'alerts', isMobileViewport: true });
		assert.equal(
			countTestid(html, 'alarme-tab'),
			1,
			'AC-1 FAIL (Mobile): der Alerts-Tab rendert nicht genau eine AlarmeTab-Instanz.'
		);
		assert.equal(
			countTestid(html, 'alert-rules-editor'),
			0,
			'AC-1 FAIL (Mobile): der Alt-Mount AlertRulesEditor ist weiterhin im Dokument.'
		);
		assert.equal(
			countTestid(html, 'alert-channel-toggle-premium_sms'),
			1,
			'AC-1 FAIL (Mobile): keine Premium-SMS-Kanalzeile im Alerts-Tab (Issue #2229).'
		);
	});
});

describe('AC-3: E-Mail-Kanal zeigt den internen route-Default (aus) — kein fest verdrahtetes "true"', () => {
	test('alert-channel-toggle-email ist im UNCHECKED-Zustand (aria-checked="false")', () => {
		const html = renderTripNew({ activeTab: 'alerts', isMobileViewport: false });
		const email = outerHtml(html, 'alert-channel-toggle-email');
		assert.match(
			email,
			/aria-checked="false"/,
			'AC-3 FAIL: der E-Mail-Kanal-Schalter ist gecheckt — das waere der ' +
				'AlarmeTab-interne "vergleich"-Hardcode-Zweig (displayChannelState), der ' +
				'nur greift, wenn TripNewEditor eine Kanal-Wertprop (sendTelegram) setzt.'
		);
	});
});

describe('AC-6: AlarmeTab bleibt dauerhaft gemountet (Muster WeatherMetricsTab, isMobileViewport-Gate)', () => {
	const kombinationen: { activeTab: string; isMobileViewport: boolean }[] = [
		{ activeTab: 'alerts', isMobileViewport: false },
		{ activeTab: 'alerts', isMobileViewport: true },
		{ activeTab: 'route', isMobileViewport: false },
	];

	for (const kombi of kombinationen) {
		test(`${JSON.stringify(kombi)} → genau 1 alarme-tab (nie 0, nie 2)`, () => {
			const html = renderTripNew(kombi);
			assert.equal(
				countTestid(html, 'alarme-tab'),
				1,
				`AC-6 FAIL: ${JSON.stringify(kombi)} liefert nicht genau eine AlarmeTab-Instanz — ` +
					'entweder fehlt das isMobileViewport-Gate (0 bei anderem Tab) oder es existieren ' +
					'zwei Instanzen gleichzeitig (Desktop UND Mobile im DOM).'
			);
		});
	}
});

describe('AC-7 (Strukturwächter): Alt-Modell-Code ist entfernt (kein Verhaltensnachweis)', () => {
	const editorSrc = readFileSync(
		join(FRONTEND, 'src/lib/components/trip-new/TripNewEditor.svelte'),
		'utf-8'
	);
	const logicSrc = readFileSync(join(FRONTEND, 'src/lib/components/trip-new/tripNewLogic.ts'), 'utf-8');

	test('TripNewEditor.svelte referenziert kein alertRules/activeAlertChannels mehr', () => {
		assert.doesNotMatch(
			editorSrc,
			/\balertRules\b/,
			'AC-7 FAIL: TripNewEditor.svelte referenziert weiterhin `alertRules`.'
		);
		assert.doesNotMatch(
			editorSrc,
			/\bactiveAlertChannels\b/,
			'AC-7 FAIL: TripNewEditor.svelte referenziert weiterhin `activeAlertChannels`.'
		);
	});

	test('TripNewEditor.svelte importiert AlertRulesEditor nicht mehr und mountet es nicht mehr', () => {
		// Wortgrenze verhindert einen Teiltreffer in "AlertRulesEditor" selbst nicht
		// (das WÄRE ein Treffer) — wohl aber in unverwandten Bezeichnern. Das ist
		// hier gewollt: der Mount UND der Import muessen beide verschwinden.
		assert.doesNotMatch(
			editorSrc,
			/\bAlertRulesEditor\b/,
			'AC-7 FAIL: TripNewEditor.svelte referenziert weiterhin `AlertRulesEditor` ' +
				'(Import oder Mount).'
		);
	});

	test('tripNewLogic.ts referenziert kein alertRules/AlertRule mehr (Typ-Import inklusive)', () => {
		assert.doesNotMatch(
			logicSrc,
			/\balertRules\b/,
			'AC-7 FAIL: tripNewLogic.ts referenziert weiterhin `alertRules`.'
		);
		assert.doesNotMatch(
			logicSrc,
			/\bAlertRule\b/,
			'AC-7 FAIL: tripNewLogic.ts importiert weiterhin den Typ `AlertRule`.'
		);
	});

	test('AlertRulesEditor.svelte bleibt als Datei bestehen (kein Löschen)', () => {
		assert.doesNotThrow(
			() =>
				readFileSync(
					join(FRONTEND, 'src/lib/components/alert-rules-editor/AlertRulesEditor.svelte'),
					'utf-8'
				),
			'AC-7 FAIL: AlertRulesEditor.svelte wurde gelöscht — die Spec verlangt nur die ' +
				'Entfernung des Mounts, nicht der Komponente (legacy_wizard_removed.test.ts haelt ' +
				'sie auf der keep-Liste).'
		);
	});
});
