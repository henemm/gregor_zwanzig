// TDD RED — Issue #3440 (S5a, Scheibe #2797, Epic #2791): Zeilenmodell und Rückmeldungen des Menüs „Test schicken ▾“.
// Spec: docs/specs/modules/feat_3440_test_schicken_menue.md — AC-2, AC-3, AC-4, AC-5, AC-10, AC-11, AC-19 (Kern-Schicht).
//
// VERTRAG für den Developer — frontend/src/lib/components/molecules/testSchickenModell.ts (reine Funktionen, node:testbar,
// Texte nur über den Katalog in der aktuellen Sprache; Sperrlogik NIE neu ableiten, sondern aus
// zustellungModell.kanalStatus(profil) übernehmen):
//
//   export type Berichtsart = 'morning' | 'evening';
//   export type TestKanal = KanalId | 'alle';                      // KanalId aus zustellungModell.ts
//   export interface TestZeile {
//     kanal: KanalId;
//     name: string;                       // tr(KANAL_NAME_KEYS[kanal]) — „E-Mail“, „Telegram“, „SMS“, „Premium-SMS“
//     bedienbar: boolean;                 // false ⇒ Zeile ausgegraut, Klick schickt nichts
//     ziel: string;                       // bedienbar: E-Mail adresseGekuerzt, Telegram „verbunden“, SMS nummerGekuerzt,
//                                         //            Premium „inReach · über Satellit“; gesperrt: ''
//     grund: string | null;               // gesperrt: kanalStatus(profil)[kanal].grund (E-Mail unbestätigt: „Adresse noch nicht bestätigt.“)
//     sperrText: string | null;           // gesperrt: tr('zustellung.gesperrt', { grund }) — „gesperrt: {Grund}“
//     kontoLink: null | { verb: KontoVerb; text: string; href: '/account' };  // verb/text identisch zu kanalStatus
//   }
//   export interface TestMenueModell {
//     segment: null | { wert: Berichtsart; optionen: { wert: Berichtsart; text: string }[] };  // nur context 'route'
//     zeilen: TestZeile[];                // immer vier, Reihenfolge email, telegram, sms, premium_sms
//     alle: { text: string };             // „Alle eingerichteten Kanäle“
//     erweiterungen: { id: string; text: string }[];  // Slot nach dem Trenner unter „Alle“ (#3441 Test-Alarm); in S5a leer
//   }
//   export function testMenueModell(profil: ZustellungProfil | null | undefined, context: 'route' | 'vergleich',
//                                   berichtsart?: Berichtsart /* Default 'morning' */): TestMenueModell;
//   export function einzelRueckmeldung(p: { context: 'route' | 'vergleich'; berichtsart: Berichtsart; kanal: KanalId;
//                                           ziel: string; jetzt: Date }): string;
//       // „{Morgen-Briefing|Abend-Briefing|Briefing} an {Kanal} geschickt · {Ziel} · {hh:mm}“ (hh:mm lokal aus `jetzt`)
//   export function alleRueckmeldung(p: { context: 'route' | 'vergleich'; berichtsart: Berichtsart;
//                                         sentChannels: KanalId[]; profil: ZustellungProfil | null | undefined }): string;
//       // „{Briefing} geschickt: E-Mail ✓ · Telegram übersprungen ({Grund}) · SMS fehlgeschlagen · …“
//       // ✓ = in sentChannels; übersprungen ({letzter Teil von kanalStatus.statusText}) = nicht bedienbar;
//       // fehlgeschlagen = bedienbar, aber nicht in sentChannels. Reihenfolge wie die Zeilen.
//
// Alle Profile sind echte Objekte in der Form von GET /api/auth/profile; Adressen/Nummern erfunden (example.com).
//
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types --experimental-test-module-mocks \
//     --test src/lib/components/molecules/__tests__/test_schicken_modell.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { locale, tr } from '../../../i18n/index.ts';
import { kanalStatus, KANAELE, type KanalId } from '../../shared/zustellung-tab/zustellungModell.ts';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Json = any;

afterEach(() => locale.set('de'));

