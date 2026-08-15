// E2E (Staging) — #1703 Scheibe 8: kanal-eigene Metrikauswahl der
// Vergleichs-Uebersicht auf der ANLEGE-Seite `/compare/new`.
//
// 🔴 EINZIGER Waechter der ANLEGE-Naht. Die beiden Nachbardateien
// (compare-uebersicht-kanal-bedienung/-persistenz) legen ihren Vergleich per
// API an und fahren danach ausschliesslich den BEARBEITEN-Pfad des Hubs.
// `/compare/new` mountet denselben `WeatherMetricsTab context="vergleich"`
// (CompareNewEditor.svelte:394 Desktop / :491 Mobil) — die Kanal-Reiter sind
// dort also ebenfalls bedienbar, aber der Weg dahinter ist ein voellig
// anderer: KEIN PUT je Geste, sondern genau EIN POST beim „Briefing
// aktivieren" (CompareWizardState.saveNewPreset:163 ->
// buildNewComparePresetPayload:341/414 -> display_config.channel_active_metrics).
// Abgesichert war dieser Weg bisher nur an der reinen Payload-Funktion
// (compareEditorSave.test.ts) — kein Browser hat die Anlege-Seite je mit einem
// Kanal-Override gesehen. Ohne diese Datei ist die Kette „Reiter erscheint ->
// Geste trifft den Wizard-Zustand -> Zustand ueberlebt vier Reiterwechsel ->
// Server behaelt ihn" unbewacht; die Bedienflaeche waere dort eine Attrappe,
// ohne dass ein Test rot wird.
//
// Gemessen wird am GESPEICHERTEN Stand (GET /api/compare/presets/{id}), nicht
// an der Oberflaeche: die zeigt den Override auch dann korrekt, wenn er nie
// gesendet wurde (dieselbe Lehre wie M3/M4 der Spec).
//
// Spec: docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md — § Testauflage
// benennt nur die drei Hub-Buendel, die Anlege-Seite kommt in der Spec gar
// nicht vor (Luecke, PO-Frage 2026-08-13). Sinngemaess beruehrte Zusicherungen:
// AC-S8-12 (drei Reiter, umschaltbar), AC-S8-5 („Aus" ist ein Zustand),
// AC-S8-10 (nur EDITIERTE Kanaele werden serialisiert).
// Aufbau, Selektoren, #1423-Warteregel, Ausfuehrbefehl:
// ./compare-uebersicht-kanal.helpers.ts

import { test, expect, type Page } from '@playwright/test';
import { cleanupTracked, createTestLocation, registerForCleanup } from './helpers';
import {
	aktiveMetriken, ausMetriken, ausSchaltenOhneSpeichern, gespeicherteKanalAuswahl,
	waehleKanal, type KanalFlaeche
} from './compare-uebersicht-kanal.helpers';

/** Testgroesse der kanal-eigenen Abwahl — eine Groesse mit EINER Auswertung,
 *  fest in der Vorgabemenge COMPARE_METRIC_KEYS (corridorEditorState.ts:475). */
const WEG = 'pop_max_pct';

/**
 * Freischalt-Kette der Anlege-Seite bis zum Reiter „Wetter-Metriken":
 * Name -> mind. 2 Orte -> Wetter-Metriken (compareNewLogic.unlockedTabs).
 *
 * 🔴 #1423-Warteregel: der Metrik-Block ist waehrend des Katalog-Ladens
 * bewusst aus dem DOM entfernt (WeatherMetricsTab.svelte:1204-1207) — deshalb
 * hier wie im Hub-Helfer `waitFor({state:'attached'})`, nie eine
 * Momentaufnahme.
 * 🔴 Scope-Pflicht: alle Selektoren haengen am Uebersichts-Block
 * `[data-testid="layout-tab"][data-context="vergleich"]`. WeatherV2Reihenfolge
 * ist im Reiter DREIMAL gemountet (Uebersicht/Stundenverlauf/Ausblick) mit
 * denselben `wm2-*`-Testids; an der Seite haengende Selektoren traefen den
 * falschen Block.
 */
