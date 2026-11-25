// Issue #2795 S3b, Teilschritt 1b — Modell des Reiters „Zustellung“ (Trip und Orts-Briefing, EIN Code).
// Spec: docs/specs/modules/feat_2795_s3b_teil1_zustellung.md (Implementation Details §1, §2).
//
// Reine Funktionen: Kanalstatus aus der EINEN Profil-Antwort (GET /api/auth/profile, AC-36),
// Formularstand aus Trip bzw. Preset, Zaehler, Tabellenkopf, Warnboxen, Dringlichkeit,
// Raster-Pruefung der Uhrzeit, Unterzeilen und Laufzeit-Saetze. Texte kommen aus dem Katalog in der
// aktuellen Sprache (tr/trn); Datenwerte LOW/MODERATE/HIGH bleiben unuebersetzt (ADR-0104).
// Kein Netz-/DOM-Zugriff — node:testbar.

import { get } from 'svelte/store';
import { tr, trn, locale, type MessageKey } from '../../../i18n/index.ts';
import { fmtDateNumeric, fmtTime } from '../../../i18n/format.ts';
import type { ComparePreset, Trip } from '../../../types.ts';
import type { ConnectionProfile } from '../versand-tab/channelConnectionStatus.ts';
import { derivePremiumSmsAlarmGate } from '../alarme-tab/premiumSmsAlarmGate.ts';
import { reconstructTripAlertChannels } from '../alarme-tab/tripChannelReconstruction.ts';
import { CHANNEL_THRESHOLD_KEYS } from '../alarme-tab/alertChannelState.ts';
import { ABEND_STANDARD, MORGEN_STANDARD, hhmm, leseBriefingStartwerte } from '../briefingStartwerte.ts';
import { formatDateRange } from '../../../utils/tripHero.ts';

export type KanalId = 'email' | 'telegram' | 'sms' | 'premium_sms';
export const KANAELE: readonly KanalId[] = ['email', 'telegram', 'sms', 'premium_sms'];
export type Dringlichkeit = 'LOW' | 'MODERATE' | 'HIGH';
export const DRINGLICHKEITEN: readonly Dringlichkeit[] = ['LOW', 'MODERATE', 'HIGH'];
export type Kontext = 'route' | 'vergleich';
export type ZustellungProfil = ConnectionProfile & { tier?: 'free' | 'standard' | 'premium' };

export type KontoVerb = 'verbinden' | 'bestaetigen' | 'pruefen';

export interface KanalStatus {
	kanal: KanalId;
	verbunden: boolean;
	ton: 'ok' | 'warn' | 'off';
	statusText: string;
	ziel: string;
	briefingGesperrt: boolean;
	alarmGesperrt: boolean;
	grund: string | null;
	alarmSperre: string | null;
	kontoLink: null | { verb: KontoVerb; text: string };
}

export interface ZustellungStand {
	morgenAn: boolean;
	morgenZeit: string;
	abendAn: boolean;
	abendZeit: string;
	briefing: Record<KanalId, boolean>;
	alarme: Record<KanalId, boolean>;
	dringlichkeit: Record<KanalId, Dringlichkeit>;
	stilleAn: boolean;
	stilleVon: string;
	stilleBis: string;
	cooldown: number;
	endDate: string | null;
}

export const COOLDOWN_STANDARD = 120;
// Anzeigewerte der Stille-Stunden-Felder, solange nichts gespeichert ist (Schalter aus).
const STILLE_VON_STANDARD = '22:00';
const STILLE_BIS_STANDARD = '06:00';

const KONTO_KEYS: Record<KontoVerb, MessageKey> = {
	verbinden: 'zustellung.konto.verbinden',
	bestaetigen: 'zustellung.konto.bestaetigen',
	pruefen: 'zustellung.konto.pruefen'
};

/** Katalogschluessel des Kanalnamens (Zeilenbeschriftung). */
export const KANAL_NAME_KEYS: Record<KanalId, MessageKey> = {
	email: 'zustellung.kanal.email',
	telegram: 'zustellung.kanal.telegram',
	sms: 'zustellung.kanal.sms',
	premium_sms: 'zustellung.kanal.premium_sms'
};

function kontoLink(verb: KontoVerb): { verb: KontoVerb; text: string } {
	return { verb, text: tr(KONTO_KEYS[verb]) };
}

