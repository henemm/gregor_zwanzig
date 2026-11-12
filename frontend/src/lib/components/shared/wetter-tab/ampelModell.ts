// Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Stufe 3.1: Modell-Schicht der Ampel.
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md, Implementation Details §1/§2.
//
// Reine Funktionen, EIN Code fuer Trip (`route`) und Orts-Briefing (`vergleich`).
// Spiegel von src/app/ampel.py (`_verschmelzen`, `deviation_count`, `validate_ampel`).
// Vorlagen-Ampeln kommen aus `/api/templates`, Metrik-Eigenschaften aus `/api/metrics`;
// keine Frontend-Kopie. Texte liefert das Modell nie: nur Katalogschluessel (Bereich
// `wetter`) und Platzhalter-Werte.
// Kein Browser-/SvelteKit-Import, lauffaehig unter node --experimental-strip-types.

import type { Ampel, AmpelAlarmAb, AmpelFarbe, AmpelMetrik, AmpelSeite } from '../../../types.ts';
import { klon } from './klon.ts';

export type { Ampel, AmpelMetrik, AmpelSeite };
export type AlarmAb = AmpelAlarmAb;
export type Farbe = AmpelFarbe;
export type Seite = AmpelSeite;
export type VorlagenAmpeln = Record<string, Ampel>;
export type Kontext = 'route' | 'vergleich';

/** Eigenschaften einer Metrik aus `/api/metrics` (Teil-PR 1, AC-27). */
export type MetrikEigenschaften = {
	id: string;
	group: string;
	alertable: boolean;
	is_precursor: boolean;
	allowed_sides: string | null;
	display_only: boolean;
	unit: string;
	label_de?: string;
	label_en?: string;
};

/** Katalogschluessel + Platzhalter-Werte (der Text kommt aus `wetter.json`). */
export type KatalogModell<A extends string = string> = {
	art: A;
	schluessel: string;
	werte: Record<string, string | number>;
};

export const STANDARD_VORLAGE = 'allgemein';
const GEWITTER = 'thunder';
const UNTEN = ['red', 'orange', 'yellow'] as const; // aufsteigend: rot < orange < gelb
const OBEN = ['yellow', 'orange', 'red'] as const; // aufsteigend: gelb < orange < rot
const ALARM_AB: readonly AlarmAb[] = ['never', 'yellow', 'orange', 'red'];
const ALARM_AB_GEWITTER: readonly AlarmAb[] = ['never', 'orange', 'red'];
const RANG: Record<string, number> = { yellow: 1, orange: 2, red: 3 };
/** Gruppenfolge der Zeilen (Gesamt-Spec §4); welche Metrik in welche Gruppe gehoert, sagt `/api/metrics`. */
const GRUPPEN_FOLGE = ['temperature', 'wind', 'precip_thunder', 'sky_visibility', 'snow_height'];

const ohneZeile = (): AmpelMetrik => ({ enabled: false, lower: {}, upper: {}, alarm_ab: 'never' });
const istObjekt = (x: unknown): x is Record<string, unknown> => x !== null && typeof x === 'object' && !Array.isArray(x);

// ── Daten-Adapter ────────────────────────────────────────────────────────────

/** GET /api/templates -> Vorlagen-ID -> vollstaendige Vorlagen-Ampel. */
export function vorlagenAusTemplates(liste: { id: string; ampel?: Ampel | null }[]): VorlagenAmpeln {
	const aus: VorlagenAmpeln = {};
	for (const t of Array.isArray(liste) ? liste : []) {
		if (t?.id && t.ampel) aus[t.id] = klon(t.ampel);
	}
	return aus;
}

