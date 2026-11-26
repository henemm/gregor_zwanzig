// Issue #2913 (Epic #2791) — Staging-Abgleich der Elementliste (AC-13 bis AC-15).
// Spec: docs/specs/modules/einstellungen_neu_neustart_adr_waechter_elementliste.md
//
// Start über den Starter (übersetzt CLI-Flags in die Umgebung und reicht den Exit-Code durch):
//   cd frontend && npm run elementliste:abgleich -- [--strict] [--abnahme] [--scope <reiter[/zustand]>] [--sprache en]
// Direkt: npx playwright test --config playwright.elementliste.staging.config.ts
//   (Umgebung: ELEMENTLISTE_SCOPE, ELEMENTLISTE_STRICT, ELEMENTLISTE_ABNAHME, ELEMENTLISTE_SPRACHE, ELEMENTLISTE_TRIP_ID,
//    ELEMENTLISTE_ORTE_ID, ELEMENTLISTE_BERICHT_DIR; Login GZ_AUTH_USER/GZ_AUTH_PASS)
//
// Die ganze Entscheidungslogik (Prod-Schutz, Optionen, Scope, Route-Abfangen-Plan, Bewertung, Bericht,
// Exit) liegt browserfrei in e2e/elementliste_abgleich_logik.ts und ist dort per Unit-Test bewacht.
// Diese Spec bedient nur den Browser. Login nur im Speicher (keine Auth-Datei), Logout am Ende.
// Fehlt dem Test-Konto ein Trip bzw. Orts-Vergleich, legt die Spec einen kurzlebigen Prüf-Datensatz
// (Präfix E2E-GZ) an und löscht ihn am Ende wieder. „Konto mit Lücken“ entsteht nur durch Umschreiben
// lesender Konto-Abrufe (GET) im Browser; das Konto selbst bleibt unverändert.
// Mockup-Daten im Prüfkonto (#2967): vorher auf dem Staging-Host scripts/staging_pruefkonto_mockupdaten.py
// laufen lassen (Runbook docs/runbooks/staging_pruefkonto_seed.md); es gibt ELEMENTLISTE_TRIP_ID und
// ELEMENTLISTE_ORTE_ID aus. Geschrieben wird nur dort, dieser Abgleich bleibt rein lesend.
// Login dafür mit dem Prüfkonto: GZ_AUTH_USER/GZ_AUTH_PASS = GZ_PRUEFKONTO_USER/GZ_PRUEFKONTO_PASS aus der
// Staging-.env (nicht das geteilte Konto „default“, sonst fehlen die Seed-IDs).
import { test, expect, type Page, type APIRequestContext } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';
import {
	STAGING_URL,
	planeAbgleich,
	routenPlan,
	herstellungsGrund,
	seitenPfad,
	bewerteAbschnitt,
	alleNichtPruefbar,
	sprachGrund,
	wiederherzustellendeSprache,
	stelleSpracheWieder,
	GEGENRICHTUNG_WURZEL,
	HUB_ANKER_KOPF,
	HUB_ANKER_FLAECHE,
	zaehleAnker,
	warteAufHubAnker,
	type HubAnker,
	istGegenrichtung,
	werteGegenrichtungAus,
	angenommeneWerte,
	namenPaareAus,
	grenzenAusMockup,
	ladeRegeln,
	ladeKontoTexte,
	metrikNamenAusRegister,
	werteLaufAus,
	bedieneAbschnitt,
	abschnittHaken,
	mitAufraeumen,
	ordneAbschnitte,
	eingabeText,
	sichtbareTextBloecke,
	seitenIdFuer,
	wetterPruefPayload,
	eigeneVorlagePayload,
	pruefReste,
	wetterTripId,
	WETTER_DATENSAETZE,
	WETTER_NAME,
	WETTER_TRIP_ID,
	EIGENE_VORLAGE_NAME,
	ABGLEICH_TRIP_ID,
	ABGLEICH_NAMEN,
	MOCKUP_LAGE,
	type WetterIds,
	type WetterPruefQuelle,
	type BedienOps,
	type Ergebnis,
	type ListenElement,
	type OhneHubEintrag,
	type ZusaetzlichEintrag
} from './elementliste_abgleich_logik.ts';

// Prod-Schutz, bevor irgendeine Seite geladen wird (auch bei überschriebener Base-URL).
assertNotProdBaseURL(process.env.GZ_SVELTE_BASE ?? STAGING_URL);

