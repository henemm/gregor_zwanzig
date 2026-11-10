// Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): Speicher-Payloads des Reiters und des Dialogs.
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md, Datenfluss, Implementation Details §1/§2/§5.
//
// Die Auswahl steht in ZWEI Quellen und wird konsistent geschrieben (AC-37):
//   - `metrics[]` (Trip) bzw. `active_metrics` (Orts-Briefing) als vollstaendige Liste
//     (Reihenfolge der bestehenden Liste, neue Metriken hinten, uebrige Eintragsfelder bleiben),
//   - `ampel` als VOLLSTAENDIGE minimale Abweichungsmenge gegen die Vorlage (der Server
//     ersetzt `ampel` als Ganzes), `ampel.metrics.<id>.enabled` nur bei Abweichung.
// Kein Browser-/SvelteKit-Import, lauffaehig unter node --experimental-strip-types.

import type { Ampel, AmpelMetrik, AmpelSeite } from './ampelModell.ts';
import { aktiveMetriken, gleicheSeite } from './ampelModell.ts';
import { amtlicheWarnungenFelder, type WarnFelder } from './amtlicheWarnungen.ts';

const OHNE_ZEILE: AmpelMetrik = { enabled: false, lower: {}, upper: {}, alarm_ab: 'never' };

/** Seite fuer die Menge: nur gesetzte Grenzen; ganz offen = `null` (Vorlagen-Grenze kommt nicht zurueck). */
function seiteFuerMenge(seite: AmpelSeite | null | undefined): AmpelSeite | null {
	const aus: AmpelSeite = {};
	for (const [k, v] of Object.entries(seite ?? {})) if (v !== null && v !== undefined) aus[k as keyof AmpelSeite] = v;
	return Object.keys(aus).length ? aus : null;
}

/** Abweichende Felder einer Zeile gegen die Vorlagen-Zeile. */
function zeilenAbweichung(a: AmpelMetrik, v: AmpelMetrik, an: boolean): AmpelMetrik {
	const d: AmpelMetrik = {};
	if (an !== (v.enabled === true)) d.enabled = an;
	for (const k of ['lower', 'upper'] as const) {
		if (!gleicheSeite(a[k], v[k])) d[k] = seiteFuerMenge(a[k]);
	}
	if (a.alarm_ab && a.alarm_ab !== v.alarm_ab) d.alarm_ab = a.alarm_ab;
	return d;
}

/** Minimale, vollstaendige Abweichungsmenge des Bearbeitungsstands gegen die Vorlage. */
export function abweichungsMenge(vorlage: Ampel, aufgeloest: Ampel, auswahl: string[]): Ampel {
	const menge: Ampel = { template: vorlage.template };
	const metrics: Record<string, AmpelMetrik> = {};
	const ids = new Set([...Object.keys(aufgeloest?.metrics ?? {}), ...auswahl]);
	for (const id of ids) {
		const a = aufgeloest?.metrics?.[id] ?? OHNE_ZEILE;
		const d = zeilenAbweichung(a, vorlage.metrics?.[id] ?? OHNE_ZEILE, auswahl.includes(id));
		if (Object.keys(d).length) metrics[id] = d;
	}
	if (Object.keys(metrics).length) menge.metrics = metrics;
	const thunder: NonNullable<Ampel['thunder']> = {};
	for (const k of ['mittel', 'hoch'] as const) {
		const f = aufgeloest?.thunder?.[k];
		if (f && f !== vorlage.thunder?.[k]) thunder[k] = f;
	}
	if (Object.keys(thunder).length) menge.thunder = thunder;
	return menge;
}

type TripMetrik = { metric_id: string; enabled: boolean } & Record<string, unknown>;

/** Trip `metrics[]`: bestehende Eintraege in ihrer Reihenfolge (nur `enabled` neu), neue hinten. */
function tripMetriken(bestand: TripMetrik[] | undefined, auswahl: string[]): TripMetrik[] {
	const liste = (Array.isArray(bestand) ? bestand : []).map((e) => ({ ...structuredClone(e), enabled: auswahl.includes(e.metric_id) }));
	const da = new Set(liste.map((e) => e.metric_id));
	for (const id of auswahl) if (!da.has(id)) liste.push({ metric_id: id, enabled: true });
	return liste;
}

type VergleichMetrik = { metric_id: string; aggregation: string } & Record<string, unknown>;

