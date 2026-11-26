// Issue #2655 (i18n F6, Epic #2644) — gemeinsamer SSR-Pruefstand fuer den
// geteilten Versand-Reiter (VersandTab + versand-tab/*, TelegramKurzstilToggle)
// in BEIDEN Kontexten (route | vergleich). Echte Svelte-Komponenten, gerendert
// mit svelte/server; Zone Europe/Berlin (Meldedatum der Premium-SMS-Rueckadresse).
// Nutzer `golden-de`, Profile laut Spec Implementation Details 7:
// „alles gekoppelt", „Premium-SMS verfallen", „nur E-Mail".
// Golden: tests/golden/f6_versand_tab/funktionen.de.txt = Ist-Stand VOR der
// Umstellung (#3385: die HTML-Goldens der geloeschten Bausteine entfallen);
// funktionen.en.txt = Review-Hilfe, aktualisiert mit
//   cd frontend && GZ_GOLDEN_SCHREIBEN=en npm test -- src/lib/components/shared/versand-tab/__tests__/versand_tab_sprache.test.ts
// Spec: docs/specs/modules/i18n_f6_versand_tab_2655.md
// Pfadregel #1409: alles relativ zu DIESER Datei.

import { register } from 'node:module';
import { mkdirSync, writeFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import path from 'node:path';

process.env.TZ = 'Europe/Berlin';

export const HERE = path.dirname(fileURLToPath(import.meta.url));
// __tests__ -> versand-tab -> shared -> components -> lib -> src -> frontend
export const FRONTEND = path.resolve(HERE, '../../../../../..');
export const VT = path.resolve(HERE, '..');
export const GOLDEN_DIR = path.resolve(FRONTEND, '..', 'tests', 'golden', 'f6_versand_tab');
register(pathToFileURL(path.join(FRONTEND, 'test-svelte-ssr-hooks.mjs')).href, pathToFileURL(FRONTEND + '/').href);

const imp = async (datei: string) => await import(pathToFileURL(datei).href);

export const { locale, trFor, tr } = await imp(path.join(FRONTEND, 'src/lib/i18n/index.ts'));
export const { premiumSmsChannelState } = await imp(path.join(VT, 'premiumSmsChannelState.ts'));
export const { channelConnectionStatus } = await imp(path.join(VT, 'channelConnectionStatus.ts'));
export const { sendTargetLabel } = await imp(path.join(VT, 'sendTargetLabel.ts'));
export const { formatNextBriefing } = await imp(path.join(VT, 'nextBriefingText.ts'));
export const { baueReportConfigPayload, ladeReportZustand } = await imp(path.join(VT, 'reportConfigPayload.ts'));

// #3385: die Bausteine des Versand-Reiters (Kanaele, Zeitplan, Laufzeit, Naechstes Briefing)
// sind als Waisen geloescht; mit ihnen entfallen die HTML-Goldens. Es bleibt die Funktionstabelle.

export type Kontext = 'route' | 'vergleich';

/** Profile wie GET /api/auth/profile (Nutzer golden-de). */
export const PROFILE: Record<string, Record<string, unknown>> = {
	alles_gekoppelt: {
		id: 'golden-de',
		mail_to: 'golden@example.org',
		email_verified: true,
		telegram_chat_id: '987654321',
		sms_to: '+491511234567',
		sms_allowed: true,
		sms_verified: true,
		premium_sms_allowed: true,
		premium_sms_reply_to: '+15551234567',
		premium_sms_reply_at: '2026-10-27T10:00:00Z',
		premium_sms_reply_state: 'fresh'
	},
	premium_verfallen: {
		id: 'golden-de',
		mail_to: 'golden@example.org',
		email_verified: true,
		sms_to: '+491511234567',
		sms_allowed: true,
		sms_verified: false,
		premium_sms_allowed: true,
		premium_sms_reply_to: '+15551234567',
		premium_sms_reply_at: '2026-09-20T10:00:00Z',
		premium_sms_reply_state: 'stale'
	},
	nur_email: {
		id: 'golden-de',
		mail_to: 'golden@example.org',
		email_verified: true,
		sms_allowed: false,
		premium_sms_allowed: false
	}
};

/** Backend-Werte `NextBriefing` (GET /api/next-briefings). */
export const NB: Record<string, Record<string, unknown> | null> = {
	termin: { at: '2026-10-28T07:00:00+01:00', local_date: '2026-10-28', local_time: '07:00', tz: 'Europe/Paris', tz_abbr: 'CET', slot: 'morning' },
	uebersprungen: {
		at: '2026-10-28T07:00:00+01:00',
		local_date: '2026-10-28',
		local_time: '07:00',
		tz_abbr: 'CET',
		skipped: { local_date: '2026-10-29', local_time: '07:00', slot: 'morning' }
	},
	ueberfaellig: { at: '2026-10-28T07:00:00+01:00', local_date: '2026-10-28', local_time: '07:00', tz_abbr: 'CET', overdue: true },
	pausiert_bis: { at: null, reason: 'paused', paused_until: '2026-10-28' },
	pausiert: { at: null, reason: 'paused' },
	manuell: { at: null, reason: 'manual' },
	beendet: { at: null, reason: 'ended' },
	abgeschaltet: { at: null, reason: 'disabled' },
	kein_termin: { at: null, reason: 'none' },
	kaputt: { at: '2026-10-28T07:00:00+01:00', local_date: 'Unfug' },
	nicht_geladen: null
};

const PREMIUM_EINGABEN: Record<string, Record<string, unknown> | null> = {
	ohne_profil: null,
	nicht_verfuegbar: { premium_sms_allowed: false },
	nie_gemeldet: { premium_sms_allowed: true, premium_sms_reply_state: 'none' },
	gelernt: { premium_sms_allowed: true, premium_sms_reply_state: 'fresh', premium_sms_reply_to: '+1555', premium_sms_reply_at: '2026-10-30T09:00:00Z' },
	verfallen: { premium_sms_allowed: true, premium_sms_reply_state: 'stale', premium_sms_reply_at: '2026-09-20T09:00:00Z' }
};

const ZIEL_EINGABEN: [string, Record<string, unknown> | null, Record<string, unknown> | null][] = [
	['ohne_profil', null, null],
	['ohne_adresse', {}, null],
	['unbestaetigt', { mail_to: 'a@example.org', email_verified: false }, null],
	['nur_email', PROFILE.nur_email, { send_telegram: true, send_sms: true }],
	['alles', PROFILE.alles_gekoppelt, { send_telegram: true, send_sms: true, send_premium_sms: true }]
];

/** Funktionsergebnisse als Tabelle `Eingabe → Ausgabe` (eine Zeile je Fall). */
export function funktionsTabelle(): string {
	const z: string[] = [];
	const j = (v: unknown) => JSON.stringify(v);
	for (const [k, p] of Object.entries(PREMIUM_EINGABEN)) z.push(`premiumSmsChannelState(${k}) → ${j(premiumSmsChannelState(p))}`);
	for (const k of Object.keys(PROFILE)) z.push(`channelConnectionStatus(${k}) → ${j(channelConnectionStatus(PROFILE[k]))}`);
	z.push(`channelConnectionStatus(email_unbestaetigt) → ${j(channelConnectionStatus({ mail_to: 'a@b', email_verified: false }))}`);
	z.push(`channelConnectionStatus(leer) → ${j(channelConnectionStatus(null))}`);
	for (const [k, p, s] of ZIEL_EINGABEN) z.push(`sendTargetLabel(${k}) → ${j(sendTargetLabel(p, s))}`);
	for (const context of ['route', 'vergleich'] as const) {
		for (const [k, nb] of Object.entries(NB)) z.push(`formatNextBriefing(${k}, ${context}) → ${j(formatNextBriefing(nb, context))}`);
	}
	return z.join('\n');
}

/** Schreibt die Golden-Dateien einer Sprache. */
export function schreibeGolden(lang: 'de' | 'en'): void {
	mkdirSync(GOLDEN_DIR, { recursive: true });
	locale.set(lang);
	try {
		writeFileSync(path.join(GOLDEN_DIR, `funktionen.${lang}.txt`), funktionsTabelle() + '\n');
	} finally {
		locale.set('de');
	}
}

if (process.env.GZ_GOLDEN_SCHREIBEN === 'de' || process.env.GZ_GOLDEN_SCHREIBEN === 'en') {
	if (import.meta.url === pathToFileURL(process.argv[1] ?? '').href) schreibeGolden(process.env.GZ_GOLDEN_SCHREIBEN);
}
