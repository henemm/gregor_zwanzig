// Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Stufe 3.2: Bearbeitungsstand des Reiters.
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md, Datenfluss, Implementation Details §2/§4.
//
// EIN Stand fuer Trip (`route`) und Orts-Briefing (`vergleich`). Die Unterschiede der beiden
// Kontexte sind reine DATEN (wo Auswahl und Tagesfenster am Abo stehen) und stehen als Tabelle,
// nicht als Kontext-Weiche. Alle Operationen sind rein (neuer Stand, Eingabe unveraendert).
// Kein Browser-/SvelteKit-Import, lauffaehig unter node --experimental-strip-types.

import type { Ampel, AmpelMetrik, AmpelSeite } from '../../../types.ts';
import { vorlageIdFuer } from '../../alerts-tab/alarmAbAnzeige.ts';
import { amtlicheWarnungenAn, type WarnFelder } from './amtlicheWarnungen.ts';
import { abweichungsMenge } from './ampelSchreiben.ts';
import { klon } from './klon.ts';
import {
	alarmAbFuerAlle,
	auswahlLesen,
	verschmelzen,
	zaehleAbweichungenGegen,
	zuruecksetzen,
	STANDARD_VORLAGE,
	type AlarmAb,
	type AltSchluessel,
	type Kontext,
	type MetrikEigenschaften,
	type VorlagenAmpeln
} from './ampelModell.ts';

export type Tagesfenster = { start: number; end: number };

export type WetterStand = {
	vorlageId: string;
	/** Aufgeloeste Ampel (Vorlage + Abweichungen), `template` = vorlageId. */
	ampel: Ampel;
	auswahl: string[];
	warnungenAn: boolean;
	radarAn: boolean;
	tagesfenster: Tagesfenster;
};

/** Abo (Trip oder Vergleichs-Preset) in der Sicht des Reiters — locker typisiert. */
export type AboSicht = Record<string, unknown> & {
	display_config?: Record<string, unknown> | null;
	report_config?: Record<string, unknown> | null;
};

const STANDARD_FENSTER: Tagesfenster = { start: 4, end: 19 };

function zahl(x: unknown, ersatz: number): number {
	return typeof x === 'number' && Number.isFinite(x) ? x : ersatz;
}

/** Wo das Tagesfenster am Abo steht: Trip `report_config.day_window_*`, Orte top-level (Datenfluss). */
const FENSTER_QUELLE: Record<Kontext, (abo: AboSicht) => Record<string, unknown>> = {
	route: (abo) => abo.report_config ?? {},
	vergleich: (abo) => abo
};

export function tagesfensterLesen(context: Kontext, abo: AboSicht | null | undefined): Tagesfenster {
	const q = FENSTER_QUELLE[context](abo ?? {});
	return {
		start: zahl(q.day_window_start_hour, STANDARD_FENSTER.start),
		end: zahl(q.day_window_end_hour, STANDARD_FENSTER.end)
	};
}

/** Erst-Hydration aus dem gespeicherten Abo. `alsVorlage`: ohne eigene Auswahl gilt die Vorlage
 *  (Anlegen, AC-39). Vorlagen-ID wie Python `_aufloesen` (template → preset_name → profil). */
export function standAusAbo(context: Kontext, abo: AboSicht | null | undefined, vorlagen: VorlagenAmpeln, alt: AltSchluessel = {}): WetterStand {
	const dc = (abo?.display_config ?? {}) as Record<string, unknown>;
	const aboAmpel = (dc.ampel ?? null) as Ampel | null;
	const vorlageId = vorlageIdFuer(aboAmpel, dc.preset_name as string | undefined, abo?.profil as string | undefined, vorlagen);
	const ampel = verschmelzen(vorlagen[vorlageId] ?? vorlagen[STANDARD_VORLAGE], aboAmpel);
	ampel.template = vorlageId;
	return {
		vorlageId,
		ampel,
		auswahl: auswahlLesen(context, dc as Parameters<typeof auswahlLesen>[1], ampel, alt),
		warnungenAn: amtlicheWarnungenAn(abo as WarnFelder),
		radarAn: abo?.radar_alert_enabled === true,
		tagesfenster: tagesfensterLesen(context, abo)
	};
}

/** Abweichungsmenge des Stands gegen seine Vorlage (was gespeichert wird). */
export function mengeVon(s: WetterStand, vorlagen: VorlagenAmpeln): Ampel {
	return abweichungsMenge(vorlagen[s.vorlageId], s.ampel, s.auswahl);
}