const FRONTEND = join(fileURLToPath(new URL('.', import.meta.url)), '..');
const LISTE = join(FRONTEND, '..', 'docs/context/einstellungen_neu/elementliste.json');
const FREIGABEN = join(FRONTEND, '..', 'docs/context/einstellungen_neu/elementliste_freigaben.json');
// Ganzseiten-Abgleich (feat_2913_abgleich_ganzseite): Besitzer je Abweichung und Ausnahmen der Gegenrichtung.
const BESITZER = join(FRONTEND, '..', 'docs/context/einstellungen_neu/elementliste_besitzer.json');
// #3421: Grenzwerte des Soll-Bilds (TRIP_METRICS / ORTE_METRICS) für den Grenzen-Prüfdatensatz.
const MOCKUP = join(FRONTEND, '..', 'docs/context/einstellungen_neu/seiten/mockup-hub-fassung4.html');
// #3422: Namenspaare DE → EN (Schnappschuss + Server-Katalog vergleich.zeile.*) für die EN-Gegenrichtung.
const METRIK_NAMEN = join(FRONTEND, '..', 'docs/context/einstellungen_neu/daten/metrik_namen.json');
const KATALOG_VERGLEICH = (sprache: 'de' | 'en') => join(FRONTEND, '..', `src/i18n/messages/${sprache}/vergleich.json`);
const BERICHT_DIR = process.env.ELEMENTLISTE_BERICHT_DIR ?? join(FRONTEND, 'test-results', 'elementliste-abgleich');

/**
 * Sichtbare Texte (eigene Textknoten, aria-label von Schaltern/Knöpfen/Gruppen/Textfeldern, Eingaben) in
 * DOM-Reihenfolge. #2913 Fix-Loop 2: vorher werden alle `details` im Abschnitt geöffnet, wie der Generator
 * es im Mockup tut (C1); aria-label auch von role=group/textbox, z. B. bits-ui TimeField (C2).
 */
async function texteImBereich(page: Page, abschnitt: string): Promise<{ marker: boolean; texte: string[] }> {
	// #3251: Haken der App (vorlage-abweichung liegt in der Karte data-abschnitt="vorlage").
	const selektor = `[data-abschnitt="${abschnittHaken(abschnitt)}"]`;
	await page.evaluate(oeffneDetails, { selektor, alle: false });
	await page.waitForTimeout(200);
	return page.evaluate(sichtbareTexte, { selektor, alle: false });
}

/**
 * Gegenrichtung (feat_2913_abgleich_ganzseite, AC-5): sichtbare Texte unter ALLEN Hub-Containern
 * (`GEGENRICHTUNG_WURZEL`: HubKopf und Reiterfläche), nie `body` — Seitenleiste, BottomNav und
 * SaveIndicator liegen außerhalb und gehören nicht zur Seite.
 */
async function texteUnterHub(page: Page): Promise<{ anker: HubAnker; texte: string[] }> {
	await page.evaluate(oeffneDetails, { selektor: GEGENRICHTUNG_WURZEL, alle: true });
	await page.waitForTimeout(200);
	// Fix-Loop 3 (F002): Rohwerte je Anker; entscheiden tut pruefeHubAnker (über werteGegenrichtungAus).
	// #2973: bei langsamer Staging-Antwort fehlt ein Anker kurz; bis ~5 s warten, dann erst Texte lesen.
	const anker = await warteAufHubAnker(
		async () => await page.evaluate(zaehleAnker, { kopf: HUB_ANKER_KOPF, flaeche: HUB_ANKER_FLAECHE }),
		(ms) => page.waitForTimeout(ms)
	);
	const { texte } = await page.evaluate(sichtbareTexte, { selektor: GEGENRICHTUNG_WURZEL, alle: true });
	return { anker, texte };
}

/** Im Browser: alle `details` unter dem ersten (bzw. jedem) Treffer des Selektors öffnen. */
function oeffneDetails(arg: { selektor: string; alle: boolean }): void {
	const wurzeln = arg.alle ? Array.from(document.querySelectorAll(arg.selektor)) : [document.querySelector(arg.selektor)];
	for (const w of wurzeln) w?.querySelectorAll('details').forEach((d) => ((d as HTMLDetailsElement).open = true));
}

/**
 * Im Browser: sichtbare Texte unter dem ersten Treffer (`alle: false`, ohne Treffer ersatzweise die ganze
 * Seite für „nur seitenweit gefunden“) bzw. unter jedem Treffer (`alle: true`, ohne Treffer keine Texte).
 */
