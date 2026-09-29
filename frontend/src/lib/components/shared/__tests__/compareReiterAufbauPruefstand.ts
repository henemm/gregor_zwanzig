// Gemeinsamer Prüfstand: baut für JEDEN der vier selbst speichernden
// Ortsvergleich-Reiter (Alarme, Versand, Wertebereiche, Wetter-Metriken) den
// echten Speicherweg auf — echtes `erstelle…Speicherung`, echte Hydration,
// echter SaveStatus-Controller mit Kennung {typ:'vergleich', id}, echte
// Hub-Queue, Transport über `api` (Issue #2375). KEINE Testdatei.
//
// Importiert NUR Exporte, die heute schon existieren — ein von der Spec neu
// verlangter Baustein (`buildComparePresetPartialPayload`) wird hier bewusst
// NICHT importiert, sonst scheiterte jede Datei, die diesen Prüfstand lädt,
// schon beim Laden statt an der Zusicherung.

import { api } from '../../../api.ts';
import { clearEtagRegistry } from '../../../etagRegistry.ts';
import {
	createGoMergeServer,
	vollerVergleich,
	type GoMergeServer,
	type MitschnittEintrag
} from './goMergeServerPruefstand.ts';
import type { ComparePreset } from '../../../types.ts';
import type { SaveStatus } from '../../../stores/saveStatusStore.svelte.ts';
import { createPutQueue } from '../../compare/compareHubPersistenz.ts';
import { hydrateAlarmFieldsFromPreset } from '../../compare/compareHubHydration.ts';
import type { PutClient } from '../tripSpeicherung.ts';
import { erstelleAlarmeVergleichSpeicherung } from '../alarmeVergleichSpeicherung.ts';
import {
	erstelleVersandVergleichSpeicherung,
	hydrateVersandFieldsFromPreset
} from '../versandVergleichSpeicherung.ts';
import { erstelleWertebereicheVergleichSpeicherung } from '../corridor-editor/wertebereicheVergleichSpeicherung.ts';
import { erstelleWetterMetrikenVergleichSpeicherung } from '../weather-metrics-tab/weatherMetricsCompareSave.ts';
import { createController } from './versandVergleichPruefstand.ts';
import {
	hydrierterWs as hydrierterWertebereicheWs,
	wertebereicheBedienung
} from '../corridor-editor/__tests__/wertebereicheVergleichPruefstand.ts';
import {
	hydrierterWs as hydrierterWetterWs,
	wetterMetrikenBedienung
} from '../weather-metrics-tab/__tests__/wetterMetrikenVergleichPruefstand.ts';

export type Reiter = 'alarme' | 'versand' | 'wertebereiche' | 'wetterMetriken';
export const REITER: Reiter[] = ['alarme', 'versand', 'wertebereiche', 'wetterMetriken'];

export interface ReiterAufbau {
	zustand: Record<string, unknown>;
	ctl: SaveStatus;
	speicherung: { aenderungMelden(): void };
	/** aktuelle Basis (`currentPreset` im Hub) */
	basis(): ComparePreset;
	/** eine Änderung an EINEM Eigenfeld, wie der Nutzer sie auslöst */
	aendern(): void;
	/** Leerauswahl bzw. Löschen (Test 2) — nur wo die Spec es verlangt */
	leeren(): void;
}

