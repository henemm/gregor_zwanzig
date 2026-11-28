// TDD RED — Issue #2795 S3b, Teilschritt 1b (Neubau Reiter „Zustellung“), Modell-Schicht `zustellungModell.ts`.
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md — Implementation Details §1, §2;
// AC-2, AC-3, AC-8 (Oberflaechen-Teil), AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16, AC-17,
// AC-19, AC-20, AC-21, AC-24, AC-26, AC-35 (Texte folgen der Sprache).
//
// Reine Funktionen, EIN Code fuer Trip (context="route") und Orts-Briefing (context="vergleich").
// Quelle der Kanal-Zustaende ist allein die EINE Profil-Antwort (GET /api/auth/profile, AC-36).
// Texte kommen aus dem Katalog (tr/trn, aktuelle `locale`), Datenwerte (LOW/MODERATE/HIGH) bleiben
// unuebersetzt (ADR-0104).
//
// Festgelegte API (shared/zustellung-tab/zustellungModell.ts):
//   type KanalId = 'email' | 'telegram' | 'sms' | 'premium_sms'
//   const KANAELE: readonly KanalId[]            // Zeilenfolge: email, telegram, sms, premium_sms
//   type Dringlichkeit = 'LOW' | 'MODERATE' | 'HIGH'
//   type Kontext = 'route' | 'vergleich'
//   type ZustellungProfil = ConnectionProfile & { tier?: 'free' | 'standard' | 'premium' }
//
//   interface KanalStatus {
//     kanal: KanalId;
//     verbunden: boolean;          // sendebereit: Briefing- und Alarm-Zelle bedienbar, zaehlt mit
//     ton: 'ok' | 'warn' | 'off';  // Statuspunkt
//     statusText: string;          // „bestätigt“ | „verbunden“ | „unbestätigt“ | „nicht verbunden“;
//                                  // Premium-SMS: „inReach · Rückadresse gelernt {datum} · zuletzt gemeldet {zeit}“
//                                  //              bzw. „inReach · Rückadresse verfallen“
//     ziel: string;                // E-Mail-Adresse / Chat / Nummer, '' wenn unbekannt
//     briefingGesperrt: boolean;   // Briefing-Schalter disabled (und aus)
//     alarmGesperrt: boolean;      // Alarm-Zelle zeigt Sperrtext statt Schalter
//     grund: string | null;        // Hinweiszeile („Telegram-Chat fehlt.“, „Nummer noch nicht bestätigt.“,
//                                  // „E-Mail-Adresse fehlt“, „SMS ab Level Standard“,
//                                  // Premium verfallen: „Schick eine Nachricht vom Gerät, …“); null = bedienbar
//     alarmSperre: string | null;  // Text der Alarm-Zelle: „gesperrt“ (#3437: Grund steht schon in der Hinweiszeile),
//                                  // „gesperrt: {Grund}“ nur wenn der Grund dort nicht wortgleich steht; null = Schalter
//     kontoLink: null | { verb: 'verbinden' | 'bestaetigen' | 'pruefen'; text: string } // „Im Konto … →“
//   }
//   kanalStatus(profil: ZustellungProfil | null | undefined): Record<KanalId, KanalStatus>
//
//   interface ZustellungStand {
//     morgenAn: boolean; morgenZeit: string;   // „HH:MM“
//     abendAn: boolean;  abendZeit: string;    // „HH:MM“
//     briefing: Record<KanalId, boolean>;      // Briefing-Kanalschalter (Trip: report_config.send_*, Orte: send_*)
//     alarme: Record<KanalId, boolean>;        // alert_channels
//     dringlichkeit: Record<KanalId, Dringlichkeit>; // alert_channel_thresholds, fehlend = LOW
//     stilleAn: boolean; stilleVon: string; stilleBis: string; // alert_quiet_from/_to („HH:MM“)
//     cooldown: number;                        // alert_cooldown_minutes, Standard 120
//     endDate: string | null;                  // nur Orte (end_date, null = bis auf Weiteres); Trip: null
//   }
//   standAusTrip(trip: Trip): ZustellungStand
//   standAusPreset(preset: ComparePreset): ZustellungStand   // send_email fehlt = true
//
//   zaehler(stand, status): { briefing: number; alarme: number }   // nur „an UND verbunden“
//   tabellenKopf(z: { briefing: number; alarme: number }): string  // „Briefings über 1 Kanal · Alarme über 2 Kanäle“
//   warnboxen(z): { briefing: null | { titel: string; text: string }; alarme: null | { titel: string; text: string } }
//   dringlichkeitVon(thresholds: Record<string, string | undefined> | null | undefined, kanal: KanalId): Dringlichkeit
//   dringlichkeitZelle(kanal, stand, status):
//       { art: 'strich' } | { art: 'segment'; wert: Dringlichkeit; optionen: { wert: Dringlichkeit; text: string }[] }
//   zeitFehler(wert: string): string | null   // null = gueltig (Raster 00/15/30/45, „HH:MM“ oder „HH:MM:SS“)
//   briefingUnterzeilen(context: Kontext): { morgen: string; abend: string }
//   laufzeitTrip(trip: Pick<Trip, 'stages'>): string      // „{Daten}. Die Briefings enden nach … in den Etappen.“
//   laufzeitOrte(endDate: string | null | undefined): { wahl: 'offen' | 'datum'; satz: string }
//
// RED heute: zustellungModell.ts und der Katalog zustellung.json existieren nicht.
//
//   cd frontend && npm test -- src/lib/components/shared/zustellung-tab/__tests__/zustellungModell.test.ts