function sichtbareTexte(arg: { selektor: string; alle: boolean }): { marker: boolean; texte: string[] } {
	const treffer = arg.alle ? Array.from(document.querySelectorAll(arg.selektor)) : [document.querySelector(arg.selektor)].filter((x): x is Element => x !== null);
	const wurzeln = treffer.length > 0 ? treffer.filter((w) => !treffer.some((a) => a !== w && a.contains(w))) : arg.alle ? [] : [document.body];
	const eingabe = (window as unknown as { __gzEingabeText?: (e: { tag: string; ariaLabel: string | null; placeholder: string | null; value: string }) => string }).__gzEingabeText;
	if (typeof eingabe !== 'function') throw new Error('sichtbareTexte: window.__gzEingabeText fehlt (addInitScript mit eingabeText nicht gelaufen)');
	// #3203 (Fix-Loop 1, F003): die ganze Sammel-Regel (Sichtbarkeit, Eingaben, aria-label, Textblöcke) ist
	// sichtbareTextBloecke aus der Logik (per addInitScript im Fenster, dort per node --test bewacht).
	type Sammler = (w: Element, stil: (e: Element) => { display: string; visibility: string }, ein: typeof eingabe) => string[];
	const sammle = (window as unknown as { __gzSichtbareTextBloecke?: Sammler }).__gzSichtbareTextBloecke;
	if (typeof sammle !== 'function') throw new Error('sichtbareTexte: window.__gzSichtbareTextBloecke fehlt (addInitScript mit sichtbareTextBloecke nicht gelaufen)');
	// Anzeige wie bisher über checkVisibility (auch Vorfahren oberhalb der Wurzel, content-visibility);
	// display:contents hat keine eigene Box, seine Kinder bleiben sichtbar.
	const stil = (e: Element) => {
		const s = getComputedStyle(e);
		return { display: s.display === 'contents' || e.checkVisibility() ? s.display : 'none', visibility: s.visibility };
	};
	const texte: string[] = [];
	for (const wurzel of wurzeln) texte.push(...sammle(wurzel, stil, eingabe));
	return { marker: treffer.length > 0, texte };
}


/**
 * Navigation im Browser statt Seitenaufruf vom Server: erst die Startseite laden, dann einen Link zum Ziel
 * klicken. SvelteKit holt die Hub-Daten dabei per `__data.json`, das sich abfangen lässt (beim ersten,
 * serverseitig gerenderten Aufruf stecken sie fertig im HTML).
 */
async function navigiereImBrowser(page: Page, pfad: string): Promise<void> {
	await page.goto('/', { waitUntil: 'load' });
	await page.waitForTimeout(1000);
	await page.evaluate((href) => {
		const wurzel = document.querySelector('body > div[style*="contents"]') ?? document.body;
		const a = document.createElement('a');
		a.href = href;
		a.id = 'e2e-gz-elementliste-nav';
		a.textContent = 'Abgleich';
		wurzel.appendChild(a);
	}, pfad);
	const ziel = new URL(pfad, page.url()).pathname;
	await Promise.all([page.waitForURL((u) => u.pathname === ziel, { timeout: 20_000 }), page.click('#e2e-gz-elementliste-nav')]);
}

/** Prüf-Datensätze, falls das Test-Konto keine hat; Rückgabe: Aufräumfunktion. */
async function pruefDaten(api: APIRequestContext, ids: Record<string, string | null>): Promise<() => Promise<void>> {
	const aufraeumen: Array<() => Promise<unknown>> = [];
	if (!ids.trip) {
		const id = ABGLEICH_TRIP_ID;
		await api.delete(`/api/trips/${id}`).catch(() => {});
		const r = await api.post('/api/trips', {
			data: {
				id,
				name: ABGLEICH_NAMEN[0],
				// #2913 c2: Region wie im Mockup, damit die Eyebrow „Trip · Mallorca“ prüfbar ist (nicht nur „Trip“).
				region: 'Mallorca',
				stages: [
					{
						id: `${id}-stage-1`,
						name: 'Etappe 1',
						date: new Date().toISOString().slice(0, 10),
						waypoints: [
							{ id: `${id}-wp-1`, name: 'Start', lat: 39.6, lon: 2.5, elevation_m: 100 },
							{ id: `${id}-wp-2`, name: 'Ziel', lat: 39.7, lon: 2.6, elevation_m: 600 }
						]
					}
				]
			}
		});
		if (r.ok()) {
			ids.trip = id;
			aufraeumen.push(() => api.delete(`/api/trips/${id}`));
		}
	}
	if (!ids.orte) {
		const ort = await api.post('/api/locations', { data: { name: ABGLEICH_NAMEN[1], lat: 51.96, lon: 7.63 } });
		if (ort.ok()) {
			const ortId = String((await ort.json()).id);
			aufraeumen.push(() => api.delete(`/api/locations/${ortId}`));
			const v = await api.post('/api/compare/presets', {
				// #2913 c2: Region und Morgen-Briefing 07:00, damit Eyebrow („Orte · {region}“) und Meta-Zeile prüfbar sind.
				// Region bewusst nicht „Münsterland“: das ist im Mockup der Name des Vergleichs (Brotkrumen, Titel); die
				// Region steht live zusätzlich unter dem Titel und würde sonst als Name gefunden (falsche Reihenfolge).
				data: {
					name: ABGLEICH_NAMEN[2],
					location_ids: [ortId],
					schedule: 'daily',
					profil: 'wandern',
					empfaenger: ['urlauber@example.com'],
					morning_enabled: true,
					morning_time: '07:00:00',
					display_config: { region: 'Westfalen' }
				}
			});
			if (v.ok()) {
				const vid = String((await v.json()).id);
				ids.orte = vid;
				aufraeumen.unshift(() => api.delete(`/api/compare/presets/${vid}`));
			}
		}
	}
	return async () => {
		for (const f of aufraeumen) await f().catch(() => {});
	};
}

