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
	aktiveMetriken,
	alarmAbFuerAlle,
	ausgebbarTeilen,
	AUSWAHL_ABLEITUNG,
	auswahlLesen,
	vergleichsKatalogIds,
	verschmelzen,
	zaehleAbweichungenGegen,
	zuruecksetzen,
	STANDARD_VORLAGE,
	type AlarmAb,
	type AltSchluessel,
	type AuswahlQuellen,
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

/** Radar-Schalter lesen (#2800): am Trip gilt ein fehlendes Feld als an (Bestandstrips laufen
 *  seit #822 ohne Schalter), am Orts-Briefing als aus (`compare_radar_alert.py`). Dokumentierte
 *  Default-Asymmetrie, siehe api_contract.md. */
const RADAR_LESEN: Record<Kontext, (wert: unknown) => boolean> = {
	route: (wert) => wert !== false,
	vergleich: (wert) => wert === true
};

/** Gueltige Stunde wie Python (`type(x) is int`, 0-23). */
function stunde(x: unknown): x is number {
	return typeof x === 'number' && Number.isInteger(x) && x >= 0 && x <= 23;
}

/** Wo das Tagesfenster am Abo steht: Trip `report_config.day_window_*`, Orte top-level (Datenfluss). */
const FENSTER_QUELLE: Record<Kontext, (abo: AboSicht) => Record<string, unknown>> = {
	route: (abo) => abo.report_config ?? {},
	vergleich: (abo) => abo
};

/** Wirksames Tagesfenster wie Python `resolve_configured_window` (#3047 E5): nur ein gueltiges Paar
 *  (beide Stunden 0-23, Start != Ende) gilt, sonst 4-19 — ein halbes Paar wird nicht einzeln ergaenzt. */
export function tagesfensterLesen(context: Kontext, abo: AboSicht | null | undefined): Tagesfenster {
	const q = FENSTER_QUELLE[context](abo ?? {});
	const start = q.day_window_start_hour;
	const end = q.day_window_end_hour;
	return stunde(start) && stunde(end) && start !== end ? { start, end } : { ...STANDARD_FENSTER };
}

/** Vorlagen-Auswahl im Vergleich nur mit Groessen, die der Vergleich ausgeben kann (#3047 E6);
 *  ohne bekannten Katalog bleibt sie unveraendert. */
function nurAusgebbar(context: Kontext, auswahl: string[], alt: AltSchluessel): string[] {
	const ids = new Set(vergleichsKatalogIds(alt));
	return ids.size ? ausgebbarTeilen(context, auswahl, ids).zeilen : auswahl;
}

/** Erst-Hydration aus dem gespeicherten Abo. Ohne eigene Auswahl gilt der Mail-Standard
 *  (#3047 E1, `quellen.eig` fuer den Trip-Register-Standard); `quellen.alsVorlage`: die Vorlage
 *  (Anlege-Kette). Vorlagen-ID wie Python `_aufloesen` (template → preset_name → profil). */
export function standAusAbo(
	context: Kontext,
	abo: AboSicht | null | undefined,
	vorlagen: VorlagenAmpeln,
	alt: AltSchluessel = {},
	quellen: AuswahlQuellen = {}
): WetterStand {
	const dc = (abo?.display_config ?? {}) as Record<string, unknown>;
	const aboAmpel = (dc.ampel ?? null) as Ampel | null;
	const vorlageId = vorlageIdFuer(aboAmpel, dc.preset_name as string | undefined, abo?.profil as string | undefined, vorlagen);
	const ampel = verschmelzen(vorlagen[vorlageId] ?? vorlagen[STANDARD_VORLAGE], aboAmpel);
	ampel.template = vorlageId;
	const auswahl = auswahlLesen(context, dc as Parameters<typeof auswahlLesen>[1], ampel, alt, quellen);
	return {
		vorlageId,
		ampel,
		auswahl: quellen.alsVorlage ? nurAusgebbar(context, auswahl, alt) : auswahl,
		warnungenAn: amtlicheWarnungenAn(abo as WarnFelder),
		radarAn: RADAR_LESEN[context](abo?.radar_alert_enabled),
		tagesfenster: tagesfensterLesen(context, abo)
	};
}

/** Vorlage mit ausdruecklichem `enabled` je Groesse (sonst unveraendert). */
function mitEnabled(v: Ampel, ids: string[], an: (id: string) => boolean): Ampel {
	if (!ids.length) return v;
	return verschmelzen(v, { template: v.template, metrics: Object.fromEntries(ids.map((id) => [id, { enabled: an(id) }])) });
}

/** Wie der Kontext die Vorlage ausgibt (#3193, Tabelle statt Weiche):
 *  - route: die Kinder eines gewaehlten Elters gelten als gewaehlt (Python-Ableitung, p5c/p15);
 *  - vergleich: nicht ausgebbare Groessen (nicht im Katalog) sind neutral, ihr `enabled` folgt der
 *    Auswahl (#3047 E6: weggefiltert oder gesperrt erhalten ist keine Abweichung). Ohne bekannten
 *    Katalog bleibt die Rohvorlage (analog `nurAusgebbar`). */
