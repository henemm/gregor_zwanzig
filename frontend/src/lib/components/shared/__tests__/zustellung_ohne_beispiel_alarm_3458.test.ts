// TDD RED — Issue #3458 (S5b-2, Scheibe #2797): Alarm-Vorschau-Oberfläche entfernen.
// Spec docs/specs/modules/fix_3458_alarm_vorschau_entfernen.md — AC-1, AC-2, AC-3, AC-4, AC-7 (Kern-Schicht).
//
// Die Vorschau (Abschnitt „Beispiel-Alarm“ am Ende des Reiters Zustellung, Abschnitt „Beispiel-Warnung“
// im Reiter Alarme, Knopf „Vorschau laden“) ist durch den Test-Alarm im Menü „Test schicken ▾“ (#3441)
// ersetzt (PO-Entscheidung A14). Gemessen am ECHTEN serverseitigen Render (svelte/server) von
//   shared/zustellung-tab/ZustellungTab.svelte (Hub, Trip und Orte),
//   trip-new/TripNewEditor.svelte und compare-new/CompareNewEditor.svelte (Anlegen, Reiter Zustellung),
//   shared/AlarmeTab.svelte (Anlegen, beide Kontexte),
// an der Abschnittsliste alarmeTabSections, am Katalog DE/EN (Daten) und an den Exporten von api.ts
// (dynamischer Import, kein Dateitext). Kein Mock.
//
// RED heute: BeispielAlarm/AlertPreviewCard sind eingebunden, 'sample' wird angehängt, Katalog trägt
// alarme.beispiel_warnung und alarme.vorschau.*, api.ts exportiert alarmVorschau. Grün bleibt (Regressions-
// schutz, AC-4): der Eintrag Test-Alarm im Menümodell.
//
//   cd frontend && npm test -- src/lib/components/shared/__tests__/zustellung_ohne_beispiel_alarm_3458.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { FRONTEND, lade, renderKomponente, renderTrip, renderVergleichNeu, innen, sichtbarerText, tagsMitTestid } from './infoboxSsr.ts';
import { alarmeTabSections } from '../alarme-tab/alarmeTabSections.ts';
import { alarmePropsAus } from '../../compare/alarmePropsAus.ts';
import * as modell from '../../molecules/testSchickenModell.ts';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = any;

const TRIP = { id: 't-3458', name: 'SSR-3458', stages: [], alert_rules: [], report_config: undefined };
const PRESET = {
	id: 'cp-3458', name: 'SSR-3458-Orte', location_ids: ['loc-a', 'loc-b'],
	alert_channels: { email: true, telegram: true, sms: false, premium_sms: false }
};
const TRIP_ANLEGEN = { name: 'Anlegen-3458', startDate: '2026-07-01', stageNames: ['E1'], wtVisited: true, zuVisited: true };
const VERGLEICH_ANLEGEN = { metrikenVisited: true, zustellungVisited: true };

const ohneKommentare = (h: string) => h.replace(/<!--[\s\S]*?-->/g, '');
const anzahl = (h: string, merkmal: string) => h.split(merkmal).length - 1;

/** Zusicherung AC-1/AC-2: im Reiter-HTML keine Spur der Vorschau. */
function keineVorschau(reiterHtml: string, wo: string): void {
	assert.equal(anzahl(reiterHtml, 'data-abschnitt="beispiel-alarm"'), 0, `${wo}: Abschnitt „beispiel-alarm“ noch da`);
	assert.equal(anzahl(reiterHtml, 'data-testid="zustellung-beispiel-alarm"'), 0, `${wo}: zustellung-beispiel-alarm noch da`);
	assert.equal(anzahl(reiterHtml, 'data-testid="alert-preview-card"'), 0, `${wo}: Vorschau-Karte alert-preview-card noch da`);
	assert.equal(anzahl(reiterHtml, 'data-testid="alert-preview-load-btn"'), 0, `${wo}: Knopf alert-preview-load-btn noch da`);
	const text = sichtbarerText(reiterHtml);
	assert.ok(!text.includes('Vorschau laden'), `${wo}: Text „Vorschau laden“ noch sichtbar`);
	assert.ok(!text.includes('Beispiel-Warnung'), `${wo}: Text „Beispiel-Warnung“ noch sichtbar`);
}