async function modul(): Promise<Json> {
	try {
		return await import('../testSchickenModell.ts');
	} catch (e) {
		assert.fail(`TDD RED: molecules/testSchickenModell.ts fehlt oder lädt nicht (${(e as Error).message})`);
	}
}

const MAIL = 'henning@example.com';

function profilNormal(over: Json = {}): Json {
	return {
		tier: 'premium',
		mail_to: MAIL,
		email_verified: true,
		telegram_chat_id: '987654321',
		sms_to: '+491711234567',
		sms_allowed: true,
		sms_verified: true,
		premium_sms_allowed: true,
		premium_sms_reply_to: 'wanderer-3440@inreach.example.com',
		premium_sms_reply_at: '2026-11-01T18:04:00Z',
		premium_sms_reply_state: 'fresh',
		...over
	};
}

/** Zustand „Lücken“ wie Mockup/Elementliste: Telegram fehlt, SMS unbestätigt, Premium-Rückadresse verfallen. */
function profilLuecken(): Json {
	return profilNormal({
		telegram_chat_id: '',
		sms_to: '',
		sms_verified: false,
		pending_sms_to: '+49 171 0000000',
		premium_sms_reply_state: 'stale'
	});
}

const zeileVon = (m: Json, k: KanalId) => m.zeilen.find((z: Json) => z.kanal === k);

/** Abo-Kanalstand „alle vier im Briefing an“ (Fix-Loop F001: alleRueckmeldung kennt den Abo-Stand). */
const ALLE_AN = { email: true, telegram: true, sms: true, premium_sms: true } as const;

// ── AC-3: vier Zeilen, Reihenfolge, Ziele ────────────────────────────────────

describe('#3440 AC-3 — vier Kanalzeilen in fester Reihenfolge mit Zielen', () => {
	test('alle verbunden: E-Mail, Telegram, SMS, Premium-SMS mit gekürzten Zielen, alle bedienbar', async () => {
		const { testMenueModell } = await modul();
		const m = testMenueModell(profilNormal(), 'route');
		assert.deepEqual(m.zeilen.map((z: Json) => z.kanal), ['email', 'telegram', 'sms', 'premium_sms']);
		assert.deepEqual(m.zeilen.map((z: Json) => z.name), ['E-Mail', 'Telegram', 'SMS', 'Premium-SMS']);
		assert.deepEqual(m.zeilen.map((z: Json) => z.ziel), ['henning@…', 'verbunden', '+49 171 …', 'inReach · über Satellit']);
		for (const z of m.zeilen) {
			assert.equal(z.bedienbar, true, `${z.kanal} muss bedienbar sein`);
			assert.equal(z.sperrText, null, `${z.kanal}: kein Sperrtext`);
			assert.equal(z.kontoLink, null, `${z.kanal}: kein Konto-Link`);
		}
	});

	test('Telegram-Ziel nennt nie Chat-ID oder Namen (#3202), E-Mail nie die volle Adresse', async () => {
		const { testMenueModell } = await modul();
		const m = testMenueModell(profilNormal(), 'vergleich');
		const alles = JSON.stringify(m);
		assert.ok(!alles.includes('987654321'), 'Chat-ID im Modell');
		assert.ok(!alles.includes(MAIL), 'volle E-Mail-Adresse im Modell');
		assert.ok(!alles.includes('1711234567'), 'volle Telefonnummer im Modell');
	});

	test('EN: Kanalnamen und Ziele aus dem englischen Katalog, Premium-Ziel nicht deutsch', async () => {
		locale.set('en');
		const { testMenueModell } = await modul();
		const m = testMenueModell(profilNormal(), 'route');
		assert.deepEqual(m.zeilen.map((z: Json) => z.name), ['Email', 'Telegram', 'SMS', 'Premium SMS']);
		assert.equal(zeileVon(m, 'telegram').ziel, 'connected');
		const premium = zeileVon(m, 'premium_sms').ziel;
		assert.match(premium, /inReach/);
		assert.notEqual(premium, 'inReach · über Satellit', 'EN zeigt den deutschen Premium-Text');
		assert.equal(m.alle.text === 'Alle eingerichteten Kanäle', false, 'EN zeigt „Alle eingerichteten Kanäle“');
	});
});

