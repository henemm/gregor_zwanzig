// Gemeinsamer Aufbau der Klickpfad-Buendel zu Issue #1703 Scheibe 8
// (kanal-eigene Metrikauswahl der Vergleichs-UEBERSICHTSTABELLE).
// Spec: docs/specs/modules/feat_1703_s8_compare_kanal_tabs.md § Testauflage.
//
// 🔴 #1423-Lehre: NIE `count() === 0 -> weiter`. Der Metrik-Block ist waehrend
// des Katalog-Ladens bewusst aus dem DOM entfernt (WeatherMetricsTab.svelte:
// 1204-1207) — eine Momentaufnahme macht daraus ein stilles "gibt es nicht".
// `oeffneUebersicht()` wartet das Ladeende per `waitFor({state:'attached'})`
// ab; erst danach darf eine LEERE Liste behauptet werden.
// 🔴 Scope-Pflicht: der Reiter mountet WeatherV2Reihenfolge DREIMAL
// (Uebersicht/Stundenverlauf/Ausblick) mit denselben `wm2-*`-Testids — alles
// hier haengt am Block `[data-testid="layout-tab"][data-context="vergleich"]`.
//
// #2794 S3a: Grundauswahl (Schritt Wetter) und Kanal-Karte (Schritt Zustellung) liegen in getrennten
// Schritten — siehe `KanalFlaeche.reiter`.
// #3154 (#3122 B3b): im Hub gibt es die Kanal-Karte nicht mehr (Karte „Was steht wo“ im Reiter Wetter,
// Helfer e2e/was-steht-wo.helpers.ts); die Hub-Helfer sind entfernt. Hier bleibt nur, was die Anlege-Seite
// /compare/new nutzt (compare-neu-kanal-anlegen.staging.spec.ts).
//
// Alle Buendel ausfuehren (aus frontend/, NACH Merge + Staging-Deploy) —
// die Config nimmt Hub- UND Anlege-Pfad auf:
//   set -a; source /home/hem/gregor_zwanzig/.claude/validator.env; set +a
//   set -a; source /home/hem/gregor_zwanzig_staging/.env; set +a
//   npx playwright test --config=e2e/playwright.compare-uebersicht-kanal.staging.config.ts

import { expect, type Locator, type Page } from '@playwright/test';

export type KanalId = 'email' | 'telegram' | 'sms';

/** Kappungs-Aussage je Kanal (ltChannels.ts::ltCapNoteText) — zugleich Beleg,
 *  dass ein Reiterwechsel angekommen und gerendert ist. */
const KANAL_HINWEIS: Record<KanalId, RegExp> = {
	email: /keine Begrenzung/,
	telegram: /^Telegram: \d+ Metriken · /,
	sms: /Fließtext, \d+ Zeichen$/
};

/** #2794 S3a (Spec feat_2794_s3a_teil2_leiste.md): die Grundauswahl steht im Reiter
 *  `wetter`, die Kanal-Karte (Layout/Reihenfolge) im Reiter `zustellung`. Im Hub ist
 *  jeweils nur EIN Reiter-Inhalt gemountet — die Flaeche kennt daher zwei Reiter und
 *  wechselt per echtem Klick. Die Locatoren sind seitenweit und loesen erst beim
 *  Zugriff auf, gelten also nach jedem Reiterwechsel neu.
 *  Achtung: ein Reiterwechsel flusht eine ausstehende Aenderung (eigener PUT) — wo
 *  Grundauswahl- und Kanal-Geste frueher im selben Entprell-Fenster lagen, entstehen
 *  jetzt zwei PUTs (Begruendung wie MS-2 in hub-wetter-metriken-speichert-selbst). */
export type KanalReiter = 'wetter' | 'zustellung';

export interface KanalFlaeche {
	page: Page;
	/** Panel des Reiters Zustellung (Kanal-Karte). */
	panel: Locator;
	layout: Locator;
	reihenfolge: Locator;
	/** Grundauswahl im Reiter Wetter — vorher `zuGrundauswahl(f)` aufrufen. */
	grundauswahl: Locator;
	/** Wechselt per Klick in den Reiter und wartet dessen Inhalt ab. */
	reiter: (ziel: KanalReiter) => Promise<void>;
}

/** Aktive, sortierbare Liste des offenen Kanal-Reiters. */
export function aktiveMetriken(f: KanalFlaeche): Promise<(string | null)[]> {
	return f.reihenfolge.locator('[data-testid="wm2-reihenfolge-row"]')
		.evaluateAll((els) => els.map((e) => e.getAttribute('data-metric-id')));
}

/** Gruppe "Aus in diesem Kanal" (ADR-0050 Regel 4). */
export function ausMetriken(f: KanalFlaeche): Promise<(string | null)[]> {
	return f.reihenfolge.locator('[data-testid="wm2-aus-row"]')
		.evaluateAll((els) => els.map((e) => e.getAttribute('data-metric-id')));
}

/** Kanal umschalten — und den Wechsel an seiner WIRKUNG abwarten. */
export async function waehleKanal(f: KanalFlaeche, kanal: KanalId): Promise<void> {
	await f.layout.getByTestId(`channel-tab-${kanal}`).click();
	await expect(f.layout.getByTestId('lt-cap-note')).toHaveText(KANAL_HINWEIS[kanal], { timeout: 10_000 });
}

/** „Aus in diesem Kanal“ OHNE Speicher-Erwartung — fuer die Anlege-Seite
 *  `/compare/new`: dort gibt es kein PUT je Geste, der Vergleich existiert noch
 *  gar nicht. Gespeichert wird dort genau einmal, per POST beim „Briefing
 *  aktivieren" (compare-neu-kanal-anlegen.staging.spec.ts). Die Zusicherung
 *  bleibt dieselbe: die Groesse muss in der Aus-Gruppe ANKOMMEN — ein blosser
 *  Klick ohne diese Wirkung waere kein Nachweis. */
export async function ausSchaltenOhneSpeichern(f: KanalFlaeche, metrik: string): Promise<void> {
	await f.reihenfolge
		.locator(`[data-testid="wm2-reihenfolge-row"][data-metric-id="${metrik}"]`)
		.getByRole('button', { name: 'Aus', exact: true }).click();
	await expect.poll(() => ausMetriken(f), { timeout: 10_000 }).toContain(metrik);
}
