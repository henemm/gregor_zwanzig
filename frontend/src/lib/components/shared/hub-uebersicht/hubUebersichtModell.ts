// hubUebersichtModell — Issue #2682 (Epic #2345): EIN Modell der Hub-Übersicht
// für Trip (route) und Ortsvergleich (vergleich).
// Spec: docs/specs/modules/feat_2682_hub_uebersicht_geteilt.md (Entscheidungen 2–7)
//
// Reine Ableiter, kein Netz, kein DOM. Der Baustein HubUebersicht.svelte
// verzweigt nicht nach der Art, er rendert nur dieses Modell: Kennzahlen
// (Kurzform mobil, Langform Desktop), Versand-Karte und — nur beim Vergleich —
// Orte- und Wertebereiche-Karte (Vergleichs-Hauptfläche).
//
// Jeder Text ist aus den Eingabedaten abgeleitet (AC-15): keine festen Kanäle,
// kein Festtext ohne Datenquelle.

import type { ComparePreset, Trip } from '../../../types.ts';
import type { TripStatus } from '../../../utils/tripStatus.ts';
import { reportSlotAktiv } from '../../../utils/reportSlotAktiv.ts';
import type { BriefingHistoryEntry } from '../briefingHistory.ts';
import { formatNextBriefing, type NextBriefing } from '../versand-tab/nextBriefingText.ts';
import {
	channelNamesLabel,
	formatLastSent,
	presetBriefingTimesLabel,
	presetProfileLabel,
	type CompareStatus
} from '../../compare/subscriptionHelpers.ts';
// Issue #2659 (i18n F10): Texte je Aufruf aus dem Katalog (aktionen.*/home.*/trip.status.*,
// vergleich.hub.*); der Baustein liest `$locale` und rechnet beim Sprachwechsel neu.
import { tr, trn, type MessageKey } from '../../../i18n/index.ts';
import { alarmZaehler, type MetrikEigenschaften, type VorlagenAmpeln } from '../wetter-tab/ampelModell.ts';
import { standAusAbo, type AboSicht } from '../wetter-tab/wetterZustand.ts';

export type KennzahlId = 'status' | 'naechster-versand' | 'briefings' | 'zuletzt-raus' | 'kanaele';
export type Sprungziel = { tab: string; anchor?: 'versand' };
/** Ton des Punkts vor dem Wert; fehlt ⇒ Wert ohne Punkt. */
export type Punkt = 'good' | 'neutral';

export interface Kennzahl {
	id: KennzahlId;
	label: string;
	kurz: string;
	lang: string;
	mobil: boolean;
	testid?: string;
	testidMobil?: string;
	punkt?: Punkt;
}

export interface VersandKarte {
	titelKurz: string;
	titelLang: string;
	beschreibungKurz: string;
	beschreibungLang: string;
	testid: string;
	sprungziel: { tab: 'zustellung'; anchor: 'versand' };
}

/** Zusammenfassungs-Karte der Vergleichs-Hauptfläche (Orte, Wertebereiche). */
export interface Karte {
	eyebrow: string;
	titel: string;
	beschreibungKurz: string;
	beschreibungLang: string;
	sprungziel: Sprungziel;
}

export interface HubUebersichtModell {
	kennzahlen: Kennzahl[];
	versandKarte: VersandKarte;
	testidPraefix: 'compare' | 'hub-uebersicht';
	rasterTestid: string;
	stapelTestid: string;
	orteKarte?: Karte & { namen: string[] };
	wertebereicheKarte?: Karte;
}

/** Stand der Versand-Historie — strukturell gleich dem Lader (briefingHistoryLader.svelte.ts). */
export type LetzterVersandStand = {
	zustand: 'laedt' | 'geladen' | 'fehler';
	eintraege: BriefingHistoryEntry[];
};

export type Kanal = 'email' | 'telegram' | 'sms' | 'premium_sms';

const KANAL_NAMEN: Record<Kanal, string> = {
	email: 'Email',
	telegram: 'Telegram',
	sms: 'SMS',
	premium_sms: 'Premium-SMS'
};

/** Wortgleich zum Status-Schild im Kopf (shared/status-schild/StatusSchild.svelte, Entscheidung 2);
 *  bewacht durch den Render-Vergleich in hub_uebersicht_modell.test.ts (AC-5). */
const TRIP_STATUS_TEXT: Record<TripStatus, MessageKey> = {
	draft: 'trip.status.draft',
	planned: 'trip.status.planned',
	active: 'trip.status.active',
	paused: 'trip.status.paused',
	finished: 'trip.status.finished',
	archived: 'trip.status.archived'
};
// #2794 S3a: Versand-Abschnitt im Reiter Zustellung, Wertebereiche im Reiter Wetter.
const VERSAND_ZIEL = { tab: 'zustellung', anchor: 'versand' } as const;