// ── AC-4: gesperrte Zeilen, Grund und Verb identisch zu kanalStatus ──────────

describe('#3440 AC-4 — gesperrte Kanäle: Grund und Konto-Verb aus kanalStatus', () => {
	for (const sprache of ['de', 'en'] as const) {
		test(`Lücken (${sprache}): Telegram/SMS/Premium gesperrt, Grund + Verb + Text identisch zu kanalStatus`, async () => {
			locale.set(sprache);
			const { testMenueModell } = await modul();
			const profil = profilLuecken();
			const m = testMenueModell(profil, 'route');
			const status = kanalStatus(profil);
			for (const k of ['telegram', 'sms', 'premium_sms'] as const) {
				const z = zeileVon(m, k);
				assert.equal(z.bedienbar, false, `${k} muss gesperrt sein`);
				assert.equal(z.grund, status[k].grund, `${k}: Grund weicht von kanalStatus ab`);
				assert.equal(z.sperrText, tr('zustellung.gesperrt', { grund: status[k].grund ?? '' }), `${k}: Sperrtext`);
				assert.deepEqual(
					{ verb: z.kontoLink?.verb, text: z.kontoLink?.text, href: z.kontoLink?.href },
					{ verb: status[k].kontoLink?.verb, text: status[k].kontoLink?.text, href: '/account' },
					`${k}: Konto-Link`
				);
			}
			assert.equal(zeileVon(m, 'email').bedienbar, true, 'E-Mail bleibt im Zustand Lücken frei (Mockup)');
		});
	}

	test('DE-Wortlaut wie Mockup: „gesperrt: Telegram-Chat fehlt.“ / „Im Konto verbinden →“ usw.', async () => {
		const { testMenueModell } = await modul();
		const m = testMenueModell(profilLuecken(), 'vergleich');
		assert.equal(zeileVon(m, 'telegram').sperrText, 'gesperrt: Telegram-Chat fehlt.');
		assert.equal(zeileVon(m, 'telegram').kontoLink.text, 'Im Konto verbinden →');
		assert.equal(zeileVon(m, 'sms').sperrText, 'gesperrt: Nummer noch nicht bestätigt.');
		assert.equal(zeileVon(m, 'sms').kontoLink.text, 'Im Konto bestätigen →');
		assert.equal(
			zeileVon(m, 'premium_sms').sperrText,
			'gesperrt: Schick eine Nachricht vom Gerät, dann ist die Rückadresse wieder gültig.'
		);
		assert.equal(zeileVon(m, 'premium_sms').kontoLink.text, 'Im Konto prüfen →');
	});

	test('Tarif ohne SMS/Premium: Sperre folgt kanalStatus (Verb „prüfen“), nicht eigener Logik', async () => {
		const { testMenueModell } = await modul();
		const profil = profilNormal({ tier: 'free', sms_allowed: false, premium_sms_allowed: false });
		const m = testMenueModell(profil, 'route');
		const status = kanalStatus(profil);
		for (const k of ['sms', 'premium_sms'] as const) {
			assert.equal(zeileVon(m, k).bedienbar, !status[k].briefingGesperrt, `${k}: bedienbar weicht von kanalStatus ab`);
			assert.equal(zeileVon(m, k).kontoLink?.verb, status[k].kontoLink?.verb);
		}
	});
});

// ── AC-5: E-Mail unbestätigt gesperrt ────────────────────────────────────────

