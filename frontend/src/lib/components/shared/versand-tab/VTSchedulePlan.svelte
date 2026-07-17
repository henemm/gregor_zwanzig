<script lang="ts">
	// VT_SchedulePlan — Issue #1232 Scheibe 1: "Briefing-Zeitplan" im geteilten
	// VersandTab-Organism (context="route").
	//
	// 1:1-Struktur aus versand-tab.jsx (VT_SchedulePlan), Datenbindung an die
	// echten ReportConfig-Felder statt der JSX-Mock-Seeds:
	//   morning_enabled/evening_enabled, morning_time/evening_time,
	//   multi_day_trend_morning/evening (KL-2: eigene Trend-Karte mit zwei
	//   Anhänge-Schaltern statt eigener Uhrzeit).
	// KL-1: keine per-Karte-Kanal-Chips (kein Backend-Feld für per-Briefing-Kanäle).
	//
	// Spec: docs/specs/modules/versand_tab_route.md (AC-3, AC-4, KL-1, KL-2)

	import { Eyebrow, Card } from '$lib/components/atoms';
	import { Checkbox } from '$lib/components/ui/checkbox';

	interface Props {
		/** Issue #1232 Scheibe 2b: context-Diskriminierung — vergleich zeigt
		 * keine Mehrtages-Trend-Karte (KL-2: kein multi_day_trend-Feld am
		 * ComparePreset) und eine eigene Intro-Copy-Zeile. */
		context?: 'route' | 'vergleich';
		hasActiveChannel: boolean;
		morning_enabled: boolean;
		morning_time: string;
		evening_enabled: boolean;
		evening_time: string;
		multi_day_trend_morning?: boolean;
		multi_day_trend_evening?: boolean;
		onMorningToggle: (e: Event) => void;
		onEveningToggle: (e: Event) => void;
		onMorningTime: (e: Event) => void;
		onEveningTime: (e: Event) => void;
		onTrendMorningToggle?: (e: Event) => void;
		onTrendEveningToggle?: (e: Event) => void;
	}
	let {
		context = 'route',
		hasActiveChannel,
		morning_enabled,
		morning_time,
		evening_enabled,
		evening_time,
		multi_day_trend_morning = false,
		multi_day_trend_evening = false,
		onMorningToggle,
		onEveningToggle,
		onMorningTime,
		onEveningTime,
		onTrendMorningToggle,
		onTrendEveningToggle
	}: Props = $props();

	const isRoute = $derived(context === 'route');

	// Issue #1286: Quick-Pick-Chips — feuern denselben Callback wie das
	// Zeit-Input, mit einem synthetischen Event (Factory-Pattern, Safari-
	// Closure-Schutz, CLAUDE.md).
	function makeQuickPickHandler(cb: (e: Event) => void, value: string) {
		return function doQuickPick() {
			cb({ target: { value } } as unknown as Event);
		};
	}
</script>

