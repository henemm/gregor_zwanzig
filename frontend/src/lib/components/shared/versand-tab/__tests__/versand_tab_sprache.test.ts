// Issue #2655 (i18n F6, Epic #2644) — AC-1, AC-2, AC-3, AC-4, AC-6: der geteilte
// Versand-Reiter (Trip UND Ortsvergleich, EIN Baustein) spricht die Sprache des
// angemeldeten Nutzers. Echte SSR-Renders (svelte/server, Pruefstand f6VersandSsr.ts):
//   * AC-6: Deutsch ist byte-gleich zur Ausgabe VOR der Umstellung
//     (tests/golden/f6_versand_tab/funktionen.de.txt; #3385: HTML-Goldens und AC-1
//     entfallen mit den geloeschten Bausteinen),
//   * AC-2: premiumSmsChannelState je Zustand in beiden Sprachen,
//   * AC-3: formatNextBriefing (pausiert, manuell, beendet, Termin, uebersprungen),
//   * AC-4: zwei Nutzer (en/de) durch den ECHTEN Layout-Loader (+layout.server.ts);
//     ersetzt ist nur die Netzgrenze (fetch je Sitzungs-Cookie).
// Jeder en-Fall rendert zuerst de und schaltet dann OHNE Neuladen auf en: eine
// Mutation tr()/$t -> trFor('de', …) macht ihn rot. Englische und deutsche
// Texte sind als feste Literale verankert (f6KatalogAnker.ts).
// Spec: docs/specs/modules/i18n_f6_versand_tab_2655.md
//
//   cd frontend && npm test -- src/lib/components/shared/versand-tab/__tests__/versand_tab_sprache.test.ts

