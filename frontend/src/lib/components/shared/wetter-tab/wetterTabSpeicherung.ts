// Issue #2794 S3a, Teil-PR 3 (Reiter Wetter), Stufe 3.2: der EINE Speicherer des Reiters (AC-38).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md, Datenfluss „Speichern" und „Konflikt".
//
//   Trip (`route`): ein Speichervorgang aus zwei disjunkten PUTs wie bisher (`tripSpeicherung.ts`):
//     PUT /api/trips/{id}/weather-config mit `ampel` + `metrics` (display_config-Teil), danach
//     PUT /api/trips/{id} mit `official_alerts_enabled`, `official_warnings`, `report_config`.
//   Orts-Briefing (`vergleich`): EIN Eintrag in der Hub-Schreibschlange (If-Match), nur die
//     Eigenfelder (display_config `ampel` + `active_metrics`, Warn-Felder, Radar, Tagesfenster);
//     der Server mergt display_config auf Ebene 1. Bei 412 laedt der Reiter das Abo neu (die
//     fremde Aenderung bleibt sichtbar und wird nicht still ueberschrieben) und meldet den Konflikt
//     an den Controller („Nochmal speichern" sendet danach den neu geladenen Stand).
//   Anlegen (`createMode`): kein Netz — der Stand geht als Nutzlast an die Anlege-Seite.
//
// Die Rumpf-Funktionen lesen Stand und Abo erst beim Senden (keine eingefrorene Kopie).
// Kein Browser-/SvelteKit-Import, lauffaehig unter node --experimental-strip-types.