/** GET /api/metrics (Listen je Kategorie) -> Metrik-ID -> Eigenschaften. */
export function eigenschaftenAusKatalog(apiMetrics: Record<string, Record<string, unknown>[]>): Record<string, MetrikEigenschaften> {
	const aus: Record<string, MetrikEigenschaften> = {};
	for (const liste of Object.values(apiMetrics ?? {})) {
		for (const k of Array.isArray(liste) ? liste : []) {
			const id = k.id as string;
			aus[id] = {
				id,
				group: k.group as string,
				alertable: k.alertable as boolean,
				is_precursor: k.is_precursor as boolean,
				allowed_sides: (k.allowed_sides ?? null) as string | null,
				display_only: k.display_only as boolean,
				unit: k.unit as string,
				label_de: k.label_de as string | undefined,
				label_en: k.label_en as string | undefined
			};
		}
	}
	return aus;
}

/** Vorlagen-ID eines Abos: `ampel.template`, unbekannt oder fehlend -> „allgemein“. */
export function vorlageIdVon(abo: Ampel | null | undefined, vorlagen: VorlagenAmpeln): string {
	const tid = abo?.template;
	return tid && tid in vorlagen ? tid : STANDARD_VORLAGE;
}

// ── Aufloesung und Abweichungen ──────────────────────────────────────────────

/** Spiegel von `app.ampel._verschmelzen`: Vorlage + Abo-Abweichungen, mutiert nichts.
 *  Eine ungueltige Abo-Ampel wird wie in Python ignoriert (Vorlage greift). */
export function verschmelzen(vorlage: Ampel, abo?: Ampel | null): Ampel {
	const res = klon(vorlage);
	res.metrics = res.metrics ?? {};
	res.thunder = res.thunder ?? {};
	if (!abo || ampelFehler(abo).length > 0) return res;
	for (const [mid, e] of Object.entries(abo.metrics ?? {})) {
		const ziel = (res.metrics[mid] = res.metrics[mid] ?? ohneZeile());
		for (const k of ['lower', 'upper'] as const) {
			if (k in e) ziel[k] = klon(e[k]) ?? {}; // null = Seite bewusst offen
		}
		if (e.enabled !== undefined && e.enabled !== null) ziel.enabled = e.enabled;
		if (e.alarm_ab !== undefined && e.alarm_ab !== null) ziel.alarm_ab = e.alarm_ab;
	}
	for (const [k, v] of Object.entries(abo.thunder ?? {})) {
		if (v !== undefined && v !== null) (res.thunder as Record<string, AmpelFarbe>)[k] = v;
	}
	return res;
}

/** Seite ohne offene (null) Grenzen. */
function ohneOffene(seite: AmpelSeite | null | undefined): Record<string, number> {
	const aus: Record<string, number> = {};
	for (const [k, v] of Object.entries(seite ?? {})) if (v !== null && v !== undefined) aus[k] = v;
	return aus;
}

/** Gleiche Grenzen auf einer Seite (offene Grenzen zaehlen nicht). */
export function gleicheSeite(a: AmpelSeite | null | undefined, b: AmpelSeite | null | undefined): boolean {
	const x = ohneOffene(a);
	const y = ohneOffene(b);
	const kx = Object.keys(x);
	return kx.length === Object.keys(y).length && kx.every((k) => k in y && x[k] === y[k]);
}

/** Weicht eine Abo-Zeile von der Vorlagen-Zeile ab? (Grenzen, enabled, alarm_ab) */
function zeileWeichtAb(e: AmpelMetrik, v: AmpelMetrik): boolean {
	const grenzen = (['lower', 'upper'] as const).some((k) => k in e && !gleicheSeite(e[k], v[k]));
	const werte = (['enabled', 'alarm_ab'] as const).some((k) => e[k] !== undefined && e[k] !== null && e[k] !== v[k]);
	return grenzen || werte;
}

