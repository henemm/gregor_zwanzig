// E2E — Issue #2347 S3a (Epic #2345, Etappe P6): Speicherverhalten des Wertebereich-Bausteins im
// Hub — EINE Zusicherung für BEIDE Hubs (Trip und Ortsvergleich) per Schleife über HUB_KINDS.
//
// Spec (Ursprung): docs/specs/modules/feat_2347_s3a_paritaets_e2e.md § AC-3 (WS-1..WS-8)
//
// Verlauf: #2792 S1c-3 sperrte die Korridor-Zeilen (nur lesbar, kein PUT). #2794 Teil 3
// (docs/specs/modules/feat_2794_s3a_teil3_wetter.md §4, Known Limitations „Löschung erst Teil-PR 4")
// mountet den CorridorEditor im Reiter Wetter nicht mehr; Wertebereiche stellt der Nutzer jetzt über
// die Ampel ein („Grenzen ändern", AC-16; „Nicht im Briefing", AC-19). Die Fälle WS-1..WS-8 bleiben
// je Geste bestehen und prüfen dieselben Aussagen am neuen Träger `WetterTab`:
//   - jede Bedienfolge erzeugt GENAU EINEN Schreibvorgang des Reiters (AC-38), ein bloßer Entwurf
//     ohne „Fertig" keinen;
//   - die Altfelder (`corridors`, Vergleich zusätzlich `ideal_ranges`/`telegram_style`) bleiben auf
//     dem Server unverändert (Read-Modify-Write, AC-30);
//   - zweite, erlaubte Schreibgesten (WS-3 Alarm, WS-4 fremder Name, WS-5 Pausieren) bleiben als
//     Gegenprobe erhalten; keine überschreibt die andere.
//
// Kein fester Schlaf: „kein PUT" per Stabilitätsfenster (deutlich über dem 700-ms-Entprell-Fenster).
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung über den storageState aus
// global.setup.ts. Wegwerf-Objekte E2E-GZ-, Aufräumen im finally.

import { test, expect, type Page } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, hubApiPath, type HubKind } from './helpers';
import { WT, auswahlImStand, oeffneWetter, vorlagen } from './s3a2794-teil3.helpers';
import {
	ALTFELDER,
	anzeige,
	bleibtBei,
	dc,
	fertig,
	grenzenOeffnen,
	seedGrenzen,
	seiteImStand,
	stand,
	zaehleAlleSchreiben,
	zaehleWetterSchreiben,
	type Stand
} from './s3a2794-wetter-ci.helpers';

/** kind-Tabelle: Alarm-Gegenprobe im Reiter Zustellung (WS-3), Status-Weg (WS-5), Konflikt-Verhalten (WS-4). */
const WS_SEL: Record<
	HubKind,
	{
		alarm: (page: Page) => ReturnType<Page['locator']>;
		alarmWert: (s: Stand) => unknown;
		alarmNeu: boolean;
		statusSchluessel: string[];
		statusPausiert: (rumpf: Stand) => boolean;
		istPausiert: (s: Stand) => boolean;
		/** 412: lädt der Reiter das Abo neu (Vergleich, Spec Datenfluss „Konflikt") oder behält er die Eingabe (Trip)? */
		konfliktLaedtNeu: boolean;
	}
> = {
	route: {
		alarm: (page) => page.locator('[data-testid="zustellung-tab"]:visible [data-testid="zustellung-stille-schalter"]').first(),
		// #2795 S3b 1b: Alarm-Geste im Reiter Zustellung ist der Schalter „Stille Stunden“ (role=switch).
		alarmWert: (s) => Boolean(s.alert_quiet_from) && Boolean(s.alert_quiet_to),
		alarmNeu: true,
		statusSchluessel: ['paused'],
		statusPausiert: (r) => r.paused === true,
		istPausiert: (s) => Boolean(s.paused_at),
		konfliktLaedtNeu: false
	},
	vergleich: {
		alarm: (page) => page.locator('[data-testid="zustellung-tab"]:visible [data-testid="zustellung-stille-schalter"]').first(),
		// #2795 S3b 1b: Alarm-Geste im Reiter Zustellung ist der Schalter „Stille Stunden“ (role=switch).
		alarmWert: (s) => Boolean(s.alert_quiet_from) && Boolean(s.alert_quiet_to),
		alarmNeu: true,
		statusSchluessel: ['previous_schedule', 'schedule'],
		statusPausiert: (r) => r.schedule === 'manual',
		istPausiert: (s) => s.schedule === 'manual',
		konfliktLaedtNeu: true
	}
};