async function oeffneAnlegeUebersicht(
	page: Page, name: string, orteNamen: string[]
): Promise<KanalFlaeche> {
	// Desktop VOR dem Laden: die Mobil-Weiche liest matchMedia beim Mount
	// (CompareNewEditor.svelte:111-117) und nur EIN Zweig mountet den Reiter.
	await page.setViewportSize({ width: 1440, height: 900 });
	await page.goto('/compare/new');
	await expect(page.locator('[data-testid="compare-editor"]:visible')).toBeVisible({ timeout: 20_000 });

	await page.getByTestId('compare-editor-name').fill(name);
	await page.getByTestId('compare-editor-continue-orte').click();

	// Orte-Bibliothek: nur im Desktop-Zweig gerendert (Step2Orte ohne `dense`).
	const bibliothek = page.locator('[data-testid="compare-step2-library"]:visible').first();
	await bibliothek.waitFor({ state: 'visible', timeout: 20_000 });
	for (const ort of orteNamen) await bibliothek.getByText(ort, { exact: true }).click();

	// Positiv-Anker der Freischaltung: erst ab zwei Orten ist der Weiter-Knopf
	// bedienbar. Ohne diese Zusicherung bliebe ein Klick auf den gesperrten
	// Knopf wirkungslos und der Fehlschlag traefe erst spaeter eine
	// Metrik-Zusicherung — mit falscher Ursache.
	const weiter = page.getByTestId('compare-editor-continue-metriken');
	await expect(
		weiter, 'Freischaltung: "Wetter-Metriken" bleibt trotz zwei gewaehlter Orte gesperrt'
	).toBeEnabled({ timeout: 15_000 });
	await weiter.click();
	await expect(page.getByTestId('compare-editor-tab-metriken')).toHaveAttribute('data-active', 'true');

	const panel = page.locator('[data-testid="weather-metrics-tab-vergleich"]:visible').first();
	await expect(panel).toBeVisible({ timeout: 20_000 });
	const grundauswahl = panel.getByTestId('weather-metrics-vergleich-list');
	await grundauswahl.waitFor({ state: 'attached', timeout: 25_000 });
	const layout = panel.locator('[data-testid="layout-tab"][data-context="vergleich"]');
	await layout.waitFor({ state: 'attached', timeout: 25_000 });
	const reihenfolge = layout.getByTestId('weather-metrics-vergleich-reihenfolge');
	await reihenfolge.waitFor({ state: 'attached', timeout: 25_000 });
	return { page, panel, layout, reihenfolge, grundauswahl };
}

/**
 * Rest der Kette (Wertebereiche -> Alarme -> Versand) und „Briefing
 * aktivieren". Jeder Reiterbesuch schaltet den naechsten frei (*Visited-Flags,
 * compareNewLogic.ts:32-46); erst der Versand-Besuch macht den
 * Aktivieren-Knopf bedienbar (canActivate). Liefert die ID des angelegten
 * Vergleichs und traegt ihn zur Bereinigung ein.
 */
async function briefingAktivieren(page: Page): Promise<string> {
	await page.getByTestId('compare-editor-continue-idealwerte').click();
	await page.getByTestId('compare-editor-continue-alarme').click();
	await page.getByTestId('compare-editor-continue-versand').click();

	const aktivieren = page.getByTestId('compare-editor-activate');
	await expect(
		aktivieren, 'Freischaltung: "Briefing aktivieren" bleibt nach dem Versand-Besuch gesperrt'
	).toBeEnabled({ timeout: 20_000 });

	const antwort = page.waitForResponse(
		(r) => r.request().method() === 'POST' && r.url().includes('/api/compare/presets'),
		{ timeout: 30_000 }
	);
	await aktivieren.click();
	const res = await antwort;
	expect(res.ok(), `Anlage fehlgeschlagen: HTTP ${res.status()}`).toBeTruthy();
	const angelegt = (await res.json()) as { id: string };
	registerForCleanup('preset', angelegt.id);
	// Erst der Redirect (saveNewPreset -> goto) belegt, dass der Editor die
	// Anlage als durchgelaufen ansieht — nicht der blosse HTTP-Erfolg.
	await page.waitForURL(new RegExp(`/compare/${angelegt.id}$`), { timeout: 20_000 });
	return angelegt.id;
}