describe('#3458 AC-1 — Reiter Zustellung im Hub endet bei Stille Stunden, keine Vorschau', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`${context}: kein Beispiel-Alarm, keine Vorschau-Karte, kein „Vorschau laden“`, async () => {
			const ZustellungTab = await lade('shared/zustellung-tab/ZustellungTab.svelte');
			const props = context === 'route' ? { context, trip: TRIP } : { context, preset: PRESET };
			const h = ohneKommentare(renderKomponente(ZustellungTab, props));
			assert.equal(anzahl(h, 'data-testid="zustellung-tab"'), 1, 'Messaufbau: Reiter Zustellung nicht gerendert');
			keineVorschau(h, `Hub ${context}`);
			const abschnitte = [...innen(h, 'zustellung-tab').matchAll(/data-abschnitt="([^"]+)"/g)].map((m) => m[1]);
			assert.equal(abschnitte.at(-1), 'stille-stunden', `letzter Abschnitt ist ${abschnitte.at(-1)}`);
		});
	}
});

describe('#3458 AC-2 — Reiter Zustellung im Anlegen ohne Vorschau', () => {
	for (const mobil of [false, true]) {
		test(`Trip-Anlegen (${mobil ? 'Mobil' : 'Desktop'})`, async () => {
			const html = ohneKommentare(await renderTrip({ ...TRIP_ANLEGEN, activeTab: 'zustellung', isMobileViewport: mobil }));
			assert.equal(tagsMitTestid(html, 'zustellung-tab').length, 1, 'Messaufbau: Reiter Zustellung nicht im Trip-Anlegen');
			keineVorschau(innen(html, 'zustellung-tab'), 'Trip-Anlegen');
		});
		test(`Orts-Vergleich-Anlegen (${mobil ? 'Mobil' : 'Desktop'})`, async () => {
			const html = ohneKommentare(await renderVergleichNeu({ ...VERGLEICH_ANLEGEN, activeTab: 'zustellung', isMobileViewport: mobil }));
			assert.equal(tagsMitTestid(html, 'zustellung-tab').length, 1, 'Messaufbau: Reiter Zustellung nicht im Vergleich-Anlegen');
			keineVorschau(innen(html, 'zustellung-tab'), 'Vergleich-Anlegen');
		});
	}
});