/** Abweichungen einer Abo-Ampel gegen eine gegebene Vorlagen-Ampel (Spiegel `deviation_count`). */
export function zaehleAbweichungenGegen(vorlage: Ampel, abo: Ampel | null | undefined): number {
	if (!abo) return 0;
	let n = 0;
	for (const [mid, e] of Object.entries(abo.metrics ?? {})) {
		if (zeileWeichtAb(e ?? {}, vorlage.metrics?.[mid] ?? ohneZeile())) n++;
	}
	const v = vorlage.thunder ?? {};
	const gewitter = { ...v, ...ohneOffene(abo.thunder as AmpelSeite) } as Record<string, unknown>;
	const geaendert = Object.keys(gewitter).some((k) => gewitter[k] !== (v as Record<string, unknown>)[k]);
	return n + (geaendert ? 1 : 0);
}

/** Abweichungen einer Abo-Ampel von ihrer Vorlage (`abo.template`, sonst „allgemein“). */
export function zaehleAbweichungen(abo: Ampel | null | undefined, vorlagen: VorlagenAmpeln): number {
	if (!abo) return 0;
	return zaehleAbweichungenGegen(vorlagen[vorlageIdVon(abo, vorlagen)], abo);
}

// ── Regeln: Grenzen (AC-17) und Gewitter (AC-18) ─────────────────────────────

/** Gesetzte Werte einer Seite in Schluessel-Reihenfolge; Fehler bei Nicht-Zahl oder Reihenfolge. */
function seitePruefen(werte: unknown, keys: readonly string[], fehlerReihenfolge: string, fehler: string[]): number[] {
	if (werte === null || werte === undefined) return [];
	if (!istObjekt(werte)) {
		fehler.push('wetter.grenzen.fehler_zahl');
		return [];
	}
	const gesetzt: number[] = [];
	for (const k of keys) {
		const v = werte[k];
		if (v === null || v === undefined) continue;
		if (typeof v !== 'number' || !Number.isFinite(v)) {
			fehler.push('wetter.grenzen.fehler_zahl');
			continue;
		}
		gesetzt.push(v);
	}
	if (gesetzt.some((a, i) => i > 0 && gesetzt[i - 1] >= a)) fehler.push(fehlerReihenfolge);
	return gesetzt;
}

/** Reihenfolge-Regeln einer Zeile (AC-17): unten rot < orange < gelb, oben gelb < orange < rot,
 *  unten nicht ueber oben (Gleichheit erlaubt). Liefert Katalogschluessel, leer = gueltig. */
export function grenzenFehler(e: { lower?: AmpelSeite | null; upper?: AmpelSeite | null }): string[] {
	const fehler: string[] = [];
	const unten = seitePruefen(e?.lower, UNTEN, 'wetter.grenzen.fehler_unten', fehler);
	const oben = seitePruefen(e?.upper, OBEN, 'wetter.grenzen.fehler_oben', fehler);
	if (unten.length && oben.length && unten[unten.length - 1] > oben[0]) fehler.push('wetter.grenzen.fehler_kreuz');
	return [...new Set(fehler)];
}

/** Gewitter-Farbregeln: mittel gelb/orange/rot, hoch nur orange/rot, hoch nicht schwaecher als mittel. */
export function gewitterFehler(thunder: unknown): string[] {
	if (!istObjekt(thunder)) return ['wetter.gewitter.fehler_farbe'];
	const { mittel, hoch } = thunder as { mittel?: unknown; hoch?: unknown };
	const fehler: string[] = [];
	if (mittel !== undefined && mittel !== null && !(String(mittel) in RANG)) fehler.push('wetter.gewitter.fehler_farbe');
	if (hoch !== undefined && hoch !== null && !gewitterFarben('hoch').includes(hoch as Farbe)) fehler.push('wetter.gewitter.fehler_hoch_gelb');
	if (String(mittel) in RANG && String(hoch) in RANG && RANG[String(hoch)] < RANG[String(mittel)]) fehler.push('wetter.gewitter.fehler_hoch_schwaecher');
	return fehler;
}