/** EINE Regel für „Zuletzt raus" (Entscheidung 3): neuester Eintrag mit on_demand !== true. */
export function neuesterPlanmaessigerEintrag(eintraege: BriefingHistoryEntry[]): BriefingHistoryEntry | null {
	for (let i = eintraege.length - 1; i >= 0; i--) {
		if (eintraege[i].on_demand !== true) return eintraege[i];
	}
	return null;
}

/** Briefing-Kanäle eines Trips aus report_config (einzige Wahrheit); E-Mail gilt als aktiv,
 *  solange send_email !== false. */
export function tripBriefingKanaele(trip: Trip): Kanal[] {
	const rc = trip.report_config ?? {};
	const kanaele: Kanal[] = [];
	if (rc.send_email !== false) kanaele.push('email');
	if (rc.send_telegram === true) kanaele.push('telegram');
	if (rc.send_sms === true) kanaele.push('sms');
	if (rc.send_premium_sms === true) kanaele.push('premium_sms');
	return kanaele;
}

/** Alert-Kanäle eines Trips: eigener Satz `alert_channels` (premium_sms fehlend = AUS, types.ts D4),
 *  sonst (Altbestand) die Briefing-Kanäle. */
export function tripAlertKanaele(trip: Trip): Kanal[] {
	const ac = trip.alert_channels;
	if (!ac) return tripBriefingKanaele(trip);
	return (['email', 'telegram', 'sms', 'premium_sms'] as const).filter((k) => ac[k] === true);
}

/** „Alarm ab"-Zähler des Reiters Wetter auf der aufgelösten Ampel des Trips (Issue #2794 U4):
 *  dieselbe Funktion `alarmZaehler` auf `standAusAbo`, kein zweites Rechenmodell.
 *  `null` = Vorlagen oder Metrik-Katalog nicht geladen. */
function tripAlarmZaehler(
	trip: Trip,
	vorlagen: VorlagenAmpeln | null | undefined,
	eig: Record<string, MetrikEigenschaften> | null | undefined
): ReturnType<typeof alarmZaehler> | null {
	if (!vorlagen || !eig || Object.keys(vorlagen).length === 0) return null;
	const stand = standAusAbo('route', trip as unknown as AboSicht, vorlagen);
	return alarmZaehler(stand.ampel, stand.auswahl, eig);
}

/** Text der Alarm-Zeile der Trip-Übersicht = Zähler des Reiters Wetter; Ladefehler ⇒ „—". */
export function tripAlarmAbText(
	trip: Trip,
	vorlagen: VorlagenAmpeln | null | undefined,
	eig: Record<string, MetrikEigenschaften> | null | undefined
): string {
	const z = tripAlarmZaehler(trip, vorlagen, eig);
	if (!z) return '—';
	return tr(z.schluessel as MessageKey, z.werte);
}

/** Hat der Trip Wetter-Änderungs-Alarme? Spiegel der Backend-Regel
 *  (src/services/trip_alert.py has_preset/has_metric_levels/has_active_rules +
 *  report_config.alert_on_changes; fehlendes Feld lädt src/app/loader.py als True)
 *  ODER Ampel-Alarmquelle (`ampel_alarmquelle_aktiv`: nur mit `display_config.ampel`,
 *  mindestens eine gewählte, alarmfähige Metrik mit „Alarm ab" ≠ nie auf der aufgelösten Ampel).
 *  Ohne geladene Vorlagen/Katalog zählen nur die bisherigen Quellen. Amtliche Warnungen zählen nicht. */
export function tripWetterAlarmAktiv(
	trip: Trip,
	vorlagen?: VorlagenAmpeln | null,
	eig?: Record<string, MetrikEigenschaften> | null
): boolean {
	const dc = trip.display_config;
	const hatPreset = !!dc?.alert_preset && dc.alert_preset !== 'deaktiviert';
	const hatStufen = !!dc?.metric_alert_levels && Object.keys(dc.metric_alert_levels).length > 0;
	const hatRegel = (trip.alert_rules ?? []).some((r) => r.enabled);
	const rc = trip.report_config;
	const beiAenderung = !!rc && (rc.alert_on_changes === undefined ? true : !!rc.alert_on_changes);
	if (hatPreset || hatStufen || hatRegel || beiAenderung) return true;
	// Wie der Server: die Ampel-Alarmquelle greift nur, wenn das Abo den Schlüssel `ampel` trägt.
	if ((dc as { ampel?: unknown } | undefined)?.ampel == null) return false;
	const z = tripAlarmZaehler(trip, vorlagen, eig);
	return z?.art === 'zaehler' && Number(z.werte.ausloesend) > 0;
}