import { test, describe, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { locale, trFor } from '../../../../i18n/index.ts';
import {
	KANAELE,
	presetVoll,
	profilAllesVerbunden,
	profilLuecken,
	profilMit,
	tripVoll,
	zustellungModell,
	type Json
} from './zustellungTabDaten.ts';

const RASTER_FEHLER = 'Bitte eine Zeit im Viertelstunden-Raster eintragen (00, 15, 30, 45)';

afterEach(() => locale.set('de'));

/** Stand mit gezielten Kanalschaltern (alles andere aus dem vollen Trip). */
async function standMit(briefing: Partial<Record<string, boolean>>, alarme: Partial<Record<string, boolean>>): Promise<Json> {
	const m = await zustellungModell();
	const s = m.standAusTrip(tripVoll());
	const aus = Object.fromEntries(KANAELE.map((k) => [k, false]));
	return { ...s, briefing: { ...aus, ...briefing }, alarme: { ...aus, ...alarme } };
}

// ── Kanalstatus aus dem Profil ──────────────────────────────────────────────

describe('AC-14: je Kanal eine Zeile mit Statuspunkt, Statustext und Ziel', () => {
	test('ac14_vier_kanaele_in_fester_reihenfolge', async () => {
		const m = await zustellungModell();
		assert.deepEqual([...m.KANAELE], ['email', 'telegram', 'sms', 'premium_sms']);
		const st = m.kanalStatus(profilAllesVerbunden());
		assert.deepEqual(Object.keys(st).sort(), [...KANAELE].sort(), 'jede der vier Zeilen hat einen Status');
	});

	test('ac14_alles_verbunden_statustexte_und_ziele', async () => {
		const m = await zustellungModell();
		const st = m.kanalStatus(profilAllesVerbunden());
		assert.equal(st.email.statusText, 'bestätigt');
		// #3202 (Spec feat_3202_kanalzeile_mockup.md, PO-Entscheidung 20.11.2026): die Kanalzeile zeigt
		// gekürzte Ziele wie im Mockup Fassung 4 — E-Mail `lokalteil@…`, Nummer `+<Vorwahl> <3 Ziffern> …`,
		// Telegram ohne Chat-ID. Die Zusicherung bleibt exakt (assert.equal auf den ganzen Wert).
		assert.equal(st.email.ziel, 'henning@…');
		assert.equal(st.telegram.statusText, 'verbunden');
		assert.equal(st.telegram.ziel, '');
		assert.equal(st.sms.statusText, 'bestätigt');
		assert.equal(st.sms.ziel, '+49 171 …');
		for (const k of KANAELE) {
			assert.equal(st[k].verbunden, true, `${k}: verbunden erwartet`);
			assert.equal(st[k].ton, 'ok', `${k}: Statuspunkt ok erwartet`);
			assert.equal(st[k].briefingGesperrt, false, `${k}: Briefing-Schalter darf nicht gesperrt sein`);
			assert.equal(st[k].alarmGesperrt, false, `${k}: Alarm-Zelle darf nicht gesperrt sein`);
			assert.equal(st[k].alarmSperre, null, `${k}: kein Sperrtext bei Verbindung`);
			assert.equal(st[k].kontoLink, null, `${k}: kein Konto-Link bei Verbindung`);
			assert.equal(st[k].grund, null, `${k}: kein Hinweis bei Verbindung`);
		}
	});
});

describe('AC-15 (#3437 AC-3/AC-4): Telegram nicht verbunden — Briefing gesperrt, Alarm-Zelle nur „gesperrt“, Konto-Link „verbinden“', () => {
	test('ac15_telegram_ohne_chat_gesperrt_mit_grund_und_link', async () => {
		const m = await zustellungModell();
		const t = m.kanalStatus(profilMit({ telegram_chat_id: '' })).telegram;
		assert.equal(t.verbunden, false);
		assert.equal(t.statusText, 'nicht verbunden');
		assert.equal(t.ton, 'off');
		assert.equal(t.briefingGesperrt, true, 'Briefing-Schalter muss gesperrt sein');
		assert.equal(t.alarmGesperrt, true, 'Alarm-Zelle muss gesperrt sein');
		assert.match(t.grund ?? '', /^Telegram-Chat fehlt/, 'Hinweis benennt den Grund');
		// #3437 (Mockup Fassung 4): der Grund steht schon in der Hinweiszeile darüber, die Zelle zeigt nur „gesperrt“.
		assert.equal(t.alarmSperre, 'gesperrt', `Alarm-Zelle muss nur „gesperrt“ zeigen, ist „${t.alarmSperre}“`);
		assert.equal(t.kontoLink?.verb, 'verbinden');
		assert.equal(t.kontoLink?.text, 'Im Konto verbinden →');
	});

	test('ac15_dringlichkeit_strich_bei_gesperrtem_kanal_auch_wenn_alarm_gespeichert_an', async () => {
		const m = await zustellungModell();
		const st = m.kanalStatus(profilMit({ telegram_chat_id: '' }));
		const stand = await standMit({ telegram: true }, { telegram: true });
		assert.deepEqual(m.dringlichkeitZelle('telegram', stand, st), { art: 'strich' });
	});
});

describe('AC-16: Sperrgruende und Konto-Verb je Lage', () => {
	test('ac16_sms_unbestaetigt_link_bestaetigen', async () => {
		const m = await zustellungModell();
		const s = m.kanalStatus(profilMit({ sms_verified: false })).sms;
		assert.equal(s.verbunden, false);
		assert.equal(s.statusText, 'unbestätigt');
		assert.equal(s.ton, 'warn');
		assert.match(s.grund ?? '', /^Nummer noch nicht bestätigt/);
		assert.equal(s.kontoLink?.verb, 'bestaetigen');
		assert.equal(s.kontoLink?.text, 'Im Konto bestätigen →');
		assert.equal(s.briefingGesperrt, true);
		assert.equal(s.alarmGesperrt, true);
		assert.equal(s.alarmSperre, 'gesperrt', '#3437 AC-5: Grund steht in der Hinweiszeile, Zelle nur „gesperrt“');
	});

	test('ac16_email_adresse_fehlt', async () => {
		const m = await zustellungModell();
		const e = m.kanalStatus(profilMit({ mail_to: '' })).email;
		assert.equal(e.verbunden, false);
		assert.equal(e.statusText, 'nicht verbunden');
		assert.match(e.grund ?? '', /^E-Mail-Adresse fehlt/);
		assert.ok(e.kontoLink, 'Konto-Link fehlt');
		assert.match(e.kontoLink!.text, /^Im Konto (verbinden|bestätigen|prüfen) →$/);
		assert.equal(e.briefingGesperrt, true);
		assert.equal(e.alarmGesperrt, true);
		assert.equal(e.alarmSperre, 'gesperrt', '#3437 AC-5: Grund steht in der Hinweiszeile, Zelle nur „gesperrt“');
	});

	// #3020 R1 (Befund B7, #1510 AC-4): unbestätigte Adresse ⇒ Briefing-Kanal E-Mail nicht bedienbar, im Trip wie in
	// Orten; der Versand weist sie ab. Nutzer B (bestätigt) als Gegenprobe, Nutzer A unbestätigt.
	for (const context of ['route', 'vergleich'] as const) {
		test(`email_unbestaetigt_briefing_nicht_bedienbar (${context})`, { todo: 'Fehler #3365: unbestätigte Adresse ist als Briefing-Kanal bedienbar' }, async () => {
			const m = await zustellungModell();
			const basis = context === 'route' ? m.standAusTrip(tripVoll()) : m.standAusPreset(presetVoll());
			const stand = { ...basis, briefing: { email: true, telegram: true, sms: false, premium_sms: false } };
			const B = m.kanalStatus(profilMit({ mail_to: 'b@example.com', email_verified: true }));
			const A = m.kanalStatus(profilMit({ mail_to: 'a@example.com', email_verified: false }));
			assert.equal(B.email.briefingGesperrt, false, 'Messaufbau: bestätigte Adresse ist bedienbar');
			assert.equal(m.zaehler(stand, B).briefing, 2, 'Messaufbau: E-Mail und Telegram zählen');
			assert.equal(A.email.briefingGesperrt, true, 'Briefing-Schalter E-Mail muss gesperrt sein');
			assert.ok(A.email.grund, 'die Sperre nennt einen Grund');
			assert.equal(m.zaehler(stand, A).briefing, 1, 'ein gesperrter Kanal zählt nicht als Briefing-Kanal');
			assert.equal(A.telegram.briefingGesperrt, false, 'andere Kanäle bleiben bedienbar');
		});
	}

	test('ac16_sms_tarif_zu_niedrig', async () => {
		const m = await zustellungModell();
		const s = m.kanalStatus(profilMit({ tier: 'free', sms_allowed: false })).sms;
		assert.equal(s.verbunden, false);
		assert.match(s.grund ?? '', /SMS ab Level Standard/);
		assert.equal(s.briefingGesperrt, true);
		assert.equal(s.alarmGesperrt, true);
		assert.equal(s.alarmSperre, 'gesperrt', '#3437 AC-5: Tarifgrund steht in der Hinweiszeile, Zelle nur „gesperrt“');
	});

	test('ac16_jeder_gesperrte_kanal_hat_grund_und_link', async () => {
		const m = await zustellungModell();
		for (const profil of [profilLuecken(), profilMit({ mail_to: '' }), profilMit({ sms_to: '' }), {}]) {
			const st = m.kanalStatus(profil);
			for (const k of KANAELE) {
				if (st[k].verbunden) continue;
				assert.ok(st[k].grund && st[k].grund.length > 0, `${k} gesperrt ohne Hinweis (${JSON.stringify(profil)})`);
				assert.ok(st[k].kontoLink, `${k} gesperrt ohne Konto-Link`);
				assert.match(st[k].kontoLink.text, /^Im Konto (verbinden|bestätigen|prüfen) →$/);
				assert.equal(st[k].briefingGesperrt, true, `${k}: gesperrt, aber Briefing-Schalter bedienbar`);
			}
		}
	});
});

describe('AC-19/AC-20/AC-21: Premium-SMS (sicherheitsrelevant)', () => {
	test('ac19_rueckadresse_gueltig_bedienbar_mit_statuszeile', async () => {
		const m = await zustellungModell();
		const p = m.kanalStatus(profilAllesVerbunden()).premium_sms;
		assert.equal(p.verbunden, true);
		assert.match(p.statusText, /^inReach · Rückadresse gelernt \S.* · zuletzt gemeldet \S/, `Statuszeile: „${p.statusText}“`);
		assert.equal(p.briefingGesperrt, false);
		assert.equal(p.alarmGesperrt, false);
	});

	test('ac20_rueckadresse_verfallen_beide_zellen_gesperrt', async () => {
		const m = await zustellungModell();
		const p = m.kanalStatus(profilMit({ premium_sms_reply_state: 'stale' })).premium_sms;
		assert.equal(p.verbunden, false, 'verfallene Rueckadresse ist NICHT sendebereit');
		assert.match(p.statusText, /Rückadresse verfallen/);
		assert.equal(p.grund, 'Schick eine Nachricht vom Gerät, dann ist die Rückadresse wieder gültig.');
		assert.equal(p.briefingGesperrt, true, 'Briefing-Zelle muss bei verfallener Rueckadresse gesperrt sein');
		assert.equal(p.alarmGesperrt, true, 'Alarm-Zelle muss bei verfallener Rueckadresse gesperrt sein');
		// #3437 AC-6: der Hinweis nennt einen anderen Text als die Sperre, daher bleibt der Grund in der Zelle.
		assert.equal(p.alarmSperre, 'gesperrt: Rückadresse verfallen');
		assert.equal(p.kontoLink?.verb, 'pruefen');
	});

	test('ac20_verfallen_wird_nicht_als_alarm_kanal_gezaehlt', async () => {
		const m = await zustellungModell();
		const st = m.kanalStatus(profilMit({ premium_sms_reply_state: 'stale' }));
		const stand = await standMit({ premium_sms: true }, { premium_sms: true });
		assert.deepEqual(m.zaehler(stand, st), { briefing: 0, alarme: 0 }, 'verfallene Premium-SMS zaehlt nicht');
		assert.deepEqual(m.dringlichkeitZelle('premium_sms', stand, st), { art: 'strich' });
	});

	// #3020 R1 (E070): nur Premium-SMS an und verbunden ist ein vollwertiger Kanal, in Trip und Orte.
	test('zaehler_nur_premium_sms_verbunden_zaehlt_und_keine_warnbox', async () => {
		const m = await zustellungModell();
		const st = m.kanalStatus(profilAllesVerbunden());
		const nurPremium = { email: false, telegram: false, sms: false, premium_sms: true };
		const orte = { ...m.standAusPreset(presetVoll()), briefing: { ...nurPremium }, alarme: { ...nurPremium } };
		for (const stand of [await standMit({ premium_sms: true }, { premium_sms: true }), orte]) {
			const z = m.zaehler(stand, st);
			assert.deepEqual(z, { briefing: 1, alarme: 1 }, 'verbundene Premium-SMS zaehlt als Kanal');
			assert.deepEqual(m.warnboxen(z), { briefing: null, alarme: null }, 'keine Warnbox „Kein Kanal“');
			assert.equal(m.tabellenKopf(z), 'Briefings über 1 Kanal · Alarme über 1 Kanal');
		}
		const z = m.zaehler(await standMit({ premium_sms: true }, { email: true }), st);
		assert.deepEqual(z, { briefing: 1, alarme: 1 }, 'Briefing und Alarme zaehlen getrennt');
	});

	test('ac20_nie_gemeldet_ebenfalls_gesperrt', async () => {
		const m = await zustellungModell();
		const p = m.kanalStatus(profilMit({ premium_sms_reply_state: 'none', premium_sms_reply_at: undefined })).premium_sms;
		assert.equal(p.verbunden, false);
		assert.equal(p.briefingGesperrt, true);
		assert.equal(p.alarmGesperrt, true);
		assert.equal(p.alarmSperre, 'gesperrt', '#3437 AC-5: „nie gemeldet“ steht in der Hinweiszeile, Zelle nur „gesperrt“');
	});

	test('ac21_tarif_wird_geprueft_profil_ohne_tarifauskunft', async () => {
		const m = await zustellungModell();
		for (const profil of [null, undefined, profilMit({ premium_sms_allowed: undefined })]) {
			const p = m.kanalStatus(profil).premium_sms;
			assert.equal(p.alarmGesperrt, true, 'ohne Tarifauskunft fail-closed');
			assert.match(p.grund ?? '', /^Tarif wird geprüft/, `Hinweiszeile: „${p.grund}“`);
			assert.equal(p.alarmSperre, 'gesperrt', `#3437 AC-5: Sperrtext nur „gesperrt“, ist „${p.alarmSperre}“`);
		}
	});

	test('ac21_tarif_unter_premium', async () => {
		const m = await zustellungModell();
		const p = m.kanalStatus(profilMit({ tier: 'standard', premium_sms_allowed: false })).premium_sms;
		assert.equal(p.alarmGesperrt, true);
		assert.match(p.grund ?? '', /ab Level Premium/, `Hinweiszeile: „${p.grund}“`);
		assert.equal(p.alarmSperre, 'gesperrt', `#3437 AC-5: Sperrtext nur „gesperrt“, ist „${p.alarmSperre}“`);
	});
});

// ── #3437: Alarm-Zelle zeigt den Grund nur einmal (Mockup Fassung 4) ────────
// Spec docs/specs/modules/fix_3437_orte_erklaer_gesperrt.md, AC-3 bis AC-8. EIN geteilter Code für Trip
// (context="route") und Orte (context="vergleich"): das Sperrverhalten bleibt in beiden Kontexten bestehen.

/** Je Sperrgrund ein Profil und der gesperrte Kanal (Grund steht wortgleich in der Hinweiszeile). */
const NACKT_GESPERRT: [fall: string, kanal: string, profil: () => Json][] = [
	['telegram_chat_fehlt', 'telegram', () => profilMit({ telegram_chat_id: '' })],
	['sms_unbestaetigt', 'sms', () => profilMit({ sms_verified: false })],
	['sms_fehlt', 'sms', () => profilMit({ sms_to: '', pending_sms_to: '' })],
	['sms_tarif', 'sms', () => profilMit({ tier: 'free', sms_allowed: false })],
	['email_fehlt', 'email', () => profilMit({ mail_to: '' })],
	['premium_tarif_gate', 'premium_sms', () => profilMit({ tier: 'standard', premium_sms_allowed: false })],
	['premium_nie_gemeldet', 'premium_sms', () => profilMit({ premium_sms_reply_state: 'none', premium_sms_reply_at: undefined })]
];

describe('#3437 AC-3/AC-4/AC-5/AC-7/AC-8: gesperrte Alarm-Zelle nur „gesperrt“ / „locked“', () => {
	for (const context of ['route', 'vergleich'] as const) {
		for (const [fall, kanal, profil] of NACKT_GESPERRT) {
			test(`${fall} (${context}): DE „gesperrt“, EN „locked“, Sperre bleibt`, async () => {
				const m = await zustellungModell();
				const basis = context === 'route' ? m.standAusTrip(tripVoll()) : m.standAusPreset(presetVoll());
				const stand = { ...basis, briefing: { ...basis.briefing, [kanal]: true }, alarme: { ...basis.alarme, [kanal]: true } };
				for (const [lang, erwartet] of [['de', 'gesperrt'], ['en', 'locked']] as const) {
					locale.set(lang);
					const st = m.kanalStatus(profil());
					const k = st[kanal];
					assert.ok(k.grund && k.grund.length > 0, `${fall}/${lang}: Hinweiszeile nennt den Grund`);
					assert.equal(k.alarmSperre, erwartet, `${fall}/${lang}: Alarm-Zelle „${k.alarmSperre}“`);
					// AC-8 (Sicherheitsregel AC-20 #2795): verkürzte Anzeige ändert das Sperrverhalten nicht.
					assert.equal(k.verbunden, false, `${fall}/${lang}: nicht sendebereit`);
					assert.equal(k.briefingGesperrt, true, `${fall}/${lang}: Briefing-Schalter gesperrt`);
					assert.equal(k.alarmGesperrt, true, `${fall}/${lang}: Alarm-Schalter gesperrt`);
					assert.deepEqual(m.dringlichkeitZelle(kanal, stand, st), { art: 'strich' }, `${fall}/${lang}: Dringlichkeit „–“`);
					const ohne = m.zaehler(stand, st);
					const alleVerbunden = m.zaehler(stand, m.kanalStatus(profilAllesVerbunden()));
					assert.equal(ohne.alarme, alleVerbunden.alarme - 1, `${fall}/${lang}: gesperrter Kanal zählt nicht als Alarm-Kanal`);
				}
			});
		}
	}

	test('premium_verfallen: Grund bleibt in der Zelle, DE und EN (AC-6/AC-7)', async () => {
		const m = await zustellungModell();
		const profil = profilMit({ premium_sms_reply_state: 'stale' });
		assert.equal(m.kanalStatus(profil).premium_sms.alarmSperre, 'gesperrt: Rückadresse verfallen');
		locale.set('en');
		assert.equal(m.kanalStatus(profil).premium_sms.alarmSperre, 'locked: reply address expired');
	});

	test('zustand_luecken: Telegram und SMS nackt, Premium mit Grund (Mockup Fassung 4, Z. 744)', async () => {
		const m = await zustellungModell();
		const st = m.kanalStatus(profilLuecken());
		assert.equal(st.telegram.alarmSperre, 'gesperrt');
		assert.equal(st.sms.alarmSperre, 'gesperrt');
		assert.equal(st.premium_sms.alarmSperre, 'gesperrt: Rückadresse verfallen');
		assert.equal(st.email.alarmSperre, null, 'E-Mail bleibt bedienbar');
	});

	test('katalog_zustellung_gesperrt_kurz_de_en (AC-7)', () => {
		assert.equal(trFor('de', 'zustellung.gesperrt_kurz' as never), 'gesperrt');
		assert.equal(trFor('en', 'zustellung.gesperrt_kurz' as never), 'locked');
		// Das Test-Schicken-Menü (AC-9) nutzt weiter den Schlüssel mit Grund.
		assert.equal(trFor('de', 'zustellung.gesperrt', { grund: 'X' }), 'gesperrt: X');
		assert.equal(trFor('en', 'zustellung.gesperrt', { grund: 'X' }), 'locked: X');
	});
});

// ── Zaehler, Tabellenkopf, Warnboxen ────────────────────────────────────────

describe('AC-13: Zaehler nur „an UND verbunden“, Kopf Singular/Plural', () => {
	test('ac13_kopf_1_kanal_2_kanaele', async () => {
		const m = await zustellungModell();
		const st = m.kanalStatus(profilAllesVerbunden());
		const z = m.zaehler(await standMit({ email: true }, { email: true, telegram: true }), st);
		assert.deepEqual(z, { briefing: 1, alarme: 2 });
		assert.equal(m.tabellenKopf(z), 'Briefings über 1 Kanal · Alarme über 2 Kanäle');
	});

	test('ac13_plural_auch_bei_0', async () => {
		const m = await zustellungModell();
		assert.equal(m.tabellenKopf({ briefing: 0, alarme: 0 }), 'Briefings über 0 Kanäle · Alarme über 0 Kanäle');
		assert.equal(m.tabellenKopf({ briefing: 4, alarme: 1 }), 'Briefings über 4 Kanäle · Alarme über 1 Kanal');
	});

	test('ac13_gesperrter_kanal_zaehlt_nicht_mit_auch_wenn_gespeichert_an', async () => {
		const m = await zustellungModell();
		const st = m.kanalStatus(profilLuecken()); // Telegram, SMS, Premium-SMS gesperrt
		const alles = Object.fromEntries(KANAELE.map((k) => [k, true]));
		const z = m.zaehler(await standMit(alles, alles), st);
		assert.deepEqual(z, { briefing: 1, alarme: 1 }, 'nur E-Mail ist an UND verbunden (Mockup „luecken“)');
		assert.equal(m.tabellenKopf(z), 'Briefings über 1 Kanal · Alarme über 1 Kanal');
	});
});

describe('AC-11/AC-12: Warnboxen getrennt, nur bei 0', () => {
	test('ac11_kein_briefing_kanal_warnbox', async () => {
		const m = await zustellungModell();
		const w = m.warnboxen({ briefing: 0, alarme: 2 });
		assert.ok(w.briefing, 'Briefing-Warnbox fehlt bei 0 Briefing-Kanaelen');
		assert.equal(
			`${w.briefing.titel} ${w.briefing.text}`,
			'Kein Kanal für Briefings an. So kommt kein Briefing bei dir an. Schalte unten mindestens einen Kanal ein.'
		);
		assert.equal(w.alarme, null, 'Alarm-Warnbox darf bei 2 Alarm-Kanaelen nicht erscheinen');
	});

	test('ac12_kein_alarm_kanal_warnbox_unabhaengig', async () => {
		const m = await zustellungModell();
		const w = m.warnboxen({ briefing: 1, alarme: 0 });
		assert.equal(w.briefing, null);
		assert.ok(w.alarme, 'Alarm-Warnbox fehlt bei 0 Alarm-Kanaelen');
		assert.equal(`${w.alarme.titel} ${w.alarme.text}`, 'Kein Kanal für Alarme an. Alarme gehen nirgends hin.');
		const beide = m.warnboxen({ briefing: 0, alarme: 0 });
		assert.ok(beide.briefing && beide.alarme, 'bei 0/0 erscheinen beide Warnboxen');
		const keine = m.warnboxen({ briefing: 1, alarme: 1 });
		assert.deepEqual(keine, { briefing: null, alarme: null });
	});
});

// ── Dringlichkeit ───────────────────────────────────────────────────────────

describe('AC-17: Dringlichkeit „–“ bei Alarm aus, Segment gering · mittel · hoch bei Alarm an, fehlend = LOW', () => {
	test('ac17_strich_wenn_alarm_aus', async () => {
		const m = await zustellungModell();
		const st = m.kanalStatus(profilAllesVerbunden());
		const stand = await standMit({ email: true }, { email: false });
		assert.deepEqual(m.dringlichkeitZelle('email', stand, st), { art: 'strich' });
	});

	test('ac17_segment_wenn_alarm_an_mit_lokalisierten_optionen', async () => {
		const m = await zustellungModell();
		const st = m.kanalStatus(profilAllesVerbunden());
		const stand = { ...(await standMit({}, { sms: true })), dringlichkeit: { email: 'LOW', telegram: 'LOW', sms: 'MODERATE', premium_sms: 'HIGH' } };
		const z = m.dringlichkeitZelle('sms', stand, st);
		assert.equal(z.art, 'segment');
		assert.equal(z.wert, 'MODERATE');
		assert.deepEqual(
			z.optionen.map((o: Json) => [o.wert, o.text]),
			[
				['LOW', 'gering'],
				['MODERATE', 'mittel'],
				['HIGH', 'hoch']
			]
		);
	});

	// #2801 (ADR-0131): fehlend/unbekannt = Vorbelegung des Kanals (E-Mail/Telegram LOW, SMS MODERATE,
	// Premium-SMS HIGH); ein gesetzter Wert, auch LOW, bleibt.
	test('ac17_fehlender_oder_unbekannter_wert_gilt_als_vorbelegung_des_kanals', async () => {
		const m = await zustellungModell();
		assert.equal(m.dringlichkeitVon(undefined, 'email'), 'LOW');
		assert.equal(m.dringlichkeitVon({}, 'telegram'), 'LOW');
		assert.equal(m.dringlichkeitVon(undefined, 'sms'), 'MODERATE');
		assert.equal(m.dringlichkeitVon({}, 'premium_sms'), 'HIGH');
		assert.equal(m.dringlichkeitVon({ sms: 'LOW' }, 'sms'), 'LOW', 'gesetztes LOW bleibt');
		assert.equal(m.dringlichkeitVon({ sms: 'MODERATE' }, 'sms'), 'MODERATE');
		assert.equal(m.dringlichkeitVon({ premium_sms: 'HIGH' }, 'premium_sms'), 'HIGH');
		assert.equal(m.dringlichkeitVon({ email: 'gering' }, 'email'), 'LOW', 'Altwert/Unbekanntes faellt auf die Vorbelegung');
		assert.equal(m.dringlichkeitVon({ sms: 'gering' }, 'sms'), 'MODERATE', 'Altwert/Unbekanntes faellt auf die Vorbelegung');
	});

	test('ac35_optionen_englisch_datenwert_unuebersetzt', async () => {
		const m = await zustellungModell();
		locale.set('en');
		const st = m.kanalStatus(profilAllesVerbunden());
		const z = m.dringlichkeitZelle('email', await standMit({}, { email: true }), st);
		assert.deepEqual(z.optionen.map((o: Json) => o.wert), ['LOW', 'MODERATE', 'HIGH'], 'Datenwerte nie uebersetzen');
		assert.deepEqual(z.optionen.map((o: Json) => o.text), ['low', 'moderate', 'high']);
	});
});

// ── Stand aus Trip / Preset ─────────────────────────────────────────────────

describe('Stand aus dem gespeicherten Abo (Trip und Orts-Briefing)', () => {
	test('ac2_trip_stand_zeiten_schalter_kanaele', async () => {
		const m = await zustellungModell();
		const s = m.standAusTrip(tripVoll());
		assert.equal(s.morgenZeit, '07:00');
		assert.equal(s.abendZeit, '18:00');
		assert.equal(s.morgenAn, true);
		assert.equal(s.abendAn, true);
		assert.deepEqual(s.briefing, { email: true, telegram: true, sms: false, premium_sms: false });
		assert.deepEqual(s.alarme, { email: true, telegram: true, sms: true, premium_sms: false });
		// #2801: premium_sms fehlt im Abo -> Vorbelegung HIGH.
		assert.deepEqual(s.dringlichkeit, { email: 'LOW', telegram: 'LOW', sms: 'MODERATE', premium_sms: 'HIGH' });
		assert.equal(s.endDate, null, 'Trip hat keine eigene Laufzeit');
	});

	test('ac4_trip_0645_wird_als_0645_gelesen', async () => {
		const m = await zustellungModell();
		const s = m.standAusTrip(tripVoll({ report_config: { ...tripVoll().report_config, morning_time: '06:45:00' } }));
		assert.equal(s.morgenZeit, '06:45', '06:45 darf beim Lesen nicht auf 06:00 gekappt werden');
	});

	test('ac2_vorgabe_0700_1800_wenn_zeit_fehlt', async () => {
		const m = await zustellungModell();
		const t = tripVoll();
		delete t.report_config.morning_time;
		delete t.report_config.evening_time;
		const s = m.standAusTrip(t);
		assert.equal(s.morgenZeit, '07:00');
		assert.equal(s.abendZeit, '18:00');
		const p = presetVoll();
		delete p.morning_time;
		delete p.evening_time;
		const sp = m.standAusPreset(p);
		assert.equal(sp.morgenZeit, '07:00');
		assert.equal(sp.abendZeit, '18:00');
	});

	test('ac23_preset_send_email_fehlt_gilt_als_an', async () => {
		const m = await zustellungModell();
		const p = presetVoll();
		delete p.send_email;
		assert.equal(m.standAusPreset(p).briefing.email, true, 'Alt-Preset ohne send_email: E-Mail-Briefing an');
		assert.equal(m.standAusPreset(presetVoll({ send_email: false })).briefing.email, false);
	});

	test('ac4_preset_stand_zeiten_kanaele_laufzeit', async () => {
		const m = await zustellungModell();
		const s = m.standAusPreset(presetVoll({ morning_time: '06:45:00', end_date: '2027-03-31' }));
		assert.equal(s.morgenZeit, '06:45');
		assert.equal(s.abendZeit, '18:00');
		assert.deepEqual(s.briefing, { email: true, telegram: true, sms: false, premium_sms: false });
		assert.deepEqual(s.alarme, { email: true, telegram: true, sms: false, premium_sms: false });
		// #2801: sms und premium_sms fehlen im Abo -> Vorbelegung MODERATE bzw. HIGH.
		assert.deepEqual(s.dringlichkeit, { email: 'LOW', telegram: 'HIGH', sms: 'MODERATE', premium_sms: 'HIGH' });
		assert.equal(s.endDate, '2027-03-31');
		assert.equal(m.standAusPreset(presetVoll({ end_date: undefined })).endDate, null);
		assert.equal(m.standAusPreset(presetVoll({ end_date: '' })).endDate, null, 'leeres end_date = bis auf Weiteres');
	});

	test('ac24_stille_stunden_an_aus', async () => {
		const m = await zustellungModell();
		const an = m.standAusTrip(tripVoll());
		assert.equal(an.stilleAn, true);
		assert.equal(an.stilleVon, '22:00');
		assert.equal(an.stilleBis, '06:00');
		const aus = m.standAusPreset(presetVoll({ alert_quiet_from: undefined, alert_quiet_to: undefined }));
		assert.equal(aus.stilleAn, false, 'ohne gespeicherte Stille Stunden ist der Schalter aus');
	});

	test('ac26_cooldown_zeigt_gespeicherten_wert_standard_120', async () => {
		const m = await zustellungModell();
		assert.equal(m.standAusTrip(tripVoll()).cooldown, 45, 'gespeicherter Wert, nicht der Mockup-Beispielwert');
		assert.equal(m.standAusPreset(presetVoll({ alert_cooldown_minutes: 10 })).cooldown, 10);
		assert.equal(m.standAusTrip(tripVoll({ alert_cooldown_minutes: undefined })).cooldown, 120);
		assert.equal(m.standAusPreset(presetVoll({ alert_cooldown_minutes: undefined })).cooldown, 120);
	});

	test('ac17_trip_ohne_alert_channels_erbt_briefing_kanaele', async () => {
		// Bestandsverhalten tripChannelReconstruction.ts: ohne alert_channels erben die Alarme report_config.send_*.
		const m = await zustellungModell();
		const s = m.standAusTrip(tripVoll({ alert_channels: undefined }));
		assert.deepEqual(s.alarme, { email: true, telegram: true, sms: false, premium_sms: false });
	});
});

// ── Raster-Validierung ──────────────────────────────────────────────────────

describe('AC-8 (Oberflaechen-Teil): Uhrzeit nur im Viertelstunden-Raster', () => {
	test('ac8_rasterzeiten_gueltig', async () => {
		const m = await zustellungModell();
		for (const z of ['06:45', '07:00', '00:15', '23:45', '12:30', '06:45:00', '18:00:00']) {
			assert.equal(m.zeitFehler(z), null, `${z} muss gueltig sein`);
		}
	});

	test('ac8_0650_meldung_im_wortlaut', async () => {
		const m = await zustellungModell();
		for (const z of ['06:50', '06:01', '07:59', '06:50:00']) {
			assert.equal(m.zeitFehler(z), RASTER_FEHLER, `${z}: Meldung erwartet`);
		}
	});

	test('ac8_unsinnige_eingaben_sind_fehler', async () => {
		const m = await zustellungModell();
		for (const z of ['24:00', '6:45', 'ab:cd', '06:45:30']) {
			assert.notEqual(m.zeitFehler(z), null, `${z} darf nicht als gueltig durchgehen`);
		}
	});
});

// ── Unterzeilen, Laufzeit ───────────────────────────────────────────────────

describe('AC-2/AC-3: Unterzeilen der Briefing-Karten je Kontext', () => {
	test('ac2_trip_unterzeilen', async () => {
		const m = await zustellungModell();
		assert.deepEqual(m.briefingUnterzeilen('route'), { morgen: 'für die Etappe des Tages', abend: 'für die Etappe von morgen' });
	});

	test('ac3_orte_unterzeilen', async () => {
		const m = await zustellungModell();
		assert.deepEqual(m.briefingUnterzeilen('vergleich'), { morgen: 'für heute', abend: 'für morgen' });
	});
});

describe('AC-9/AC-10: Laufzeit', () => {
	test('ac9_trip_satz_mit_daten_der_etappen', async () => {
		const m = await zustellungModell();
		const st = (...d: string[]) => ({ stages: d.map((date) => ({ date })) }) as never;
		const rest = ' Die Briefings enden nach der letzten Etappe. Die Daten pflegst du in den Etappen.';
		assert.equal(m.laufzeitTrip(tripVoll()), '23.–26. Februar 2026.' + rest);
		assert.equal(m.laufzeitTrip(st('2026-02-27', '2026-03-02')), '27. Februar – 2. März 2026.' + rest);
		assert.equal(m.laufzeitTrip(st('2026-12-30', '2027-01-02')), '30. Dezember 2026 – 2. Januar 2027.' + rest);
		assert.equal(m.laufzeitTrip(st('2026-02-23')), '23. Februar 2026.' + rest);
		locale.set('en');
		assert.equal(m.laufzeitTrip(tripVoll()), '23–26 February 2026. The briefings end after the last stage. You maintain the dates in the stages.');
	});

	test('ac10_orte_ohne_enddatum_bis_auf_weiteres', async () => {
		const m = await zustellungModell();
		for (const e of [null, undefined, '']) {
			assert.deepEqual(m.laufzeitOrte(e), { wahl: 'offen', satz: 'Das Briefing läuft, bis du es pausierst.' });
		}
	});

	test('ac10_orte_mit_enddatum_bis_datum', async () => {
		const m = await zustellungModell();
		const l = m.laufzeitOrte('2027-03-31');
		assert.equal(l.wahl, 'datum');
		// Mockup „…“, Spec-Zitat ‚…‘ (geschachtelt) — beide Anfuehrungen sind der freigegebene Wortlaut.
		assert.match(l.satz, /^Danach pausiert das Briefing von selbst\. Im Kopf steht dann [„‚]Laufzeit überschritten[“‘]\.$/);
	});
});

describe('AC-35: Modelltexte folgen der Sprache', () => {
	test('ac35_englisch_kein_deutscher_text', async () => {
		const m = await zustellungModell();
		locale.set('en');
		const kopf: string = m.tabellenKopf({ briefing: 1, alarme: 2 });
		const w = m.warnboxen({ briefing: 0, alarme: 0 });
		const t = m.kanalStatus(profilMit({ telegram_chat_id: '' })).telegram;
		const texte = [kopf, w.briefing.titel, w.briefing.text, w.alarme.titel, w.alarme.text, t.grund, t.kontoLink?.text, m.zeitFehler('06:50'),
			m.briefingUnterzeilen('route').morgen, m.laufzeitOrte(null).satz];
		for (const x of texte) {
			assert.ok(typeof x === 'string' && x.length > 0, 'leerer Text');
			assert.doesNotMatch(x, /[äöüß]|\b(Kanal|Kanäle|Briefings über|nicht|für|Bitte)\b/, `deutscher Text in en: „${x}“`);
		}
		assert.match(kopf, /\b1\b/);
		assert.match(kopf, /\b2\b/);
	});
});