import type { SaveFn, SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { baueWetterMetrikenSpeicherung, mitKonfliktSchluessel } from '../tripSpeicherung.ts';
import { tripSpeicherPayload, vergleichSpeicherPayload } from './ampelSchreiben.ts';
import type { AltSchluessel, VorlagenAmpeln } from './ampelModell.ts';
import type { WarnFelder } from './amtlicheWarnungen.ts';
import type { AboSicht, WetterStand } from './wetterZustand.ts';

/** Besitzer des Speicher-Platzes im Controller (nie die Reiterkennung `wetter`, s. Owner-Waechter). */
export const WETTER_OWNER = 'wetter-ampel';

export interface SchreibClient {
	get<T>(path: string): Promise<T>;
	put<T>(path: string, body: unknown, init?: RequestInit): Promise<T>;
}

export type SpeicherOptionen = {
	client: SchreibClient;
	/** Aktueller Bearbeitungsstand (Getter: erst beim Senden gelesen). */
	stand: () => WetterStand;
	vorlagen: () => VorlagenAmpeln;
	/** Lebender Abo-Stand der Seite (Trip bzw. Vergleich). */
	abo: () => AboSicht;
	saveController?: SaveStatus;
	enqueueHubWrite?: <T>(fn: () => Promise<T>) => Promise<T>;
	/** Server-Antwort an die Seite (Trip bzw. Vergleich). */
	uebernehmen?: (antwort: unknown) => void;
	/** Vergleich: nach 412 neu geladenes Abo, der Reiter hydriert daraus neu. */
	neuGeladen?: (abo: AboSicht) => void;
	/** Anlegen: Nutzlast an die Anlege-Seite statt PUT. */
	anlegen?: (nutzlast: unknown) => void;
	/** Vergleich: Auswertung je neu hinzugefuegter Metrik (Katalog der Vergleichs-Metriken). */
	aggregationFuer?: (id: string) => string;
	/** Vergleich: Altformat-Schluessel von `active_metrics` -> Groesse (Fix-Loop 3, C2). */
	altSchluessel?: AltSchluessel;
};

export type Speicherer = { melden(): void };

/** Trip-Nutzlast aus Stand und lebendem Abo (zwei disjunkte Teile). */
export function tripNutzlast(o: SpeicherOptionen) {
	const s = o.stand();
	const abo = o.abo();
	const v = o.vorlagen();
	return tripSpeicherPayload({
		vorlage: v[s.vorlageId],
		aufgeloest: s.ampel,
		auswahl: s.auswahl,
		displayConfig: (abo.display_config ?? {}) as Parameters<typeof tripSpeicherPayload>[0]['displayConfig'],
		reportConfig: abo.report_config ?? {},
		warnFelder: abo as WarnFelder,
		warnungenAn: s.warnungenAn,
		tagesfenster: s.tagesfenster
	});
}

/** Vergleichs-Nutzlast: nur Eigenfelder, display_config nur `ampel` + `active_metrics`. */
export function vergleichNutzlast(o: SpeicherOptionen) {
	const s = o.stand();
	const abo = o.abo();
	const voll = vergleichSpeicherPayload({
		vorlage: o.vorlagen()[s.vorlageId],
		aufgeloest: s.ampel,
		auswahl: s.auswahl,
		displayConfig: (abo.display_config ?? {}) as Parameters<typeof vergleichSpeicherPayload>[0]['displayConfig'],
		aggregationFuer: o.aggregationFuer ?? (() => 'max'),
		altSchluessel: o.altSchluessel,
		warnFelder: abo as WarnFelder,
		warnungenAn: s.warnungenAn,
		radarAn: s.radarAn,
		tagesfenster: s.tagesfenster
	});
	const { ampel, active_metrics } = voll.display_config;
	return { ...voll, display_config: { ampel, active_metrics } };
}

function tripSpeicherer(o: SpeicherOptionen): Speicherer {
	return {
		melden() {
			const id = String(o.abo().id);
			const fn = baueWetterMetrikenSpeicherung<unknown>(
				o.client,
				id,
				() => tripNutzlast(o).weatherConfig,
				() => tripNutzlast(o).tripFelder,
				(antwort) => o.uebernehmen?.(antwort),
				WETTER_OWNER
			);
			o.saveController?.schedule(fn, 700, 'wetter-ampel');
		}
	};
}

/** Ein Vergleichs-PUT in der Hub-Schlange; bei 412 neu laden, dann den Konflikt melden. */
function vergleichSaveFn(o: SpeicherOptionen): SaveFn {
	const fn: SaveFn = async (init) => {
		const pfad = `/api/compare/presets/${String(o.abo().id)}`;
		const reihe = o.enqueueHubWrite ?? (<T>(f: () => Promise<T>) => f());
		await reihe(async () => {
			try {
				o.uebernehmen?.(await o.client.put<unknown>(pfad, vergleichNutzlast(o), init));
			} catch (e) {
				if ((e as { status?: number })?.status === 412) {
					const frisch = await o.client.get<AboSicht>(pfad).catch(() => null);
					if (frisch) {
						o.uebernehmen?.(frisch);
						o.neuGeladen?.(frisch);
					}
				}
				throw e;
			}
		});
	};
	return mitKonfliktSchluessel(fn, WETTER_OWNER);
}

function vergleichSpeicherer(o: SpeicherOptionen): Speicherer {
	return {
		melden() {
			o.saveController?.schedule(vergleichSaveFn(o), 700, 'wetter-ampel');
		}
	};
}

/** Anlegen: dieselbe Nutzlast wie beim Speichern, aber an die Anlege-Seite (kein PUT). */
const ANLEGE_NUTZLAST: Record<'route' | 'vergleich', (o: SpeicherOptionen) => unknown> = {
	route: tripNutzlast,
	vergleich: vergleichNutzlast
};

export function anlegeSpeicherer(o: SpeicherOptionen, kind: 'route' | 'vergleich'): Speicherer {
	return { melden: () => o.anlegen?.(ANLEGE_NUTZLAST[kind](o)) };
}

/** Der Speicherer je Kontext (Tabelle statt Kontext-Weiche). */
export const SPEICHERER: Record<'route' | 'vergleich', (o: SpeicherOptionen) => Speicherer> = {
	route: tripSpeicherer,
	vergleich: vergleichSpeicherer
};