/** Liste aus einer API-Antwort (Array oder Objekt mit einem Array-Feld). */
function alsListe(x: unknown): Record<string, unknown>[] {
	if (Array.isArray(x)) return x as Record<string, unknown>[];
	const feld = Object.values((x ?? {}) as Record<string, unknown>).find(Array.isArray);
	return (feld ?? []) as Record<string, unknown>[];
}

// #3192 (AC-1): je Kontext zwei Prüf-Datensätze; welcher je Abschnitt gilt, entscheidet seitenIdFuer (Logik).
const KEINE_WETTER_IDS: WetterIds = { trip: null, orte: null };

/** `allowed_sides` je Metrik aus /api/metrics (nach Kategorie gruppiert); Fehlschlag ⇒ {} (dann keine Overrides). */
async function metrikSeiten(api: APIRequestContext): Promise<Record<string, { allowed_sides: string | null }>> {
	const r = await api.get('/api/metrics').catch(() => null);
	const antwort: unknown = r?.ok() ? await r.json().catch(() => null) : null;
	const out: Record<string, { allowed_sides: string | null }> = {};
	for (const gruppe of Object.values((antwort ?? {}) as Record<string, unknown>)) {
		if (!Array.isArray(gruppe)) continue;
		for (const m of gruppe as Record<string, unknown>[]) {
			if (typeof m?.id === 'string') out[m.id] = { allowed_sides: typeof m.allowed_sides === 'string' ? m.allowed_sides : null };
		}
	}
	return out;
}

/**
 * #2966 (AC-8), #3192 (AC-1 bis AC-3): Wetter-Prüf-Datensätze auf Mockup-Lage — je Kontext „mit Abweichung“
 * (gültiger Grenzen-Override je Briefing-Metrik, Gewitter über `thunder`) und „ohne Abweichung“ (nur Vorlage
 * und Metrik-Auswahl); Trip aktiv `alpen-trekking`, Orts-Vergleich `allgemein` mit drei Orten; dazu je Art
 * eine eigene Vorlage. Reste eines abgebrochenen Laufs werden vorher entfernt; die Aufräumschritte landen in
 * `aufraeumen` und laufen im finally des Tests (auch nach einem Fehler). Der GR221-Seed bleibt unberührt
 * (nur eigene IDs und Namen mit Präfix E2E-GZ werden gelöscht).
 */
