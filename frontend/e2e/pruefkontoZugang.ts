// Issue #3423 (Punkt 4) — Prüfkonto, Zweitkonto und Seed-IDs für die Staging-Specs
// auf den Prüfkonto-Beispieldaten (hub-test-alarm, hub-send-menue, elementliste-abgleich,
// wsw-abnahme-3037).
//
// Vom iMac (`ssh henemm-pruefen spec-run …`) kommen Staging-.env und validator.env durch,
// aber keine ELEMENTLISTE_*-Variablen, und GZ_AUTH_* ist dort das geteilte Konto (bzw. bei
// --lang en das EN-Konto). Dieser Helfer wählt deshalb selbst:
//   - Prüfkonto:  GZ_PRUEFKONTO_USER/PASS, sonst GZ_AUTH_USER/PASS (Server-Weg)
//   - Zweitkonto: GZ_ZWEITKONTO_USER/PASS, sonst GZ_AUTH_USER/PASS — nie das Prüfkonto
//   - Seed-IDs:   ELEMENTLISTE_TRIP_ID/ELEMENTLISTE_ORTE_ID, sonst lesend per GET nach dem Login
// Der Seed selbst läuft nur auf dem Server (scripts/staging_pruefkonto_mockupdaten.py,
// Runbook docs/runbooks/staging_pruefkonto_seed.md); hier wird nichts geschrieben.
//
// Alle Funktionen nehmen die Umgebung als Parameter, damit sie mit Klartext-Daten testbar sind
// (e2e/pruefkontoZugang.test.ts).

export type Umgebung = Record<string, string | undefined>;
export interface Zugang {
	user: string;
	pass: string;
}

/** Minimaler Ausschnitt von Playwrights APIRequestContext, den der Seed-Lookup braucht. */
export interface LeseApi {
	get(pfad: string): Promise<{ status(): number; ok(): boolean; json(): Promise<unknown> }>;
}

export const SEED_TRIP_ID = 'gz2967-gr221-mallorca';
export const SEED_VERGLEICH_NAME = 'Münsterland';

const SEED_HINWEIS =
	'Seed fehlt auf Staging: einmalig auf dem Server scripts/staging_pruefkonto_mockupdaten.py laufen lassen ' +
	'(Runbook docs/runbooks/staging_pruefkonto_seed.md).';

/** Wert einer gesetzten, nicht leeren Variable, sonst undefined. */
function gesetzt(env: Umgebung, name: string): string | undefined {
	const wert = env[name];
	return wert === undefined || wert === '' ? undefined : wert;
}

/**
 * Zugang aus `<praefix>_USER`/`<praefix>_PASS`, nur wenn beide gesetzt sind. Mit `streng` ist ein
 * halb gesetztes Paar ein Fehler statt eines stillen Rückfalls auf das nächste Paar.
 */
function paar(env: Umgebung, praefix: string, streng = false): Zugang | undefined {
	const user = gesetzt(env, `${praefix}_USER`);
	const pass = gesetzt(env, `${praefix}_PASS`);
	if (streng && (user === undefined) !== (pass === undefined)) {
		const fehlt = user === undefined ? `${praefix}_USER` : `${praefix}_PASS`;
		throw new Error(`${praefix}_USER/${praefix}_PASS nur halb gesetzt: ${fehlt} fehlt — beide setzen oder beide leer lassen.`);
	}
	return user && pass ? { user, pass } : undefined;
}

/** Prüfkonto wie pruefkontoZugang(), aber undefined statt Abbruch, wenn gar kein Paar gesetzt ist. */
export function pruefkontoZugangFallsGesetzt(env: Umgebung = process.env): Zugang | undefined {
	return paar(env, 'GZ_PRUEFKONTO', true) ?? paar(env, 'GZ_AUTH');
}

/** Prüfkonto: GZ_PRUEFKONTO_* hat Vorrang vor GZ_AUTH_* (auch bei --lang en). */
export function pruefkontoZugang(env: Umgebung = process.env): Zugang {
	const zugang = pruefkontoZugangFallsGesetzt(env);
	if (!zugang) {
		throw new Error(
			'Prüfkonto-Zugang fehlt: weder GZ_PRUEFKONTO_USER/GZ_PRUEFKONTO_PASS noch GZ_AUTH_USER/GZ_AUTH_PASS gesetzt ' +
				'(Quelle: Staging-.env, siehe docs/reference/operations_playbook.md).'
		);
	}
	return zugang;
}

/** Zweitkonto: GZ_ZWEITKONTO_*, sonst GZ_AUTH_* — bricht ab, wenn es das Prüfkonto wäre. */
export function zweitkontoZugang(env: Umgebung = process.env): Zugang {
	const zugang = paar(env, 'GZ_ZWEITKONTO', true) ?? paar(env, 'GZ_AUTH');
	if (!zugang) {
		throw new Error('Zweitkonto-Zugang fehlt: weder GZ_ZWEITKONTO_USER/GZ_ZWEITKONTO_PASS noch GZ_AUTH_USER/GZ_AUTH_PASS gesetzt.');
	}
	if (zugang.user === pruefkontoZugang(env).user) {
		throw new Error('Zweitkonto ist dasselbe Konto wie das Prüfkonto — GZ_ZWEITKONTO_* auf ein anderes Konto setzen.');
	}
	return zugang;
}

/** ID des Vergleichs mit exakt dem Seed-Namen aus der Preset-Liste. */
export function vergleichAusPresets(liste: unknown): string {
	const eintraege = Array.isArray(liste) ? (liste as Array<{ id?: unknown; name?: unknown }>) : [];
	const treffer = eintraege.find((e) => e?.name === SEED_VERGLEICH_NAME && typeof e.id === 'string' && e.id !== '');
	if (!treffer) throw new Error(`Vergleich „${SEED_VERGLEICH_NAME}" nicht gefunden. ${SEED_HINWEIS}`);
	return treffer.id as string;
}

/** Trip-ID des Seeds: ELEMENTLISTE_TRIP_ID hat Vorrang; sonst lesender Lookup mit dem eingeloggten Prüfkonto. */
export async function seedTripId(api: LeseApi, env: Umgebung = process.env): Promise<string> {
	const envTrip = gesetzt(env, 'ELEMENTLISTE_TRIP_ID');
	if (envTrip) return envTrip;
	const res = await api.get(`/api/trips/${SEED_TRIP_ID}`);
	if (!res.ok()) throw new Error(`Trip ${SEED_TRIP_ID} nicht abrufbar (HTTP ${res.status()}). ${SEED_HINWEIS}`);
	return SEED_TRIP_ID;
}

/** Vergleichs-ID des Seeds: ELEMENTLISTE_ORTE_ID hat Vorrang; sonst lesender Lookup per Name. */
export async function seedVergleichId(api: LeseApi, env: Umgebung = process.env): Promise<string> {
	const envOrte = gesetzt(env, 'ELEMENTLISTE_ORTE_ID');
	if (envOrte) return envOrte;
	const res = await api.get('/api/compare/presets');
	if (!res.ok()) throw new Error(`Vergleichsliste nicht abrufbar (HTTP ${res.status()}). ${SEED_HINWEIS}`);
	return vergleichAusPresets(await res.json());
}

/** Seed-IDs: ELEMENTLISTE_* haben Vorrang; sonst lesender Lookup mit dem eingeloggten Prüfkonto. */
export async function seedIds(api: LeseApi, env: Umgebung = process.env): Promise<{ route: string; vergleich: string }> {
	const route = await seedTripId(api, env);
	const vergleich = await seedVergleichId(api, env);
	return { route, vergleich };
}
