<script lang="ts">
	// Step 4: Briefings & Kanaele (Epic #136 Sub-Spec #164).
	// Quelle: docs/specs/modules/epic_136_step4_briefings.md §7
	//
	// Drei Sektionen, jede in eigenem GCard mit Eyebrow-Ueberschrift:
	//   1. Kanaele       (4 ChannelToggles: email, signal, telegram, sms-disabled)
	//   2. Reports       (2 ReportRows: morning, evening)
	//   3. Schwellwerte  (4 ThresholdRows: gust_kmh, precip_mm, thunder_level, snow_line_m)
	//
	// State: getContext('trip-wizard-state') — alle Mutationen direkt an
	// `wizard.briefings.{channels|reports|thresholds}.*`.
	//
	// Save-Button kommt aus TripWizardShell, nicht hier (state.save()).

	import { getContext } from 'svelte';
	import { Eyebrow } from '$lib/components/ui/eyebrow';
	import { GCard } from '$lib/components/ui/g-card';
	import type { WizardState, BriefingConfig } from '../wizardState.svelte';
	import ChannelToggle from './ChannelToggle.svelte';
	import ReportRow from './ReportRow.svelte';
	import ThresholdRow from './ThresholdRow.svelte';

	type ThunderLevel = 'NONE' | 'MED' | 'HIGH';

	const wizard = getContext<WizardState>('trip-wizard-state');

	// --- Factory-Handler (CLAUDE.md Safari-Pattern) -------------------------

	function makeChannelHandler(channel: keyof BriefingConfig['channels']) {
		return function doToggleChannel(checked: boolean): void {
			wizard.briefings.channels[channel] = checked;
		};
	}

	function makeReportEnabledHandler(report: 'morning' | 'evening') {
		return function doToggleReport(enabled: boolean): void {
			wizard.briefings.reports[report].enabled = enabled;
		};
	}

	function makeReportTimeHandler(report: 'morning' | 'evening') {
		return function doSetReportTime(time: string): void {
			wizard.briefings.reports[report].time = time;
		};
	}

	function makeNumberThresholdHandler(field: 'gust_kmh' | 'precip_mm' | 'snow_line_m') {
		return function doSetNumberThreshold(v: number | ThunderLevel | null): void {
			// `v` ist hier immer number|null — ThunderLevel kommt nur vom thunder-Handler.
			wizard.briefings.thresholds[field] = v as number | null;
		};
	}

	function doSetThunderThreshold(v: number | ThunderLevel | null): void {
		wizard.briefings.thresholds.thunder_level = v as ThunderLevel | null;
	}

	// SMS-Channel ist disabled — Toggle hat einen No-op-Handler.
	function doNoopSmsToggle(_checked: boolean): void {
		// intentional no-op — SMS-Channel ist in der UI gesperrt (Spec §7, AC#5)
	}
</script>

<div data-testid="trip-wizard-step4-container" class="space-y-6 py-4">
	<!-- Sektion 1: Kanaele -->
	<section class="space-y-2">
		<Eyebrow class="text-xs uppercase tracking-wide text-[var(--g-ink-faint)]"
			>Kanaele</Eyebrow
		>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<div data-testid="trip-wizard-step4-channels-list" class="space-y-3">
				<ChannelToggle
					label="E-Mail"
					checked={wizard.briefings.channels.email}
					onchange={makeChannelHandler('email')}
					testid="trip-wizard-step4-channel-email"
				/>
				<ChannelToggle
					label="Signal"
					checked={wizard.briefings.channels.signal}
					onchange={makeChannelHandler('signal')}
					testid="trip-wizard-step4-channel-signal"
				/>
				<ChannelToggle
					label="Telegram"
					checked={wizard.briefings.channels.telegram}
					onchange={makeChannelHandler('telegram')}
					testid="trip-wizard-step4-channel-telegram"
				/>
				<ChannelToggle
					label="SMS"
					checked={false}
					disabled
					hint="demnaechst verfuegbar"
					onchange={doNoopSmsToggle}
					testid="trip-wizard-step4-channel-sms"
				/>
			</div>
		</GCard>
	</section>

	<!-- Sektion 2: Reports -->
	<section class="space-y-2">
		<Eyebrow class="text-xs uppercase tracking-wide text-[var(--g-ink-faint)]"
			>Reports</Eyebrow
		>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<div data-testid="trip-wizard-step4-reports-list" class="space-y-3">
				<ReportRow
					label="Morgen-Briefing"
					enabled={wizard.briefings.reports.morning.enabled}
					time={wizard.briefings.reports.morning.time}
					onEnabledChange={makeReportEnabledHandler('morning')}
					onTimeChange={makeReportTimeHandler('morning')}
					testidToggle="trip-wizard-step4-report-morning-toggle"
					testidTime="trip-wizard-step4-report-morning-time"
				/>
				<ReportRow
					label="Abend-Briefing"
					enabled={wizard.briefings.reports.evening.enabled}
					time={wizard.briefings.reports.evening.time}
					onEnabledChange={makeReportEnabledHandler('evening')}
					onTimeChange={makeReportTimeHandler('evening')}
					testidToggle="trip-wizard-step4-report-evening-toggle"
					testidTime="trip-wizard-step4-report-evening-time"
				/>
			</div>
		</GCard>
	</section>

	<!-- Sektion 3: Alert-Schwellwerte -->
	<section class="space-y-2">
		<Eyebrow class="text-xs uppercase tracking-wide text-[var(--g-ink-faint)]"
			>Alert-Schwellwerte</Eyebrow
		>
		<GCard class="rounded-md border border-[var(--g-ink-faint)]/20 p-4">
			<div data-testid="trip-wizard-step4-thresholds-list" class="space-y-3">
				<ThresholdRow
					label="Boeen"
					type="number"
					unit="km/h"
					value={wizard.briefings.thresholds.gust_kmh}
					onchange={makeNumberThresholdHandler('gust_kmh')}
					testid="trip-wizard-step4-threshold-gust"
				/>
				<ThresholdRow
					label="Niederschlag"
					type="number"
					unit="mm"
					value={wizard.briefings.thresholds.precip_mm}
					onchange={makeNumberThresholdHandler('precip_mm')}
					testid="trip-wizard-step4-threshold-precip"
				/>
				<ThresholdRow
					label="Gewitter"
					type="thunder"
					value={wizard.briefings.thresholds.thunder_level}
					onchange={doSetThunderThreshold}
					testid="trip-wizard-step4-threshold-thunder"
				/>
				<ThresholdRow
					label="Schneefallgrenze"
					type="number"
					unit="m"
					value={wizard.briefings.thresholds.snow_line_m}
					onchange={makeNumberThresholdHandler('snow_line_m')}
					testid="trip-wizard-step4-threshold-snow"
				/>
			</div>
		</GCard>
	</section>
</div>
