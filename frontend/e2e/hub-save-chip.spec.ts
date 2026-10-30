// E2E — Issue #2347 S2 (Epic #2345, Etappe P6): geteilter Speicher-Chip im Hub —
// EINE Chip-Zusicherung für BEIDE Hubs (Trip und Ortsvergleich) per Schleife über
// HUB_KINDS. Nur der Auslöser der echten Änderung ist kind-spezifisch
// (Vergleich: Ort entfernen; Trip: Etappen-Datum ändern + blur).
//
// Spec: docs/specs/modules/feat_2347_s2_paritaets_e2e.md § AC-6 (SC-1..SC-6)
//
// Ersetzt (Zuordnungstabelle Zeilen 31-34, 56-57):
//   - die vier Fälle der entfernten Compare-Chip-Altdatei (AC-1..AC-4)
//   - trip-hub-kopf-region-aktivitaet.spec.ts AC-11 (Trip) :974 → SC-5,
//     AC-11 (Vergleich) :1000 → SC-6
//   Trip-Auslöser nach Vorbild issue-758-save-indicator.spec.ts AC-1 (bleibt bestehen).
//   #2347 S4 Teil D: compare-flow-navigation F001 (Bestand mit channel_layouts öffnet
//   ohne Ungespeichert) → SC-1b je kind.
//
// Kein fester Schlaf: „null PUTs" (SC-3) wird per `expect.poll` als Stabilitäts-
// fenster geprüft (statt des festen 2-s-Schlafs des Altfalls, Zuordnung Zeile 33).
// Der Zwischenzustand `saving` wird über eine verzögerte PUT-Antwort (route-Handler,
// 800 ms) beobachtbar gemacht — Muster AC-11 aus trip-hub-kopf-region-aktivitaet.
// Anmeldung über den storageState aus global.setup.ts (Admin-Sitzung).

import { test, expect, type Page, type Request } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, hubApiPath, openHub, seedHub, type HubKind } from './helpers';

const DESKTOP = { width: 1280, height: 900 };
const VERZOEGERUNG_MS = 800;
const SEED_DATUM = '2027-08-01'; // Datum der einzigen Etappe aus seedHub('route')

const chip = (page: Page) => page.locator('[data-testid="save-indicator"]');

/** Zählt die PUTs auf genau dieses Objekt (ab Aufrufzeitpunkt). */
function zaehlePuts(page: Page, pfad: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (r) => {
		if (r.method() === 'PUT' && new URL(r.url()).pathname === pfad) puts.push(r);
	});
	return puts;
}

/** Verzögert PUTs auf die Ressource, damit `saving` beobachtbar wird. */
async function verzoegerePuts(page: Page, pfad: string): Promise<void> {
	await page.route(`**${pfad}`, async (route) => {
		if (route.request().method() === 'PUT') await new Promise((r) => setTimeout(r, VERZOEGERUNG_MS));
		await route.continue();
	});
}

/** Lässt PUTs auf die Ressource mit 500 scheitern. */
async function scheiternPuts(page: Page, pfad: string): Promise<void> {
	await page.route(`**${pfad}`, (route) => {
		if (route.request().method() === 'PUT') {
			return route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'stubbed failure' }) });
		}
		return route.continue();
	});
}

async function stand(page: Page, kind: HubKind, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Record<string, unknown>;
}

const etappenDatum = (page: Page) =>
	page.getByTestId('stage-date-field').first().locator('input[type="date"]');

/** Öffnet den Punkte-Reiter und prüft die Ausgangslage des kind-eigenen Auslösers. */
async function oeffneAusloeser(page: Page, kind: HubKind, id: string): Promise<void> {
	const sel = HUB_SEL[kind];
	await openHub(page, kind, id, { tab: sel.punkteReiter });
	await expect(page.locator(`[data-testid="${sel.panel}-${sel.punkteReiter}"]:visible`)).toBeVisible({ timeout: 10_000 });
	// kind-Zweig (Spec SC-2): der Auslöser ist kind-spezifisch, die Chip-Zusicherung gemeinsam.
	if (kind === 'vergleich') {
		await expect(page.getByTestId('hub-orte-row')).toHaveCount(2);
	} else {
		await expect(page.getByTestId('edit-stages-panel')).toBeVisible({ timeout: 10_000 });
		await expect(etappenDatum(page)).toHaveValue(SEED_DATUM);
	}
	await expect(chip(page)).toBeVisible({ timeout: 10_000 });
}