describe('#3458 AC-3 — Reiter Alarme ohne Abschnitt „Beispiel-Warnung“', () => {
	const ERWARTET = {
		route: ['official-warnings', 'metric-levels', 'channels', 'cooldown', 'quiet-hours'],
		vergleich: ['official-warnings', 'radar', 'metric-levels', 'channels', 'cooldown', 'quiet-hours']
	} as const;
	const OHNE_ZUSTELLUNG = { route: ['official-warnings', 'metric-levels'], vergleich: ['official-warnings', 'radar', 'metric-levels'] } as const;

	for (const context of ['route', 'vergleich'] as const) {
		test(`${context}: alarmeTabSections ohne 'sample', übrige Abschnitte in bisheriger Reihenfolge`, () => {
			assert.deepEqual(alarmeTabSections(context), [...ERWARTET[context]]);
			assert.deepEqual(alarmeTabSections(context, true), [...OHNE_ZUSTELLUNG[context]]);
		});

		test(`${context} (createMode): gerenderter Reiter ohne Beispiel-Warnung und Vorschau-Karte`, async () => {
			const AlarmeTab = await lade('shared/AlarmeTab.svelte');
			const wiz: Json = {
				officialWarningsEnabled: true, radarAlertEnabled: false, activeMetricKeys: null, metricAlertLevels: {},
				sendTelegram: true, sendSms: false, sendPremiumSms: false, channelThresholds: {}, telegramStyle: 'rich',
				alertCooldownMinutes: 30, alertQuietFrom: '22:00', alertQuietTo: '07:00'
			};
			const props = context === 'route'
				? { context, trip: { ...TRIP, id: '__new__', display_config: {} }, createMode: true, activeMetrics: [], metricLevels: {}, profileOverride: { premium_sms_allowed: true } }
				: { context, ...alarmePropsAus(wiz), createMode: true, catalog: [], profileOverride: { premium_sms_allowed: true } };
			const h = ohneKommentare(renderKomponente(AlarmeTab, props));
			const ids = [...h.matchAll(/data-testid="alarme-section-([a-z-]+)"/g)].map((m) => m[1]);
			assert.ok(ids.includes('official-warnings') && ids.includes('metric-levels'), `Messaufbau: Abschnitte fehlen ${JSON.stringify(ids)}`);
			assert.ok(!ids.includes('sample'), `Abschnitt „sample“ noch gerendert: ${JSON.stringify(ids)}`);
			assert.equal(anzahl(h, 'data-testid="alert-preview-card"'), 0, 'Vorschau-Karte im Reiter Alarme');
			assert.ok(!sichtbarerText(h).includes('Beispiel-Warnung'), 'Text „Beispiel-Warnung“ im Reiter Alarme');
		});
	}
});

describe('#3458 AC-7 — Katalog DE/EN ohne Vorschau-Schlüssel', () => {
	for (const sprache of ['de', 'en'] as const) {
		test(`${sprache}: weder alarme.beispiel_warnung noch alarme.vorschau.*`, () => {
			const ordner = path.join(FRONTEND, 'src/lib/i18n/messages', sprache);
			const dateien = readdirSync(ordner).filter((d) => d.endsWith('.json'));
			assert.ok(dateien.length > 0, `Messaufbau: keine Katalogdateien in ${ordner}`);
			const verwaist: string[] = [];
			for (const d of dateien) {
				const schluessel = Object.keys(JSON.parse(readFileSync(path.join(ordner, d), 'utf8')));
				for (const k of schluessel) {
					if (k === 'alarme.beispiel_warnung' || k.startsWith('alarme.vorschau.')) verwaist.push(`${d}:${k}`);
				}
			}
			assert.deepEqual(verwaist, [], `verwaiste Vorschau-Schlüssel (${sprache}): ${verwaist.length}`);
		});
	}
});

describe('#3458 — api.ts ohne Vorschau-Aufruf', () => {
	test('kein Export alarmVorschau, langlaeufer ohne alarmVorschau', async () => {
		const api: Json = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/api.ts')).href);
		assert.ok(api.langlaeufer && typeof api.langlaeufer === 'object', 'Messaufbau: langlaeufer fehlt');
		assert.equal('alarmVorschau' in api, false, 'api.ts exportiert noch alarmVorschau');
		assert.equal('alarmVorschau' in api.langlaeufer, false, 'langlaeufer.alarmVorschau existiert noch');
	});
});

describe('#3458 AC-4 — Ersatzweg: Test-Alarm im Menü „Test schicken ▾“ bleibt', () => {
	const PROFIL = { tier: 'premium', mail_to: 'wanderer@example.com', email_verified: true, telegram_chat_id: '42' };
	for (const context of ['route', 'vergleich'] as const) {
		test(`${context}: Eintrag test-alarm vorhanden und bedienbar`, () => {
			const m = (modell as Json).testMenueModell(PROFIL, context);
			const e = m.erweiterungen.find((x: Json) => x.id === 'test-alarm');
			assert.ok(e, `kein Eintrag test-alarm: ${JSON.stringify(m.erweiterungen)}`);
			assert.equal(e.text, 'Test-Alarm');
			assert.equal(e.bedienbar, true);
		});
	}
});