<div>
	<Eyebrow style="margin-bottom: 10px;">Briefing-Zeitplan</Eyebrow>

	{#if !hasActiveChannel}
		<div class="vt-empty-box" data-testid="briefings-channel-empty">
			<strong class="vt-empty-strong">Kein Kanal aktiv.</strong> Aktiviere oben mindestens einen Briefing-Kanal,
			damit hier Zeitplan-Optionen erscheinen.
		</div>
	{:else}
		{#if context === 'vergleich'}
			<div class="vt-vergleich-intro">
				Wie beim Trip: das <strong>Morgen-Briefing</strong> zeigt den heutigen Tag, das
				<strong>Abend-Briefing</strong> den morgigen. Du wählst nur die Uhrzeit.
			</div>
		{/if}
		<div class="vt-schedule-grid">
			<Card padding={18}>
				<div class="vt-card-head">
					<div>
						<div class="vt-card-title">Morgen-Briefing</div>
						<div class="vt-card-sub">Gleicher Tag — alles für die heutige Etappe</div>
					</div>
					<span data-testid="morning-master-switch">
						<Checkbox checked={morning_enabled} onchange={onMorningToggle}>Aktiv</Checkbox>
					</span>
				</div>
				<div class="vt-card-body">
					<label class="vt-time-label">
						<span class="vt-time-caption">Uhrzeit</span>
						<input
							type="time"
							data-testid="report-morning-time"
							class="vt-time-input"
							step={3600}
							value={morning_time}
							disabled={!morning_enabled}
							onchange={onMorningTime}
						/>
					</label>
					<div class="vt-quickpick-row">
						<button
							type="button"
							data-testid="report-morning-quickpick-07"
							class="vt-quick-chip"
							disabled={!morning_enabled}
							onclick={makeQuickPickHandler(onMorningTime, '07:00')}
						>
							Morgens 07:00
						</button>
						<button
							type="button"
							data-testid="report-morning-quickpick-18"
							class="vt-quick-chip"
							disabled={!morning_enabled}
							onclick={makeQuickPickHandler(onMorningTime, '18:00')}
						>
							Abends 18:00
						</button>
					</div>
				</div>
			</Card>

			<Card padding={18}>
				<div class="vt-card-head">
					<div>
						<div class="vt-card-title">Abend-Briefing</div>
						<div class="vt-card-sub">Nächster Tag — Ausblick auf morgen</div>
					</div>
					<span data-testid="evening-master-switch">
						<Checkbox checked={evening_enabled} onchange={onEveningToggle}>Aktiv</Checkbox>
					</span>
				</div>
				<div class="vt-card-body">
					<label class="vt-time-label">
						<span class="vt-time-caption">Uhrzeit</span>
						<input
							type="time"
							data-testid="report-evening-time"
							class="vt-time-input"
							step={3600}
							value={evening_time}
							disabled={!evening_enabled}
							onchange={onEveningTime}
						/>
					</label>
					<div class="vt-quickpick-row">
						<button
							type="button"
							data-testid="report-evening-quickpick-07"
							class="vt-quick-chip"
							disabled={!evening_enabled}
							onclick={makeQuickPickHandler(onEveningTime, '07:00')}
						>
							Morgens 07:00
						</button>
						<button
							type="button"
							data-testid="report-evening-quickpick-18"
							class="vt-quick-chip"
							disabled={!evening_enabled}
							onclick={makeQuickPickHandler(onEveningTime, '18:00')}
						>
							Abends 18:00
						</button>
					</div>
				</div>
			</Card>

			{#if isRoute}
				<Card padding={18}>
					<div class="vt-card-head">
						<div>
							<div class="vt-card-title">Mehrtages-Trend</div>
							<div class="vt-card-sub">Sonntags · 3–7-Tage-Ausblick (optional)</div>
						</div>
					</div>
					<div class="vt-card-body vt-trend-body">
						<span data-testid="report-morning-trend">
							<Checkbox checked={multi_day_trend_morning} disabled={!morning_enabled} onchange={onTrendMorningToggle}
								>im Morgen-Briefing</Checkbox
							>
						</span>
						<span data-testid="report-evening-trend">
							<Checkbox checked={multi_day_trend_evening} disabled={!evening_enabled} onchange={onTrendEveningToggle}
								>im Abend-Briefing</Checkbox
							>
						</span>
					</div>
				</Card>
			{/if}
		</div>
	{/if}
</div>

<style>
	.vt-empty-box {
		padding: 16px 18px;
		background: rgba(192, 138, 26, 0.07);
		border: 1px solid var(--g-warn, #c08a1a);
		border-radius: var(--g-r-2, 8px);
		font-size: 13px;
		color: var(--g-ink-2);
		line-height: 1.55;
	}
	.vt-empty-strong {
		color: #8a6210;
	}
	.vt-vergleich-intro {
		font-size: 12.5px;
		color: var(--g-ink-3);
		line-height: 1.5;
		margin: 0 0 12px;
		max-width: 620px;
	}
	.vt-vergleich-intro strong {
		color: var(--g-ink-2);
	}
	.vt-schedule-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: 16px;
	}
	.vt-card-head {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 12px;
	}
	.vt-card-title {
		font-size: 15px;
		font-weight: 600;
	}
	.vt-card-sub {
		font-size: 12.5px;
		color: var(--g-ink-3);
		margin-top: 2px;
	}
	.vt-card-body {
		margin-top: 14px;
		padding-top: 12px;
		border-top: 1px solid var(--g-rule-soft, #e2ddd2);
	}
	.vt-trend-body {
		display: flex;
		flex-direction: column;
		gap: 8px;
	}
	.vt-time-label {
		display: inline-flex;
		align-items: center;
		gap: 7px;
	}
	.vt-time-caption {
		font-family: var(--g-font-mono);
		font-size: 9.5px;
		color: var(--g-ink-4);
		letter-spacing: 0.08em;
		text-transform: uppercase;
	}
	.vt-time-input {
		font-family: var(--g-font-mono);
		font-size: 13px;
		font-weight: 600;
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-1, 4px);
		padding: 5px 8px;
		background: var(--g-card);
		color: var(--g-ink);
	}
	.vt-time-input:disabled {
		color: var(--g-ink-4);
		background: var(--g-paper-deep, #efece3);
		cursor: not-allowed;
	}
	.vt-quickpick-row {
		display: flex;
		gap: 6px;
		margin-top: 10px;
	}
	.vt-quick-chip {
		border: 1px solid var(--g-rule-soft, #e2ddd2);
		border-radius: 999px;
		font-family: var(--g-font-mono);
		font-size: 11px;
		color: var(--g-ink-3);
		padding: 3px 9px;
		background: transparent;
		cursor: pointer;
	}
	.vt-quick-chip:hover:not(:disabled) {
		background: var(--g-paper-deep, #efece3);
		color: var(--g-ink);
	}
	.vt-quick-chip:disabled {
		color: var(--g-ink-4);
		cursor: not-allowed;
		opacity: 0.6;
	}

	@media (max-width: 899px) {
		.vt-schedule-grid {
			grid-template-columns: 1fr;
		}
		.vt-time-input {
			min-height: 44px;
			font-size: 16px;
			width: 100%;
			box-sizing: border-box;
		}
		.vt-quick-chip {
			min-height: 36px;
			font-size: 12px;
		}
	}
</style>
