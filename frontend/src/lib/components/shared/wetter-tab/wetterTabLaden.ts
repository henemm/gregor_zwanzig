// Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Stufe 3.2: Daten des Reiters laden.
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md, Datenfluss „Lesen".
//
// EIN Lader fuer Trip (`route`) und Orts-Briefing (`vergleich`): Katalog `/api/metrics`
// (Gruppe, Alarmfaehigkeit, erlaubte Seiten), Vorlagen `/api/templates` (je Vorlage `ampel`),
// eigene Vorlagen `/api/metric-presets` (nur die Art des Kontexts), danach die aufgeloesten Ampeln
// von Abo und eigenen Vorlagen (#2988, ampelAufloesung.ts). Kein Zwischenspeicher:
// „Erneut laden" fragt den Server wirklich neu (AC-9). Bricht ein Abruf ab, wirft der Lader;
// der Reiter zeigt dann die Fehlermeldung und laesst die gespeicherten Einstellungen in Ruhe.
// Kein Browser-/SvelteKit-Import, lauffaehig unter node --experimental-strip-types.

import type { Ampel, MetricPreset } from '../../../types.ts';
import { eintragAusAbo, eintragAusVorlage, loeseAmpelnAuf, type Aufgeloest, type AufloesungClient } from './ampelAufloesung.ts';
import { aktiveMetriken, eigenschaftenAusKatalog, vorlagenAusTemplates } from './ampelModell.ts';
import type { Kontext, MetrikEigenschaften, VorlagenAmpeln } from './ampelModell.ts';
import type { MessageKey } from '../../../i18n/index.ts';
import type { AboSicht } from './wetterZustand.ts';

/** Der Teil von `api`, den der Lader braucht. */
export interface LeseClient extends AufloesungClient {
	get<T>(path: string): Promise<T>;
}

export type VorlageEintrag = { id: string; label: string; anzahl: number; stichworte: string[] };
/** #3111 AC-5: `beschreibung` (aus `MetricPreset.description`) ergänzt die Unterzeile „eigene". */
/** #3189: `herkunftName` = Name des Trips/Orts-Vergleichs zum Speicherzeitpunkt. */
export type EigeneVorlage = { id: string; name: string; ampel: Ampel; beschreibung?: string; herkunftName?: string };

export type WetterDaten = {
	eig: Record<string, MetrikEigenschaften>;
	vorlagen: VorlagenAmpeln;
	liste: VorlageEintrag[];
	eigene: EigeneVorlage[];
	/** Aufgeloeste Ampel des Abos (#2988). */
	aufgeloest: Aufgeloest;
};

type TemplateAntwort = { id: string; label?: string; ampel?: Ampel | null };

/** Bestandsvorlagen ohne `kind` stammen aus dem Trip-Editor (Teil-PR 1) und gelten als `route`. */
function artVon(p: MetricPreset): Kontext {
	return p.kind ?? 'route';
}

function presetListe(antwort: unknown): MetricPreset[] {
	if (Array.isArray(antwort)) return antwort as MetricPreset[];
	const p = (antwort as { presets?: MetricPreset[] } | null)?.presets;
	return Array.isArray(p) ? p : [];
}

/** Kurzbeschreibung je Systemvorlage: Metrikzahl und die ersten Metrik-Kennungen (Stichworte). */
export function vorlagenListe(templates: TemplateAntwort[], vorlagen: VorlagenAmpeln): VorlageEintrag[] {
	return (Array.isArray(templates) ? templates : [])
		.filter((t) => t?.id && vorlagen[t.id])
		.map((t) => {
			const aktiv = aktiveMetriken(vorlagen[t.id]);
			return { id: t.id, label: t.label ?? t.id, anzahl: aktiv.length, stichworte: aktiv.slice(0, 3) };
		});
}

/**
 * #3111 AC-4 (Mockup Fassung 4): kuratierte Stichworte je bekannter Systemvorlage (Katalogschluessel).
 * Loest feat_2794_s3a AC-10 fuer bekannte IDs ab; unbekannte IDs behalten die Ableitung.
 */
