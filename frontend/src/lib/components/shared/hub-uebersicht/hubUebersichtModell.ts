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
	sprungziel: { tab: 'wetter-metriken'; anchor: 'versand' };
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

/** Wortgleich zum Status-Badge im Trip-Kopf (TripStatusBadge.svelte, Entscheidung 2);
 *  bewacht durch den Render-Vergleich in hub_uebersicht_modell.test.ts (AC-5). */
const TRIP_STATUS_TEXT: Record<TripStatus, string> = {
	draft: 'Entwurf',
	planned: 'Geplant',
	active: 'Aktiv',
	paused: 'Pausiert',
	finished: 'Fertig',
	archived: 'Archiviert'
};

const DRAFT_TITEL_LANG = 'Noch nicht geplant';
const DRAFT_TITEL_KURZ = 'Nicht geplant';
const DRAFT_TEXT_LANG = 'Briefing-Uhrzeiten unter Wetter-Metriken im Abschnitt Versand festlegen.';
const DRAFT_TEXT_KURZ = 'Aktivierung offen';
const VERSAND_ZIEL = { tab: 'wetter-metriken', anchor: 'versand' } as const;

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

/** Hat der Trip Wetter-Änderungs-Alarme („bei Δ")? Spiegel der Backend-Regel
 *  (src/services/trip_alert.py has_preset/has_metric_levels/has_active_rules +
 *  report_config.alert_on_changes; fehlendes Feld lädt src/app/loader.py als True).
 *  Amtliche Warnungen zählen nicht. */
export function tripWetterAlarmAktiv(trip: Trip): boolean {
	const dc = trip.display_config;
	const hatPreset = !!dc?.alert_preset && dc.alert_preset !== 'deaktiviert';
	const hatStufen = !!dc?.metric_alert_levels && Object.keys(dc.metric_alert_levels).length > 0;
	const hatRegel = (trip.alert_rules ?? []).some((r) => r.enabled);
	const rc = trip.report_config;
	const beiAenderung = !!rc && (rc.alert_on_changes === undefined ? true : !!rc.alert_on_changes);
	return hatPreset || hatStufen || hatRegel || beiAenderung;
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
	if (reportSlotAktiv(rc, 'morning')) teile.push(`Morgen ${slotStunde(rc?.morning_time, 7)}`);
	if (reportSlotAktiv(rc, 'evening')) teile.push(`Abend ${slotStunde(rc?.evening_time, 18)}`);
	return teile.length > 0 ? teile.join(' · ') : '—';
}

function zuletztRaus(stand: LetzterVersandStand): string {
	if (stand.zustand !== 'geladen') return '—';
	return formatLastSent(neuesterPlanmaessigerEintrag(stand.eintraege)?.sent_at);
}

function versandKarte(entwurf: boolean, zeiten: string, naechster: string, testid: string): VersandKarte {
	return {
		titelKurz: entwurf ? DRAFT_TITEL_KURZ : zeiten,
		titelLang: entwurf ? DRAFT_TITEL_LANG : zeiten,
		beschreibungKurz: entwurf ? DRAFT_TEXT_KURZ : `Briefings ${zeiten}`,
		beschreibungLang: entwurf ? DRAFT_TEXT_LANG : `Briefings ${zeiten} · nächster Versand ${naechster}.`,
		testid,
		sprungziel: VERSAND_ZIEL
	};
}

/** Die fünf Kennzahlen in fester Reihenfolge; Briefings nur auf dem Desktop (Entscheidung 7). */
function kennzahlen(
	t: Record<KennzahlId, { kurz: string; lang: string; punkt?: Punkt }>,
	ids: Partial<Record<KennzahlId, { testid?: string; testidMobil?: string }>>
): Kennzahl[] {
	const labels: Array<[KennzahlId, string]> = [
		['status', 'Status'],
		['naechster-versand', 'Nächster Versand'],
		['briefings', 'Briefings'],
		['zuletzt-raus', 'Zuletzt raus'],
		['kanaele', 'Kanäle']
	];
	return labels.map(([id, label]) => ({ id, label, mobil: id !== 'briefings', ...t[id], ...ids[id] }));
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
				status: { ...gleich(TRIP_STATUS_TEXT[status]), punkt: status === 'active' ? 'good' : 'neutral' },
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

const VERGLEICH_STATUS: Record<CompareStatus, { kurz: string; lang: string; punkt: Punkt }> = {
	active: { kurz: 'Läuft autom.', lang: 'Läuft automatisch', punkt: 'good' },
	draft: { kurz: 'Entwurf', lang: 'Entwurf · nicht aktiv', punkt: 'neutral' },
	paused: { kurz: 'Pausiert', lang: 'Pausiert', punkt: 'neutral' }
};

/** Orte-Karte: Zahl und Namen nur der AUFLÖSBAREN Orte (Entscheidung 5, AC-4). */
function orteKarte(aufgeloesteOrte: Array<{ rank: number; loc?: { name: string } }>): Karte & { namen: string[] } {
	const namen = aufgeloesteOrte.flatMap(({ loc }) => (loc ? [loc.name] : []));
	const n = namen.length;
	return {
		eyebrow: 'Orte',
		titel: `${n} Kandidaten`,
		namen,
		beschreibungKurz: `${namen.slice(0, 2).join(' · ')}${n > 2 ? ` +${n - 2}` : ''}`,
		beschreibungLang: `${namen.slice(0, 3).join(' · ')}${n > 3 ? ` +${n - 3} weitere` : ''}`,
		sprungziel: { tab: 'orte' }
	};
}

function wertebereicheKarte(preset: ComparePreset): Karte {
	const anzahl = Object.keys(preset.display_config?.ideal_ranges ?? {}).length;
	return {
		eyebrow: 'Wertebereiche',
		titel: presetProfileLabel(preset.profil) || String(preset.profil ?? ''),
		beschreibungKurz: `${anzahl} Metriken · Markierung, kein Score`,
		beschreibungLang: `${anzahl} Metriken mit Idealbereich — im Briefing pro Wert markiert. Kein Score, kein Ranking.`,
		sprungziel: { tab: 'wertebereiche' }
	};
}

export function deriveVergleichKennzahlen(
	preset: ComparePreset,
	status: CompareStatus,
	briefing: NextBriefing | null | undefined,
	aufgeloesteOrte: Array<{ rank: number; loc?: { id: string; name: string } }>
): HubUebersichtModell {
	const zeiten = presetBriefingTimesLabel(preset);
	const naechster = formatNextBriefing(briefing, 'vergleich');
	return {
		kennzahlen: kennzahlen(
			{
				status: VERGLEICH_STATUS[status],
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
		wertebereicheKarte: wertebereicheKarte(preset)
	};
}