/** Vergleich `active_metrics`: bestehende Eintraege der Auswahl in ihrer Reihenfolge, neue hinten. */
function vergleichMetriken(bestand: VergleichMetrik[] | undefined, auswahl: string[], aggregationFuer: (id: string) => string): VergleichMetrik[] {
	const liste = (Array.isArray(bestand) ? bestand : []).filter((e) => auswahl.includes(e.metric_id)).map((e) => structuredClone(e));
	const da = new Set(liste.map((e) => e.metric_id));
	for (const id of auswahl) if (!da.has(id)) liste.push({ metric_id: id, aggregation: aggregationFuer(id) });
	return liste;
}

type Tagesfenster = { start: number; end: number };

export type TripSpeicherEingabe = {
	vorlage: Ampel;
	aufgeloest: Ampel;
	auswahl: string[];
	displayConfig: { metrics?: TripMetrik[] } & Record<string, unknown>;
	reportConfig: Record<string, unknown> | null | undefined;
	warnFelder: WarnFelder | null | undefined;
	warnungenAn: boolean;
	tagesfenster: Tagesfenster;
};

/** Trip: zwei disjunkte PUTs (`/weather-config` mit `ampel` + `metrics`, danach `/trips/{id}`
 *  mit Warn-Feldern und `report_config`). Fremde `display_config`-Schluessel sendet der Reiter nicht. */
export function tripSpeicherPayload(e: TripSpeicherEingabe) {
	const warn = amtlicheWarnungenFelder(e.warnungenAn, e.warnFelder);
	return {
		weatherConfig: {
			ampel: abweichungsMenge(e.vorlage, e.aufgeloest, e.auswahl),
			metrics: tripMetriken(e.displayConfig?.metrics, e.auswahl)
		},
		tripFelder: {
			official_alerts_enabled: warn.official_alerts_enabled,
			official_warnings: warn.official_warnings,
			report_config: {
				...structuredClone(e.reportConfig ?? {}),
				day_window_start_hour: e.tagesfenster.start,
				day_window_end_hour: e.tagesfenster.end
			}
		}
	};
}

export type VergleichSpeicherEingabe = {
	vorlage: Ampel;
	aufgeloest: Ampel;
	auswahl: string[];
	displayConfig: { active_metrics?: VergleichMetrik[] } & Record<string, unknown>;
	aggregationFuer: (id: string) => string;
	warnFelder: WarnFelder | null | undefined;
	warnungenAn: boolean;
	radarAn: boolean;
	tagesfenster: Tagesfenster;
};

/** Orts-Briefing: ein Eintrag in der Hub-Schreibschlange (Read-Modify-Write: ganze `display_config`
 *  mit neuer `ampel` und `active_metrics`, Warn-Felder, Radar, Tagesfenster top-level). */
export function vergleichSpeicherPayload(e: VergleichSpeicherEingabe) {
	const warn = amtlicheWarnungenFelder(e.warnungenAn, e.warnFelder);
	return {
		display_config: {
			...structuredClone(e.displayConfig ?? {}),
			ampel: abweichungsMenge(e.vorlage, e.aufgeloest, e.auswahl),
			active_metrics: vergleichMetriken(e.displayConfig?.active_metrics, e.auswahl, e.aggregationFuer)
		},
		official_alerts_enabled: warn.official_alerts_enabled,
		official_warnings: warn.official_warnings,
		radar_alert_enabled: e.radarAn,
		day_window_start_hour: e.tagesfenster.start,
		day_window_end_hour: e.tagesfenster.end
	};
}

// ── Dialog „Als eigene Vorlage speichern“ (AC-42) ────────────────────────────

export type EigeneVorlageEingabe = {
	name: string;
	beschreibung: string;
	alsStandard: boolean;
	kind: 'route' | 'vergleich';
	ampel: Ampel;
};

/** Body fuer POST /api/metric-presets: aufgeloeste Abo-Ampel + Art, ohne Zeithorizonte und Zusammenfassung. */
export function eigeneVorlagePayload(e: EigeneVorlageEingabe) {
	const beschreibung = (e.beschreibung ?? '').trim();
	const ampel = structuredClone(e.ampel);
	return {
		name: (e.name ?? '').trim(),
		...(beschreibung ? { description: beschreibung } : {}),
		is_default: e.alsStandard === true,
		kind: e.kind,
		ampel,
		metrics: aktiveMetriken(ampel).map((id) => ({ metric_id: id, enabled: true, use_friendly_format: false }))
	};
}

/** Pflichtfeld Name: Katalogschluessel bei leerem Namen, sonst `null`. */
export function vorlagenNameFehler(name: string): string | null {
	return (name ?? '').trim() ? null : 'wetter.dialog.name_pflicht';
}
