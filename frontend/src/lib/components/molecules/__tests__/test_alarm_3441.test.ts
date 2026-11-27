// TDD RED — Issue #3441 (S5b, Scheibe #2797): Eintrag „Test-Alarm“ im Menü „Test schicken ▾“.
// Spec: docs/specs/modules/feat_3441_test_alarm.md — AC-1, AC-7, AC-8, AC-9, AC-14, AC-15, AC-17 (Kern-Schicht).
//
// VERTRAG für den Developer:
//   testSchickenModell.testMenueModell(profil, context, berichtsart?, optionen?: { alarmLaeuft?: boolean })
//       .erweiterungen = [{ id: 'test-alarm', text, untertitel, bedienbar }]   // bedienbar=false, solange er läuft
//   testSchickenModell.testAlarmErgebnis({ ergebnis: { kind, message, code?, sentChannels?, skippedChannels?,
//       failedChannels? }, jetzt: Date }): { ok: boolean; text: string }
//       // „Test-Alarm geschickt: {Kanal} ✓ · {Kanal} übersprungen ({Grund}) · {Kanal} fehlgeschlagen · {hh:mm}“
//       // Reihenfolge der Kanäle wie die Menüzeilen; code keine_alarm_kanaele ⇒ Leer-Text im Fehlerton.
//   subscriptionExec.sendTestAlarm(kind: 'trip' | 'vergleich', id, fetchFn)
//       // POST /api/briefings/{id}/test-alert?kind=route|vergleich; Ergebnis wie SendRunResult plus code,
//       // skippedChannels/failedChannels ({channel, reason}[]) aus der Antwort.
//   HubKopf/TripHeader reichen onErweiterung durch; beide Seiten nutzen sendTestAlarm + testAlarmErgebnis.
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/molecules/__tests__/test_alarm_3441.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { locale } from '../../../i18n/index.ts';
import { ladeSvelte, komponenten, attribut, ids } from '../../shared/__tests__/aktionsmodellAst.ts';
import * as modell from '../testSchickenModell.ts';
import * as exec from '../../shared/subscriptionExec.ts';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = any;
const M = modell as Json;
const E = exec as Json;

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, '../../../..');
const REPO = path.resolve(SRC, '../..');
const KOMP = path.join(SRC, 'lib/components');
const MSG = (l: string) => path.join(SRC, `lib/i18n/messages/${l}/test_schicken.json`);
const katalog = (l: string): Record<string, string> => JSON.parse(readFileSync(MSG(l), 'utf8'));

const TITEL = 'Test-Alarm';
const UNTERTITEL = 'Beispiel-Alarm mit echten Werten an alle Alarm-Kanäle';
const LEER = 'Kein Alarm-Kanal eingerichtet, der Test-Alarm ging nirgends hin.';
const JETZT = new Date(2026, 10, 27, 20, 41);
const PROFIL = { tier: 'premium', mail_to: 'wanderer@example.com', email_verified: true, telegram_chat_id: '42' };

afterEach(() => locale.set('de'));

describe('#3441 AC-1 / AC-17 — Erweiterung „Test-Alarm“ nach „Alle eingerichteten Kanäle“', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`${context}: genau ein Eintrag test-alarm mit Titel und Untertitel, bedienbar`, () => {
			const m = M.testMenueModell(PROFIL, context);
			assert.equal(m.erweiterungen.length, 1, JSON.stringify(m.erweiterungen));
			const [e] = m.erweiterungen;
			assert.deepEqual([e.id, e.text, e.untertitel, e.bedienbar], ['test-alarm', TITEL, UNTERTITEL, true]);
		});
	}
	test('beide Kontexte: dieselbe Erweiterung (ein Baustein)', () => {
		assert.deepEqual(M.testMenueModell(PROFIL, 'route').erweiterungen, M.testMenueModell(PROFIL, 'vergleich').erweiterungen);
	});
	test('während der Test-Alarm läuft, ist der Eintrag gesperrt; Kanalzeilen bleiben unverändert', () => {
		const laeuft = M.testMenueModell(PROFIL, 'route', 'morning', { alarmLaeuft: true });
		assert.equal(laeuft.erweiterungen[0]?.bedienbar, false);
		assert.deepEqual(laeuft.zeilen, M.testMenueModell(PROFIL, 'route').zeilen);
	});
	test('EN: englischer Titel und Untertitel aus dem Katalog', () => {
		locale.set('en');
		const [e] = M.testMenueModell(PROFIL, 'vergleich').erweiterungen;
		assert.ok(e && e.text && e.text !== TITEL && e.untertitel && e.untertitel !== UNTERTITEL, JSON.stringify(e));
	});
});