export function reiterAufbau(
	reiter: Reiter,
	start: ComparePreset,
	client: PutClient = api
): ReiterAufbau {
	let basis = start;
	const ctl = createController(start.id);
	const queue = createPutQueue();
	const gemeinsam = {
		client,
		preset: () => basis,
		enqueueHubWrite: <T>(fn: () => Promise<T>) => queue.enqueue(fn),
		onCompareUpdate: (p: ComparePreset) => {
			basis = p;
		},
		saveController: ctl
	};

	if (reiter === 'alarme') {
		const zustand: Record<string, unknown> = {};
		hydrateAlarmFieldsFromPreset(zustand, start, []);
		const speicherung = erstelleAlarmeVergleichSpeicherung({ ...gemeinsam, zustand });
		return {
			zustand,
			ctl,
			speicherung,
			basis: () => basis,
			aendern() {
				zustand.radarAlertEnabled = !(zustand.radarAlertEnabled as boolean);
			},
			leeren() {
				zustand.metricAlertLevels = {};
			}
		};
	}
	if (reiter === 'versand') {
		const zustand = hydrateVersandFieldsFromPreset(start) as unknown as Record<string, unknown>;
		const speicherung = erstelleVersandVergleichSpeicherung({ ...gemeinsam, zustand });
		return {
			zustand,
			ctl,
			speicherung,
			basis: () => basis,
			aendern() {
				zustand.morningTime = '07:15';
			},
			leeren() {
				// „Bis auf Weiteres" — reiner Button-Klick
				zustand.endDate = null;
			}
		};
	}
	if (reiter === 'wertebereiche') {
		const zustand = hydrierterWertebereicheWs(start);
		const bedienung = wertebereicheBedienung(zustand);
		const speicherung = erstelleWertebereicheVergleichSpeicherung({ ...gemeinsam, zustand });
		return {
			zustand,
			ctl,
			speicherung,
			basis: () => basis,
			aendern() {
				bedienung.patch('wind_max_kmh', { max: 55 });
			},
			leeren() {
				// Korridor-Leerung: alle Korridore entfernt ⇒ auch keine Ideal-Ranges
				for (const c of (zustand.corridors as Array<{ metric: string }>).map((k) => k.metric)) {
					bedienung.remove(c);
				}
			}
		};
	}
	const zustand = hydrierterWetterWs(start);
	const bedienung = wetterMetrikenBedienung(zustand);
	const speicherung = erstelleWetterMetrikenVergleichSpeicherung({ ...gemeinsam, zustand });
	return {
		zustand,
		ctl,
		speicherung,
		basis: () => basis,
		aendern() {
			bedienung.toggleMetric('gust_max_kmh');
		},
		leeren() {
			// alle Metriken abgewählt, Stundenverlauf und Ausblick geleert
			bedienung.reorderMetrics([]);
			bedienung.hourlyDragEnd([]);
			bedienung.outlookSelect([]);
		}
	};
}

/**
 * Zwei-Tab-Konflikt im Kern nachgestellt (Issue #2375, Test 6): Tab B hat den
 * Vergleich geladen (ETag bekannt), Tab A ändert danach den NAMEN, B speichert
 * eine eigene Reiter-Änderung ⇒ 412 ⇒ „Nochmal speichern" (`retryConflict`).
 * Der Ersatz-Server mergt wie Go. Installiert und entfernt ihn selbst
 * (verschachtelungsfest über einem ggf. schon installierten fakeTripServer).
 */
export async function konfliktMitFremdemNamen(
	reiter: Reiter,
	id: string
): Promise<{
	server: GoMergeServer;
	aufbau: ReiterAufbau;
	erster: MitschnittEintrag;
	retryRumpf: Record<string, unknown>;
	zustandNach412: string;
}> {
	clearEtagRegistry();
	const server = createGoMergeServer({ [id]: vollerVergleich(id) });
	server.install();
	try {
		await api.get(`/api/compare/presets/${id}`);
		server.fremdSchreiben(id, { name: 'Fremd von A' });
		const aufbau = reiterAufbau(reiter, vollerVergleich(id) as unknown as ComparePreset);
		aufbau.aendern();
		aufbau.speicherung.aenderungMelden();
		await aufbau.ctl.flush();
		const erster = server.mitschnitt.filter((e) => e.method === 'PUT')[0];
		const zustandNach412 = aufbau.ctl.state;
		await aufbau.ctl.retryConflict();
		const retry = server.mitschnitt.filter((e) => e.method === 'PUT').at(-1)!;
		return { server, aufbau, erster, retryRumpf: retry.anfrage as Record<string, unknown>, zustandNach412 };
	} finally {
		server.restore();
	}
}