/** Löst die echte, kind-eigene Änderung aus (Ort entfernen bzw. Etappen-Datum + blur). */
async function loeseAenderungAus(page: Page, kind: HubKind, neuesDatum: string): Promise<void> {
	if (kind === 'vergleich') {
		await page.getByTestId('hub-orte-remove').first().click();
	} else {
		await etappenDatum(page).fill(neuesDatum);
		await etappenDatum(page).blur();
	}
}

const etappenDaten = (s: Record<string, unknown>) =>
	((s.stages as Array<{ date?: string }> | undefined) ?? []).map((e) => e.date);
const ortAnzahl = (s: Record<string, unknown>) => ((s.location_ids as unknown[] | undefined) ?? []).length;

for (const kind of HUB_KINDS) {
	// Zur Sammelzeit gelesen: ohne HUB_SEL in helpers.ts bricht schon die Liste ab.
	const sel = HUB_SEL[kind];

	test(`SC-1 (${kind}): Hub öffnen ⇒ Chip idle „Gespeichert", genau ein save-indicator im DOM`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedHub(page.request, kind);
		try {
			await openHub(page, kind, hub.id);
			await expect(page.getByTestId(sel.reiterListe)).toBeVisible({ timeout: 10_000 });
			await expect(chip(page)).toBeVisible({ timeout: 10_000 });
			await expect(chip(page)).toHaveAttribute('data-state', 'idle');
			await expect(chip(page)).toContainText('Gespeichert');
			// Ohne :visible — ein zweiter, versteckter Chip zählt mit.
			await expect(chip(page)).toHaveCount(1);
		} finally {
			await hub.aufraeumen();
		}
	});

	// SC-1b — #2347 S4 Teil D: Alt compare-flow-navigation F001 „bestehender Vergleich MIT
	// gesetzten channel_layouts öffnet ohne Ungespeichert-Anzeige" (Fix-Loop #1256: ein
	// Katalog-Rewrite der Kanal-Layouts machte den Stand beim bloßen Öffnen schmutzig).
	// Kein Kind-Kontrast: beide Arten tragen `display_config.channel_layouts` (Trip: echte
	// Kanal-Auswahl, WeatherMetricsTab.svelte liest sie beim Laden zurück, #1575 S3;
	// Vergleich: Bestandsfeld, das der Compare-Speicherpfad verwirft, compareEditorSave.ts
	// #1351). Geöffnet wird der Reiter, der das Feld verarbeitet (Wetter-Metriken mit dem
	// geteilten LayoutTab) — der Standard-Reiter allein würde den Fehlerweg nie betreten.
	// Nur die Metrik-Kennung ist katalogbedingt je Art (Trip `gust`, Vergleich `wind_max_kmh`).
	test(`SC-1b (${kind}): Bestand MIT channel_layouts im Reiter Wetter-Metriken öffnen ⇒ Chip idle, null PUTs, Feld unverändert`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const metrik = kind === 'route' ? 'gust' : 'wind_max_kmh';
		const eintrag = [{ metric_id: metrik, enabled: true, bucket: 'primary', order: 0 }];
		const hub = await seedHub(page.request, kind, {
			extra: { display_config: { channel_layouts: { email: eintrag, telegram: eintrag, sms: eintrag } } }
		});
		try {
			const vorher = ((await stand(page, kind, hub.id)).display_config as Record<string, unknown> | undefined)
				?.channel_layouts;
			expect(
				Object.keys((vorher as Record<string, unknown> | undefined) ?? {}),
				'Vorbedingung: der Bestand trägt channel_layouts — sonst prüft SC-1b nichts.'
			).toEqual(expect.arrayContaining(['email', 'telegram', 'sms']));

			const puts = zaehlePuts(page, hubApiPath(kind, hub.id));
			await openHub(page, kind, hub.id, { tab: 'wetter-metriken' });
			await expect(
				page.locator('[data-testid="layout-tab"]:visible').first(),
				'SC-1b: der geteilte LayoutTab (Kanal-Umschalter) im Reiter Wetter-Metriken fehlt'
			).toBeVisible({ timeout: 15_000 });
			await expect(chip(page)).toBeVisible({ timeout: 10_000 });

			// Stabilitätsfenster statt festem Schlaf (Alt: fester 2,5-s-Schlaf): in dieser Zeit
			// hätte ein Rewrite-Effekt geschrieben bzw. den Chip umgestellt.
			let seit = 0;
			await expect
				.poll(
					async () => {
						const zustand = `${puts.length}|${await chip(page).getAttribute('data-state')}`;
						if (zustand !== '0|idle') {
							seit = 0;
							return zustand;
						}
						seit ||= Date.now();
						return Date.now() - seit >= 2_500 ? 'stabil' : zustand;
					},
					{ message: 'SC-1b: Öffnen speichert oder macht den Chip schmutzig', timeout: 12_000, intervals: [200] }
				)
				.toBe('stabil');
			await expect(chip(page)).not.toContainText('Nicht gespeichert');

			const nachher = ((await stand(page, kind, hub.id)).display_config as Record<string, unknown> | undefined)
				?.channel_layouts;
			expect(nachher, 'SC-1b: channel_layouts hat sich durch bloßes Öffnen verändert').toEqual(vorher);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`SC-2 (${kind}): echte Änderung ⇒ Chip saving → idle „Gespeichert HH:MM", Änderung überlebt Neuladen`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedHub(page.request, kind);
		try {
			const pfad = hubApiPath(kind, hub.id);
			await oeffneAusloeser(page, kind, hub.id);
			await verzoegerePuts(page, pfad);

			await loeseAenderungAus(page, kind, '2027-08-20');

			await expect(chip(page), 'eine echte Änderung schaltet den Chip auf saving').toHaveAttribute(
				'data-state',
				'saving',
				{ timeout: 5_000 }
			);
			await expect(chip(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			await expect(chip(page)).toContainText('Gespeichert');
			await expect(chip(page).locator('.save-time')).toHaveText(/^\d{2}:\d{2}$/);
			await page.unroute(`**${pfad}`);

			const gespeichert = await stand(page, kind, hub.id);
			if (kind === 'vergleich') expect(ortAnzahl(gespeichert), 'Server: ein Ort entfernt').toBe(1);
			else expect(etappenDaten(gespeichert)[0], 'Server: neues Etappen-Datum').toBe('2027-08-20');

			await page.reload();
			await expect(page.locator(`[data-testid="${sel.panel}-${sel.punkteReiter}"]:visible`)).toBeVisible({
				timeout: 10_000
			});
			if (kind === 'vergleich') await expect(page.getByTestId('hub-orte-row')).toHaveCount(1);
			else await expect(etappenDatum(page)).toHaveValue('2027-08-20');
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`SC-3 (${kind}): Zahlenfeld in Wertebereiche fokussieren/verlassen ohne Änderung ⇒ Chip unverändert, null PUTs`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedHub(page.request, kind);
		try {
			const pfad = hubApiPath(kind, hub.id);
			await openHub(page, kind, hub.id, { tab: 'wertebereiche' });
			await expect(page.locator(`[data-testid="${sel.panel}-wertebereiche"]:visible`)).toBeVisible({ timeout: 10_000 });
			// HubKind == context-Parameter des geteilten Korridor-Editors.
			await expect(page.getByTestId(`corridor-editor-${kind}`)).toBeVisible({ timeout: 10_000 });

			// Frischer Seed hat keine aktive Metrik — eine über den echten Klick-Pfad
			// hinzufügen, damit ein Zahlenfeld entsteht. Dieser beabsichtigte PUT wird
			// abgewartet, BEVOR der Zähler startet (sonst verfälscht er „null PUTs").
			const hinzufuegePut = page.waitForResponse(
				(r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === pfad,
				{ timeout: 10_000 }
			);
			await page.locator('[data-testid^="corridor-editor-pool-item-"]:visible').first().click();
			expect((await hinzufuegePut).ok(), 'das Hinzufügen einer Metrik speichert auf dem Hub-Objekt').toBeTruthy();
			const feld = page.getByTestId('corridor-editor-table').locator('input[type="number"]').first();
			await expect(feld).toBeVisible({ timeout: 10_000 });
			await expect(chip(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

			const puts = zaehlePuts(page, pfad);
			const vorher = (await chip(page).textContent()) ?? '';

			await feld.focus();
			await feld.blur();

			// Stabilitätsfenster: die PUT-Zahl muss 2 s lang bei 0 bleiben.
			let seit = 0;
			await expect
				.poll(
					() => {
						if (puts.length !== 0) {
							seit = 0;
							return puts.length;
						}
						seit ||= Date.now();
						return Date.now() - seit >= 2_000 ? 'stabil' : 0;
					},
					{ message: 'Fokussieren/Verlassen ohne Wertänderung darf keinen PUT auslösen', timeout: 8_000, intervals: [200] }
				)
				.toBe('stabil');

			expect(puts.length, 'kein PUT ohne Wertänderung').toBe(0);
			expect((await chip(page).textContent()) ?? '', 'Chip samt Zeitstempel unverändert').toBe(vorher);
			await expect(chip(page)).toHaveAttribute('data-state', 'idle');
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`SC-4 (${kind}): PUT 500 auf den Auslöser ⇒ Chip error „Fehler beim Speichern", Rollback sichtbar`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedHub(page.request, kind);
		try {
			const pfad = hubApiPath(kind, hub.id);
			await oeffneAusloeser(page, kind, hub.id);
			await scheiternPuts(page, pfad);

			await loeseAenderungAus(page, kind, '2027-08-22');

			await expect(chip(page), 'ein fehlgeschlagener PUT schaltet den Chip auf error').toHaveAttribute(
				'data-state',
				'error',
				{ timeout: 10_000 }
			);
			await expect(chip(page)).toContainText('Fehler beim Speichern');

			// Rollback sichtbar (kein stiller Datenverlust) und Server-Stand unverändert.
			const gespeichert = await stand(page, kind, hub.id);
			if (kind === 'vergleich') {
				await expect(page.getByTestId('hub-orte-row')).toHaveCount(2);
				expect(ortAnzahl(gespeichert), 'Server: beide Orte unverändert').toBe(2);
			} else {
				await expect(etappenDatum(page)).toHaveValue(SEED_DATUM);
				expect(etappenDaten(gespeichert)[0], 'Server: Etappen-Datum unverändert').toBe(SEED_DATUM);
			}
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`SC-5 (${kind}): Region im Kopf speichern (PUT verzögert) ⇒ Chip saving ⇒ idle „Gespeichert HH:MM"`, async ({
		page
	}) => {
		test.setTimeout(90_000);
		await page.setViewportSize(DESKTOP);
		const hub = await seedHub(page.request, kind);
		try {
			const pfad = hubApiPath(kind, hub.id);
			await openHub(page, kind, hub.id);
			await expect(page.getByTestId(`${sel.kopf}-region-edit-toggle`)).toBeVisible({ timeout: 15_000 });
			await verzoegerePuts(page, pfad);

			await page.getByTestId(`${sel.kopf}-region-edit-toggle`).click();
			await page.getByTestId(`${sel.kopf}-region-edit`).fill('SC-5 Region');
			await page.getByTestId(`${sel.kopf}-region-save`).click();

			await expect(chip(page)).toHaveAttribute('data-state', 'saving', { timeout: 5_000 });
			await expect(chip(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			await expect(chip(page)).toContainText('Gespeichert');
			await expect(chip(page).locator('.save-time')).toHaveText(/^\d{2}:\d{2}$/);
			await page.unroute(`**${pfad}`);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`SC-6 (${kind}): Profil/Aktivität im Kopf wählen (PUT verzögert) ⇒ Chip saving ⇒ idle am selben Controller, genau ein Chip`, async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		// Seed-Wert muss vom Zielwert HUB_SEL[kind].profilWert verschieden sein, sonst
		// ist der Klick keine Änderung (seedHub('vergleich') trägt profil 'wandern').
		const ausgang = kind === 'route' ? 'trekking' : 'allgemein';
		const hub = await seedHub(page.request, kind, { extra: { [sel.profilFeld]: ausgang } });
		try {
			const pfad = hubApiPath(kind, hub.id);
			expect(sel.profilWert, 'Vorbedingung: Zielwert ≠ Seed-Wert').not.toBe(ausgang);
			await openHub(page, kind, hub.id);
			const kachel = page.getByTestId(`${sel.kopf}-profil-option-${sel.profilWert}`);
			await expect(kachel).toBeVisible({ timeout: 15_000 });
			await verzoegerePuts(page, pfad);

			await kachel.click();

			await expect(chip(page)).toHaveAttribute('data-state', 'saving', { timeout: 5_000 });
			await expect(chip(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			await expect(chip(page)).toContainText('Gespeichert');
			await expect(chip(page).locator('.save-time')).toHaveText(/^\d{2}:\d{2}$/);
			await expect(chip(page)).toHaveCount(1);
			await page.unroute(`**${pfad}`);
		} finally {
			await hub.aufraeumen();
		}
	});
}