describe('#3440 AC-5 — E-Mail unbestätigt ist im Menü gesperrt (ADR-0092)', () => {
	test('email_verified=false: „gesperrt: Adresse noch nicht bestätigt.“ + „Im Konto bestätigen →“', async () => {
		const { testMenueModell } = await modul();
		const m = testMenueModell(profilNormal({ email_verified: false }), 'route');
		const z = zeileVon(m, 'email');
		assert.equal(z.bedienbar, false);
		assert.equal(z.grund, 'Adresse noch nicht bestätigt.');
		assert.equal(z.sperrText, 'gesperrt: Adresse noch nicht bestätigt.');
		assert.deepEqual(z.kontoLink, { verb: 'bestaetigen', text: 'Im Konto bestätigen →', href: '/account' });
		// Die Zustellung bleibt unverändert (Warnpunkt, bedienbar) — die Sperre lebt nur im Menü-Modell.
		assert.equal(kanalStatus(profilNormal({ email_verified: false })).email.briefingGesperrt, false);
	});

	test('ohne mail_to: E-Mail gesperrt mit dem Grund aus kanalStatus (Verb „verbinden“)', async () => {
		const { testMenueModell } = await modul();
		const profil = profilNormal({ mail_to: '' });
		const z = zeileVon(testMenueModell(profil, 'vergleich'), 'email');
		assert.equal(z.bedienbar, false);
		assert.equal(z.grund, kanalStatus(profil).email.grund);
		assert.equal(z.kontoLink?.verb, 'verbinden');
	});
});

// ── AC-2: Segment nur beim Trip ──────────────────────────────────────────────

describe('#3440 AC-2 — Segment Morgen/Abend nur bei context="route"', () => {
	test('route: Segment mit Vorauswahl Morgen und zwei Optionen aus dem Katalog', async () => {
		const { testMenueModell } = await modul();
		const m = testMenueModell(profilNormal(), 'route');
		assert.deepEqual(m.segment, {
			wert: 'morning',
			optionen: [
				{ wert: 'morning', text: 'Morgen-Briefing' },
				{ wert: 'evening', text: 'Abend-Briefing' }
			]
		});
		assert.equal(testMenueModell(profilNormal(), 'route', 'evening').segment.wert, 'evening');
	});

	test('vergleich: kein Segment, auch nicht bei übergebener Berichtsart', async () => {
		const { testMenueModell } = await modul();
		assert.equal(testMenueModell(profilNormal(), 'vergleich').segment, null);
		assert.equal(testMenueModell(profilNormal(), 'vergleich', 'evening').segment, null);
	});

	test('beide Kontexte: dieselben vier Zeilen (ein Baustein, ADR-0097)', async () => {
		const { testMenueModell } = await modul();
		assert.deepEqual(testMenueModell(profilLuecken(), 'route').zeilen, testMenueModell(profilLuecken(), 'vergleich').zeilen);
	});
});

// ── AC-19: Erweiterungs-Slot, kein Test-Alarm ────────────────────────────────

// #3441 (S5b) stellt um: der Slot trägt jetzt genau den Eintrag „Test-Alarm“ (Details: test_alarm_3441.test.ts).
describe('#3440 AC-19 / #3441 AC-1 — Erweiterungs-Slot nach „Alle“ trägt den Test-Alarm', () => {
	for (const context of ['route', 'vergleich'] as const) {
		test(`${context}: „Alle eingerichteten Kanäle“ + Erweiterung test-alarm`, async () => {
			const { testMenueModell } = await modul();
			const m = testMenueModell(profilNormal(), context);
			assert.equal(m.alle.text, 'Alle eingerichteten Kanäle');
			assert.deepEqual(m.erweiterungen.map((e: Json) => e.id), ['test-alarm']);
		});
	}
});

// ── AC-11: Einzel-Rückmeldung ────────────────────────────────────────────────

