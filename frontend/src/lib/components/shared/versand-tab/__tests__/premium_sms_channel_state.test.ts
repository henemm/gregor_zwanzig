// TDD RED — Issue #1717 (Scheibe S3): Premium-SMS in der Oberflaeche.
// Spec: docs/specs/modules/feat_1717_s3_premium_sms_ui.md — AC-3, AC-5, AC-6.
//
// Reine Funktionspruefung des geteilten Zustands-Helfers
// `../premiumSmsChannelState.ts` (noch nicht vorhanden -> die Datei bricht beim
// Import ab, ERR_MODULE_NOT_FOUND: "Funktion fehlt", nicht "Tippfehler").
// Kein Mock, kein try/catch um den Import — der Fehlschlag soll unmissverstaendlich
// sein.
//
// VERTRAG, den dieser Test festnagelt (Implementierung in Phase 6):
//
//   export type PremiumSmsTone = 'good' | 'warn' | 'neutral';
//   export interface PremiumSmsChannelState {
//     disabled: boolean;          // Checkbox nicht anklickbar
//     tone: PremiumSmsTone;       // Dot-Ton (Dot akzeptiert 'warn', ui/dot/Dot.svelte:10)
//     statusLabel: string;        // Mono-Label neben dem Dot
//     hint: string;               // Prosa-Hinweis unter der Checkbox
//     reportedAtLabel: string;    // Meldedatum ("zuletzt gemeldet am ...")
//   }
//   export function premiumSmsChannelState(
//     profile: ConnectionProfile | null | undefined
//   ): PremiumSmsChannelState;
//
// Eingabe sind ausschliesslich die vier neuen ConnectionProfile-Felder
// (`premium_sms_allowed`, `premium_sms_reply_to`, `premium_sms_reply_at`,
// `premium_sms_reply_state`). Der Helfer rechnet KEINE Frist nach — die
// 30-Tage-Frist bleibt serverseitig (AC-5, Kontext-Risiko 3).
//
// Pfadregel #1409: der Pruefling wird relativ zu DIESER Datei aufgeloest
// (`../premiumSmsChannelState.ts`), nie ueber einen festen Hauptrepo-Pfad.
//
// Ausfuehrung:
//   cd frontend && node --import ./test-lib-loader.mjs --experimental-strip-types \
//     --test src/lib/components/shared/versand-tab/__tests__/premium_sms_channel_state.test.ts

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';

import { premiumSmsChannelState } from '../premiumSmsChannelState.ts';

/** Profilform wie sie `GET /api/auth/profile` nach S3 liefert (Go: auth.go
 * profileResponse). Lokal deklariert, damit dieser Test nicht an der
 * Typdeklaration haengt, sondern am Verhalten. */
interface PremiumProfile {
	sms_to?: string;
	sms_allowed?: boolean;
	premium_sms_allowed?: boolean;
	premium_sms_reply_to?: string;
	premium_sms_reply_at?: string;
	premium_sms_reply_state?: 'none' | 'stale' | 'fresh';
}

/** Vom Geraet gelernte Garmin-Rueckadresse (S1) — hat KEINE feste Nummer. */
const REPLY_TO = '15551234567';
const SMS_TO = '+49150000000';

function isoAgo(ms: number): string {
	return new Date(Date.now() - ms).toISOString();
}
const TAG_MS = 24 * 60 * 60 * 1000;

/** Premium-Tier, frische gelernte Rueckadresse — der Alles-gut-Fall. */
const FRESH: PremiumProfile = {
	sms_to: SMS_TO,
	sms_allowed: true,
	premium_sms_allowed: true,
	premium_sms_reply_to: REPLY_TO,
	premium_sms_reply_at: isoAgo(2 * TAG_MS),
	premium_sms_reply_state: 'fresh'
};

/** Noch nie gemeldet — Backend-Sperrgrund `premium_sms_no_reply_address`. */
const NONE: PremiumProfile = {
	sms_to: SMS_TO,
	sms_allowed: true,
	premium_sms_allowed: true,
	premium_sms_reply_state: 'none'
};

/** Laut Server verfallen — Backend-Sperrgrund `premium_sms_reply_address_stale`. */
const STALE: PremiumProfile = {
	...FRESH,
	premium_sms_reply_at: isoAgo(90 * TAG_MS),
	premium_sms_reply_state: 'stale'
};

/** Datumsdarstellungen auf einen Platzhalter normalisieren — was danach noch
 * unterschiedlich ist, ist KEIN Datum (also z.B. eine Tage-Zahl). */
function ohneDatum(text: string): string {
	return text.replace(/\d{1,4}[.\-/]\s?\d{1,2}[.\-/]\s?\d{1,4}/g, '«DATUM»');
}