const BASIS_IM_KONTEXT: Record<Kontext, (v: Ampel, auswahl: string[], alt: AltSchluessel) => Ampel> = {
	route: (v) => {
		const aktiv = aktiveMetriken(v);
		const kinder = AUSWAHL_ABLEITUNG.route(aktiv).filter((id) => !aktiv.includes(id));
		return mitEnabled(v, kinder, () => true);
	},
	vergleich: (v, auswahl, alt) => {
		const katalog = new Set(vergleichsKatalogIds(alt));
		if (!katalog.size) return v;
		const neutral = [...new Set([...Object.keys(v.metrics ?? {}), ...auswahl])].filter((id) => !katalog.has(id));
		return mitEnabled(v, neutral, (id) => auswahl.includes(id));
	}
};

/** Die EINE Vergleichsbasis „Vorlage im Kontext“ (#3193): Zaehler, Menge und Speicherweg messen
 *  ausschliesslich gegen sie. `aufgeloest` traegt die Zeilen der Basis, die der Stand noch nicht hat
 *  (ein abgeleitetes Kind ohne eigene Zeile ist keine Abweichung, sein „−“ schon). */
export function vorlageImKontext(
	s: WetterStand,
	vorlagen: VorlagenAmpeln,
	context: Kontext,
	alt: AltSchluessel = {}
): { vorlage: Ampel; aufgeloest: Ampel } {
	const vorlage = BASIS_IM_KONTEXT[context](vorlagen[s.vorlageId], s.auswahl, alt);
	const aufgeloest = klon(s.ampel);
	aufgeloest.metrics = aufgeloest.metrics ?? {};
	for (const [id, e] of Object.entries(vorlage.metrics ?? {})) if (!(id in aufgeloest.metrics)) aufgeloest.metrics[id] = klon(e);
	return { vorlage, aufgeloest };
}

/** Abweichungsmenge des Stands gegen die Vorlage im Kontext (was gespeichert wird). */
export function mengeVon(s: WetterStand, vorlagen: VorlagenAmpeln, context: Kontext, alt: AltSchluessel = {}): Ampel {
	const b = vorlageImKontext(s, vorlagen, context, alt);
	return abweichungsMenge(b.vorlage, b.aufgeloest, s.auswahl);
}

/** Zahl der Abweichungen, wie der Picker sie zeigt (AC-28: sofort nach jeder Eingabe): genau die
 *  Menge, die auch gespeichert wird (#3193). */
export function abweichungenVon(s: WetterStand, vorlagen: VorlagenAmpeln, context: Kontext, alt: AltSchluessel = {}): number {
	if (!vorlagen[s.vorlageId]) return 0;
	return zaehleAbweichungenGegen(vorlageImKontext(s, vorlagen, context, alt).vorlage, mengeVon(s, vorlagen, context, alt));
}

/** Vorlage uebernehmen oder zuruecksetzen: Auswahl, Grenzen, Alarmstufen der Vorlage (AC-11/12);
 *  im Vergleich nur ausgebbare Groessen (#3047 E6, `alt` = Vergleichs-Katalog). */
export function mitVorlage(s: WetterStand, vorlageId: string, vorlagen: VorlagenAmpeln, context: Kontext = 'route', alt: AltSchluessel = {}): WetterStand {
	const r = zuruecksetzen(vorlageId, vorlagen);
	r.ampel.template = vorlageId;
	return { ...s, vorlageId, ampel: r.ampel, auswahl: nurAusgebbar(context, AUSWAHL_ABLEITUNG[context](r.auswahl), alt) };
}

/** Eigene Vorlage uebernehmen: ihre vollstaendige Ampel, Vorlage = ihre Systemvorlage. */
export function mitEigenerVorlage(s: WetterStand, ampel: Ampel, vorlagen: VorlagenAmpeln, context: Kontext = 'route', alt: AltSchluessel = {}): WetterStand {
	const vorlageId = ampel?.template && ampel.template in vorlagen ? ampel.template : STANDARD_VORLAGE;
	const neu = klon(ampel);
	neu.template = vorlageId;
	const auswahl = Object.entries(neu.metrics ?? {}).filter(([, e]) => e?.enabled === true).map(([id]) => id);
	return { ...s, vorlageId, ampel: neu, auswahl: nurAusgebbar(context, AUSWAHL_ABLEITUNG[context](auswahl), alt) };
}

/** „−": Metrik aus dem Briefing nehmen (AC-19). */
export function ohneMetrik(s: WetterStand, id: string): WetterStand {
	return { ...s, auswahl: s.auswahl.filter((x) => x !== id) };
}

/** „+": Metrik hinten anhaengen (AC-19); im Trip mit den Kindern, die Python aus ihr ableitet
 *  (#3047 p5c — vorhandene Auswahl bleibt, auch ein bewusst abgewaehltes Kind eines anderen Elters). */
export function mitMetrik(s: WetterStand, id: string, context: Kontext = 'route'): WetterStand {
	if (s.auswahl.includes(id)) return s;
	const neu = AUSWAHL_ABLEITUNG[context]([id]).filter((x) => x === id || !s.auswahl.includes(x));
	return { ...s, auswahl: [...s.auswahl, ...neu] };
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