function metrikFehler(mid: string, e: unknown): string[] {
	if (!istObjekt(e)) return ['wetter.grenzen.fehler_ungueltig'];
	const fehler = grenzenFehler(e as AmpelMetrik);
	const a = e.alarm_ab;
	if (a !== undefined && a !== null && !(mid === GEWITTER ? ALARM_AB_GEWITTER : ALARM_AB).includes(a as AlarmAb)) {
		fehler.push('wetter.grenzen.fehler_ungueltig');
	}
	if (e.enabled !== undefined && e.enabled !== null && typeof e.enabled !== 'boolean') fehler.push('wetter.grenzen.fehler_ungueltig');
	return fehler;
}

/** Ganze Ampel pruefen, regelgleich mit Python `validate_ampel` und Go `validateAmpel`.
 *  Liefert Katalogschluessel (ohne Doppelte), leer = gueltig. */
export function ampelFehler(ampel: unknown): string[] {
	if (ampel === null || ampel === undefined) return [];
	if (!istObjekt(ampel)) return ['wetter.grenzen.fehler_ungueltig'];
	const fehler: string[] = [];
	if (ampel.template !== undefined && ampel.template !== null && typeof ampel.template !== 'string') fehler.push('wetter.grenzen.fehler_ungueltig');
	const metrics = ampel.metrics;
	if (metrics !== undefined && metrics !== null && !istObjekt(metrics)) fehler.push('wetter.grenzen.fehler_ungueltig');
	else for (const [mid, e] of Object.entries(metrics ?? {})) fehler.push(...metrikFehler(mid, e));
	if (ampel.thunder !== undefined && ampel.thunder !== null) fehler.push(...gewitterFehler(ampel.thunder));
	return [...new Set(fehler)];
}

/** Waehlbare Farben je Gewitter-Stufe (ADR-0106: „keins“ gruen, „leicht“ fest gelb). */
export function gewitterFarben(stufe: 'mittel' | 'hoch'): Farbe[] {
	return stufe === 'mittel' ? ['yellow', 'orange', 'red'] : ['orange', 'red'];
}

/** „Alarm ab“-Optionen einer Zeile: nicht alarmfaehig -> keine; Gewitter ohne Gelb. */
export function alarmAbOptionen(id: string, eig: MetrikEigenschaften | undefined): AlarmAb[] {
	if (!eig?.alertable) return [];
	return [...(id === GEWITTER ? ALARM_AB_GEWITTER : ALARM_AB)];
}

// ── „gruen: …“-Zeile und Erklaersatz (nur Schluessel + Platzhalter) ──────────

/** Mildeste gesetzte Grenze einer Seite ab einer Stufe (gelb = ganze Seite). Gilt fuer
 *  beide Seiten: in beiden ist gelb die mildeste, rot die schaerfste Grenze. */
function grenzeAb(seite: AmpelSeite | null | undefined, ab: Farbe): number | null {
	const s = seite ?? {};
	for (const k of OBEN.slice(RANG[ab] - 1)) {
		const v = s[k];
		if (v !== null && v !== undefined) return v;
	}
	return null;
}

/** „grün: a bis b {Einheit}“ / „grün: ab …“ / „grün: bis …“ / „immer grün“ (AC-15). */
export function gruenZeile(eintrag: AmpelMetrik, eig: MetrikEigenschaften | undefined): KatalogModell<'von_bis' | 'ab' | 'bis' | 'immer'> {
	const einheit = eig?.unit ?? '';
	const unten = grenzeAb(eintrag?.lower, 'yellow');
	const oben = grenzeAb(eintrag?.upper, 'yellow');
	if (unten !== null && oben !== null) return { art: 'von_bis', schluessel: 'wetter.gruen.von_bis', werte: { von: unten, bis: oben, einheit } };
	if (unten !== null) return { art: 'ab', schluessel: 'wetter.gruen.ab', werte: { ab: unten, einheit } };
	if (oben !== null) return { art: 'bis', schluessel: 'wetter.gruen.bis', werte: { bis: oben, einheit } };
	return { art: 'immer', schluessel: 'wetter.gruen.immer', werte: {} };
}

