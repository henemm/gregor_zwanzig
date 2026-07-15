<script lang="ts">
	// AlarmeScheduleTab — Issue #1258 Scheibe S3 (D4): duenner Trip-Container
	// analog BriefingScheduleTab.svelte. Bettet den geteilten AlarmeTab
	// (context="route") ein und berechnet NUR die route-spezifischen
	// Initialwerte aus dem Trip (Metrik-Levels, Korridor-Zaehler, Kanal-
	// Rekonstruktion) — der Container haelt KEINE eigene Persistenz-Quelle
	// mehr.
	//
	// Adversary Fix-Loop 1, F001: Kanal-Toggle und Metrik-Level-Aenderung
	// hatten hier je einen eigenen Debounce-Save-Aufruf (auf demselben
	// saveController), neben dem EINEN $effect in AlarmeTab.svelte — alle
	// drei teilten sich denselben Ein-Slot-Debounce
	// (saveStatusStore.svelte.ts:67-72), zwei Aenderungen aus verschiedenen
	// Quellen im 700ms-Fenster verwarfen die erste Payload still
	// (Datenverlust). Fix: Kanaele und Metrik-Level sind jetzt Teil der EINEN
	// konsolidierten Payload in AlarmeTab.svelte — dieser Container liefert
	// nur noch Initialwerte, keine zweite Schreibquelle mehr.
	//
	// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md
	//   (Implementation Details Abschnitt 9 "S3-Detail-Festlegungen", D4, AC-13..15)
	// Kontext: docs/context/feat-1258-s3-trip-alarme-tab.md

	import AlarmeTab from '$lib/components/shared/AlarmeTab.svelte';
	import { reconstructTripAlertChannels } from '../shared/alarme-tab/tripChannelReconstruction.ts';
	import type { Trip, AlertMetric, SensLevel } from '$lib/types';
	import type { SaveStatus } from '$lib/stores/saveStatusStore.svelte';

	interface Props {
		trip: Trip;
		onTripUpdate?: (updated: Trip) => void;
		saveController?: SaveStatus;
		/** Tab-Wechsel (analog BriefingScheduleTab onJump). "Wertebereiche öffnen →" springt in 'alerts'. */
		onJump?: (tab: string) => void;
	}
	let { trip, onTripUpdate, saveController, onJump }: Props = $props();

	// ── (c) Metrik-Level-Tabelle: Initialwert aus display_config.metric_alert_levels ──
	const metricLevels = $derived(
		(trip.display_config?.metric_alert_levels ?? {}) as Record<AlertMetric, SensLevel>
	);
	const activeMetrics = $derived(Object.keys(metricLevels) as AlertMetric[]);

	// ── (a) Korridor-Zusammenfassung: notify-Zaehler (Toggles bleiben im CorridorEditor) ──
	const notifyCount = $derived((trip.corridors ?? []).filter((c) => c.notify).length);

	// ── (d) Kanaele: AC-15 Ist-Zustand-Rekonstruktion als Initialwert ──────────
	const existingChannels = $derived(reconstructTripAlertChannels(trip));
</script>

<div class="alarme-schedule-tab">
	<AlarmeTab
		context="route"
		{trip}
		{onTripUpdate}
		{saveController}
		{activeMetrics}
		{metricLevels}
		{notifyCount}
		onJumpToWertebereiche={() => onJump?.('alerts')}
		{existingChannels}
	/>
</div>