async function wetterPruefDaten(api: APIRequestContext, liste: ListenElement[], aufraeumen: Array<() => Promise<unknown>>): Promise<WetterIds> {
	const ids: WetterIds = { trip: {}, orte: {} };
	for (const id of [WETTER_TRIP_ID, ...WETTER_DATENSAETZE.map(wetterTripId)]) await api.delete(`/api/trips/${id}`).catch(() => {});
	for (const p of alsListe(await (await api.get('/api/compare/presets')).json().catch(() => []))) {
		if (String(p.name ?? '').startsWith(WETTER_NAME)) await api.delete(`/api/compare/presets/${encodeURIComponent(String(p.id))}`).catch(() => {});
	}
	for (const o of alsListe(await (await api.get('/api/locations')).json().catch(() => []))) {
		if (String(o.name ?? '').startsWith(WETTER_NAME)) await api.delete(`/api/locations/${encodeURIComponent(String(o.id))}`).catch(() => {});
	}
	for (const p of alsListe(await (await api.get('/api/metric-presets')).json().catch(() => []))) {
		if (p.name === EIGENE_VORLAGE_NAME) await api.delete(`/api/metric-presets/${encodeURIComponent(String(p.id))}`).catch(() => {});
	}
	// Payloads (Metrik-Auswahl, Overrides, Beschreibung) baut die Logik (wetterPruefPayload, eigeneVorlagePayload; unit-getestet).
	const quelle: WetterPruefQuelle = {
		liste,
		vorlagen: alsListe(await (await api.get('/api/templates')).json().catch(() => [])),
		eig: await metrikSeiten(api),
		ortIds: [],
		datum: new Date().toISOString().slice(0, 10)
	};

	// #3421: Grenzen-Datensatz mit den Grenzwerten des Soll-Bilds je Kontext (auch Minuswerte).
	const mockup = readFileSync(MOCKUP, 'utf8');
	for (const d of WETTER_DATENSAETZE) {
		const id = wetterTripId(d);
		const trip = await api.post('/api/trips', { data: wetterPruefPayload('trip', d, { ...quelle, grenzen: grenzenAusMockup(mockup, 'trip') }) });
		if (trip.ok()) {
			ids.trip![d] = id;
			aufraeumen.push(() => api.delete(`/api/trips/${id}`));
		} else console.error(`Wetter-Prüf-Trip (${d}) nicht anlegbar: HTTP ${trip.status()} ${await trip.text().catch(() => '')}`);
	}

	// Drei eigene Prüf-Orte (Mockup: „für diese Orte“), geteilt von beiden Vergleichs-Datensätzen.
	for (let i = 0; i < MOCKUP_LAGE.orte.orte; i++) {
		const ort = await api.post('/api/locations', { data: { name: `${WETTER_NAME} Ort ${i + 1}`, lat: 51.96 + i * 0.05, lon: 7.63 + i * 0.05 } });
		if (!ort.ok()) continue;
		const ortId = String((await ort.json()).id);
		quelle.ortIds.push(ortId);
		aufraeumen.push(() => api.delete(`/api/locations/${ortId}`));
	}
	if (quelle.ortIds.length === MOCKUP_LAGE.orte.orte) {
		for (const d of WETTER_DATENSAETZE) {
			const v = await api.post('/api/compare/presets', { data: wetterPruefPayload('orte', d, { ...quelle, grenzen: grenzenAusMockup(mockup, 'orte') }) });
			if (v.ok()) {
				const vid = String((await v.json()).id);
				ids.orte![d] = vid;
				aufraeumen.unshift(() => api.delete(`/api/compare/presets/${vid}`));
			} else console.error(`Wetter-Prüf-Vergleich (${d}) nicht anlegbar: HTTP ${v.status()} ${await v.text().catch(() => '')}`);
		}
	} else console.error(`Wetter-Prüf-Orte: nur ${quelle.ortIds.length} von ${MOCKUP_LAGE.orte.orte} anlegbar`);

	for (const kind of ['route', 'vergleich'] as const) {
		const p = await api.post('/api/metric-presets', { data: eigeneVorlagePayload(kind) });
		if (p.ok()) {
			const pid = String((await p.json()).id);
			aufraeumen.push(() => api.delete(`/api/metric-presets/${encodeURIComponent(pid)}`));
		} else console.error(`Eigene Prüf-Vorlage (${kind}) nicht anlegbar: HTTP ${p.status()}`);
	}
	return ids;
}

/**
 * Fix-Loop F002 (b): Leckprüfung nach dem Aufräumen — Bestand per API lesen, Reste filtert pruefReste (Logik,
 * unit-getestet). Ein gescheiterter Abruf ist selbst ein Befund (nie still „kein Leck“).
 */
async function leckPruefung(api: APIRequestContext): Promise<string[]> {
	const befunde: string[] = [];
	const lies = async (pfad: string): Promise<Record<string, unknown>[]> => {
		const r = await api.get(pfad).catch(() => null);
		if (!r?.ok()) {
			befunde.push(`Abruf ${pfad} für die Leckprüfung fehlgeschlagen: HTTP ${r?.status() ?? 'ohne Antwort'}`);
			return [];
		}
		return alsListe(await r.json().catch(() => []));
	};
	const bestand = { trips: await lies('/api/trips'), vergleiche: await lies('/api/compare/presets'), orte: await lies('/api/locations'), vorlagen: await lies('/api/metric-presets') };
	return [...befunde, ...pruefReste(bestand)];
}

/** Metriken mit Knopf „Grenzen ändern“ auf der geladenen Seite (= im Briefing, nicht reine Anzeige). */
async function briefingAufSeite(page: Page): Promise<string[]> {
	const praefix = 'wetter-grenzen-aendern-';
	return page.evaluate((p) => Array.from(document.querySelectorAll(`[data-testid^="${p}"]`)).map((el) => (el.getAttribute('data-testid') ?? '').slice(p.length)), praefix);
}

/**
 * #2966: Browser-Operationen für `bedieneAbschnitt` (Ablauf und Tripwire liegen in der Logik). Vor einer Taste
 * wird der Fokus gelöst, damit die Taste das Fenster erreicht. Die Speichern-Karte (#3190) beendet Escape bei
 * Fokus in der Karte selbst; der Bedienplan schließt sie darum über „Abbrechen“ (save-preset-cancel).
 */