// ── Untertitel `Einheit · Hinweis` (#2913 Fix Metrik-Liste, AC-5, Mockup Z. ~434) ──

/** Metriken mit eigenem Hinweis im Katalog (`wetter.hinweis.<id>`, Mockup Fassung 3). */
export const HINWEIS_IDS: readonly string[] = [
	'temperature',
	'temperature_night',
	'wind',
	'gust',
	'precipitation',
	'thunder',
	'visibility',
	'cloud_low',
	'uv_index',
	'freezing_level',
	'snowfall_limit',
	'sunshine'
];

/** Katalogschluessel des Hinweises: reine Anzeige vor Vorbote vor Metrik-Hinweis; sonst keiner. */
export function hinweisSchluessel(id: string, eig: MetrikEigenschaften | undefined): string | null {
	if (eig?.display_only) return 'wetter.untertitel.nur_anzeige';
	if (eig?.is_precursor) return 'wetter.untertitel.vorbote';
	return HINWEIS_IDS.includes(id) ? `wetter.hinweis.${id}` : null;
}

/** Untertitel unter dem Metrik-Namen: `[Einheit, Hinweis]` mit „ · “ verbunden, ohne leere Teile. */
export function untertitel(id: string, eig: MetrikEigenschaften | undefined, uebersetze: (schluessel: string) => string): string {
	const k = hinweisSchluessel(id, eig);
	return [eig?.unit ?? '', k ? uebersetze(k) : ''].filter(Boolean).join(' · ');
}

export type ErklaerArt = 'normal' | 'gewitter' | 'gewitter_nie' | 'nie' | 'vorbote' | 'anzeige' | 'ohne_grenze';

/** Gewitter: erste Stufe (mittel, hoch), deren Farbe die Alarmstufe erreicht. */
function gewitterSatz(stufe: Farbe, thunder: Ampel['thunder']): KatalogModell<ErklaerArt> {
	for (const g of ['mittel', 'hoch'] as const) {
		const farbe = thunder?.[g];
		if (farbe && RANG[farbe] >= RANG[stufe]) {
			return { art: 'gewitter', schluessel: 'wetter.erklaer.gewitter', werte: { gewitter_stufe: g, stufe } };
		}
	}
	return { art: 'gewitter_nie', schluessel: 'wetter.erklaer.gewitter_nie', werte: { stufe } };
}

/** Erklaersatz einer Zeile (AC-15/16/18) als Katalogschluessel + Platzhalter.
 *  `stufe` und `gewitter_stufe` sind Protokoll-Token (Farbe/Stufe), die Oberflaeche setzt das Katalogwort ein. */
export function erklaersatz(id: string, eintrag: AmpelMetrik, eig: MetrikEigenschaften | undefined, thunder?: Ampel['thunder']): KatalogModell<ErklaerArt> {
	if (eig?.display_only) return { art: 'anzeige', schluessel: 'wetter.erklaer.anzeige', werte: {} };
	if (!eig?.alertable && eig?.is_precursor) return { art: 'vorbote', schluessel: 'wetter.erklaer.vorbote', werte: {} };
	const stufe = eintrag?.alarm_ab;
	if (!eig?.alertable || !stufe || stufe === 'never') return { art: 'nie', schluessel: 'wetter.erklaer.nie', werte: {} };
	if (id === GEWITTER) return gewitterSatz(stufe, thunder);
	const einheit = eig.unit ?? '';
	const oben = grenzeAb(eintrag.upper, stufe);
	const unten = grenzeAb(eintrag.lower, stufe);
	if (oben !== null && unten !== null) return { art: 'normal', schluessel: 'wetter.erklaer.normal_beidseitig', werte: { oben, unten, einheit, stufe } };
	if (oben !== null) return { art: 'normal', schluessel: 'wetter.erklaer.normal_oben', werte: { oben, einheit, stufe } };
	if (unten !== null) return { art: 'normal', schluessel: 'wetter.erklaer.normal_unten', werte: { unten, einheit, stufe } };
	return { art: 'ohne_grenze', schluessel: 'wetter.erklaer.ohne_grenze', werte: { stufe } };
}