describe('#1717 AC-3/AC-5/AC-6 — premiumSmsChannelState (geteilter Zustands-Helfer)', () => {
	// ─── AC-3 ────────────────────────────────────────────────────────────────
	test('state_labels_are_pairwise_distinct', () => {
		const faelle: Array<[string, PremiumProfile]> = [
			['none', NONE],
			['stale', STALE],
			['fresh', FRESH]
		];
		const hints = faelle.map(([name, p]) => {
			const hint = premiumSmsChannelState(p).hint;
			assert.ok(
				typeof hint === 'string' && hint.trim().length > 0,
				`AC-3 (${name}): Hinweistext fehlt — kein Zustand darf still verschwiegen werden.`
			);
			return [name, hint] as const;
		});

		for (let i = 0; i < hints.length; i++) {
			for (let j = i + 1; j < hints.length; j++) {
				assert.notEqual(
					hints[i][1],
					hints[j][1],
					`AC-3: Zustaende "${hints[i][0]}" und "${hints[j][0]}" zeigen denselben Hinweistext ` +
						`("${hints[i][1]}") — ein Nutzer kann "keine Adresse" nicht von "veraltete Adresse" unterscheiden.`
				);
			}
		}

		// Beide Sperrfaelle muessen die Checkbox auch tatsaechlich sperren.
		for (const [name, p] of [['none', NONE], ['stale', STALE]] as const) {
			assert.equal(
				premiumSmsChannelState(p).disabled,
				true,
				`AC-3 (${name}): Checkbox waere anklickbar, obwohl der Sendepfad diesen Fall blockt.`
			);
		}
		assert.equal(
			premiumSmsChannelState(FRESH).disabled,
			false,
			'AC-3 (fresh): Checkbox muss bei Premium-Tier + frischer Rueckadresse anklickbar sein.'
		);
	});

	// ─── AC-5 ────────────────────────────────────────────────────────────────
	test('state_feld_gewinnt_gegen_lokal_berechnetes_alter', () => {
		// (a) Server sagt "stale", der Rohzeitstempel sieht frisch aus (1 Stunde alt).
		const widerspruchStale: PremiumProfile = {
			...FRESH,
			premium_sms_reply_at: isoAgo(60 * 60 * 1000),
			premium_sms_reply_state: 'stale'
		};
		const a = premiumSmsChannelState(widerspruchStale);
		assert.equal(
			a.disabled,
			true,
			'AC-5: Server sagt "stale", der Zeitstempel ist 1 Stunde alt — die Anzeige folgt dem ' +
				'state-Feld, nicht einer im Frontend nachgerechneten Frist (sonst steht hier eine ' +
				'zweite 30-Tage-Konstante).'
		);
		assert.equal(
			ohneDatum(a.hint),
			ohneDatum(premiumSmsChannelState(STALE).hint),
			'AC-5: Der widerspruechliche Fall muss dieselbe Aussage tragen wie ein kanonisch ' +
				'veraltetes Profil — abweichender Text heisst: es wurde lokal gerechnet.'
		);

		// (b) Gegenrichtung — Server sagt "fresh", der Rohzeitstempel ist 400 Tage alt.
		const widerspruchFresh: PremiumProfile = {
			...FRESH,
			premium_sms_reply_at: isoAgo(400 * TAG_MS),
			premium_sms_reply_state: 'fresh'
		};
		const b = premiumSmsChannelState(widerspruchFresh);
		assert.equal(
			b.disabled,
			false,
			'AC-5 (Gegenrichtung): Server sagt "fresh" bei 400 Tage altem Zeitstempel — eine lokale ' +
				'Fristrechnung wuerde hier sperren und damit dem Server widersprechen.'
		);
		assert.equal(
			ohneDatum(b.hint),
			ohneDatum(premiumSmsChannelState(FRESH).hint),
			'AC-5 (Gegenrichtung): Aussage muss die eines frischen Profils sein.'
		);
	});

	test('hinweistext_nennt_keine_tage_zahl', () => {
		const stale31 = { ...STALE, premium_sms_reply_at: isoAgo(31 * TAG_MS) };
		const stale400 = { ...STALE, premium_sms_reply_at: isoAgo(400 * TAG_MS) };
		const a = premiumSmsChannelState(stale31);
		const b = premiumSmsChannelState(stale400);

		assert.notEqual(
			a.reportedAtLabel,
			b.reportedAtLabel,
			'AC-5: Zwei unterschiedlich alte Rueckadressen muessen unterschiedliche Meldedaten zeigen.'
		);

		for (const [name, s] of [['31 Tage alt', a], ['400 Tage alt', b]] as const) {
			assert.ok(
				!/\bTag(e|en)?\b/i.test(s.hint),
				`AC-5 (${name}): Der Hinweistext nennt eine Tage-Angabe ("${s.hint}") — das ist die ` +
					'30-Tage-Frist in Prosaform, also dieselbe Kopie.'
			);
		}

		assert.equal(
			ohneDatum(a.hint),
			ohneDatum(b.hint),
			`AC-5: Die beiden Hinweistexte duerfen sich NUR im Meldedatum unterscheiden — ` +
				`"${a.hint}" vs. "${b.hint}".`
		);
	});

	// ─── AC-6 ────────────────────────────────────────────────────────────────
	test('disabled_bei_tarif_sperre_trotz_frischer_adresse', () => {
		const standardTier: PremiumProfile = {
			sms_to: SMS_TO,
			sms_allowed: true, // normaler SMS-Kanal erlaubt (Tier standard)
			premium_sms_allowed: false, // Premium-SMS NICHT (nur Tier premium)
			premium_sms_reply_to: REPLY_TO,
			premium_sms_reply_at: isoAgo(1 * TAG_MS),
			premium_sms_reply_state: 'fresh'
		};
		const s = premiumSmsChannelState(standardTier);

		assert.equal(
			s.disabled,
			true,
			'AC-6: Tier standard darf Premium-SMS nicht einschalten koennen, auch nicht mit frischer ' +
				'Rueckadresse — sonst verspricht die Checkbox etwas, das der Sendepfad (S2a AC-8) blockt.'
		);
		assert.notEqual(
			s.hint,
			premiumSmsChannelState(FRESH).hint,
			'AC-6: Ein tarifgesperrter Nutzer sieht denselben Text wie ein voll berechtigter — ' +
				'die Tarif-Sperre bleibt damit unsichtbar.'
		);
	});
});