const STICHWORTE: Readonly<Record<string, MessageKey>> = {
	'alpen-trekking': 'wetter.vorlage.stichworte.alpen_trekking',
	wandern: 'wetter.vorlage.stichworte.wandern',
	skitouren: 'wetter.vorlage.stichworte.skitouren',
	wintersport: 'wetter.vorlage.stichworte.wintersport',
	radtour: 'wetter.vorlage.stichworte.radtour',
	wassersport: 'wetter.vorlage.stichworte.wassersport',
	allgemein: 'wetter.vorlage.stichworte.allgemein'
};

/**
 * Kurzbeschreibung einer Systemvorlage: Metrikzahl aus den Daten, dazu die kuratierten Stichworte
 * aus dem Katalog; fuer unbekannte IDs die Namen der ersten aktiven Metriken (Fallback).
 */
export function vorlageKurzbeschreibung(
	v: VorlageEintrag,
	uebersetze: (key: MessageKey, params?: Record<string, string | number>) => string,
	metrikName: (id: string) => string
): string {
	const zahl = uebersetze('wetter.vorlage.metrikzahl', { count: v.anzahl });
	const key = STICHWORTE[v.id];
	return [zahl, ...(key ? [uebersetze(key)] : v.stichworte.map(metrikName))].join(' · ');
}

/** Eine eigene Vorlage im Reiter: Ampel kommt fertig herein, Beschreibung (#3111 AC-5) mitgenommen. Laden und frisch Gespeichert. */
export function eigeneVorlageAus(p: MetricPreset, ampel: Ampel): EigeneVorlage {
	return {
		id: p.id,
		name: p.name,
		ampel,
		...(p.description ? { beschreibung: p.description } : {}),
		...(p.herkunft?.name ? { herkunftName: p.herkunft.name } : {})
	};
}

/**
 * #3189 AC-1/AC-5: Herkunft einer neu gespeicherten Vorlage aus dem Abo (Trip bzw. Orts-Vergleich,
 * derselbe Code): `{id, name}`; im Anlege-Modus oder ohne ID/Namen `undefined`.
 */
export function vorlageHerkunft(abo: { id?: unknown; name?: unknown } | null | undefined, createMode: boolean): { id: string; name: string } | undefined {
	if (createMode || !abo) return undefined;
	const id = typeof abo.id === 'string' ? abo.id.trim() : '';
	const name = typeof abo.name === 'string' ? abo.name.trim() : '';
	return id && name ? { id, name } : undefined;
}

/** #3111 AC-6: Zahl der Orte eines Orts-Briefings (`location_ids`); ohne Liste `undefined`. */
export function ortAnzahlVon(abo: { location_ids?: unknown } | null | undefined): number | undefined {
	const ids = abo?.location_ids;
	return Array.isArray(ids) ? ids.length : undefined;
}

/** Laedt Katalog, Vorlagen und eigene Vorlagen der Art `kind`, dann die Ampeln von Abo und eigenen
 *  Vorlagen in EINER Abfrage; wirft, wenn ein Abruf scheitert. */
export async function ladeWetterDaten(client: LeseClient, kind: Kontext, abo: AboSicht | null | undefined): Promise<WetterDaten> {
	const [katalog, templates, presets] = await Promise.all([
		client.get<Record<string, Record<string, unknown>[]>>('/api/metrics'),
		client.get<TemplateAntwort[]>('/api/templates'),
		client.get<unknown>('/api/metric-presets')
	]);
	const vorlagen = vorlagenAusTemplates(templates as { id: string; ampel?: Ampel | null }[]);
	const eigene = presetListe(presets).filter((p) => p?.id && artVon(p) === kind);
	const [aufgeloest, ...ampeln] = await loeseAmpelnAuf(client, [eintragAusAbo(abo), ...eigene.map(eintragAusVorlage)]);
	return {
		eig: eigenschaftenAusKatalog(katalog),
		vorlagen,
		liste: vorlagenListe(templates, vorlagen),
		eigene: eigene.map((p, i) => eigeneVorlageAus(p, ampeln[i].ampel)),
		aufgeloest
	};
}