test.describe('#1703 S8: Anlege-Seite /compare/new — die Kanal-Reiter der Uebersicht wirken bis in den angelegten Vergleich', () => {
	test.afterAll(async ({ request }) => await cleanupTracked(request));

	test('eine Abwahl im SMS-Reiter der Anlege-Seite steht nach dem "Briefing aktivieren" im gespeicherten Vergleich — E-Mail und Telegram bleiben ohne Eintrag', async ({
		page, request
	}) => {
		const suffix = Date.now();
		const ortA = await createTestLocation(request, { name: `1703-s8-neu-A-${suffix}` });
		const ortB = await createTestLocation(request, { name: `1703-s8-neu-B-${suffix}` });
		const f = await oeffneAnlegeUebersicht(
			page, `E2E-GZ-1703-s8-anlegen-${suffix}`, [ortA.name, ortB.name]
		);

		// (1) Die drei Kanal-Reiter existieren auf der ANLEGE-Seite ueberhaupt.
		for (const ch of ['email', 'telegram', 'sms'] as const) {
			await expect(
				f.layout.getByTestId(`channel-tab-${ch}`), `Kanal-Reiter "${ch}" fehlt auf /compare/new`
			).toBeVisible({ timeout: 10_000 });
		}
		// Ohne eigenen Override folgt jeder Kanal der Grundauswahl. Diese Liste
		// ist der Bezugspunkt aller weiteren Zusicherungen — sie wird ABGELESEN,
		// nicht angenommen (die Vorgabemenge eines neuen Vergleichs haengt an
		// COMPARE_METRIC_KEYS und darf sich aendern, ohne diesen Test zu brechen).
		const alleAktiven = await aktiveMetriken(f);
		expect(
			alleAktiven.length,
			'die Grundauswahl eines neuen Vergleichs ist leer — ohne aktive Zeile ist die Abwahl unten keine Aussage'
		).toBeGreaterThan(0);
		expect(alleAktiven, `Testgroesse "${WEG}" fehlt in der Grundauswahl`).toContain(WEG);

		// (2) Umschalten wirkt: `waehleKanal` wartet auf die Kappungs-Aussage des
		// ZIEL-Kanals, nicht auf den blossen Klick.
		await waehleKanal(f, 'telegram');
		await waehleKanal(f, 'sms');
		expect(
			await aktiveMetriken(f), 'ohne eigenen Override muss der SMS-Reiter die Grundauswahl zeigen'
		).toEqual(alleAktiven);

		// (3) Kanal-eigene Abwahl (copy-on-write: der Override entsteht hier
		// ueberhaupt erst, WeatherMetricsTab.svelte:1103-1109).
		await ausSchaltenOhneSpeichern(f, WEG);
		const erwartetSms = alleAktiven.filter((m) => m !== WEG);
		expect(await aktiveMetriken(f), 'SMS-Reiter direkt nach der Abwahl').toEqual(erwartetSms);

		// (4) … und sie trifft NUR den SMS-Reiter. Positiv-Anker zuerst (volle
		// Liste), erst danach ist die leere Aus-Gruppe eine Aussage (#1423).
		await waehleKanal(f, 'email');
		expect(
			await aktiveMetriken(f), 'der E-Mail-Reiter darf die SMS-eigene Abwahl nicht mitbekommen'
		).toEqual(alleAktiven);
		expect(
			await ausMetriken(f),
			'"Aus in diesem Kanal" gehoert dem SMS-Reiter — im E-Mail-Reiter darf die Gruppe leer sein'
		).toEqual([]);

		// (5) Anlegen — genau EIN POST, kein PUT (der Vergleich existiert noch nicht).
		const presetId = await briefingAktivieren(page);

		// (6) 🔴 Der Kern: am GESPEICHERTEN Stand, nicht an der Oberflaeche.
		// Faellt `channelActiveMetricKeys` aus `saveNewPreset()` (Z. 163) oder
		// `channel_active_metrics` aus `buildNewComparePresetPayload()` (Z. 414),
		// bleibt die Bedienung oben unveraendert gruen — nur hier wird es rot.
		expect(
			await gespeicherteKanalAuswahl(request, presetId, 'sms'),
			`FAIL: der SMS-Override der Anlege-Seite ist im angelegten Vergleich nicht angekommen. ` +
				`\`null\` heisst "Schluessel fehlt" (nie mitgesendet), eine andere Liste heisst "falscher ` +
				`Stand serialisiert". Erwartet: Grundauswahl ohne "${WEG}".`
		).toEqual(erwartetSms);

		// Die beiden nie editierten Kanaele duerfen KEINEN Eintrag tragen —
		// „fehlend != leer" (#1191/#1366): ein `[]` hier hiesse "bewusste
		// Leerauswahl" und wuerde E-Mail und Telegram beim Rendern leerraeumen.
		// Zugleich die Gegenprobe zu (2): ein blosser Reiter-WECHSEL ist keine
		// Aenderung und darf nichts anlegen.
		for (const ch of ['email', 'telegram'] as const) {
			expect(
				await gespeicherteKanalAuswahl(request, presetId, ch),
				`FAIL: Kanal "${ch}" wurde nie editiert und darf im angelegten Vergleich keinen Eintrag ` +
					`haben — ein leeres Array waere eine bewusste Leerauswahl und liesse den Kanal leer rendern`
			).toBeNull();
		}
	});
});
