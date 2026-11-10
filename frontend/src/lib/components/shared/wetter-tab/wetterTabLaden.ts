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

/** Der Teil von `api`, den der Lader braucht. */
export interface LeseClient {
	get<T>(path: string): Promise<T>;
}

export type VorlageEintrag = { id: string; label: string; anzahl: number; stichworte: string[] };
export type EigeneVorlage = { id: string; name: string; ampel: Ampel };

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

/** Eigene Vorlagen der Art `kind`, jede mit ihrer vollstaendigen Ampel (Fallback §6 a). */
export function eigeneVorlagen(antwort: unknown, kind: Kontext, vorlagen: VorlagenAmpeln): EigeneVorlage[] {
	return presetListe(antwort)
		.filter((p) => p?.id && artVon(p) === kind)
		.map((p) => ({ id: p.id, name: p.name, ampel: eigeneVorlageAmpel(p, vorlagen) }));
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