/** Zahl der Abweichungen, wie der Picker sie zeigt (AC-28: sofort nach jeder Eingabe). */
export function abweichungenVon(s: WetterStand, vorlagen: VorlagenAmpeln): number {
	const v = vorlagen[s.vorlageId];
	return v ? zaehleAbweichungenGegen(v, mengeVon(s, vorlagen)) : 0;
}

/** Vorlage uebernehmen oder zuruecksetzen: Auswahl, Grenzen, Alarmstufen der Vorlage (AC-11/12). */
export function mitVorlage(s: WetterStand, vorlageId: string, vorlagen: VorlagenAmpeln): WetterStand {
	const r = zuruecksetzen(vorlageId, vorlagen);
	r.ampel.template = vorlageId;
	return { ...s, vorlageId, ampel: r.ampel, auswahl: r.auswahl };
}

/** Eigene Vorlage uebernehmen: ihre vollstaendige Ampel, Vorlage = ihre Systemvorlage. */
export function mitEigenerVorlage(s: WetterStand, ampel: Ampel, vorlagen: VorlagenAmpeln): WetterStand {
	const vorlageId = ampel?.template && ampel.template in vorlagen ? ampel.template : STANDARD_VORLAGE;
	const neu = klon(ampel);
	neu.template = vorlageId;
	const auswahl = Object.entries(neu.metrics ?? {}).filter(([, e]) => e?.enabled === true).map(([id]) => id);
	return { ...s, vorlageId, ampel: neu, auswahl };
}

/** „−": Metrik aus dem Briefing nehmen (AC-19). */
export function ohneMetrik(s: WetterStand, id: string): WetterStand {
	return { ...s, auswahl: s.auswahl.filter((x) => x !== id) };
}

/** „+": Metrik hinten anhaengen (AC-19). */
export function mitMetrik(s: WetterStand, id: string): WetterStand {
	return s.auswahl.includes(id) ? s : { ...s, auswahl: [...s.auswahl, id] };
}

/** „Alarm ab" einer Zeile. */
export function mitAlarmAb(s: WetterStand, id: string, stufe: AlarmAb): WetterStand {
	const ampel = klon(s.ampel);
	ampel.metrics = ampel.metrics ?? {};
	ampel.metrics[id] = { ...(ampel.metrics[id] ?? { enabled: false, lower: {}, upper: {} }), alarm_ab: stufe };
	return { ...s, ampel };
}

/** „Alarm ab fuer alle" (AC-14): nur alarmfaehige gewaehlte Metriken. */
export function mitAlarmAbFuerAlle(s: WetterStand, stufe: AlarmAb, eig: Record<string, MetrikEigenschaften>): WetterStand {
	return { ...s, ampel: alarmAbFuerAlle(s.ampel, s.auswahl, stufe, eig) };
}

export type Entwurf = { id: string; lower?: AmpelSeite | null; upper?: AmpelSeite | null; thunder?: Ampel['thunder'] };

/** Seite ohne ungueltige Eingaben (NaN) — fuer die Anzeige waehrend der Eingabe. */
function anzeigeSeite(seite: AmpelSeite | null | undefined): AmpelSeite {
	const aus: AmpelSeite = {};
	for (const [k, v] of Object.entries(seite ?? {})) {
		if (typeof v === 'number' && Number.isFinite(v)) aus[k as keyof AmpelSeite] = v;
	}
	return aus;
}

/** Stand mit offenem Entwurf aus „Grenzen ändern"; `fuerAnzeige` blendet ungueltige Felder aus. */
export function mitEntwurf(s: WetterStand, e: Entwurf | null, fuerAnzeige = false): WetterStand {
	if (!e) return s;
	const ampel = klon(s.ampel);
	if (e.thunder) ampel.thunder = { ...(ampel.thunder ?? {}), ...e.thunder };
	const zeile: AmpelMetrik = { ...(ampel.metrics?.[e.id] ?? { enabled: false, alarm_ab: 'never' }) };
	for (const k of ['lower', 'upper'] as const) {
		if (k in e) zeile[k] = fuerAnzeige ? anzeigeSeite(e[k]) : (e[k] ?? {});
	}
	ampel.metrics = { ...(ampel.metrics ?? {}), [e.id]: zeile };
	return { ...s, ampel };
}