function bedienbar(kanal: KanalId, ton: 'ok' | 'warn', statusText: string, ziel: string): KanalStatus {
	return { kanal, verbunden: true, ton, statusText, ziel, briefingGesperrt: false, alarmGesperrt: false, grund: null, alarmSperre: null, kontoLink: null };
}

/** Gesperrter Kanal: Briefing-Schalter aus/disabled, Alarm-Zelle „gesperrt: {Grund}“, Hinweis + Konto-Link. */
function gesperrt(
	kanal: KanalId,
	p: { ton: 'warn' | 'off'; statusText: string; ziel: string; grund: string; sperre: string; verb: KontoVerb }
): KanalStatus {
	return {
		kanal,
		verbunden: false,
		ton: p.ton,
		statusText: p.statusText,
		ziel: p.ziel,
		briefingGesperrt: true,
		alarmGesperrt: true,
		grund: p.grund,
		alarmSperre: tr('zustellung.gesperrt', { grund: p.sperre }),
		kontoLink: kontoLink(p.verb)
	};
}

/** Satzpunkt am Ende entfernen (Hinweis „Telegram-Chat fehlt.“ → Sperrgrund „Telegram-Chat fehlt“). */
const ohnePunkt = (s: string) => s.replace(/\.$/, '');

// ── Kuerzung fuer die Kanalzeile (#3202, Mockup Fassung 4) ──────────────────
// Nur die Kanalzeile kuerzt; Kontosettings und Versand-Dialoge zeigen weiterhin den Volltext.

/** „henning@example.com“ → „henning@…“; Lokalteil nie weiter gekuerzt; ohne „@“ oder leer → ''. */
export function adresseGekuerzt(mail: string | null | undefined): string {
	const s = (mail ?? '').trim();
	const at = s.indexOf('@');
	return at > 0 ? `${s.slice(0, at)}@…` : '';
}

// Landesvorwahlen mit 1 bzw. 2 Ziffern (ITU-T E.164); alle uebrigen haben 3 Ziffern.
const VORWAHL_1 = new Set(['1', '7']);
const VORWAHL_2 = new Set([
	'20', '27', '30', '31', '32', '33', '34', '36', '39', '40', '41', '43', '44', '45', '46', '47', '48', '49',
	'51', '52', '53', '54', '55', '56', '57', '58', '60', '61', '62', '63', '64', '65', '66', '81', '82', '84',
	'86', '90', '91', '92', '93', '94', '95', '98'
]);

/** „+491711234567“ → „+49 171 …“; ohne „+“ die ersten 3 Ziffern + „ …“; leer → ''. Nie der Volltext. */
export function nummerGekuerzt(nr: string | null | undefined): string {
	const s = (nr ?? '').trim();
	const ziffern = s.replace(/\D/g, '');
	if (!ziffern) return '';
	if (!s.startsWith('+')) return `${ziffern.slice(0, 3)} …`;
	const vorwahl = VORWAHL_1.has(ziffern[0])
		? ziffern.slice(0, 1)
		: VORWAHL_2.has(ziffern.slice(0, 2))
			? ziffern.slice(0, 2)
			: ziffern.slice(0, 3);
	const rest = ziffern.slice(vorwahl.length, vorwahl.length + 3);
	return rest ? `+${vorwahl} ${rest} …` : `+${vorwahl} …`;
}

function premiumStatus(p: ZustellungProfil): KanalStatus {
	// #3202 (Mockup Fassung 4): die Premium-Zeile zeigt nur den Status, nie die Rueckadresse.
	const ziel = '';
	const nichtVerbunden = tr('zustellung.status.nicht_verbunden');
	// Tarif-Gate zuerst, fail-closed ohne Tarifauskunft (premiumSmsAlarmGate.ts, AC-21).
	const gate = derivePremiumSmsAlarmGate(p);
	if (gate.disabled) {
		const grund = gate.hint ?? '';
		return gesperrt('premium_sms', { ton: 'off', statusText: nichtVerbunden, ziel, grund, sperre: grund, verb: 'pruefen' });
	}
	if (p.premium_sms_reply_state === 'fresh') {
		const d = p.premium_sms_reply_at ? new Date(p.premium_sms_reply_at) : null;
		const gueltig = d && !Number.isNaN(d.getTime());
		const datum = gueltig ? fmtDateNumeric(d, get(locale)) : '–';
		const zeit = gueltig ? fmtTime(d) : '–';
		return bedienbar('premium_sms', 'ok', tr('zustellung.premium.status', { datum, zeit }), ziel);
	}
	if (p.premium_sms_reply_state === 'stale') {
		// AC-20 (sicherheitsrelevant): eine verfallene Rueckadresse kann ein fremdes Geraet erreichen —
		// Briefing- UND Alarm-Zelle gesperrt (Bestandsregel premiumSmsChannelState.ts, Zweig stale).
		return gesperrt('premium_sms', {
			ton: 'warn',
			statusText: tr('zustellung.premium.status_verfallen'),
			ziel,
			grund: tr('zustellung.premium.verfallen_hinweis'),
			sperre: tr('zustellung.premium.verfallen'),
			verb: 'pruefen'
		});
	}
	// 'none' und Unbekanntes: noch nie gemeldet — ebenfalls nicht sendebereit.
	const grund = tr('versand.premium_sms.hinweis.nie_gemeldet');
	return gesperrt('premium_sms', { ton: 'off', statusText: nichtVerbunden, ziel, grund, sperre: grund, verb: 'pruefen' });
}