/** Slot-Stunde als „HH:00" — der Versand nutzt nur die Stunde (Default 7/18 wie der Scheduler). */
export function slotStunde(raw: string | undefined, standardStunde: number): string {
	const m = /^(\d{1,2}):/.exec(raw ?? '');
	const stunde = m ? Number(m[1]) : standardStunde;
	return `${String(stunde).padStart(2, '0')}:00`;
}

function tripBriefingZeiten(trip: Trip): string {
	const rc = trip.report_config;
	const teile: string[] = [];
	if (reportSlotAktiv(rc, 'morning')) teile.push(`${tr('aktionen.historie.morgen')} ${slotStunde(rc?.morning_time, 7)}`);
	if (reportSlotAktiv(rc, 'evening')) teile.push(`${tr('aktionen.historie.abend')} ${slotStunde(rc?.evening_time, 18)}`);
	return teile.length > 0 ? teile.join(' · ') : '—';
}

function zuletztRaus(stand: LetzterVersandStand): string {
	if (stand.zustand !== 'geladen') return '—';
	return formatLastSent(neuesterPlanmaessigerEintrag(stand.eintraege)?.sent_at);
}

function versandKarte(entwurf: boolean, zeiten: string, naechster: string, testid: string): VersandKarte {
	return {
		titelKurz: entwurf ? tr('aktionen.uebersicht.nicht_geplant') : zeiten,
		titelLang: entwurf ? tr('aktionen.uebersicht.noch_nicht_geplant') : zeiten,
		beschreibungKurz: entwurf ? tr('aktionen.uebersicht.aktivierung_offen') : tr('aktionen.uebersicht.briefings_zeiten', { zeiten }),
		beschreibungLang: entwurf
			? tr('aktionen.uebersicht.uhrzeiten_festlegen')
			: tr('aktionen.uebersicht.briefings_naechster', { zeiten, naechster }),
		testid,
		sprungziel: VERSAND_ZIEL
	};
}

/** Die fünf Kennzahlen in fester Reihenfolge; Briefings nur auf dem Desktop (Entscheidung 7). */
function kennzahlen(
	t: Record<KennzahlId, { kurz: string; lang: string; punkt?: Punkt }>,
	ids: Partial<Record<KennzahlId, { testid?: string; testidMobil?: string }>>
): Kennzahl[] {
	const labels: Array<[KennzahlId, MessageKey]> = [
		['status', 'aktionen.uebersicht.status'],
		['naechster-versand', 'home.hero.naechster_versand'],
		['briefings', 'aktionen.uebersicht.briefings'],
		['zuletzt-raus', 'aktionen.uebersicht.zuletzt_raus'],
		['kanaele', 'home.hero.kanaele']
	];
	return labels.map(([id, key]) => ({ id, label: tr(key), mobil: id !== 'briefings', ...t[id], ...ids[id] }));
}

const gleich = (text: string) => ({ kurz: text, lang: text });
const kanalWert = (text: string) => ({ ...gleich(text), punkt: text === '—' ? undefined : ('good' as const) });

export function deriveRouteKennzahlen(
	trip: Trip,
	status: TripStatus,
	briefing: NextBriefing | null | undefined,
	letzterVersand: LetzterVersandStand
): HubUebersichtModell {
	const zeiten = tripBriefingZeiten(trip);
	const naechster = formatNextBriefing(briefing, 'route');
	const namen = tripBriefingKanaele(trip).map((k) => KANAL_NAMEN[k]);
	const p = 'hub-uebersicht';
	const ids = (id: KennzahlId) => ({ testid: `${p}-stat-${id}`, testidMobil: `${p}-stat-${id}-mobile` });
	return {
		kennzahlen: kennzahlen(
			{
				status: { ...gleich(tr(TRIP_STATUS_TEXT[status])), punkt: status === 'active' ? 'good' : 'neutral' },
				'naechster-versand': gleich(naechster),
				briefings: gleich(zeiten),
				'zuletzt-raus': gleich(zuletztRaus(letzterVersand)),
				kanaele: kanalWert(namen.length > 0 ? namen.join(' · ') : '—')
			},
			{
				status: ids('status'),
				'naechster-versand': ids('naechster-versand'),
				briefings: { testid: `${p}-stat-briefings` },
				'zuletzt-raus': ids('zuletzt-raus'),
				kanaele: ids('kanaele')
			}
		),
		versandKarte: versandKarte(status === 'draft', zeiten, naechster, `${p}-versand-edit`),
		testidPraefix: p,
		rasterTestid: `${p}-monitoring-mobile`,
		stapelTestid: `${p}-summary-mobile`
	};
}