// ── Gruppen und Auswahl (AC-15, AC-37, AC-39) ────────────────────────────────

/** Zeilen je Gruppe in fester Gruppenfolge, nur belegte; Metriken ohne Katalog-Eintrag fallen weg. */
export function zeilenGruppen(auswahl: string[], eig: Record<string, MetrikEigenschaften>): { gruppe: string; metriken: string[] }[] {
	const je = new Map<string, string[]>();
	for (const id of auswahl) {
		const g = eig[id]?.group;
		if (!g) continue;
		if (!je.has(g)) je.set(g, []);
		if (!je.get(g)!.includes(id)) je.get(g)!.push(id);
	}
	const folge = [...GRUPPEN_FOLGE, ...[...je.keys()].filter((g) => !GRUPPEN_FOLGE.includes(g))];
	return folge.filter((g) => je.has(g)).map((g) => ({ gruppe: g, metriken: je.get(g)! }));
}

/** Aktive Metriken einer aufgeloesten Ampel (`enabled === true`), in Ampel-Reihenfolge. */
export function aktiveMetriken(aufgeloest: Ampel): string[] {
	return Object.entries(aufgeloest?.metrics ?? {}).filter(([, e]) => e?.enabled === true).map(([id]) => id);
}

type AuswahlQuelle = { metrics?: { metric_id: string; enabled?: boolean }[]; active_metrics?: (string | { metric_id: string })[] } & Record<string, unknown>;

/** Altformat von `active_metrics` (api_contract #1373): Anzeige-Schluessel -> Groesse + Auswertung. */
export type AltSchluessel = Record<string, { metric_id: string; aggregation: string }>;

/** Uebersetzungstabelle aus dem Vergleichs-Katalog (GET /api/compare/metrics, `metric` = Schluessel). */
export function altSchluesselAusKatalog(eintraege: { metric: string; metric_id?: string; aggregation?: string }[]): AltSchluessel {
	const aus: AltSchluessel = {};
	for (const e of Array.isArray(eintraege) ? eintraege : []) {
		if (e?.metric && e.metric_id && e.aggregation) aus[e.metric] = { metric_id: e.metric_id, aggregation: e.aggregation };
	}
	return aus;
}

/** Groesse eines `active_metrics`-Eintrags: Neuformat `{metric_id}` oder Altformat-Schluessel;
 *  ein nicht aufloesbarer Schluessel bleibt unveraendert stehen (verlustfrei, #1373). */
export function vergleichsMetrikId(eintrag: unknown, alt: AltSchluessel = {}): string {
	if (typeof eintrag === 'string') return alt[eintrag]?.metric_id ?? eintrag;
	return (eintrag as { metric_id: string } | null)?.metric_id as string;
}

/** Auswahl lesen: Trip aus `metrics[]` (enabled), Vergleich aus `active_metrics` (eindeutig, Alt-
 *  und Neuformat pro Element); fehlt die Liste, gilt die aufgeloeste Ampel (AC-39). Trip
 *  `metrics: []` gilt wie in Python (models.py D4: leer = kein Maximum, Standard gilt) als fehlende
 *  Liste (F007); eine leere Vergleichs-Liste bleibt leer. */
export function auswahlLesen(context: Kontext, displayConfig: AuswahlQuelle | null | undefined, aufgeloest: Ampel, alt: AltSchluessel = {}): string[] {
	const liste = AUSWAHL_QUELLE[context](displayConfig, alt);
	return liste ?? aktiveMetriken(aufgeloest);
}

/** Auswahl-Quelle je Kontext als Daten (Trip `metrics[]` mit `enabled`, Vergleich `active_metrics`);
 *  `null` = Liste fehlt. Tabelle statt Kontext-Weiche (Ratsche context_herkunft_zweige_eingefroren). */