function seitenOps(page: Page, neuLaden: () => Promise<void>, anfragen: { method: string; url: string }[]): BedienOps {
	return {
		neuLaden,
		briefing: () => briefingAufSeite(page),
		klick: async (testid) => {
			await page.locator(`[data-testid="${testid}"]`).first().click({ timeout: 10_000 });
			await page.waitForTimeout(400);
		},
		taste: async (taste) => {
			await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
			await page.keyboard.press(taste);
			await page.waitForTimeout(400);
		},
		lesen: (abschnitt) => texteImBereich(page, abschnitt),
		nachlauf: () => page.waitForTimeout(1500).catch(() => {}),
		anfragen
	};
}

test('Elementliste gegen Staging: Bericht je Element (gefunden / abweichend / nicht_pruefbar)', async ({ page, baseURL }) => {
	test.setTimeout(1_800_000);
	const alle: ListenElement[] = JSON.parse(readFileSync(LISTE, 'utf8')).elemente;
	const plan = planeAbgleich({ liste: alle, env: process.env, baseURL });
	const ergebnisse = new Map<string, Ergebnis>();
	const zusaetzlich: ZusaetzlichEintrag[] = [];
	// Gegenrichtungs-Kombinationen ohne Hub-Marker: im Bericht sichtbar, unter --strict/--abnahme rot.
	const ohneHub: OhneHubEintrag[] = [];
	// Freigaben, Besitzer und Ausnahmen zuerst lesen: ein ungültiger Eintrag bricht ab, bevor eine Seite lädt.
	const regeln = ladeRegeln({ freigaben: FREIGABEN, besitzer: BESITZER }, alle);
	const lies = (pfad: string): unknown => JSON.parse(readFileSync(pfad, 'utf8'));
	const namenDeEn = namenPaareAus(lies(METRIK_NAMEN), lies(KATALOG_VERGLEICH('de')), lies(KATALOG_VERGLEICH('en')));
	const api = page.request;

	if (process.env.GZ_AUTH_USER && process.env.GZ_AUTH_PASS) {
		const login = await api.post('/api/auth/login', { data: { username: process.env.GZ_AUTH_USER, password: process.env.GZ_AUTH_PASS } });
		expect(login.ok(), `Login HTTP ${login.status()}`).toBeTruthy();
	}
	const ids: Record<string, string | null> = { trip: process.env.ELEMENTLISTE_TRIP_ID ?? null, orte: process.env.ELEMENTLISTE_ORTE_ID ?? null };
	// C3: die Profilsprache überstimmt das Cookie. Sie wird für den Lauf gesetzt und im finally auf den
	// vorherigen Wert zurückgestellt (geteiltes Staging-Hilfskonto — Zurückstellen ist Pflicht).
	const profil = await api.get('/api/auth/profile');
	const vorherSprache = wiederherzustellendeSprache(profil.ok() ? await profil.json() : null);
	const aufraeumen = await pruefDaten(api, ids);
	// #2966 (AC-7): jeder Schreib-Befund des Tripwires lässt den Lauf scheitern. Der Listener speist die
	// Anfragen-Liste für bedieneAbschnitt (gezählt wird ab Bedienbeginn).
	const schreibBefunde: string[] = [];
	const bedienAnfragen: { method: string; url: string }[] = [];
	page.on('request', (r) => bedienAnfragen.push({ method: r.method(), url: r.url() }));
	let leckBefunde: string[] = ['Leckprüfung nicht gelaufen'];
	// Fix-Loop F001 (AC-4): die im Browser wirkende Eingabefeld-Regel IST eingabeText (per CDP, nicht CSP-betroffen).
	await page.addInitScript(`window.__gzEingabeText = ${eingabeText.toString()};`);
	// #3203: die im Browser wirkende Sichtbarkeitsregel IST sichtbareTextBloecke (keine Kopie in dieser Spec).
	await page.addInitScript(`window.__gzSichtbareTextBloecke = ${sichtbareTextBloecke.toString()};`);
	let spracheZurueck: Awaited<ReturnType<typeof stelleSpracheWieder>> = { ok: false, meldung: 'Zurückstellen der Profilsprache nicht gelaufen' };
	try {
		const gesetzt = await api.put('/api/auth/profile', { data: { language: plan.sprache } });
		expect(gesetzt.ok(), `Profilsprache ${plan.sprache} setzen: HTTP ${gesetzt.status()}`).toBeTruthy();
		const konto = await ladeKontoTexte((pfad) => api.get(pfad), ids);
		// #3011: Metriknamen einmal laden; `{metrik}` der Gegenrichtung erklärt nur sie (und Listen-Namen). Fehlschlag ⇒ [] (nie geraten).
		const register = await api.get('/api/metrics').catch(() => null);
		const metrikNamen = register?.ok() ? metrikNamenAusRegister(await register.json().catch(() => null)) : [];
		if (metrikNamen.length === 0) console.error('Elementlisten-Abgleich: keine Metriknamen aus /api/metrics; {metrik} erklärt nur Namen der Elementliste');
		const templates = await api.get('/api/templates');
		const vorlagen = alsListe(templates.ok() ? await templates.json() : []).map((v) => String(v.id));
		// #2966 (AC-8): Wetter-Prüf-Datensatz (alle Metriken) nur für Bedien-Abschnitte; mitAufraeumen löscht ihn immer.
		const mitWetter = plan.kombis.some(({ k }) => k.reiter === 'wetter');
		await mitAufraeumen((auf) => (mitWetter ? wetterPruefDaten(api, alle, auf) : Promise.resolve(KEINE_WETTER_IDS)), async (wetterIds) => {
			for (const { k, el } of plan.kombis) {
				const id = ids[k.ctx];
				if (!id) {
					for (const [i, e] of alleNichtPruefbar(el, `kein ${k.ctx === 'trip' ? 'Trip' : 'Orts-Vergleich'} im Test-Konto und Prüf-Datensatz nicht anlegbar`)) ergebnisse.set(i, e);
					continue;
				}
				const rp = routenPlan(k.zustand);
				await page.unrouteAll({ behavior: 'ignoreErrors' });
				if (rp.art === 'nicht_herstellbar') {
					for (const [i, e] of alleNichtPruefbar(el, rp.grund)) ergebnisse.set(i, e);
					continue;
				}
				if (rp.art === 'haengen') await page.route(rp.muster, () => new Promise<void>(() => {}));
				if (rp.art === 'fehler') await page.route(rp.muster, (route) => route.fulfill({ status: rp.status, body: '{"error":"elementliste-abgleich"}' }));
				let umgeschrieben = 0;
				if (rp.art === 'konto_luecken') {
					// Nur lesende Konto-Abrufe werden umgeschrieben; Schreib-Requests laufen unverändert durch.
					await page.route(rp.muster, async (route) => {
						if (route.request().method() !== rp.methode) return route.continue();
						const antwort = await route.fetch();
						const r = rp.ersetze(route.request().url(), await antwort.text());
						if (r.geaendert) umgeschrieben++;
						await route.fulfill({ response: antwort, body: r.text });
					});
				}
				// Seitenaufruf unter dem Routen-Plan der Kombination; #2966: auch der Neuaufruf je Bedien-Abschnitt.
				const seiteLaden = async (seitenId: string): Promise<void> => {
					const pfad = seitenPfad(k.ctx, seitenId, k.reiter);
					if (rp.art === 'konto_luecken' && rp.navigation === 'browser') {
						await navigiereImBrowser(page, pfad);
					} else {
						await page.goto(pfad, { waitUntil: 'domcontentloaded' });
					}
					await page.waitForTimeout(rp.art === 'haengen' ? 1500 : 3000);
				};
				await seiteLaden(id);
				const falscheSprache = sprachGrund(plan.sprache, await page.evaluate(() => document.documentElement.getAttribute('lang')));
				if (falscheSprache) {
					for (const [i, e] of alleNichtPruefbar(el, falscheSprache)) ergebnisse.set(i, e);
					continue;
				}
				const nichtHergestellt = herstellungsGrund(rp, umgeschrieben);
				if (nichtHergestellt) {
					for (const [i, e] of alleNichtPruefbar(el, nichtHergestellt)) ergebnisse.set(i, e);
					continue;
				}
				if (k.segment) {
					const knopf = page.getByRole('radio', { name: k.segment, exact: true }).or(page.getByRole('tab', { name: k.segment, exact: true }));
					if ((await knopf.count()) === 0) {
						for (const [i, e] of alleNichtPruefbar(el, `Kanal-Segment „${k.segment}“ ist auf der Seite nicht bedienbar`)) ergebnisse.set(i, e);
						continue;
					}
					await knopf.first().click();
				}
				const abschnitte = new Map<string, ListenElement[]>();
				for (const e of el) abschnitte.set(e.abschnitt, [...(abschnitte.get(e.abschnitt) ?? []), e]);
				// #2966: Bedien-Abschnitte erst nach der Gegenrichtung, je mit frischer Seite.
				// #3192 (AC-2): aktive Vorlage der Mockup-Lage je Kontext (Trip alpen-trekking, Orte allgemein).
				const lage = { ctx: k.ctx, vorlagen, aktiveVorlage: (MOCKUP_LAGE as Record<string, { aktiv: string } | undefined>)[k.ctx]?.aktiv ?? 'allgemein' };
				const zuBedienen: Array<[string, ListenElement[]]> = [];
				for (const weg of ordneAbschnitte([...abschnitte.keys()], lage, alle)) {
					const { abschnitt } = weg;
					const liste = abschnitte.get(abschnitt)!;
					if (weg.weg === 'bedienen') {
						zuBedienen.push([abschnitt, liste]);
						continue;
					}
					const befund = await texteImBereich(page, abschnitt);
					if (weg.weg === 'nicht_herstellbar' && !befund.marker) {
						for (const [i, e] of alleNichtPruefbar(liste, weg.grund)) ergebnisse.set(i, e);
						continue;
					}
					for (const [i, e] of bewerteAbschnitt(liste, befund, plan.sprache, abschnitt)) ergebnisse.set(i, e);
				}
				// Gegenrichtung: nur Zustand normal, ohne Segment, Desktop-Viewport (Config); erklärt wird gegen die
				// ganze Liste (kopf/reiterleiste stehen unter Reiter wetter), unabhängig vom Scope.
				if (istGegenrichtung(k)) {
					const hub = await texteUnterHub(page);
					// Fehlt Kopf oder Reiterfläche, ist die Seite nur teilweise gelesen: nie still „kein zusaetzlich“, sondern Befund ohneHub.
					// #3419 Nr. 6: Beispielwerte, die die Hinrichtung dieser Seite angenommen hat, gelten als erklärt.
					const angenommen = angenommeneWerte(el, ergebnisse, plan.sprache);
					const gegen = werteGegenrichtungAus({ ctx: k.ctx, reiter: k.reiter, anker: hub.anker, texte: hub.texte }, alle, regeln.ausnahmen, konto, plan.sprache, metrikNamen, { namenDeEn, angenommen });
					zusaetzlich.push(...gegen.zusaetzlich);
					if (gegen.ohneHub) ohneHub.push(gegen.ohneHub);
				}
				// #2966 (AC-6, AC-7): Script-Zustände per Bedienplan herstellen — nur öffnen, abbrechen, leer absenden.
				for (const [abschnitt, liste] of zuBedienen) {
					// #3192 (AC-1): Grenzen-Abschnitte auf dem Datensatz mit Abweichung, Vorlage-Abschnitte ohne.
					const seitenId = k.reiter === 'wetter' ? seitenIdFuer(abschnitt, k.ctx, wetterIds) : id;
					if (!seitenId) {
						for (const [i, e] of alleNichtPruefbar(liste, `Wetter-Prüf-Datensatz (${k.ctx}, Abschnitt ${abschnitt}) nicht anlegbar`)) ergebnisse.set(i, e);
						continue;
					}
					const lauf = await bedieneAbschnitt(abschnitt, lage, seitenOps(page, () => seiteLaden(seitenId), bedienAnfragen));
					if (lauf.art === 'schreibbefund') {
						schreibBefunde.push(`${k.ctx}/${k.zustand}/${abschnitt}: ${lauf.grund}`);
						for (const e of liste) ergebnisse.set(e.id, { status: 'abweichend', grund: lauf.grund });
					} else if (lauf.art === 'nicht_pruefbar') {
						for (const [i, e] of alleNichtPruefbar(liste, lauf.grund)) ergebnisse.set(i, e);
					} else {
						for (const [i, e] of bewerteAbschnitt(liste, lauf.befund, plan.sprache, abschnitt)) ergebnisse.set(i, e);
					}
				}
			}
		});
	} finally {
		await page.unrouteAll({ behavior: 'ignoreErrors' });
		spracheZurueck = await stelleSpracheWieder((daten) => api.put('/api/auth/profile', { data: daten }), vorherSprache);
		await aufraeumen();
		// Fix-Loop F002 (b): nach beiden Aufräumschritten (Wetter-Prüfdaten in mitAufraeumen, pruefDaten hier).
		leckBefunde = await leckPruefung(api);
		await api.post('/api/auth/logout').catch(() => {});
	}

	// Freigaben, Besitzer, Bericht und Exit (strict UND abnahme aus plan.optionen) bildet die Logik.
	const { pfade, ende } = werteLaufAus({ plan, ergebnisse, zusaetzlich, ohneHub, regeln, berichtDir: BERICHT_DIR });
	console.log(`Elementlisten-Abgleich: ${ende.meldung} → ${pfade.json}, ${pfade.md}`);
	// F005: ein gescheitertes Zurückstellen der Profilsprache lässt den Lauf scheitern (auch ohne --strict).
	expect(spracheZurueck.ok, spracheZurueck.ok ? '' : spracheZurueck.meldung).toBe(true);
	// #2966 (AC-7): eine schreibende Anfrage während der Bedienung ist immer ein Fehlschlag.
	expect(schreibBefunde, schreibBefunde.join('\n')).toEqual([]);
	// Fix-Loop F002 (b): kein Prüf-Datensatz (Trip, Vergleich, Ort, eigene Vorlage) darf das Laufende überleben.
	expect(leckBefunde, `Prüf-Reste nach dem Aufräumen:\n${leckBefunde.join('\n')}`).toEqual([]);
	expect(ende.exit, ende.meldung).toBe(0);
});