/** Kanalstatus aller vier Zeilen aus der EINEN Profil-Antwort (AC-14 bis AC-21).
 *  #3202: Ziele gekuerzt (Mockup Fassung 4). Keine Empfaengerzahl: `preset.empfaenger` ist seit #1452
 *  wirkungslos, versendet wird nur an die Konto-Adresse (PO-Korrektur 21.11.2026). */
export function kanalStatus(profil: ZustellungProfil | null | undefined): Record<KanalId, KanalStatus> {
	const p: ZustellungProfil = profil ?? {};
	const nichtVerbunden = tr('zustellung.status.nicht_verbunden');

	let email: KanalStatus;
	if (!p.mail_to) {
		const grund = tr('zustellung.grund.email_fehlt');
		email = gesperrt('email', { ton: 'off', statusText: nichtVerbunden, ziel: '', grund, sperre: ohnePunkt(grund), verb: 'verbinden' });
	} else {
		const ziel = adresseGekuerzt(p.mail_to);
		// Unbestaetigte Adresse wird beliefert (Bestandsverhalten), daher bedienbar mit Warnpunkt.
		email = p.email_verified
			? bedienbar('email', 'ok', tr('zustellung.status.bestaetigt'), ziel)
			: bedienbar('email', 'warn', tr('zustellung.status.unbestaetigt'), ziel);
	}

	let telegram: KanalStatus;
	if (p.telegram_chat_id) {
		// #3202 (PO-Entscheidung 20.11.2026): nur „verbunden“, nie die Chat-ID, kein Telegram-Name.
		telegram = bedienbar('telegram', 'ok', tr('zustellung.status.verbunden'), '');
	} else {
		const grund = tr('zustellung.grund.telegram_fehlt');
		telegram = gesperrt('telegram', { ton: 'off', statusText: nichtVerbunden, ziel: '', grund, sperre: ohnePunkt(grund), verb: 'verbinden' });
	}

	// SMS: Tarif zuerst, dann Nummer, dann Beweis per Code (#2406: „eingetragen“ ist nicht „sendebereit“).
	let sms: KanalStatus;
	const nummer = p.sms_to || p.pending_sms_to || '';
	if (p.sms_allowed === false) {
		const grund = tr('zustellung.grund.sms_tarif');
		sms = gesperrt('sms', { ton: 'off', statusText: nichtVerbunden, ziel: nummerGekuerzt(nummer), grund, sperre: grund, verb: 'pruefen' });
	} else if (!nummer) {
		const grund = tr('zustellung.grund.sms_fehlt');
		sms = gesperrt('sms', { ton: 'off', statusText: nichtVerbunden, ziel: '', grund, sperre: ohnePunkt(grund), verb: 'verbinden' });
	} else if (p.sms_to && p.sms_verified === true) {
		sms = bedienbar('sms', 'ok', tr('zustellung.status.bestaetigt'), nummerGekuerzt(p.sms_to));
	} else {
		const grund = tr('zustellung.grund.sms_unbestaetigt');
		sms = gesperrt('sms', {
			ton: 'warn',
			statusText: tr('zustellung.status.unbestaetigt'),
			ziel: nummerGekuerzt(nummer),
			grund,
			sperre: ohnePunkt(grund),
			verb: 'bestaetigen'
		});
	}

	return { email, telegram, sms, premium_sms: premiumStatus(p) };
}

// ── Formularstand aus dem gespeicherten Abo ─────────────────────────────────

