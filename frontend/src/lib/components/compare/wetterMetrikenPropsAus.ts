// Issue #2276 Scheibe S6g (Epic #2345) — EINE Stelle, die aus dem
// Compare-Wizard-Zustand das Prop-Bündel für den geteilten Wetter-Metriken-
// Organismus (`shared/WeatherMetricsTab.svelte`) baut. Alle DREI
// Vergleichs-Mounts (Hub `CompareTabs.svelte`, Anlege-Seite Desktop + Mobil
// `CompareNewEditor.svelte`) speisen dasselbe Bündel ein — bei drei Mounts ×
// zehn Werten + neun Rückrufen wären Inline-Adapter dreifache Gelegenheit zur
// Drift (Spec, Design-Entscheidung 1).
//
// gz-eigenstaendig: Diese Uebersetzung vom Compare-Wizard-Zustand in Wertprops
// gehört nach compare/ und hat bewusst kein Trip-Pendant — läge sie in shared/,
// importierte der geteilte Bereich die Compare-Klebeschicht (genau das, was
// #2276 abbaut), und der Trip-Mount braucht sie nicht: er übergibt gar keine
// dieser zehn Props.
//
// 🔴 Aufrufform (prüfbar, kein Prosa-Wunsch, Form-Auflage der Spec):
// `{...wetterMetrikenPropsAus(wiz)}` steht IM MARKUP-AUSDRUCK jedes Mounts,
// NIEMALS in einer Skript-Variablen. Ein einmal berechnetes, dort
// eingefrorenes Objekt bestünde SSR-Prüfstand und AST-Wächter anstandslos und
// fiele erst im Browser auf.
//
// 🔴 GENAU EINE FELDKLASSE (Spec, Design-Entscheidung 2) — die Vereinfachung
// dieser Scheibe gegenüber S6c/S6d/S6e: alle zehn Felder sind Snapshot-Felder
// (Klasse A), Wertprop + eigener oder gemeinsamer Rückruf, UND Mitglied in
// `wetterMetrikenZustandsBruecke`s `werte()`. Kein persistenzloses Feld
// außerhalb der Brücke, keine toten Legacy-Restfelder.
//
// 🔴 Der gekoppelte Rückruf `onVergleichsMetrikenChange(active, channelActive)`
// (Spec, Design-Entscheidung 3): `toggleCompareMetric` schreibt heute
// `activeMetricKeys` UND — bei einer globalen Abwahl mit vorhandenen
// Kanal-Overrides (ADR-0050 Regel 3) — `channelActiveMetricKeys` in einem
// Funktionsdurchlauf. Ein 1:1-Rückruf je Feld würde diese Kopplung in zwei
// unabhängige, nacheinander feuernde Zuweisungen zerlegen — ein dazwischen
// lesender Snapshot sähe einen inkonsistenten Zwischenstand. `editCompareChannel`
// (kanal-lokale Umsortierung) nutzt DENSELBEN Rückruf, mit dem unveränderten
// `activeMetricKeys` als erstem Argument.
//
// Defaults sind identisch zu den bereits bestehenden Defaults in
// `wetterMetrikenSnapshotAus()` (`weather-metrics-tab/weatherMetricsCompareSave.ts`)
// — keine neue Fallback-Entscheidung, nur eine zweite Anwendungsstelle
// desselben Vokabulars.
//
// Kein Browser-/SvelteKit-Import — lauffähig unter node --experimental-strip-types.

import type { CompareChannelActiveMetrics } from '../shared/weather-metrics-tab/compareChannelMetricLayouts.ts';

// Issue #1361/#1372 S1b — Trip-Default (day_window.py DAY_WINDOW_START_HOUR/
// _END_HOUR), identisch zu `weatherMetricsCompareSave.ts`.
const DEFAULT_DAY_WINDOW_START_HOUR = 4;
const DEFAULT_DAY_WINDOW_END_HOUR = 19;

/** Strukturelle Sicht auf die Wetter-Metriken/Layout-Felder des Compare-Wizard-
 *  Zustands — absichtlich nicht `CompareWizardState` selbst, damit diese
 *  Funktion auch gegen einen hydrierten Plain-Zustand arbeitet. */
export interface WetterMetrikenZustandsQuelle {
	activeMetricKeys?: string[] | null;
	channelActiveMetricKeys?: CompareChannelActiveMetrics;
	officialAlertsEnabled?: boolean;
	dayWindowStartHour?: number;
	dayWindowEndHour?: number;
	hourlyMetricKeys?: string[] | null;
	hourlyEnabled?: boolean;
	outlookMetricKeys?: string[] | null;
	outlookMetricFormats?: Record<string, boolean> | null;
	outlookEnabled?: boolean;
}

/**
 * Das Prop-Bündel für `WeatherMetricsTab` im Vergleichs-Zweig: zehn Werte
 * (die einzige Feldklasse dieser Scheibe) und neun Gesten-Rückrufe — einer
 * davon (`onVergleichsMetrikenChange`) gekoppelt für die beiden Felder der
 * Metrik-Auswahl.
 */
export function wetterMetrikenPropsAus(wiz: WetterMetrikenZustandsQuelle) {
	return {
		activeMetricKeys: wiz.activeMetricKeys ?? null,
		channelActiveMetricKeys: wiz.channelActiveMetricKeys ?? { email: null, telegram: null, sms: null },
		officialAlertsEnabled: wiz.officialAlertsEnabled ?? true,
		dayWindowStartHour: wiz.dayWindowStartHour ?? DEFAULT_DAY_WINDOW_START_HOUR,
		dayWindowEndHour: wiz.dayWindowEndHour ?? DEFAULT_DAY_WINDOW_END_HOUR,
		hourlyMetricKeys: wiz.hourlyMetricKeys ?? null,
		hourlyEnabled: wiz.hourlyEnabled ?? true,
		outlookMetricKeys: wiz.outlookMetricKeys ?? null,
		outlookMetricFormats: wiz.outlookMetricFormats ?? null,
		outlookEnabled: wiz.outlookEnabled ?? true,
		onVergleichsMetrikenChange: (active: string[] | null, channelActive: CompareChannelActiveMetrics) => {
			wiz.activeMetricKeys = active;
			wiz.channelActiveMetricKeys = channelActive;
		},
		onOfficialAlertsEnabledChange: (an: boolean) => {
			wiz.officialAlertsEnabled = an;
		},
		onDayWindowStartHourChange: (v: number) => {
			wiz.dayWindowStartHour = v;
		},
		onDayWindowEndHourChange: (v: number) => {
			wiz.dayWindowEndHour = v;
		},
		onHourlyMetricKeysChange: (keys: string[] | null) => {
			wiz.hourlyMetricKeys = keys;
		},
		onHourlyEnabledChange: (an: boolean) => {
			wiz.hourlyEnabled = an;
		},
		onOutlookMetricKeysChange: (keys: string[] | null) => {
			wiz.outlookMetricKeys = keys;
		},
		onOutlookMetricFormatsChange: (formats: Record<string, boolean> | null) => {
			wiz.outlookMetricFormats = formats;
		},
		onOutlookEnabledChange: (an: boolean) => {
			wiz.outlookEnabled = an;
		}
	};
}
