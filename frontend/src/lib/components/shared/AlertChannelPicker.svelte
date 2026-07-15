<script lang="ts">
	// AlertChannelPicker — Issue #1258 Scheibe S2: geteilter Kanal-Picker fuer
	// die Alarm-Zustellung (Telegram/SMS/E-Mail), getrennt vom Briefing-Kanal-
	// Picker (VTBriefingChannels). Fuer die Kanal-Zeile existiert im Svelte-Code
	// kein Pendant (Design-Molecule ChannelRow ist reines JSX) — daher hier neu
	// nach Design gebaut, unter Wiederverwendung der bestehenden Atome
	// Switch/Card/Eyebrow.
	//
	// Design: claude-code-handoff/current/jsx/corridor-editor.jsx:469-489,
	//   ChannelRow-Molecule molecules.jsx:177-230 (dense-Layout).
	// Spec: docs/specs/modules/issue_1258_alarme_tab_official_warnings.md (AC-11)
	//
	// Ungewired in dieser Scheibe — keine Flaeche bindet diese Komponente ein.

	import { Eyebrow, Card, Switch } from '$lib/components/atoms';
	import {
		ALERT_CHANNEL_ORDER,
		NO_CHANNEL_WARNING,
		channelWarningNeeded,
		type AlertChannelState
	} from './alarme-tab/alertChannelState.ts';

	type ChannelKind = (typeof ALERT_CHANNEL_ORDER)[number];

	interface Props {
		channels: AlertChannelState;
		onToggle: (kind: ChannelKind) => void;
		targets?: Partial<Record<ChannelKind, string>>;
		dense?: boolean;
	}
	let { channels, onToggle, targets, dense = false }: Props = $props();

	const CHANNEL_LABELS: Record<ChannelKind, string> = {
		telegram: 'Telegram',
		sms: 'SMS',
		email: 'Email'
	};
	const CHANNEL_SUB: Record<ChannelKind, string> = {
		telegram: 'sofortiger Push',
		sms: 'sofort · ≤ 140 Z.',
		email: 'optional · langsamer als Push'
	};

	const activeCount = $derived(ALERT_CHANNEL_ORDER.filter((k) => channels[k]).length);
	const warningNeeded = $derived(channelWarningNeeded(channels));

	// Factory-Pattern (Safari-Closure-Schutz, CLAUDE.md) — jede Zeile bekommt
	// ihren eigenen Handler statt einer gemeinsamen Closure ueber die Loop-Variable.
	function makeToggleHandler(kind: ChannelKind) {
		return function doToggle() {
			onToggle(kind);
		};
	}
</script>

<div data-testid="alert-channel-picker">
	<div class="acp-head">
		<Eyebrow style="margin: 0;">Alert-Kanäle</Eyebrow>
		<span
			class="mono acp-counter"
			class:warn={warningNeeded}
			data-testid="alert-channel-picker-warning"
		>
			{warningNeeded ? NO_CHANNEL_WARNING : `${activeCount} aktiv`}
		</span>
	</div>
	<p class="acp-lead">
		Alerts sind kurze Sofort-Meldungen — <strong>Telegram/SMS</strong> sind dafür ideal. Das geplante
		Briefing (die Tabelle) läuft davon getrennt weiter über seine eigenen Kanäle.
	</p>
	<Card padding={0}>
		<div class="acp-rows" style:padding={dense ? '2px 14px' : '4px 18px'}>
			{#each ALERT_CHANNEL_ORDER as kind, i (kind)}
				<div
					class="acp-row"
					class:last={i === ALERT_CHANNEL_ORDER.length - 1}
					data-testid="alert-channel-row-{kind}"
				>
					<span class="mono acp-kind">{CHANNEL_LABELS[kind]}</span>
					<div class="acp-target">
						<div class="mono acp-target-value">{targets?.[kind] ?? '—'}</div>
						<div class="acp-sub">{CHANNEL_SUB[kind]}</div>
					</div>
					<div data-testid="alert-channel-toggle-{kind}">
						<Switch
							checked={channels[kind]}
							onchange={makeToggleHandler(kind)}
							tone="good"
							size={dense ? 'lg' : 'md'}
							aria-label="{CHANNEL_LABELS[kind]} umschalten"
						/>
					</div>
				</div>
			{/each}
		</div>
	</Card>
</div>

<style>
	.acp-head {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 12px;
		margin-bottom: 6px;
	}
	.acp-counter {
		font-size: 10px;
		color: var(--g-ink-3);
		letter-spacing: 0.03em;
	}
	.acp-counter.warn {
		color: var(--g-warning, var(--g-warn));
	}
	.acp-lead {
		font-size: 12.5px;
		color: var(--g-ink-3);
		line-height: 1.5;
		margin: 0 0 10px;
	}
	.acp-rows {
		display: flex;
		flex-direction: column;
	}
	.acp-row {
		display: flex;
		align-items: center;
		gap: 12px;
		padding: 10px 0;
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.acp-row.last {
		border-bottom: none;
	}
	.acp-kind {
		font-size: 10px;
		width: 60px;
		flex-shrink: 0;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--g-ink-3);
	}
	.acp-target {
		flex: 1;
		min-width: 0;
	}
	.acp-target-value {
		font-size: 12px;
		color: var(--g-ink);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}
	.acp-sub {
		font-size: 10px;
		color: var(--g-ink-4);
		margin-top: 2px;
	}
</style>