/** Dringlichkeit eines Kanals; fehlend oder unbekannt = LOW (ADR-0046). */
export function dringlichkeitVon(thresholds: Record<string, string | undefined> | null | undefined, kanal: KanalId): Dringlichkeit {
	const w = thresholds?.[kanal];
	return w === 'MODERATE' || w === 'HIGH' || w === 'LOW' ? w : 'LOW';
}

function dringlichkeiten(thresholds: Record<string, string | undefined> | null | undefined): Record<KanalId, Dringlichkeit> {
	return {
		email: dringlichkeitVon(thresholds, 'email'),
		telegram: dringlichkeitVon(thresholds, 'telegram'),
		sms: dringlichkeitVon(thresholds, 'sms'),
		premium_sms: dringlichkeitVon(thresholds, 'premium_sms')
	};
}

function stille(von: string | null | undefined, bis: string | null | undefined): Pick<ZustellungStand, 'stilleAn' | 'stilleVon' | 'stilleBis'> {
	const an = !!von && !!bis;
	return { stilleAn: an, stilleVon: hhmm(von, STILLE_VON_STANDARD), stilleBis: hhmm(bis, STILLE_BIS_STANDARD) };
}

function cooldownVon(v: unknown): number {
	return typeof v === 'number' && Number.isFinite(v) ? v : COOLDOWN_STANDARD;
}

/** Stand eines Trips (Briefing-Felder unter `report_config`). */
export function standAusTrip(trip: Trip): ZustellungStand {
	const b = leseBriefingStartwerte(trip.report_config as Record<string, unknown> | null | undefined);
	const ac = reconstructTripAlertChannels(trip);
	return {
		morgenAn: b.morning_enabled,
		morgenZeit: b.morning_time,
		abendAn: b.evening_enabled,
		abendZeit: b.evening_time,
		briefing: { email: b.send_email, telegram: b.send_telegram, sms: b.send_sms, premium_sms: b.send_premium_sms },
		alarme: { email: !!ac.email, telegram: !!ac.telegram, sms: !!ac.sms, premium_sms: !!ac.premium_sms },
		dringlichkeit: dringlichkeiten(trip.alert_channel_thresholds as Record<string, string | undefined> | undefined),
		...stille(trip.alert_quiet_from, trip.alert_quiet_to),
		cooldown: cooldownVon(trip.alert_cooldown_minutes),
		endDate: null
	};
}

/** Stand eines Orts-Briefings (Felder top-level); `send_email` fehlt = an (AC-22/AC-23). */
export function standAusPreset(preset: ComparePreset): ZustellungStand {
	const ac = preset.alert_channels;
	// Bestandsregel wie compare/alarmePropsAus.ts (reconstructCompareAlertChannels): ohne
	// alert_channels erben die Alarme die Briefing-Kanaele, E-Mail an.
	const alarme: Record<KanalId, boolean> = ac
		? { email: ac.email ?? false, telegram: ac.telegram ?? false, sms: ac.sms ?? false, premium_sms: ac.premium_sms ?? false }
		: { email: true, telegram: preset.send_telegram ?? false, sms: preset.send_sms ?? false, premium_sms: preset.send_premium_sms ?? false };
	return {
		morgenAn: preset.morning_enabled ?? true,
		morgenZeit: hhmm(preset.morning_time, MORGEN_STANDARD),
		abendAn: preset.evening_enabled ?? false,
		abendZeit: hhmm(preset.evening_time, ABEND_STANDARD),
		briefing: {
			email: preset.send_email !== false,
			telegram: preset.send_telegram === true,
			sms: preset.send_sms === true,
			premium_sms: preset.send_premium_sms === true
		},
		alarme,
		dringlichkeit: dringlichkeiten(preset.alert_channel_thresholds as Record<string, string | undefined> | undefined),
		...stille(preset.alert_quiet_from, preset.alert_quiet_to),
		cooldown: cooldownVon(preset.alert_cooldown_minutes),
		endDate: preset.end_date ? preset.end_date : null
	};
}

// ── Zaehler, Kopf, Warnboxen ────────────────────────────────────────────────

/** Zaehlt nur Kanaele, die an UND verbunden sind (Spec §2). */
export function zaehler(stand: ZustellungStand, status: Record<KanalId, KanalStatus>): { briefing: number; alarme: number } {
	let briefing = 0;
	let alarme = 0;
	for (const k of KANAELE) {
		if (!status[k].verbunden) continue;
		if (stand.briefing[k]) briefing++;
		if (stand.alarme[k]) alarme++;
	}
	return { briefing, alarme };
}

