// Issue #2988 S3: Abfrage der aufgeloesten Ampel (POST /api/ampel/aufloesung).
// Spec: docs/specs/modules/rework_2988_ampel_ableitung.md, „Der Endpunkt".
//
// Vorlage + Abweichungen rechnet allein Python; hier werden nur Eintraege gebaut und Antworten
// geprueft. Kontextfrei (Trip und Orts-Briefing). Jeder Fehler wirft: ohne Aufloesung kein Stand.
// Kein Browser-/SvelteKit-Import, lauffaehig unter node --experimental-strip-types.

import type { Ampel, MetricPreset } from '../../../types.ts';

export type AufloesungEintrag = { ampel?: unknown; preset_name?: string | null; profil?: string | null; metrics?: unknown[] | null };
export type Aufgeloest = { vorlage_id: string; ampel: Ampel };

/** Der Teil von `api`, den die Abfrage braucht. */
export interface AufloesungClient {
	post<T>(path: string, body: unknown): Promise<T>;
}

const PFAD = '/api/ampel/aufloesung';
/** Eintraege je Anfrage (Grenze des Endpunkts). */
const PAKET = 32;

function brauchbar(e: unknown): e is Aufgeloest {
	const a = e as Partial<Aufgeloest> | null | undefined;
	return typeof a?.vorlage_id === 'string' && a.vorlage_id !== '' && !!a.ampel?.metrics;
}

async function loesePaket(client: AufloesungClient, eintraege: AufloesungEintrag[]): Promise<Aufgeloest[]> {
	const antwort = await client.post<{ ergebnisse?: unknown } | null>(PFAD, { eintraege });
	const erg = antwort?.ergebnisse;
	if (!Array.isArray(erg) || erg.length !== eintraege.length || !erg.every(brauchbar)) {
		throw new Error(`${PFAD}: unbrauchbare Antwort`); // i18n-log
	}
	return erg;
}

/** Loest alle Eintraege in Paketen auf (Reihenfolge erhalten); scheitert ein Paket, scheitert alles. */
export async function loeseAmpelnAuf(client: AufloesungClient, eintraege: AufloesungEintrag[]): Promise<Aufgeloest[]> {
	const pakete: Promise<Aufgeloest[]>[] = [];
	for (let i = 0; i < eintraege.length; i += PAKET) pakete.push(loesePaket(client, eintraege.slice(i, i + PAKET)));
	return (await Promise.all(pakete)).flat();
}

/** Nur Text: ein Nicht-Text im Bestand waere 400 fuer die ganze Anfrage. */
const text = (x: unknown): string | null => (typeof x === 'string' ? x : null);

/** Abo-Sicht (Trip oder Orts-Briefing). Nie `metrics`: ein Trip ohne Ampel gaelte sonst als Altbestand. */
export function eintragAusAbo(abo: { display_config?: Record<string, unknown> | null; profil?: unknown } | null | undefined): AufloesungEintrag {
	const dc = abo?.display_config;
	return { ampel: dc?.ampel ?? null, preset_name: text(dc?.preset_name), profil: text(abo?.profil) };
}

/** Eigene Vorlage: ihre Ampel, im Altformat nur die Metrikliste (unlesbar = alles aus; unlesbare
 *  Zeilen werfen nicht, der Server uebergeht sie). */
export function eintragAusVorlage(p: MetricPreset): AufloesungEintrag {
	if (p.ampel) return { ampel: p.ampel };
	const liste = Array.isArray(p.metrics) ? p.metrics : [];
	return { metrics: liste.map((m) => ({ metric_id: m?.metric_id, enabled: m?.enabled })) };
}