const VERGLEICH_STATUS: Record<CompareStatus, { kurz: MessageKey; lang: MessageKey; punkt: Punkt }> = {
	active: { kurz: 'vergleich.hub.laeuft_autom', lang: 'vergleich.hub.laeuft_automatisch', punkt: 'good' },
	draft: { kurz: 'trip.status.draft', lang: 'vergleich.hub.entwurf', punkt: 'neutral' },
	paused: { kurz: 'trip.status.paused', lang: 'trip.status.paused', punkt: 'neutral' }
};
function vergleichStatus(status: CompareStatus): { kurz: string; lang: string; punkt: Punkt } {
	const s = VERGLEICH_STATUS[status];
	return { kurz: tr(s.kurz), lang: tr(s.lang), punkt: s.punkt };
}

/** Orte-Karte: Zahl und Namen nur der AUFLÖSBAREN Orte (Entscheidung 5, AC-4). */
function orteKarte(aufgeloesteOrte: Array<{ rank: number; loc?: { name: string } }>): Karte & { namen: string[] } {
	const namen = aufgeloesteOrte.flatMap(({ loc }) => (loc ? [loc.name] : []));
	const n = namen.length;
	return {
		eyebrow: tr('aktionen.reiter.orte'),
		titel: trn('vergleich.hub.kandidaten', n),
		namen,
		beschreibungKurz: `${namen.slice(0, 2).join(' · ')}${n > 2 ? ` +${n - 2}` : ''}`,
		beschreibungLang: `${namen.slice(0, 3).join(' · ')}${n > 3 ? ` ${tr('vergleich.hub.weitere', { anzahl: n - 3 })}` : ''}`,
		sprungziel: { tab: 'orte' }
	};
}

/** Karte „Wetter" (#2794 Fix-Loop B4): Zahl der Metriken im Briefing aus `standAusAbo`
 *  (dieselbe Auswahl wie der Reiter Wetter), nicht aus den alten `ideal_ranges`.
 *  Vorlagen nicht geladen (fehlt/null/leer) ⇒ „—" statt einer erfundenen Zahl. Liest nur. */
function wertebereicheKarte(preset: ComparePreset, vorlagen: VorlagenAmpeln | null | undefined): Karte {
	const geladen = !!vorlagen && Object.keys(vorlagen).length > 0;
	const anzahl = geladen ? standAusAbo('vergleich', preset as unknown as AboSicht, vorlagen).auswahl.length : null;
	return {
		eyebrow: tr('aktionen.reiter.wetter'),
		titel: presetProfileLabel(preset.profil) || String(preset.profil ?? ''),
		beschreibungKurz: anzahl === null ? '—' : trn('vergleich.hub.wertebereiche_kurz', anzahl),
		beschreibungLang: anzahl === null ? '—' : trn('vergleich.hub.wertebereiche_lang', anzahl),
		sprungziel: { tab: 'wetter' }
	};
}

export function deriveVergleichKennzahlen(
	preset: ComparePreset,
	status: CompareStatus,
	briefing: NextBriefing | null | undefined,
	aufgeloesteOrte: Array<{ rank: number; loc?: { id: string; name: string } }>,
	vorlagen?: VorlagenAmpeln | null
): HubUebersichtModell {
	const zeiten = presetBriefingTimesLabel(preset);
	const naechster = formatNextBriefing(briefing, 'vergleich');
	return {
		kennzahlen: kennzahlen(
			{
				status: vergleichStatus(status),
				'naechster-versand': gleich(naechster),
				briefings: gleich(zeiten),
				'zuletzt-raus': gleich(formatLastSent(preset.letzter_versand)),
				kanaele: kanalWert(channelNamesLabel(preset))
			},
			{
				briefings: { testid: 'compare-detail-stat-briefings' },
				kanaele: { testid: 'compare-detail-stat-kanaele', testidMobil: 'compare-detail-stat-kanaele-mobile' }
			}
		),
		versandKarte: versandKarte(status === 'draft', zeiten, naechster, 'compare-hub-versand-edit'),
		testidPraefix: 'compare',
		rasterTestid: 'compare-detail-monitoring-mobile',
		stapelTestid: 'compare-detail-summary-mobile',
		orteKarte: orteKarte(aufgeloesteOrte),
		wertebereicheKarte: wertebereicheKarte(preset, vorlagen)
	};
}
