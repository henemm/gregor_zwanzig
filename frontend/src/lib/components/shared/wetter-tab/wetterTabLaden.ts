// Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Stufe 3.2: Daten des Reiters laden.
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md, Datenfluss „Lesen".
//
// EIN Lader fuer Trip (`route`) und Orts-Briefing (`vergleich`): Katalog `/api/metrics`
// (Gruppe, Alarmfaehigkeit, erlaubte Seiten), Vorlagen `/api/templates` (je Vorlage `ampel`),
// eigene Vorlagen `/api/metric-presets` (nur die Art des Kontexts). Kein Zwischenspeicher:
// „Erneut laden" fragt den Server wirklich neu (AC-9). Bricht ein Abruf ab, wirft der Lader;
// der Reiter zeigt dann die Fehlermeldung und laesst die gespeicherten Einstellungen in Ruhe.
// Kein Browser-/SvelteKit-Import, lauffaehig unter node --experimental-strip-types.

import type { Ampel, MetricPreset } from '../../../types.ts';
import { aktiveMetriken, eigenschaftenAusKatalog, eigeneVorlageAmpel, vorlagenAusTemplates } from './ampelModell.ts';
import type { Kontext, MetrikEigenschaften, VorlagenAmpeln } from './ampelModell.ts';
import type { MessageKey } from '../../../i18n/index.ts';

/** Der Teil von `api`, den der Lader braucht. */
export interface LeseClient {
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

/** Eine eigene Vorlage im Reiter: Ampel aufgeloest, Beschreibung (#3111 AC-5) mitgenommen. Laden und frisch Gespeichert. */
export function eigeneVorlageAus(p: MetricPreset, vorlagen: VorlagenAmpeln): EigeneVorlage {
	return {
		id: p.id,
		name: p.name,
		ampel: eigeneVorlageAmpel(p, vorlagen),
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

/** Eigene Vorlagen der Art `kind`, jede mit ihrer vollstaendigen Ampel (Fallback §6 a). */
export function eigeneVorlagen(antwort: unknown, kind: Kontext, vorlagen: VorlagenAmpeln): EigeneVorlage[] {
	return presetListe(antwort)
		.filter((p) => p?.id && artVon(p) === kind)
		.map((p) => eigeneVorlageAus(p, vorlagen));
}

/** #3111 AC-6: Zahl der Orte eines Orts-Briefings (`location_ids`); ohne Liste `undefined`. */
export function ortAnzahlVon(abo: { location_ids?: unknown } | null | undefined): number | undefined {
	const ids = abo?.location_ids;
	return Array.isArray(ids) ? ids.length : undefined;
}

/** Laedt Katalog, Vorlagen und eigene Vorlagen; wirft, wenn einer der drei Abrufe scheitert. */
export async function ladeWetterDaten(client: LeseClient, kind: Kontext): Promise<WetterDaten> {
	const [katalog, templates, presets] = await Promise.all([
		client.get<Record<string, Record<string, unknown>[]>>('/api/metrics'),
		client.get<TemplateAntwort[]>('/api/templates'),
		client.get<unknown>('/api/metric-presets')
	]);
	const vorlagen = vorlagenAusTemplates(templates as { id: string; ampel?: Ampel | null }[]);
	return {
		eig: eigenschaftenAusKatalog(katalog),
		vorlagen,
		liste: vorlagenListe(templates, vorlagen),
		eigene: eigeneVorlagen(presets, kind, vorlagen)
	};
}
