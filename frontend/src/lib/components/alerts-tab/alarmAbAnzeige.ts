// Issue #2793 S2b (Spec feat_2793_s2_alarm_stufenwechsel.md §6): die alte
// Tabelle „Alarm-Empfindlichkeit" ist bis S3a NUR LESBAR. Je Zeile steht die
// wirksame Stufe „Alarm ab" aus `ampel.metrics.<id>.alarm_ab` (Abo-Wert, sonst
// Vorgabe der Vorlage), Vorboten „kein Alarm (Vorbote)", die D4-Metriken
// (Nullgradgrenze, Beginn-Verschiebung) ihre heutige Empfindlichkeitsstufe.
//
// Reine Funktionen, EIN Code fuer Trip und Vergleich (context="route"|"vergleich").
// Kein Browser-/SvelteKit-Import — lauffaehig unter node --experimental-strip-types.

import type { AlertMetric } from '../../types.ts';
import rawAlertMetricMapping from '../../generated/alertMetricMapping.generated.json' with { type: 'json' };

/** Katalog-IDs mit Ampel-Ausloesung (Spec §1); `temperature_cold` ist die
 *  interne Kaelte-Pseudogroesse, deren Zeile `temperature` heisst. */
const AMPEL_ZEILEN: ReadonlySet<string> = new Set(['gust', 'precipitation', 'temperature', 'thunder']);

export type AlarmAb = 'never' | 'yellow' | 'orange' | 'red';

/** Was eine Zeile anzeigt: Ampel-Stufe (`null` = Vorlage noch nicht geladen,
 *  kein Abo-Wert), Vorbote oder (D4) die alte Stufe. */
export type AlarmAbZeile =
	| { art: 'ampel'; stufe: AlarmAb | null }
	| { art: 'vorbote' }
	| { art: 'd4'; level: string };

/** AlertMetric -> Katalog-ID der Ampel-Zeile (Spec §1-Tabelle). Die Basis-
 *  Zuordnung kommt aus der generierten Python-Quelle (`catalog_id_to_alert_metrics`,
 *  #1435 E5) — keine zweite Handkopie; ergaenzt um die Delta-/Sicht-/Neuschnee-
 *  Zeilen, die dort nicht alarmfaehig gelistet sind. */
const AMPEL_KATALOG_ID: Partial<Record<AlertMetric, string>> = {
	...Object.fromEntries(
		Object.entries(rawAlertMetricMapping as Record<string, string[]>)
			.filter(([katalogId]) => AMPEL_ZEILEN.has(katalogId))
			.flatMap(([katalogId, metriken]) => metriken.map((m) => [m, katalogId]))
	),
	precipitation_change: 'precipitation',
	temperature_change: 'temperature',
	wind_change: 'wind',
	visibility: 'visibility',
	fresh_snow: 'fresh_snow'
};

/** D4 (bis S7 auf der Δ-Logik): zeigen ihre heutige Stufe, nur lesbar. */
const D4_METRIKEN: ReadonlySet<AlertMetric> = new Set<AlertMetric>([
	'freezing_level',
	'snow_line',
	'thunder_onset',
	'precipitation_heavy_onset'
]);

/** Vorboten (ADR-0010) alarmieren nie. */
const VORBOTEN: ReadonlySet<AlertMetric> = new Set<AlertMetric>(['humidity']);
/** Kein eigener Ausloeser mehr (CAPE geht ueber die Gewitterstufe ein, ADR-0106 P1). */
const KEIN_AUSLOESER: ReadonlySet<AlertMetric> = new Set<AlertMetric>(['cape']);

const ALARM_AB_WERTE: ReadonlySet<string> = new Set(['never', 'yellow', 'orange', 'red']);
const PROFIL_ZU_VORLAGE: Record<string, string> = { summer_trekking: 'alpen-trekking' };
export const STANDARD_VORLAGE = 'allgemein';

type AmpelLike = { template?: unknown; metrics?: Record<string, { alarm_ab?: unknown } | null> } | null | undefined;
export type VorlagenAmpeln = Record<string, AmpelLike>;

/** Vorlagen-ID wie Python `app.ampel._aufloesen`: `ampel.template` ->
 *  Trip `preset_name` -> Vergleichs-`profil` -> „allgemein". Unbekannte IDs
 *  fallen auf „allgemein" (die Vorlagenliste kennt der Aufrufer). */
export function vorlageIdFuer(
	ampel: AmpelLike,
	presetName: string | null | undefined,
	profil: string | null | undefined,
	bekannt: VorlagenAmpeln
): string {
	const kandidaten: unknown[] = [ampel?.template, presetName];
	if (profil) {
		const key = String(profil).trim().toLowerCase();
		kandidaten.push(PROFIL_ZU_VORLAGE[key] ?? key);
	}
	for (const k of kandidaten) {
		if (typeof k === 'string' && k) return k in bekannt ? k : STANDARD_VORLAGE;
	}
	return STANDARD_VORLAGE;
}

function alarmAbAus(ampel: AmpelLike, katalogId: string): AlarmAb | null {
	const wert = ampel?.metrics?.[katalogId]?.alarm_ab;
	return typeof wert === 'string' && ALARM_AB_WERTE.has(wert) ? (wert as AlarmAb) : null;
}

/** GET /api/templates -> Vorlagen-ID -> Ampel (`alarm_ab` je Metrik). Fehler
 *  ergeben `{}` (Anzeige „Alarm ab: —", nie ein geratenes „Nie"). */
export async function ladeVorlagenAmpeln(holen: typeof fetch): Promise<VorlagenAmpeln> {
	try {
		const r = await holen('/api/templates', { credentials: 'same-origin' });
		const liste = r.ok ? ((await r.json()) as { id?: string; ampel?: AmpelLike }[]) : [];
		return Object.fromEntries((Array.isArray(liste) ? liste : []).filter((v) => v.id).map((v) => [v.id, v.ampel ?? null]));
	} catch {
		return {};
	}
}

/** Anzeige einer Zeile: Abo-`alarm_ab`, sonst Vorgabe der Vorlage, sonst „Nie". */
export function alarmAbZeile(
	metric: AlertMetric,
	aboAmpel: AmpelLike,
	vorlage: AmpelLike,
	levels: Partial<Record<AlertMetric, string>>
): AlarmAbZeile {
	if (VORBOTEN.has(metric)) return { art: 'vorbote' };
	if (D4_METRIKEN.has(metric)) return { art: 'd4', level: levels[metric] ?? 'standard' };
	const katalogId = AMPEL_KATALOG_ID[metric];
	if (KEIN_AUSLOESER.has(metric) || !katalogId) return { art: 'ampel', stufe: 'never' };
	const abo = alarmAbAus(aboAmpel, katalogId);
	if (abo) return { art: 'ampel', stufe: abo };
	if (!vorlage) return { art: 'ampel', stufe: null };
	return { art: 'ampel', stufe: alarmAbAus(vorlage, katalogId) ?? 'never' };
}