describe('#3441 AC-7 / AC-8 / AC-9 — Rückmeldung testAlarmErgebnis', () => {
	const erg = (ergebnis: Json) => M.testAlarmErgebnis({ ergebnis, jetzt: JETZT });
	test('alles angekommen: „Test-Alarm geschickt: E-Mail ✓ · Telegram ✓ · 20:41“', () => {
		const r = erg({ kind: 'ok', message: '', sentChannels: ['telegram', 'email'], skippedChannels: [], failedChannels: [] });
		assert.deepEqual(r, { ok: true, text: 'Test-Alarm geschickt: E-Mail ✓ · Telegram ✓ · 20:41' });
	});
	test('übersprungen mit Grund und fehlgeschlagen im Vokabular von #3440', () => {
		const r = erg({
			kind: 'ok', message: '', sentChannels: ['email'],
			skippedChannels: [{ channel: 'telegram', reason: 'Chat fehlt' }],
			failedChannels: [{ channel: 'sms', reason: 'Zustellung fehlgeschlagen' }]
		});
		assert.deepEqual(r, { ok: true, text: 'Test-Alarm geschickt: E-Mail ✓ · Telegram übersprungen (Chat fehlt) · SMS fehlgeschlagen · 20:41' });
	});
	test('leere Kanalmenge: Fehlerton mit dem Leer-Text (DE und EN)', () => {
		const leer = { kind: 'rejected', message: 'Serverdetail', code: 'keine_alarm_kanaele' };
		assert.deepEqual(erg(leer), { ok: false, text: LEER });
		locale.set('en');
		const en = erg(leer);
		assert.equal(en.ok, false);
		assert.ok(en.text && en.text !== LEER && en.text !== 'Serverdetail', en.text);
	});
	test('anderer Fehler (Kontingent, Bremse, Server): bestehender Text aus fehler.versand.* bzw. Server', () => {
		assert.deepEqual(erg({ kind: 'rejected', message: 'Tageskontingent erschöpft.', code: 'kontingent_erschoepft' }),
			{ ok: false, text: 'Tageskontingent erschöpft.' });
	});
});

describe('#3441 AC-2 / AC-9 — sendTestAlarm: ein POST an test-alert, Ergebnis aus der Antwort', () => {
	function server(status: number, body: unknown) {
		const urls: string[] = [];
		const fn = (async (url: Json, init?: Json) => {
			assert.equal(String(init?.method ?? 'GET'), 'POST');
			urls.push(String(url));
			return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
		}) as typeof fetch;
		return { fn, urls };
	}
	for (const [kind, wort] of [['trip', 'route'], ['vergleich', 'vergleich']] as const) {
		test(`${kind}: URL /api/briefings/x/test-alert?kind=${wort}, Kanäle aus der Antwort`, async () => {
			const antwort = { sent_channels: ['email'], skipped_channels: [{ channel: 'sms', reason: 'Tarif' }], failed_channels: [] };
			const { fn, urls } = server(200, antwort);
			const r = await E.sendTestAlarm(kind, 'x', fn);
			assert.equal(urls.length, 1);
			const u = new URL(urls[0], 'http://gz.invalid');
			assert.equal(u.pathname, '/api/briefings/x/test-alert');
			assert.equal(u.searchParams.get('kind'), wort);
			assert.equal(r.kind, 'ok');
			assert.deepEqual([r.sentChannels, r.skippedChannels, r.failedChannels], [['email'], [{ channel: 'sms', reason: 'Tarif' }], []]);
		});
	}
	test('422 keine_alarm_kanaele: code wird mitgeliefert', async () => {
		const { fn } = server(422, { detail: 'Kein Alarm-Kanal.', code: 'keine_alarm_kanaele' });
		const r = await E.sendTestAlarm('trip', 'x', fn);
		assert.deepEqual([r.kind, r.code], ['rejected', 'keine_alarm_kanaele']);
	});
});

