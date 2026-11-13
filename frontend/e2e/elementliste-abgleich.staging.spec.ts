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
	type HubAnker,
	istGegenrichtung,
	werteGegenrichtungAus,
	ladeRegeln,
	ladeKontoTexte,
	werteLaufAus,
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
const BERICHT_DIR = process.env.ELEMENTLISTE_BERICHT_DIR ?? join(FRONTEND, 'test-results', 'elementliste-abgleich');

/**
 * Sichtbare Texte (eigene Textknoten, aria-label von Schaltern/Knöpfen/Gruppen/Textfeldern, Eingaben) in
 * DOM-Reihenfolge. #2913 Fix-Loop 2: vorher werden alle `details` im Abschnitt geöffnet, wie der Generator
 * es im Mockup tut (C1); aria-label auch von role=group/textbox, z. B. bits-ui TimeField (C2).
 */
async function texteImBereich(page: Page, abschnitt: string): Promise<{ marker: boolean; texte: string[] }> {
	const selektor = `[data-abschnitt="${abschnitt}"]`;
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
	const anker = await page.evaluate(zaehleAnker, { kopf: HUB_ANKER_KOPF, flaeche: HUB_ANKER_FLAECHE });
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
	const MIT_LABEL = new Set(['switch', 'group', 'textbox']);
	const n = (s: string | null) => String(s ?? '').replace(/\s+/g, ' ').trim();
	const texte: string[] = [];
	for (const wurzel of wurzeln) {
		for (const el of [wurzel, ...Array.from(wurzel.querySelectorAll('*'))]) {
			if (el.closest('script,style,[aria-hidden="true"]') || !el.checkVisibility()) continue;
			if (el instanceof HTMLInputElement) {
				const t = n(el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.value);
				if (t) texte.push(t);
				continue;
			}
			const label = el.getAttribute('aria-label');
			if (label && (el.tagName === 'BUTTON' || MIT_LABEL.has(el.getAttribute('role') ?? ''))) texte.push(n(label));
			let eigen = '';
			for (const k of Array.from(el.childNodes)) if (k.nodeType === 3) eigen += k.nodeValue;
			if (n(eigen)) texte.push(n(eigen));
		}
	}
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
		const id = 'e2e-gz-2913-abgleich';
		await api.delete(`/api/trips/${id}`).catch(() => {});
		const r = await api.post('/api/trips', {
			data: {
				id,
				name: 'E2E-GZ #2913 Elementlisten-Abgleich',
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
		const ort = await api.post('/api/locations', { data: { name: 'E2E-GZ #2913 Ort', lat: 51.96, lon: 7.63 } });
		if (ort.ok()) {
			const ortId = String((await ort.json()).id);
			aufraeumen.push(() => api.delete(`/api/locations/${ortId}`));
			const v = await api.post('/api/compare/presets', {
				// #2913 c2: Region und Morgen-Briefing 07:00, damit Eyebrow („Orte · {region}“) und Meta-Zeile prüfbar sind.
				// Region bewusst nicht „Münsterland“: das ist im Mockup der Name des Vergleichs (Brotkrumen, Titel); die
				// Region steht live zusätzlich unter dem Titel und würde sonst als Name gefunden (falsche Reihenfolge).
				data: {
					name: 'E2E-GZ #2913 Orte-Abgleich',
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
	let spracheZurueck: Awaited<ReturnType<typeof stelleSpracheWieder>> = { ok: false, meldung: 'Zurückstellen der Profilsprache nicht gelaufen' };
	try {
		const gesetzt = await api.put('/api/auth/profile', { data: { language: plan.sprache } });
		expect(gesetzt.ok(), `Profilsprache ${plan.sprache} setzen: HTTP ${gesetzt.status()}`).toBeTruthy();
		const konto = await ladeKontoTexte((pfad) => api.get(pfad), ids);
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
			const pfad = seitenPfad(k.ctx, id, k.reiter);
			if (rp.art === 'konto_luecken' && rp.navigation === 'browser') {
				await navigiereImBrowser(page, pfad);
			} else {
				await page.goto(pfad, { waitUntil: 'domcontentloaded' });
			}
			await page.waitForTimeout(rp.art === 'haengen' ? 1500 : 3000);
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
			for (const [abschnitt, liste] of abschnitte) {
				const befund = await texteImBereich(page, abschnitt);
				for (const [i, e] of bewerteAbschnitt(liste, befund, plan.sprache, abschnitt)) ergebnisse.set(i, e);
			}
			// Gegenrichtung: nur Zustand normal, ohne Segment, Desktop-Viewport (Config); erklärt wird gegen die
			// ganze Liste (kopf/reiterleiste stehen unter Reiter wetter), unabhängig vom Scope.
			if (istGegenrichtung(k)) {
				const hub = await texteUnterHub(page);
				// Fehlt Kopf oder Reiterfläche, ist die Seite nur teilweise gelesen: nie still „kein zusaetzlich“, sondern Befund ohneHub.
				const gegen = werteGegenrichtungAus({ ctx: k.ctx, reiter: k.reiter, anker: hub.anker, texte: hub.texte }, alle, regeln.ausnahmen, konto, plan.sprache);
				zusaetzlich.push(...gegen.zusaetzlich);
				if (gegen.ohneHub) ohneHub.push(gegen.ohneHub);
			}
		}
	} finally {
		await page.unrouteAll({ behavior: 'ignoreErrors' });
		spracheZurueck = await stelleSpracheWieder((daten) => api.put('/api/auth/profile', { data: daten }), vorherSprache);
		await aufraeumen();
		await api.post('/api/auth/logout').catch(() => {});
	}

	// Freigaben, Besitzer, Bericht und Exit (strict UND abnahme aus plan.optionen) bildet die Logik.
	const { pfade, ende } = werteLaufAus({ plan, ergebnisse, zusaetzlich, ohneHub, regeln, berichtDir: BERICHT_DIR });
	console.log(`Elementlisten-Abgleich: ${ende.meldung} → ${pfade.json}, ${pfade.md}`);
	// F005: ein gescheitertes Zurückstellen der Profilsprache lässt den Lauf scheitern (auch ohne --strict).
	expect(spracheZurueck.ok, spracheZurueck.ok ? '' : spracheZurueck.meldung).toBe(true);
	expect(ende.exit, ende.meldung).toBe(0);
});
