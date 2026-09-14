// Issue #2317 Baustein 1 — Speicherfunktionen der Trip-Reiter, die die
// Fetch-Option des Speicher-Waechters (`flush({ keepalive: true })` beim
// Entladen) an den PUT durchreichen, statt sie zu verschlucken.
// Spec: docs/specs/modules/speicherung_beim_neuladen.md § Baustein 1
//
// Genutzt von CorridorEditor/CorridorEditorMobile, AlarmeTab (Trip-Kontext) und
// WeatherMetricsTab. BEWUSST svelte-frei (kein `$app/*`, keine Runen) — sonst
// unter node:test nicht ladbar.
//
// Wichtig fuer das Entladen: vor dem `put`-Aufruf darf NICHTS abgewartet werden,
// sonst geht der Request nicht mehr im Tick des Entladens raus (#1376).

import type { SaveFn } from '../../stores/saveStatusStore.svelte.ts';

/** Der Teil von `api`, den die Speicherfunktionen brauchen. */
export interface PutClient {
	put<T>(path: string, body: unknown, init?: RequestInit): Promise<T>;
}

/**
 * Rumpf als Wert oder als Funktion. Die Funktion wird erst beim tatsaechlichen
 * Speichern gelesen — so bleibt der Stand von Feldern erhalten, die die Reiter
 * bisher erst zum Speicherzeitpunkt lasen (z.B. `trip.display_config`).
 */
export type Rumpf = unknown | (() => unknown);

function lies(rumpf: Rumpf): unknown {
	return typeof rumpf === 'function' ? (rumpf as () => unknown)() : rumpf;
}

/** Ein PUT auf `/api/trips/{id}`; `nachErfolg` bekommt die Server-Antwort. */
export function baueTripSpeicherung<T>(
	client: PutClient,
	tripId: string,
	body: Rumpf,
	nachErfolg?: (antwort: T) => void
): SaveFn {
	return async (init) => {
		const antwort = await client.put<T>(`/api/trips/${tripId}`, lies(body), init);
		nachErfolg?.(antwort);
	};
}

/**
 * Wetter-Metriken: zwei PUTs (`/weather-config`, dann `/api/trips/{id}`).
 * - Regulaer strikt nacheinander — die lokale Uebernahme von alert_rules haengt
 *   an der Trip-Antwort NACH der Wetter-Konfiguration (#850, AC-17).
 * - Beim Entladen (keepalive) beide SOFORT und unabhaengig: die Antwort des
 *   ersten kommt nie mehr an, der zweite startete sonst nie (AC-4).
 * `nachErfolg` bekommt in beiden Faellen die TRIP-Antwort, erst nach beiden PUTs.
 */
export function baueWetterMetrikenSpeicherung<T>(
	client: PutClient,
	tripId: string,
	wetterPayload: Rumpf,
	tripBody: Rumpf,
	nachErfolg?: (antwort: T) => void
): SaveFn {
	const wetterPfad = `/api/trips/${tripId}/weather-config`;
	const tripPfad = `/api/trips/${tripId}`;
	return async (init) => {
		if (init?.keepalive === true) {
			const wetter = client.put<unknown>(wetterPfad, lies(wetterPayload), init);
			const trip = client.put<T>(tripPfad, lies(tripBody), init);
			const [, antwort] = await Promise.all([wetter, trip]);
			nachErfolg?.(antwort);
			return;
		}
		await client.put<unknown>(wetterPfad, lies(wetterPayload), init);
		const antwort = await client.put<T>(tripPfad, lies(tripBody), init);
		nachErfolg?.(antwort);
	};
}