/** „Briefings über 1 Kanal · Alarme über 2 Kanäle“ (Singular nur bei genau 1). */
export function tabellenKopf(z: { briefing: number; alarme: number }): string {
	return `${trn('zustellung.kanaele.kopf_briefing', z.briefing)} · ${trn('zustellung.kanaele.kopf_alarme', z.alarme)}`;
}

export type Warnbox = { titel: string; text: string };

/** Zwei getrennte Warnboxen, je nur bei 0 (AC-11, AC-12). */
export function warnboxen(z: { briefing: number; alarme: number }): { briefing: Warnbox | null; alarme: Warnbox | null } {
	return {
		briefing: z.briefing === 0 ? { titel: tr('zustellung.warnung.briefing.titel'), text: tr('zustellung.warnung.briefing.text') } : null,
		alarme: z.alarme === 0 ? { titel: tr('zustellung.warnung.alarme.titel'), text: tr('zustellung.warnung.alarme.text') } : null
	};
}

export type DringlichkeitZelle =
	| { art: 'strich' }
	| { art: 'segment'; wert: Dringlichkeit; optionen: { wert: Dringlichkeit; text: string }[] };

/** „–“ bei Alarm aus oder gesperrtem Kanal, sonst Segment gering · mittel · hoch (AC-17). */
export function dringlichkeitZelle(kanal: KanalId, stand: ZustellungStand, status: Record<KanalId, KanalStatus>): DringlichkeitZelle {
	if (!status[kanal].verbunden || !stand.alarme[kanal]) return { art: 'strich' };
	return {
		art: 'segment',
		wert: stand.dringlichkeit[kanal] ?? 'LOW',
		optionen: DRINGLICHKEITEN.map((wert) => ({ wert, text: tr(CHANNEL_THRESHOLD_KEYS[wert]) }))
	};
}

// ── Uhrzeit, Unterzeilen, Laufzeit ──────────────────────────────────────────

/** null = gueltig: „HH:MM“ oder „HH:MM:00“, Minute im Viertelstunden-Raster (AC-8). */
export function zeitFehler(wert: string): string | null {
	const m = /^(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(wert ?? '');
	const ok = !!m && Number(m[1]) <= 23 && [0, 15, 30, 45].includes(Number(m[2])) && (m[3] === undefined || m[3] === '00');
	return ok ? null : tr('zustellung.briefing.zeit_fehler');
}

/** Kontext-Unterschiede als Daten (Ratsche context_herkunft_zweige_eingefroren). */
const UNTERZEILEN: Record<Kontext, { morgen: MessageKey; abend: MessageKey }> = {
	route: { morgen: 'zustellung.briefing.route.morgen', abend: 'zustellung.briefing.route.abend' },
	vergleich: { morgen: 'zustellung.briefing.vergleich.morgen', abend: 'zustellung.briefing.vergleich.abend' }
};

export function briefingUnterzeilen(context: Kontext): { morgen: string; abend: string } {
	return { morgen: tr(UNTERZEILEN[context].morgen), abend: tr(UNTERZEILEN[context].abend) };
}

/** Trip: „{Daten}. Die Briefings enden nach der letzten Etappe. …“ aus den Etappendaten (AC-9). */
export function laufzeitTrip(trip: Pick<Trip, 'stages'>): string {
	// #2795 Bildvergleich Runde 1: kompakter Bereich mit Monatsname wie die Datumszeile im Hub-Kopf
	// („23.–26. Februar 2026“, eintaegig ein Datum) — derselbe Formatierer (tripHero), sprachabhaengig.
	const stages = (trip.stages ?? []).filter((s) => /^\d{4}-\d{2}-\d{2}/.test(s.date ?? ''));
	const text = stages.length === 0 ? tr('zustellung.laufzeit.ohne_daten') : formatDateRange({ stages });
	return tr('zustellung.laufzeit.trip', { daten: text });
}

/** Orte: „Bis auf Weiteres“ ohne Enddatum, sonst „Bis Datum“ (AC-10). */
export function laufzeitOrte(endDate: string | null | undefined): { wahl: 'offen' | 'datum'; satz: string } {
	return endDate
		? { wahl: 'datum', satz: tr('zustellung.laufzeit.datum_satz') }
		: { wahl: 'offen', satz: tr('zustellung.laufzeit.offen_satz') };
}