describe('#3440 AC-11 — Einzel-Rückmeldung „{Briefing} an {Kanal} geschickt · {Ziel} · {hh:mm}“', () => {
	test('Trip Morgen, E-Mail, Uhr 20:41', async () => {
		const { einzelRueckmeldung } = await modul();
		const s = einzelRueckmeldung({ context: 'route', berichtsart: 'morning', kanal: 'email', ziel: 'henning@…', jetzt: new Date(2026, 10, 27, 20, 41) });
		assert.equal(s, 'Morgen-Briefing an E-Mail geschickt · henning@… · 20:41');
	});

	test('Trip Abend, Telegram, Uhr zweistellig aufgefüllt (07:05)', async () => {
		const { einzelRueckmeldung } = await modul();
		const s = einzelRueckmeldung({ context: 'route', berichtsart: 'evening', kanal: 'telegram', ziel: 'verbunden', jetzt: new Date(2026, 10, 27, 7, 5) });
		assert.equal(s, 'Abend-Briefing an Telegram geschickt · verbunden · 07:05');
	});

	test('Orte: neutrales „Briefing“ (nicht „Orts-Briefing“), Berichtsart ohne Wirkung', async () => {
		const { einzelRueckmeldung } = await modul();
		for (const berichtsart of ['morning', 'evening'] as const) {
			const s = einzelRueckmeldung({ context: 'vergleich', berichtsart, kanal: 'sms', ziel: '+49 171 …', jetzt: new Date(2026, 10, 27, 9, 0) });
			assert.equal(s, 'Briefing an SMS geschickt · +49 171 … · 09:00');
		}
	});

	test('Uhr ist injiziert: andere Zeit ⇒ anderer Text (keine eingebaute Systemuhr)', async () => {
		const { einzelRueckmeldung } = await modul();
		const a = einzelRueckmeldung({ context: 'route', berichtsart: 'morning', kanal: 'email', ziel: 'x@…', jetzt: new Date(2026, 0, 1, 23, 59) });
		assert.match(a, / · 23:59$/);
	});

	test('EN: Text aus dem englischen Katalog, kein deutsches „geschickt“', async () => {
		locale.set('en');
		const { einzelRueckmeldung } = await modul();
		const s = einzelRueckmeldung({ context: 'route', berichtsart: 'morning', kanal: 'email', ziel: 'henning@…', jetzt: new Date(2026, 10, 27, 20, 41) });
		assert.match(s, /Morning briefing/);
		assert.match(s, /henning@… · 20:41$/);
		assert.ok(!/geschickt|Morgen/.test(s), `deutscher Rest im EN-Text: ${s}`);
	});
});

// ── AC-10: Alle-Rückmeldung ──────────────────────────────────────────────────

describe('#3440 AC-10 — „Alle“: ✓ / übersprungen ({Grund}) / fehlgeschlagen', () => {
	test('Lücken-Profil, gesendet nur E-Mail: Telegram/Premium übersprungen mit Grund aus kanalStatus', async () => {
		const { alleRueckmeldung } = await modul();
		const s = alleRueckmeldung({ context: 'route', berichtsart: 'morning', sentChannels: ['email'], profil: profilLuecken(), abo: ALLE_AN });
		assert.equal(
			s,
			'Morgen-Briefing geschickt: E-Mail ✓ · Telegram übersprungen (nicht verbunden) · SMS übersprungen (unbestätigt) · Premium-SMS übersprungen (Rückadresse verfallen)'
		);
	});

	test('bedienbar, aber nicht gesendet ⇒ „fehlgeschlagen“; Orte mit neutralem „Briefing“', async () => {
		const { alleRueckmeldung } = await modul();
		const s = alleRueckmeldung({ context: 'vergleich', berichtsart: 'morning', sentChannels: ['email', 'sms'], profil: profilNormal(), abo: ALLE_AN });
		assert.equal(s, 'Briefing geschickt: E-Mail ✓ · Telegram fehlgeschlagen · SMS ✓ · Premium-SMS fehlgeschlagen');
	});

	test('Abend-Briefing, alles gesendet ⇒ vier Haken', async () => {
		const { alleRueckmeldung } = await modul();
		const s = alleRueckmeldung({ context: 'route', berichtsart: 'evening', sentChannels: [...KANAELE], profil: profilNormal(), abo: ALLE_AN });
		assert.equal(s, 'Abend-Briefing geschickt: E-Mail ✓ · Telegram ✓ · SMS ✓ · Premium-SMS ✓');
	});

	test('Reihenfolge folgt den Zeilen, nicht der Reihenfolge in sent_channels', async () => {
		const { alleRueckmeldung } = await modul();
		const s = alleRueckmeldung({ context: 'route', berichtsart: 'morning', sentChannels: ['premium_sms', 'telegram', 'email', 'sms'], profil: profilNormal(), abo: ALLE_AN });
		assert.match(s, /^Morgen-Briefing geschickt: E-Mail ✓ · Telegram ✓ · SMS ✓ · Premium-SMS ✓$/);
	});

	test('EN: kein deutsches „übersprungen“/„fehlgeschlagen“', async () => {
		locale.set('en');
		const { alleRueckmeldung } = await modul();
		const s = alleRueckmeldung({ context: 'route', berichtsart: 'morning', sentChannels: ['email'], profil: profilLuecken(), abo: ALLE_AN });
		assert.match(s, /Email ✓/);
		assert.match(s, /\(not connected\)/);
		assert.ok(!/übersprungen|fehlgeschlagen|geschickt/.test(s), `deutscher Rest im EN-Text: ${s}`);
	});
});

