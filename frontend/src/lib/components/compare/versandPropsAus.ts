// Issue #2276 Scheibe S6e (Epic #2345) — EINE Stelle, die aus dem
// Compare-Wizard-Zustand das Prop-Bündel für den geteilten Versand-Organismus
// (`shared/VersandTab.svelte`) baut. Alle DREI Vergleichs-Mounts (Hub
// `CompareTabs.svelte`, Anlege-Seite Desktop + Mobil `CompareNewEditor.svelte`)
// speisen dasselbe Bündel ein — bei drei Mounts × elf Feldern wären
// Inline-Adapter dreifache Gelegenheit zur Drift (Spec, Design-Entscheidung 1).
//
// gz-eigenstaendig: Diese Uebersetzung vom Compare-Wizard-Zustand in Wertprops
// gehört nach compare/ und hat bewusst kein Trip-Pendant — läge sie in shared/,
// importierte der geteilte Bereich die Compare-Klebeschicht (genau das, was
// #2276 abbaut und versand_tab_laedt_keine_compare_klebeschicht.test.ts
// bewacht), und der Trip-Mount braucht sie nicht: er übergibt `trip`/
// `reportConfig` ohne Zwischenschicht.
//
// 🔴 Aufrufform (prüfbar, kein Prosa-Wunsch, Form-Auflage der Spec):
// `{...versandPropsAus(wiz)}` steht IM MARKUP-AUSDRUCK jedes Mounts, NIEMALS in
// einer Skript-Variablen. Ein einmal berechnetes, dort eingefrorenes Objekt
// bestünde SSR-Prüfstand und AST-Wächter anstandslos und fiele erst im Browser
// auf — die `$state`-Lesezugriffe würden dann außerhalb des reaktiven Renderns
// registriert.
//
// 🔴 DREI FELDKLASSEN (Spec, Design-Entscheidung 2) — die Nuance dieser Scheibe:
//   Klasse A (7): sendTelegram, sendSms, morningEnabled, morningTime,
//     eveningEnabled, eveningTime, endDate — Wert + eigener Rückruf, UND
//     Mitglied in `versandZustandsBruecke`s `werte()` (Snapshot/Nutzlast/Rollback).
//   Klasse B (1): sendEmail — Wert + eigener Rückruf, aber BEWUSST NICHT in der
//     Brücke. `VersandSnapshot`/`VersandHydrationTarget` kennen das Feld nicht,
//     `ComparePreset` hat kein `send_email`, `baueVersandNutzlast` sendet es nie.
//     Nähme die Brücke es auf, sähe `versandSnapshotAus` ein Feld, das der
//     Payload-Baustein ignoriert: reines Rauschen im Diff-Gate.
//   Klasse C (3): alertCooldownMinutes, alertQuietFrom, alertQuietTo — tote
//     Legacy-Restfelder OHNE Bedienelement im Versand-Reiter (die
//     Alert-Zustellung zog in #1258 S4 nach AlarmeTab.svelte ab), die aber
//     weiter durch Snapshot/Nutzlast laufen MÜSSEN (S5 AC-11, sonst nullt der
//     Versand-PUT die Alarm-Zustellungsfelder, BUG-DATALOSS-GR221-Klasse). Ihr
//     einziger Schreibweg ist die Rollback-Senke `onVersandFeldSetzen`.
//
// Kein Browser-/SvelteKit-Import — lauffähig unter node --experimental-strip-types.

/** Strukturelle Sicht auf die Versandfelder des Compare-Wizard-Zustands —
 *  absichtlich nicht `CompareWizardState` selbst, damit diese Funktion auch
 *  gegen einen hydrierten Plain-Zustand arbeitet. */
export interface VersandZustandsQuelle {
	sendEmail?: boolean;
	sendTelegram?: boolean;
	sendSms?: boolean;
	morningEnabled?: boolean;
	morningTime?: string;
	eveningEnabled?: boolean;
	eveningTime?: string;
	endDate?: string | null;
	alertCooldownMinutes?: number;
	alertQuietFrom?: string;
	alertQuietTo?: string;
}

/**
 * Das Prop-Bündel für `VersandTab` im Vergleichs-Zweig: acht Werte (Klasse A +
 * B), drei Legacy-Lesewerte (Klasse C) ohne eigenen Rückruf, acht
 * Gesten-Rückrufe und die Rollback-Senke des unveränderten
 * Vergleichs-Speicherwegs.
 */
export function versandPropsAus(wiz: VersandZustandsQuelle) {
	return {
		sendEmail: wiz.sendEmail ?? false,
		sendTelegram: wiz.sendTelegram ?? false,
		sendSms: wiz.sendSms ?? false,
		morningEnabled: wiz.morningEnabled ?? true,
		morningTime: wiz.morningTime ?? '07:00',
		eveningEnabled: wiz.eveningEnabled ?? false,
		eveningTime: wiz.eveningTime ?? '18:00',
		endDate: wiz.endDate ?? null,
		// Klasse C: `undefined` ist hier ein gültiger Wert („nicht gesetzt") —
		// ein `?? 0`/`?? ''` würde beim nächsten PUT einen erfundenen Wert
		// persistieren.
		alertCooldownMinutes: wiz.alertCooldownMinutes,
		alertQuietFrom: wiz.alertQuietFrom,
		alertQuietTo: wiz.alertQuietTo,
		onSendEmailChange: (an: boolean) => {
			wiz.sendEmail = an;
		},
		onSendTelegramChange: (an: boolean) => {
			wiz.sendTelegram = an;
		},
		onSendSmsChange: (an: boolean) => {
			wiz.sendSms = an;
		},
		onMorningEnabledChange: (an: boolean) => {
			wiz.morningEnabled = an;
		},
		onMorningTimeChange: (zeit: string) => {
			wiz.morningTime = zeit;
		},
		onEveningEnabledChange: (an: boolean) => {
			wiz.eveningEnabled = an;
		},
		onEveningTimeChange: (zeit: string) => {
			wiz.eveningTime = zeit;
		},
		onEndDateChange: (datum: string | null) => {
			wiz.endDate = datum;
		},
		/** Rollback-Senke: `rollbackVersandSnapshot` (versandVergleichSpeicherung.ts)
		 *  setzt nach einem gescheiterten PUT feldweise zurück — auch die drei
		 *  toten Legacy-Restfelder, für die es kein Bedienelement gibt. KEIN
		 *  Bedienelement schreibt hierüber; die acht Rückrufe oben sind die
		 *  einzigen Schreibwege der Oberfläche. */
		onVersandFeldSetzen: (feld: string, wert: unknown) => {
			(wiz as unknown as Record<string, unknown>)[feld] = wert;
		}
	};
}