const AUSWAHL_QUELLE: Record<Kontext, (dc: AuswahlQuelle | null | undefined, alt: AltSchluessel) => string[] | null> = {
	route: (dc) => (Array.isArray(dc?.metrics) && dc.metrics.length > 0 ? dc.metrics.filter((m) => m?.enabled === true).map((m) => m.metric_id) : null),
	vergleich: (dc, alt) => (Array.isArray(dc?.active_metrics) ? [...new Set(dc.active_metrics.map((m) => vergleichsMetrikId(m, alt)))] : null)
};

/** Vollstaendige Ampel einer eigenen Vorlage; Bestand ohne `ampel`: „allgemein“ mit `enabled`
 *  aus den Metriken der Vorlage (Spec §6 a, AC-39). */
export function eigeneVorlageAmpel(
	preset: { metrics?: { metric_id: string; enabled?: boolean }[]; ampel?: Ampel | null },
	vorlagen: VorlagenAmpeln
): Ampel {
	if (preset?.ampel) return verschmelzen(vorlagen[vorlageIdVon(preset.ampel, vorlagen)], preset.ampel);
	const a = verschmelzen(vorlagen[STANDARD_VORLAGE], null);
	for (const e of Object.values(a.metrics ?? {})) e.enabled = false;
	for (const m of preset?.metrics ?? []) {
		if (m?.enabled !== true) continue;
		a.metrics![m.metric_id] = a.metrics![m.metric_id] ?? ohneZeile();
		a.metrics![m.metric_id].enabled = true;
	}
	return a;
}

/** Vorlagenwechsel/Zuruecksetzen: aufgeloeste Vorlagen-Ampel und Auswahl aus ihrem `enabled`. */
export function zuruecksetzen(vorlageId: string, vorlagen: VorlagenAmpeln): { ampel: Ampel; auswahl: string[] } {
	const ampel = verschmelzen(vorlagen[vorlageId] ?? vorlagen[STANDARD_VORLAGE], null);
	return { ampel, auswahl: aktiveMetriken(ampel) };
}

// ── „Alarm ab fuer alle“ (AC-14) ─────────────────────────────────────────────

/** Setzt „Alarm ab“ fuer alle gewaehlten alarmfaehigen Metriken; Gewitter: Gelb wird Orange. */
export function alarmAbFuerAlle(ampel: Ampel, auswahl: string[], stufe: AlarmAb, eig: Record<string, MetrikEigenschaften>): Ampel {
	const a = klon(ampel);
	a.metrics = a.metrics ?? {};
	for (const id of auswahl) {
		if (!eig[id]?.alertable) continue;
		a.metrics[id] = a.metrics[id] ?? ohneZeile();
		a.metrics[id].alarm_ab = id === GEWITTER && stufe === 'yellow' ? 'orange' : stufe;
	}
	return a;
}

/** Zaehler-Modell der Kopfzeile: „{ausloesend} von {alarmfaehig} … {ohne} …“ bzw. Hinweis ohne alarmfaehige Metrik. */
export function alarmZaehler(ampel: Ampel, auswahl: string[], eig: Record<string, MetrikEigenschaften>): KatalogModell<'zaehler' | 'keine_alarmfaehig'> {
	const faehig = auswahl.filter((id) => eig[id]?.alertable === true);
	if (faehig.length === 0) return { art: 'keine_alarmfaehig', schluessel: 'wetter.alarm_ab.keine_alarmfaehig', werte: {} };
	const ausloesend = faehig.filter((id) => {
		const s = ampel?.metrics?.[id]?.alarm_ab;
		return !!s && s !== 'never';
	}).length;
	return {
		art: 'zaehler',
		schluessel: 'wetter.alarm_ab.zaehler',
		werte: { ausloesend, alarmfaehig: faehig.length, ohne: auswahl.length - faehig.length }
	};
}