// ── AC-10 (Fix-Loop F001): im Abo ausgeschalteter Kanal ist „übersprungen (im Briefing aus)“ ──

/** Orts-Briefing im Standard: E-Mail an (send_email fehlt), Telegram/SMS/Premium aus. Erfundene Daten. */
function presetStandard(over: Json = {}): Json {
	return { id: 'vg-3440', name: 'Hütten-Vergleich', locations: [], ...over };
}

/** Trip mit Briefing-Kanälen unter report_config (Form von GET /api/trips/{id}). Erfundene Daten. */
function tripMit(reportConfig: Json): Json {
	return { id: 'trip-3440', name: 'Testweg', stages: [], report_config: reportConfig };
}

describe('#3440 AC-10 — „Alle“: bedienbar, aber im Abo aus ⇒ übersprungen (im Briefing aus), nie fehlgeschlagen', () => {
	test('aboKanaele liest den Abo-Stand aus derselben Quelle wie der Zustellung-Tab (Orte: Telegram standardmäßig aus)', async () => {
		const { aboKanaele } = await modul();
		assert.deepEqual(aboKanaele('vergleich', presetStandard()), { email: true, telegram: false, sms: false, premium_sms: false });
		assert.deepEqual(aboKanaele('vergleich', presetStandard({ send_telegram: true, send_email: false })), {
			email: false,
			telegram: true,
			sms: false,
			premium_sms: false
		});
		assert.deepEqual(aboKanaele('route', tripMit({ send_email: true, send_telegram: true, send_sms: false })), {
			email: true,
			telegram: true,
			sms: false,
			premium_sms: false
		});
	});

	test('Ortsvergleich, Telegram verbunden aber im Abo aus, gesendet nur E-Mail ⇒ Telegram übersprungen (im Briefing aus)', async () => {
		const { alleRueckmeldung, aboKanaele } = await modul();
		const s = alleRueckmeldung({
			context: 'vergleich',
			berichtsart: 'morning',
			sentChannels: ['email'],
			profil: profilNormal(),
			abo: aboKanaele('vergleich', presetStandard())
		});
		assert.equal(
			s,
			'Briefing geschickt: E-Mail ✓ · Telegram übersprungen (im Briefing aus) · SMS übersprungen (im Briefing aus) · Premium-SMS übersprungen (im Briefing aus)'
		);
		assert.ok(!/fehlgeschlagen/.test(s), `im Abo ausgeschalteter Kanal als Fehler gemeldet: ${s}`);
	});

	test('im Abo an, bedienbar, nicht gesendet ⇒ fehlgeschlagen (Trip, gemischter Abo-Stand)', async () => {
		const { alleRueckmeldung, aboKanaele } = await modul();
		const abo = aboKanaele('route', tripMit({ send_email: true, send_telegram: true, send_sms: false, send_premium_sms: true }));
		const s = alleRueckmeldung({ context: 'route', berichtsart: 'morning', sentChannels: ['email'], profil: profilNormal(), abo });
		assert.equal(
			s,
			'Morgen-Briefing geschickt: E-Mail ✓ · Telegram fehlgeschlagen · SMS übersprungen (im Briefing aus) · Premium-SMS fehlgeschlagen'
		);
	});

	test('gesperrt geht vor „im Briefing aus“: Grund aus kanalStatus, auch wenn der Kanal im Abo aus ist', async () => {
		const { alleRueckmeldung } = await modul();
		const aus = { email: true, telegram: false, sms: false, premium_sms: false };
		const s = alleRueckmeldung({ context: 'route', berichtsart: 'morning', sentChannels: ['email'], profil: profilLuecken(), abo: aus });
		assert.equal(
			s,
			'Morgen-Briefing geschickt: E-Mail ✓ · Telegram übersprungen (nicht verbunden) · SMS übersprungen (unbestätigt) · Premium-SMS übersprungen (Rückadresse verfallen)'
		);
	});

	test('Tarif ohne SMS/Premium (gesperrt laut kanalStatus) ⇒ übersprungen mit Tarif-Grund, nicht fehlgeschlagen', async () => {
		const { alleRueckmeldung } = await modul();
		const profil = profilNormal({ tier: 'free', sms_allowed: false, premium_sms_allowed: false });
		const status = kanalStatus(profil);
		const s = alleRueckmeldung({ context: 'route', berichtsart: 'morning', sentChannels: ['email', 'telegram'], profil, abo: ALLE_AN });
		for (const k of ['sms', 'premium_sms'] as const) {
			const name = tr(k === 'sms' ? 'zustellung.kanal.sms' : 'zustellung.kanal.premium_sms');
			if (status[k].briefingGesperrt) {
				const grund = status[k].statusText.split(' · ').pop();
				assert.ok(s.includes(`${name} übersprungen (${grund})`), `${k}: Tarif-Sperre nicht als übersprungen: ${s}`);
			}
		}
		assert.ok(!/fehlgeschlagen/.test(s), `Tarif-Sperre als Fehler gemeldet: ${s}`);
	});

	test('gesendet geht vor Abo-Stand: im Abo aus, aber in sent_channels ⇒ ✓', async () => {
		const { alleRueckmeldung } = await modul();
		const aus = { email: false, telegram: false, sms: false, premium_sms: false };
		const s = alleRueckmeldung({ context: 'vergleich', berichtsart: 'morning', sentChannels: ['telegram'], profil: profilNormal(), abo: aus });
		assert.match(s, /Telegram ✓/);
	});

	test('EN: „skipped (off in this briefing)“, kein deutscher Rest', async () => {
		locale.set('en');
		const { alleRueckmeldung, aboKanaele } = await modul();
		const s = alleRueckmeldung({
			context: 'vergleich',
			berichtsart: 'morning',
			sentChannels: ['email'],
			profil: profilNormal(),
			abo: aboKanaele('vergleich', presetStandard())
		});
		assert.match(s, /Telegram skipped \(off in this briefing\)/);
		assert.ok(!/übersprungen|im Briefing aus|failed/.test(s), `falscher Text im EN: ${s}`);
	});

	test('testErgebnis reicht den Abo-Stand an die „Alle“-Rückmeldung durch', async () => {
		const { testErgebnis, aboKanaele } = await modul();
		const r = testErgebnis({
			context: 'vergleich',
			wahl: { kanal: 'alle', berichtsart: 'morning' },
			ergebnis: { kind: 'ok', message: '', sentChannels: ['email'] },
			profil: profilNormal(),
			abo: aboKanaele('vergleich', presetStandard()),
			jetzt: new Date(2026, 10, 27, 9, 0)
		});
		assert.equal(r.ok, true);
		assert.match(r.text, /Telegram übersprungen \(im Briefing aus\)/);
		assert.ok(!/fehlgeschlagen/.test(r.text));
	});
});

// ── AC-2 / AC-11 (Fix-Loop F002): Vorauswahl beim Öffnen und Rückmeldedauer als eine Quelle ──

describe('#3440 AC-2 / AC-11 — Vorauswahl Morgen beim Öffnen, Rückmeldedauer 5 s', () => {
	test('berichtsartBeiOffen: Öffnen setzt auf Morgen zurück, Schließen lässt die Wahl stehen', async () => {
		const { berichtsartBeiOffen, BERICHTSART_START } = await modul();
		assert.equal(BERICHTSART_START, 'morning');
		assert.equal(berichtsartBeiOffen(true, 'evening'), 'morning');
		assert.equal(berichtsartBeiOffen(true, 'morning'), 'morning');
		assert.equal(berichtsartBeiOffen(false, 'evening'), 'evening');
	});

	test('RUECKMELDUNG_MS ist 5 Sekunden', async () => {
		const { RUECKMELDUNG_MS } = await modul();
		assert.equal(RUECKMELDUNG_MS, 5000);
	});
});