/** Böen (nur oben) — die Zeile, an der die Grenzen-Gesten laufen. */
const ZEILE = 'gust';

for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];
	const ws = WS_SEL[kind];

	test.describe(`Hub · Wertebereiche (Reiter Wetter, Grenzen) speichert genau einmal (${kind})`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
		});

		// WS-1 — fängt: Doppel-Commit bzw. Verlust einer von zwei schnellen Gesten; Replace statt Merge.
		test(`WS-1 (${kind}): zwei Metriken über „Nicht im Briefing" hinzufügen → genau EIN Schreibvorgang, beide hinten angehängt, Altfelder unverändert`, async ({
			page
		}) => {
			const hub = await seedGrenzen(page.request, kind);
			try {
				const vorher = ALTFELDER[kind](await stand(page, kind, hub.id));
				const { puts, beantwortet } = zaehleWetterSchreiben(page, kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);

				const plus = reiter.getByTestId(WT.nichtImBriefing).locator('[data-testid^="wetter-nicht-im-briefing-plus-"]');
				await expect(plus.nth(1), 'Vorbedingung: mindestens zwei Metriken stehen unter „Nicht im Briefing"').toBeVisible();
				const neu = [
					(await plus.nth(0).getAttribute('data-testid'))!.replace('wetter-nicht-im-briefing-plus-', ''),
					(await plus.nth(1).getAttribute('data-testid'))!.replace('wetter-nicht-im-briefing-plus-', '')
				];
				await reiter.getByTestId(WT.plus(neu[0])).click();
				await reiter.getByTestId(WT.plus(neu[1])).click();

				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				await bleibtBei(() => puts.length, 1, 1_200, 'WS-1: zwei schnelle Gesten = genau EIN Schreibvorgang des Reiters');

				const s = await stand(page, kind, hub.id);
				const reihe = kind === 'route'
					? ((dc(s).metrics ?? []) as Array<{ metric_id: string; enabled?: boolean }>).filter((m) => m.enabled !== false).map((m) => m.metric_id)
					: ((dc(s).active_metrics ?? []) as Array<{ metric_id: string }>).map((m) => m.metric_id);
				expect(reihe.slice(-2), 'AC-37: neue Metriken hinten angehängt').toEqual(neu);
				expect(auswahlImStand(kind, s)).toEqual([...hub.auswahl, ...neu].sort());
				expect(ALTFELDER[kind](s), 'AC-30: Altfelder (Korridore usw.) auf dem Server unverändert').toEqual(vorher);

				const r2 = await oeffneWetter(page, kind, hub.id);
				for (const id of neu) await expect(r2.getByTestId(WT.zeile(id)), `nach Neuladen steht ${id} im Briefing`).toBeVisible();
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-2 — fängt: ein Entwurf aus „Grenzen ändern" wird ohne „Fertig" gespeichert.
		test(`WS-2 (${kind}): Grenze tippen und ohne „Fertig" neu laden → KEIN Schreibvorgang, Serverstand und Anzeige unverändert`, async ({
			page
		}) => {
			const hub = await seedGrenzen(page.request, kind);
			try {
				const vorher = await stand(page, kind, hub.id);
				const alle = zaehleAlleSchreiben(page, kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				const v = (await vorlagen(page.request)).wandern.ampel.metrics[ZEILE].upper;
				const zeile = await grenzenOeffnen(reiter, ZEILE);
				const feld = zeile.getByTestId(WT.grenze(ZEILE, 'upper', 'orange'));
				await expect(feld, 'die Grenze der Vorlage steht im Feld').toHaveValue(String(v.orange));
				await feld.fill(String(v.orange + 3));

				await bleibtBei(() => alle.length, 0, 1_200, 'WS-2: ein Entwurf ohne „Fertig" darf nichts senden');
				await page.reload();
				const r2 = await oeffneWetter(page, kind, hub.id);
				expect(alle.length, 'WS-2: auch das Neuladen schreibt den Entwurf nicht').toBe(0);
				const z2 = await grenzenOeffnen(r2, ZEILE);
				await expect(z2.getByTestId(WT.grenze(ZEILE, 'upper', 'orange')), 'nach Neuladen steht die alte Grenze').toHaveValue(String(v.orange));
				expect((await stand(page, kind, hub.id)).display_config, 'Serverstand unverändert').toEqual(vorher.display_config);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-3 — Gegenprobe Reiterwechsel: die Grenzen-Änderung und die Alarm-Änderung im Reiter
		// Zustellung kommen BEIDE an, keine verdrängt die andere; Altfelder bleiben.
		test(`WS-3 (${kind}): Grenze ändern, sofort zu „Zustellung", dort Alarm ändern → BEIDE gespeichert, Grenze genau EINMAL geschrieben, Altfelder unverändert`, async ({
			page
		}) => {
			const hub = await seedGrenzen(page.request, kind);
			try {
				const vorher = ALTFELDER[kind](await stand(page, kind, hub.id));
				const { puts, beantwortet } = zaehleWetterSchreiben(page, kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				const zeile = await grenzenOeffnen(reiter, ZEILE);
				await zeile.getByTestId(WT.grenze(ZEILE, 'upper', 'orange')).fill('50');
				await fertig(zeile, ZEILE);

				// sofort (innerhalb des Entprell-Fensters) den Reiter wechseln
				await page.locator(`[data-testid="${sel.reiter}-zustellung"]:visible`).click();
				await expect(page.locator('[data-testid="zustellung-tab"]:visible [data-testid="zustellung-stille-schalter"]').first()).toBeVisible({ timeout: 10_000 });
				await ws.alarm(page).click();
				await expect(ws.alarm(page)).toBeChecked({ checked: ws.alarmNeu });

				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				await expect
					.poll(async () => ws.alarmWert(await stand(page, kind, hub.id)), { timeout: 10_000, message: 'die Alarm-Änderung ist gespeichert' })
					.toBe(ws.alarmNeu);
				const s = await stand(page, kind, hub.id);
				expect(seiteImStand(s, ZEILE, 'upper').orange, 'die Grenzen-Änderung ging beim Reiterwechsel verloren').toBe(50);
				expect(ALTFELDER[kind](s), 'AC-30: Altfelder auf dem Server unverändert').toEqual(vorher);
				// Ein Schreibvorgang des Reiters, der die Grenze trägt (beim Vergleich darf der Alarm-PUT
				// denselben Pfad nutzen; gezählt wird deshalb, wie oft die Grenze gesendet wurde).
				const mitGrenze = puts.filter((r) => JSON.stringify(r.postDataJSON()).includes('"orange":50'));
				expect(mitGrenze.length, 'AC-38: die Grenze genau EINMAL gesendet').toBe(1);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-4 — fremder Schreibvorgang dazwischen: der fremde Name wird nie überschrieben; der Trip
		// speichert die Grenze nach „Nochmal speichern", der Vergleich lädt bei 412 neu (AC-38).
		test(`WS-4 (${kind}): fremde Änderung dazwischen, dann Grenze ändern → Konflikt, „Nochmal speichern", fremder Name bleibt, Altfelder unverändert`, async ({
			page
		}) => {
			const hub = await seedGrenzen(page.request, kind);
			try {
				const pfad = hubApiPath(kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				const vorher = await stand(page, kind, hub.id);
				const fremderName = `${vorher.name} (fremd)`;
				const fremd = await page.request.put(pfad, { data: { name: fremderName } });
				expect(fremd.status(), 'fremder Schreibvorgang ohne If-Match wird angenommen').toBe(200);

				const zeile = await grenzenOeffnen(reiter, ZEILE);
				await zeile.getByTestId(WT.grenze(ZEILE, 'upper', 'orange')).fill('50');
				await fertig(zeile, ZEILE);

				await expect(anzeige(page), 'veralteter Stand: der Server lehnt mit 412 ab').toHaveAttribute('data-state', 'conflict', { timeout: 10_000 });
				const nochmal = anzeige(page).getByRole('button', { name: 'Nochmal speichern' });
				await expect(nochmal).toBeVisible();
				await nochmal.click();
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				const s = await stand(page, kind, hub.id);
				expect(s.name, 'der fremd gespeicherte Name darf nicht überschrieben werden').toBe(fremderName);
				expect(ALTFELDER[kind](s), 'AC-30: Altfelder auf dem Server unverändert').toEqual(ALTFELDER[kind](vorher));
				expect(
					seiteImStand(s, ZEILE, 'upper').orange === 50,
					ws.konfliktLaedtNeu ? 'AC-38: der Vergleich lädt bei 412 neu, die Grenze bleibt auf dem Serverstand' : 'Trip: „Nochmal speichern" sendet die Grenze'
				).toBe(!ws.konfliktLaedtNeu);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-5 — Gegenprobe Pausieren: die Grenzen-Änderung wird nicht verdrängt, das Pausieren trägt nur den Status.
		test(`WS-5 (${kind}): Pausieren direkt nach „Fertig" → Grenze UND Status gespeichert, Status-Rumpf nur Status, Altfelder bleiben`, async ({
			page
		}) => {
			const hub = await seedGrenzen(page.request, kind);
			try {
				const vorher = ALTFELDER[kind](await stand(page, kind, hub.id));
				const alle = zaehleAlleSchreiben(page, kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				const zeile = await grenzenOeffnen(reiter, ZEILE);
				await zeile.getByTestId(WT.grenze(ZEILE, 'upper', 'orange')).fill('50');
				await fertig(zeile, ZEILE);

				await page.getByRole('button', { name: 'Weitere Aktionen' }).first().click();
				const pausieren = page.getByRole('menuitem', { name: 'Pausieren' });
				await expect(pausieren, 'Vorbedingung: der Hub bietet „Pausieren" an').toBeVisible();
				await pausieren.click();

				await expect
					.poll(async () => ws.istPausiert(await stand(page, kind, hub.id)), { timeout: 10_000, message: 'Server: pausiert' })
					.toBe(true);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				const status = alle.filter((r) => ws.statusPausiert((r.postDataJSON() ?? {}) as Stand));
				expect(status.length, 'genau EIN Status-Schreibvorgang').toBe(1);
				expect(Object.keys(status[0].postDataJSON() as Stand).sort(), `Pausieren-Rumpf trägt nur { ${ws.statusSchluessel.join(', ')} }`).toEqual(
					ws.statusSchluessel
				);
				const s = await stand(page, kind, hub.id);
				expect(seiteImStand(s, ZEILE, 'upper').orange, 'die Grenzen-Änderung ging beim Pausieren verloren').toBe(50);
				expect(ALTFELDER[kind](s), 'AC-30: Altfelder auf dem Server unverändert').toEqual(vorher);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-8 — „Alarm ab" einer Zeile (früher „Markieren"): gespeichert, überlebt Neuladen; Korridor-
		// Markierung (`corridors[].mark`) bleibt; kein „Warnen" in der Zeile (#1371).
		test(`WS-8 (${kind}): „Alarm ab" einer Zeile umstellen → gespeichert, überlebt Neuladen, Korridor-Markierung unverändert; kein „Warnen"`, async ({
			page
		}) => {
			const hub = await seedGrenzen(page.request, kind);
			try {
				const vorher = ALTFELDER[kind](await stand(page, kind, hub.id));
				const { puts, beantwortet } = zaehleWetterSchreiben(page, kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				const zeile = reiter.getByTestId(WT.zeile(ZEILE));
				await expect(zeile.getByRole('button', { name: 'Warnen' }), 'WS-8 FAIL: „Warnen" ist wieder in der Zeile (#1371)').toHaveCount(0);
				const rot = zeile.getByTestId(WT.alarmAbStufe(ZEILE, 'red'));
				await expect(rot).toHaveAttribute('aria-checked', 'false');

				await rot.click();
				await expect(rot).toHaveAttribute('aria-checked', 'true');
				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(1);
				await bleibtBei(() => puts.length, 1, 1_200, 'WS-8: genau EIN Schreibvorgang');

				const s = await stand(page, kind, hub.id);
				expect(dc(s).ampel.metrics[ZEILE].alarm_ab, '„Alarm ab Rot" gespeichert').toBe('red');
				expect(ALTFELDER[kind](s), 'AC-30: Korridore samt Markierung unverändert').toEqual(vorher);
				const r2 = await oeffneWetter(page, kind, hub.id);
				await expect(r2.getByTestId(WT.zeile(ZEILE)).getByTestId(WT.alarmAbStufe(ZEILE, 'red'))).toHaveAttribute('aria-checked', 'true');
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-7 — fängt: ein Speichern des Reiters verändert Felder außerhalb seiner Zuständigkeit
		// (Replace statt Merge, Startwerte überschreiben gespeicherte Werte).
		test(`WS-7 (${kind}): mehrere Bedienungen im Reiter (Grenze, Alarm ab, −) → alle Einstellungen außerhalb des Reiters bleiben unverändert`, async ({
			page
		}) => {
			const hub = await seedGrenzen(page.request, kind);
			try {
				const vorher = await stand(page, kind, hub.id);
				const { beantwortet } = zaehleWetterSchreiben(page, kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				const zeile = await grenzenOeffnen(reiter, ZEILE);
				await zeile.getByTestId(WT.grenze(ZEILE, 'upper', 'orange')).fill('50');
				await fertig(zeile, ZEILE);
				await reiter.getByTestId(WT.zeile('wind')).getByTestId(WT.alarmAbStufe('wind', 'red')).click();
				const weg = hub.auswahl.find((id) => id !== ZEILE && id !== 'wind')!;
				await reiter.getByTestId(WT.entfernen(weg)).click();
				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				const nachher = await stand(page, kind, hub.id);
				// Eigenfelder des Reiters (Spec Datenfluss): display_config.{ampel, metrics|active_metrics},
				// Trip zusätzlich report_config.day_window_* (unverändert gesendet) und abgeleitete alert_rules.
				const obenEigen = new Set(['display_config', 'updated_at', 'etag', 'alert_rules', 'report_config']);
				for (const key of Object.keys(vorher)) {
					if (obenEigen.has(key)) continue;
					expect(nachher[key], `Feld „${key}" hat sich durch das Speichern des Reiters verändert`).toEqual(vorher[key]);
				}
				for (const key of Object.keys((vorher.report_config ?? {}) as Stand)) {
					expect((nachher.report_config as Stand)[key], `report_config.${key} hat sich verändert`).toEqual((vorher.report_config as Stand)[key]);
				}
				const dcEigen = new Set(['ampel', 'metrics', 'active_metrics']);
				for (const key of Object.keys(dc(vorher))) {
					if (dcEigen.has(key)) continue;
					expect(dc(nachher)[key], `display_config.${key} hat sich verändert`).toEqual(dc(vorher)[key]);
				}
				expect(seiteImStand(nachher, ZEILE, 'upper').orange).toBe(50);
				expect(dc(nachher).ampel.metrics.wind.alarm_ab).toBe('red');
				expect(auswahlImStand(kind, nachher)).not.toContain(weg);
			} finally {
				await hub.aufraeumen();
			}
		});

		// WS-6 — „Korridor leeren" heißt jetzt: alle Grenzen einer Seite leeren (AC-16 „Ein leeres Feld
		// heißt: auf dieser Seite keine Grenze."). Die Metrik bleibt im Briefing, nach Neuladen steht die Zeile noch.
		test(`WS-6 (${kind}): alle Grenzen einer Zeile leeren → „immer grün", genau EIN Schreibvorgang, nach Neuladen steht die Zeile noch`, async ({
			page
		}) => {
			const hub = await seedGrenzen(page.request, kind);
			try {
				const vorher = ALTFELDER[kind](await stand(page, kind, hub.id));
				const { puts, beantwortet } = zaehleWetterSchreiben(page, kind, hub.id);
				const reiter = await oeffneWetter(page, kind, hub.id);
				const zeile = await grenzenOeffnen(reiter, ZEILE);
				for (const f of ['yellow', 'orange', 'red'] as const) await zeile.getByTestId(WT.grenze(ZEILE, 'upper', f)).fill('');
				await fertig(zeile, ZEILE);
				await expect(zeile.getByTestId(WT.gruen(ZEILE))).toHaveText('· immer grün (keine Grenze gesetzt)');

				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(1);
				await bleibtBei(() => puts.length, 1, 1_200, 'WS-6: genau EIN Schreibvorgang');
				const s = await stand(page, kind, hub.id);
				expect(seiteImStand(s, ZEILE, 'upper'), 'oben ohne Grenze gespeichert').toEqual({});
				expect(auswahlImStand(kind, s), 'die Metrik bleibt im Briefing').toContain(ZEILE);
				expect(ALTFELDER[kind](s), 'AC-30: Altfelder auf dem Server unverändert').toEqual(vorher);

				const r2 = await oeffneWetter(page, kind, hub.id);
				await expect(r2.getByTestId(WT.zeile(ZEILE)), 'nach Neuladen steht die Zeile noch').toBeVisible();
				await expect(r2.getByTestId(WT.gruen(ZEILE))).toHaveText('· immer grün (keine Grenze gesetzt)');
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