import { test, describe, before, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { register } from 'node:module';
import { readFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import {
	FRONTEND,
	GOLDEN_DIR,
	PROFILE,
	NB,
	locale,
	trFor,
	premiumSmsChannelState,
	sendTargetLabel,
	formatNextBriefing,
	baueReportConfigPayload,
	ladeReportZustand,
	funktionsTabelle,
	schreibeGolden
} from './f6VersandSsr.ts';
import { F6_ANKER } from './f6KatalogAnker.ts';

const base = pathToFileURL(FRONTEND + '/').href;
register(pathToFileURL(path.join(FRONTEND, 'test-env-dynamic-private-stub-hooks.mjs')).href, base);
register(pathToFileURL(path.join(FRONTEND, 'src/routes/admin/__tests__/server-load-resolve.hooks.mjs')).href, base);
const layoutLoad = (await import(pathToFileURL(path.join(FRONTEND, 'src/routes/+layout.server.ts')).href)).load;
const { sendConfirmModel } = await import(pathToFileURL(path.join(FRONTEND, 'src/lib/components/molecules/sendConfirmModel.ts')).href);

before(() => {
	// Die de-Golden sind der Ist-Stand VOR der Umstellung und werden nie neu geschrieben;
	// nur die en-Ansicht (Review-Hilfe, nicht verglichen) wird aktualisiert.
	if (process.env.GZ_GOLDEN_SCHREIBEN === 'en') schreibeGolden('en');
});
afterEach(() => locale.set('de'));

/** Erst de rendern, dann OHNE Neuladen auf en schalten. */
function deDannEn<T>(f: () => T): { de: T; en: T } {
	locale.set('de');
	const de = f();
	locale.set('en');
	const en = f();
	return { de, en };
}

// #3385: die HTML-Golden-Faelle, der Messaufbau, AC-1 und #2869 rendern die geloeschten
// Bausteine (VTBriefingChannels, VTSchedulePlan, VTLaufzeit*, VTNextBriefing) und entfallen.
describe('AC-6: Deutsch byte-gleich zum Ist-Stand vor der Umstellung (Golden golden-de)', () => {
	test('funktionen.de.txt: Funktionsergebnisse unveraendert (byte-gleich, ohne Normalisierung)', () => {
		const golden = readFileSync(path.join(GOLDEN_DIR, 'funktionen.de.txt'), 'utf-8');
		locale.set('en');
		funktionsTabelle();
		locale.set('de');
		assert.equal(funktionsTabelle() + '\n', golden);
	});
});

describe('AC-2: Premium-SMS-Zustand je Sprache, disabled/tone sprachunabhaengig', () => {
	const ZUSTAENDE: [string, Record<string, unknown> | null, string, string, string, string][] = [
		['none', { premium_sms_allowed: true, premium_sms_reply_state: 'none' }, 'nicht verbunden', 'not connected', 'Das Gerät hat sich noch nie gemeldet — die Rückadresse wird beim ersten Empfang gelernt.', 'The device has never reported in — the reply address is learned on first receipt.'],
		['fresh', { premium_sms_allowed: true, premium_sms_reply_state: 'fresh' }, 'gelernt', 'learned', 'Das Gerät hat sich gemeldet — Briefings gehen an die gelernte Rückadresse.', 'The device has reported in — briefings go to the learned reply address.'],
		['stale', { premium_sms_allowed: true, premium_sms_reply_state: 'stale' }, 'verfallen', 'expired', 'Rückadresse verfallen — Garmin kann die Nummer inzwischen einem fremden Gerät zugeteilt haben. Sobald sich das Gerät wieder meldet, ist der Kanal erneut nutzbar.', 'Reply address expired — Garmin may have assigned the number to another device by now. As soon as the device reports in again, the channel can be used again.'],
		['ohne Tarif', { premium_sms_allowed: false, premium_sms_reply_state: 'fresh' }, 'nicht verfügbar', 'not available', 'Premium-SMS ab Level Premium verfügbar', 'Premium SMS is available from the Premium level']
	];
	for (const [name, p, deStatus, enStatus, deHint, enHint] of ZUSTAENDE) {
		test(name, () => {
			const { de, en } = deDannEn(() => premiumSmsChannelState(p));
			assert.equal(de.statusLabel, deStatus);
			assert.equal(de.hint, deHint);
			assert.equal(en.statusLabel, enStatus);
			assert.equal(en.hint, enHint);
			assert.equal(en.disabled, de.disabled);
			assert.equal(en.tone, de.tone);
		});
	}
	test('Meldedatum: de TT.MM.JJJJ, en „Thu 30 Oct" ohne Jahr (Annahme A2)', () => {
		const p = { premium_sms_allowed: true, premium_sms_reply_state: 'fresh', premium_sms_reply_at: '2026-10-30T09:00:00Z', premium_sms_reply_to: '+1555' };
		const { de, en } = deDannEn(() => premiumSmsChannelState(p));
		assert.equal(de.reportedAtLabel, 'zuletzt gemeldet am 30.10.2026');
		assert.equal(en.reportedAtLabel, 'last reported on Fri 30 Oct');
		assert.equal(en.contactLabel, ' (+1555)');
		assert.equal(de.contactLabel, en.contactLabel);
	});
});

describe('AC-3: formatNextBriefing in beiden Sprachen', () => {
	const FAELLE: [string, 'route' | 'vergleich', string, string][] = [
		['pausiert_bis', 'route', 'pausiert bis 28.10.', 'paused until Wed 28 Oct'],
		['pausiert', 'route', 'pausiert', 'paused'],
		['manuell', 'route', 'nur manueller Versand', 'manual delivery only'],
		['beendet', 'route', 'Trip beendet', 'Trip ended'],
		['beendet', 'vergleich', 'Ortsvergleich beendet', 'Location comparison ended'],
		['abgeschaltet', 'route', 'Briefings abgeschaltet', 'Briefings switched off'],
		['kein_termin', 'vergleich', 'kein Termin geplant', 'no time scheduled'],
		// #2869: Termin immer mit Datum; Kürzel passt zum Offset +01:00 (28.10. = Winterzeit, AC-11).
		['termin', 'route', 'Mi 28.10. 07:00 (CET)', 'Wed 28 Oct 07:00 (CET)'],
		['termin', 'vergleich', 'Mi 28.10. 07:00 (CET)', 'Wed 28 Oct 07:00 (CET)'],
		['uebersprungen', 'route', 'Mi 28.10. 07:00 (CET) — Do 29.10. 07:00 wird übersprungen', 'Wed 28 Oct 07:00 (CET) — Thu 29 Oct 07:00 is skipped'],
		['uebersprungen', 'vergleich', 'Mi 28.10. 07:00 (CET) — Do 29.10. 07:00 wird übersprungen', 'Wed 28 Oct 07:00 (CET) — Thu 29 Oct 07:00 is skipped'],
		['ueberfaellig', 'vergleich', 'Mi 28.10. 07:00 (CET) — läuft jetzt / wird nachgeholt', 'Wed 28 Oct 07:00 (CET) — running now / will be caught up'],
		['kaputt', 'route', '—', '—'],
		['nicht_geladen', 'route', '—', '—']
	];
	for (const [fall, context, de, en] of FAELLE) {
		test(`${fall} (${context})`, () => {
			const r = deDannEn(() => formatNextBriefing(NB[fall], context));
			assert.equal(r.de, de);
			assert.equal(r.en, en);
		});
	}
	test('alle sieben Wochentage je Sprache (zonenfrei aus local_date)', () => {
		const tage = ['2026-10-25', '2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31'];
		const { de, en } = deDannEn(() => tage.map((d) => formatNextBriefing({ at: 'x', local_date: d, local_time: '07:00', tz_abbr: 'CET' })).join(' | '));
		assert.equal(de, 'So 25.10. 07:00 (CET) | Mo 26.10. 07:00 (CET) | Di 27.10. 07:00 (CET) | Mi 28.10. 07:00 (CET) | Do 29.10. 07:00 (CET) | Fr 30.10. 07:00 (CET) | Sa 31.10. 07:00 (CET)');
		assert.equal(en, 'Sun 25 Oct 07:00 (CET) | Mon 26 Oct 07:00 (CET) | Tue 27 Oct 07:00 (CET) | Wed 28 Oct 07:00 (CET) | Thu 29 Oct 07:00 (CET) | Fri 30 Oct 07:00 (CET) | Sat 31 Oct 07:00 (CET)');
	});
});

describe('AC-4: zwei Nutzer, zwei Sprachen, eigene Kanaele, gleiche report_config', () => {
	const ANNA = { ...PROFILE.alles_gekoppelt, id: 'anna', mail_to: 'anna@example.org', telegram_chat_id: '111222333', sms_to: '', sms_verified: false, premium_sms_allowed: false, language: 'en' };
	const BERT = { id: 'bert', mail_to: 'bert@example.org', email_verified: true, sms_allowed: false, premium_sms_allowed: false, language: 'de' };
	const API: Record<string, Record<string, unknown>> = { A: { '/api/auth/profile': ANNA }, B: { '/api/auth/profile': BERT } };

	/** Ersetzt nur die Netzgrenze: `fetch` antwortet je Sitzungs-Cookie mit eigenen Daten (sonst 404). */
	async function mitApi<T>(lauf: () => Promise<T>): Promise<T> {
		const echt = globalThis.fetch;
		globalThis.fetch = (async (u: string, init?: { headers?: Record<string, string> }) => {
			const sitzung = /gz_session=([^;]+)/.exec(init?.headers?.Cookie ?? '')?.[1] ?? '';
			const daten = API[sitzung]?.[new URL(String(u)).pathname];
			return new Response(JSON.stringify(daten ?? null), { status: daten === undefined ? 404 : 200 });
		}) as unknown as typeof fetch;
		try {
			return await lauf();
		} finally {
			globalThis.fetch = echt;
		}
	}
	const cookies = (s: string) => ({ get: (n: string) => (n === 'gz_session' ? s : undefined) });

	/** Echter Layout-Loader (Sprache) + Profil der Sitzung → Reiter, Sende-Dialog, Nutzlast. */
	async function sichtFuer(sitzung: 'A' | 'B') {
		const { lang, profil } = await mitApi(async () => {
			const layout = await layoutLoad({ locals: { userId: sitzung, lang: 'de' }, cookies: cookies(sitzung) } as never);
			const profil = await (await fetch('http://core/api/auth/profile', { headers: { Cookie: `gz_session=${sitzung}` } })).json();
			return { lang: layout.lang as 'de' | 'en', profil };
		});
		locale.set(lang);
		const kanaele = { send_telegram: true, send_sms: true, send_premium_sms: true };
		const zustand = { ...ladeReportZustand({ send_email: true, send_telegram: true, morning_time: '07:00:00' }), telegram_style: 'rich' };
		// #3385: der Kanal-Baustein (VTBriefingChannels) ist geloescht; geprueft werden
		// Sende-Ziel, Dialog und Nutzlast.
		return {
			lang,
			ziel: sendTargetLabel(profil, kanaele).text,
			dialog: sendConfirmModel('trip', profil, kanaele).beschreibung,
			nutzlast: baueReportConfigPayload({ live: { send_email: true }, zustand })
		};
	}

	test('A englisch mit Telegram, B deutsch nur E-Mail; keine fremden Kanaele; Nutzlast gleich', async () => {
		locale.set('de');
		const a = await sichtFuer('A');
		const b = await sichtFuer('B');
		assert.equal(a.lang, 'en');
		assert.equal(b.lang, 'de');
		assert.equal(a.ziel, 'Goes to E-Mail (anna@example.org) · Telegram.');
		assert.equal(a.dialog, a.ziel);
		assert.equal(b.ziel, 'Geht an E-Mail (bert@example.org).');
		assert.equal(b.dialog, b.ziel);
		assert.ok(!a.ziel.includes('bert'), 'A sieht Daten von B');
		assert.ok(!b.ziel.includes('anna') && !b.ziel.includes('Telegram'), 'B sieht Daten/Kanaele von A');
		assert.deepEqual(a.nutzlast, b.nutzlast);
		assert.equal(JSON.stringify(a.nutzlast), JSON.stringify(b.nutzlast));
	});

	test('Sende-Ziel-Saetze der Sperrfaelle in beiden Sprachen', () => {
		const faelle: [Record<string, unknown> | null, string, string][] = [
			[null, 'Versandziel unbekannt — das Konto-Profil ist nicht verfügbar; es wird nichts gesendet.', 'Delivery target unknown — the account profile is not available; nothing is sent.'],
			[{}, 'Im Konto ist keine E-Mail-Adresse hinterlegt — es kann nichts gesendet werden.', 'No email address is set in the account — nothing can be sent.'],
			[{ mail_to: 'a@example.org' }, 'Die Adresse a@example.org ist nicht bestätigt — es wird nichts zugestellt.', 'The address a@example.org is not confirmed — nothing is delivered.']
		];
		for (const [p, de, en] of faelle) {
			const r = deDannEn(() => sendTargetLabel(p, null));
			assert.equal(r.de.text, de);
			assert.equal(r.en.text, en);
			assert.equal(r.en.gesperrt, true);
			assert.equal(r.de.gesperrt, true);
		}
		const alles = deDannEn(() => sendTargetLabel(PROFILE.alles_gekoppelt, { send_telegram: true, send_sms: true, send_premium_sms: true }).text);
		assert.equal(alles.en, 'Goes to E-Mail (golden@example.org) · Telegram · SMS · Premium-SMS.');
	});
});

describe('Anker: jeder F6-Katalogwert ist als festes de/en-Literal verankert', () => {
	/** Platzhalter des Literals (<name>) werden als Parameter `<name>` eingesetzt. */
	const params = (literal: string) =>
		Object.fromEntries([...literal.matchAll(/<([a-z0-9_]+)>/g)].map((m) => [m[1], `<${m[1]}>`]));
	for (const [k, de, en] of F6_ANKER) {
		test(k, () => {
			assert.equal(trFor('de', k, params(de)), de, `de ${k}`);
			assert.equal(trFor('en', k, params(en)), en, `en ${k}`);
		});
	}

	test('statischer Gegencheck: Anker-Tabelle == Schluessel von versand.json + telegram_kurzstil.* (de und en)', () => {
		const MSG = path.join(FRONTEND, 'src', 'lib', 'i18n', 'messages');
		for (const lang of ['de', 'en']) {
			const lade = (d: string) => Object.keys(JSON.parse(readFileSync(path.join(MSG, lang, d), 'utf-8')));
			const schluessel = [...lade('versand.json'), ...lade('bausteine.json').filter((k) => k.startsWith('telegram_kurzstil.'))];
			assert.deepEqual([...schluessel].sort(), F6_ANKER.map(([k]) => k).sort(), `${lang}: Schluessel ohne Anker oder Anker ohne Schluessel`);
		}
		assert.equal(new Set(F6_ANKER.map(([k]) => k)).size, F6_ANKER.length, 'doppelte Anker');
	});
});
