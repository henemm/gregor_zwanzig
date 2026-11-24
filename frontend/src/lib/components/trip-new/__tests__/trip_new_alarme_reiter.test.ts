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
import { pathToFileURL } from 'node:url';
import { renderTripNew, countTestid, outerHtml, FRONTEND } from './tripNewSsr.ts';
import { initialCreateTripAlarmState } from '../tripNewLogic.ts';
import { kanalStatus, standAusTrip } from '../../shared/zustellung-tab/zustellungModell.ts';

// #3332 (D1 von #3307, AC-9): im Trip-Anlegen stehen Alarm-Kanaele (inkl. Premium-SMS) mit Dringlichkeit in der
// Kanal-Tabelle des Reiters Zustellung, nicht mehr im Reiter Alarme. Die Tabelle erscheint erst nach dem
// Profil-Abruf (onMount, im SSR nie) — gemessen wird sie deshalb als ECHTE KanalTabelle im Server-Render,
// gespeist mit dem Anlege-Startstand (Eintrittstrip wie im Editor: Alarm-Kanaele aus dem Neuanlage-Alarmzustand;
// dass der Editor genau diesen Stand liefert, belegt trip_anlegen_zustellung_verdrahtung_3332, „Startstand").
const { render } = await import('svelte/server');
const KanalTabelle = (await import(pathToFileURL(join(FRONTEND, 'src/lib/components/organisms/zustellung-tab/KanalTabelle.svelte')).href)).default;
function anlegeKanalTabelle(): string {
	const a = initialCreateTripAlarmState();
	const stand = standAusTrip({ id: '__new__', name: 'x', stages: [], alert_channels: a.channels, alert_channel_thresholds: a.channelThresholds } as never);
	const status = kanalStatus({ mail_to: 'a@example.com', email_verified: true, telegram_chat_id: 'c', premium_sms_allowed: true } as never);
	return render(KanalTabelle, { props: { stand, status, onaendern: () => {} } }).body;
}

describe('AC-1: Mount-Ersetzung — AlarmeTab statt AlertRulesEditor (schließt #2229)', () => {
	test('Desktop, Tab "alarme": genau 1 alarme-tab, 0 alert-rules-editor, 1 Premium-SMS-Kanalzeile', () => {
		const html = renderTripNew({ activeTab: 'alarme', isMobileViewport: false });
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
		// #3332 AC-9: die Premium-SMS-Kanalzeile hat genau eine Bedienstelle — die Kanal-Tabelle des Reiters
		// Zustellung (gemountet im selben Schritt), nicht der Reiter Alarme.
		assert.equal(countTestid(html, 'alert-channel-toggle-premium_sms'), 0, '#3332 AC-9 FAIL: zweite Bedienstelle der Premium-SMS-Alarmwahl im Reiter Alarme.');
		assert.equal(countTestid(html, 'zustellung-tab'), 1, '#3332 AC-1 FAIL: Reiter Zustellung (Träger der Kanal-Tabelle) fehlt.');
		assert.equal(countTestid(anlegeKanalTabelle(), 'zustellung-kanal-premium_sms'), 1, 'AC-1 FAIL: keine Premium-SMS-Kanalzeile beim Anlegen (Issue #2229).');
	});

	test('Mobile, Tab "alarme": genau 1 alarme-tab, 0 alert-rules-editor, 1 Premium-SMS-Kanalzeile', () => {
		const html = renderTripNew({ activeTab: 'alarme', isMobileViewport: true });
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
		assert.equal(countTestid(html, 'alert-channel-toggle-premium_sms'), 0, '#3332 AC-9 FAIL (Mobile): zweite Bedienstelle der Premium-SMS-Alarmwahl im Reiter Alarme.');
		assert.equal(countTestid(html, 'zustellung-tab'), 1, '#3332 AC-1 FAIL (Mobile): Reiter Zustellung (Träger der Kanal-Tabelle) fehlt.');
	});
});

describe('AC-3: E-Mail-Kanal zeigt den Neuanlage-Default (an, Issue #2518)', () => {
	// #3332 (AC-9): der Alarm-Schalter E-Mail steht im Trip-Anlegen in der Kanal-Tabelle des Reiters Zustellung.
	test('zustellung-kanal-email-alarm ist im CHECKED-Zustand (aria-checked="true", Neuanlage-Default #2518)', () => {
		const email = outerHtml(anlegeKanalTabelle(), 'zustellung-kanal-email-alarm');
		assert.match(
			email,
			/aria-checked="true"/,
			'AC-3 FAIL: der E-Mail-Alarm-Schalter ist nicht gecheckt — Neuanlage-Default #2518 (Alarm-Kanaele aus dem ' +
				'Neuanlage-Alarmzustand, nicht aus den Briefing-Kanaelen).'
		);
		assert.match(outerHtml(anlegeKanalTabelle(), 'zustellung-kanal-telegram-alarm'), /aria-checked="true"/, 'AC-3 FAIL: Telegram-Alarm nicht an (Neuanlage-Default #2518)');
	});
});

describe('AC-6: AlarmeTab bleibt dauerhaft gemountet (Muster WeatherMetricsTab, isMobileViewport-Gate)', () => {
	const kombinationen: { activeTab: string; isMobileViewport: boolean }[] = [
		{ activeTab: 'alarme', isMobileViewport: false },
		{ activeTab: 'alarme', isMobileViewport: true },
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

	// Issue #2277 S3 (feat_2277_s3, AC-7) ersetzt S1-AC-7 „AlertRulesEditor.svelte
	// bleibt bestehen": der tote Strang wird jetzt geloescht.
	test('AlertRulesEditor.svelte ist gelöscht (#2277 S3 ersetzt S1-AC-7)', () => {
		assert.throws(
			() =>
				readFileSync(
					join(FRONTEND, 'src/lib/components/alert-rules-editor/AlertRulesEditor.svelte'),
					'utf-8'
				),
			'AC-7 (S3) FAIL: AlertRulesEditor.svelte existiert noch — der tote Strang muss weg.'
		);
	});
});