describe('#3441 AC-1 — Verdrahtung: onErweiterung bis zum Menü, beide Seiten denselben Weg', () => {
	const HUBKOPF = path.join(KOMP, 'shared/hub-kopf/HubKopf.svelte');
	const TRIPHEADER = path.join(KOMP, 'trip-detail/TripHeader.svelte');
	const TRIP = path.join(SRC, 'routes/trips/[id]/+page.svelte');
	const VERGLEICH = path.join(SRC, 'routes/compare/[id]/+page.svelte');
	for (const [datei, kind] of [[HUBKOPF, 'TestSchickenMenue'], [TRIPHEADER, 'HubKopf'], [TRIP, 'TripHeader'], [VERGLEICH, 'HubKopf']]) {
		test(`${path.relative(SRC, datei)} reicht onErweiterung an ${kind}`, () => {
			const k = komponenten(ladeSvelte(datei), kind);
			assert.equal(k.length, 1, `${kind} nicht genau einmal gebunden`);
			assert.ok(attribut(k[0], 'onErweiterung'), `${kind} ohne onErweiterung`);
		});
	}
	for (const seite of [TRIP, VERGLEICH]) {
		test(`${path.relative(SRC, seite)} ruft sendTestAlarm und baut die Rückmeldung mit testAlarmErgebnis`, () => {
			const namen = ids(ladeSvelte(seite).instance);
			assert.ok(namen.has('sendTestAlarm') && namen.has('testAlarmErgebnis'), 'Seite nutzt nicht den geteilten Weg');
		});
	}
});

describe('#3441 AC-14 / AC-15 — Katalog DE/EN und Elementliste ohne Lücke', () => {
	test('DE-Katalog enthält Titel, Untertitel und Leer-Text; EN hat dieselben Schlüssel', () => {
		const de = katalog('de');
		const en = katalog('en');
		for (const text of [TITEL, UNTERTITEL, LEER]) assert.ok(Object.values(de).includes(text), `DE fehlt: ${text}`);
		assert.deepEqual(Object.keys(en).sort(), Object.keys(de).sort(), 'Katalog-Parität DE/EN');
	});
	test('Elementliste test-menue: „Test-Alarm“ und Untertitel mit i18n_key, text_en, luecke false', () => {
		const liste = JSON.parse(readFileSync(path.join(REPO, 'docs/context/einstellungen_neu/elementliste.json'), 'utf8'));
		const zeilen = liste.elemente.filter((z: Json) => z.abschnitt === 'test-menue' && [TITEL, UNTERTITEL].includes(z.text_de));
		assert.ok(zeilen.length >= 4, `zu wenige Zeilen: ${zeilen.length}`);
		const de = katalog('de');
		const en = katalog('en');
		for (const z of zeilen) {
			assert.equal(z.luecke, false, z.id);
			assert.equal(de[z.i18n_key], z.text_de, `${z.id}: i18n_key ${z.i18n_key}`);
			assert.equal(en[z.i18n_key], z.text_en, `${z.id}: text_en`);
		}
	});
});
