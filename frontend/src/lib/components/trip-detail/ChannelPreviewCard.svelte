<script lang="ts">
	// Issue #365 — eine Kanal-Karte in der 4-Kanal-Live-Vorschau. Zeigt Label +
	// Spalten-Zähler, Mono-Mini-Tabelle (Kürzel-Header + 1 repräsentative Zeile),
	// ·-Detail-Zeile und Warn-Badge bei Überlauf. SMS = flache Textzeile.
	// Werte sind repräsentativ (Layout-Vorschau), nicht die Live-Wetterdaten.
	// Design: docs/design/epic_331_output_layout/screen-metrics-editor.jsx (Z. 582-650)
	import { applyChannel, type MetricEntry } from './metricsEditor.ts';

	interface Props {
		label: string;
		channelId: 'email' | 'telegram' | 'signal' | 'sms';
		budget: number;
		hint: string;
		primary: string[];
		secondary: string[];
		metricById: Record<string, MetricEntry>;
		shortById: Record<string, string>;
		sampleById: Record<string, string>;
	}
	let {
		label, channelId, budget, hint, primary, secondary,
		metricById, shortById, sampleById,
	}: Props = $props();

	const layout = $derived(applyChannel(primary, secondary, budget));
	const isSMS = $derived(channelId === 'sms');

	function shortOf(id: string): string {
		return shortById[id] ?? metricById[id]?.label.slice(0, 5) ?? id.slice(0, 5);
	}
	function sampleOf(id: string): string {
		return sampleById[id] ?? '—';
	}
	function labelOf(id: string): string {
		return metricById[id]?.label ?? id;
	}

	const counterText = $derived(
		isSMS ? 'flach' : `${layout.inTable.length}/${budget === Infinity ? '∞' : budget} Spalten`,
	);
	// Mono-Mini-Tabelle: Kürzel-Header + eine repräsentative Werte-Zeile.
	const headerLine = $derived(
		layout.inTable.map((id) => shortOf(id).slice(0, 5).padEnd(6, ' ')).join(''),
	);
	const valueLine = $derived(
		layout.inTable.map((id) => sampleOf(id).padEnd(6, ' ')).join(''),
	);
	const smsLine = $derived(
		[...primary, ...secondary].slice(0, 8).map((id) => `${shortOf(id)} ${sampleOf(id)}`).join(' · '),
	);
	const smsTruncated = $derived(primary.length + secondary.length > 8);
</script>

<div class="card" data-testid="channel-preview-card-{channelId}">
	<div class="card-head">
		<div class="head-row">
			<div class="ch-label">{label}</div>
			<span
				class="counter mono"
				class:warn={layout.demoted > 0}
				data-testid="channel-counter-{channelId}"
			>{counterText}</span>
		</div>
		<div class="hint mono">{hint}</div>
	</div>

	<div class="card-body">
		{#if !isSMS && layout.inTable.length > 0}
			<div class="mini-table mono" data-testid="channel-table-{channelId}">{headerLine}{'\n'}{valueLine}</div>
		{/if}

		{#if !isSMS && layout.detail.length > 0}
			<div class="detail">
				<span class="detail-eyebrow mono">Detail:</span>
				{layout.detail.map((id) => `${labelOf(id)} ${sampleOf(id)}`).join(' · ')}
			</div>
		{/if}

		{#if isSMS}
			<div class="sms-line" data-testid="channel-sms-{channelId}">
				{smsLine}{#if smsTruncated}<span class="ellipsis"> …</span>{/if}
			</div>
		{/if}

		{#if layout.demoted > 0}
			<div class="demote-badge" data-testid="channel-demote-{channelId}">
				⚠ {layout.demoted} {layout.demoted === 1 ? 'Spalte' : 'Spalten'} verschoben in Detail
			</div>
		{/if}
	</div>
</div>

<style>
	.card {
		background: var(--g-surface-0);
		border: 1px solid var(--g-ink-faint);
		border-radius: var(--g-radius-sm);
		overflow: hidden;
		display: flex;
		flex-direction: column;
	}
	.card-head {
		padding: var(--g-s-2) var(--g-s-3);
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.head-row {
		/* Vertikal gestapelt: Label (Zeile 1) + Zähler-Badge (Zeile 2) konkurrieren
		   NICHT um die Breite → beide vollständig, auch "Telegram" im 4er-Grid. */
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: var(--g-s-1);
	}
	.ch-label {
		font-size: var(--g-text-sm);
		font-weight: 600;
		color: var(--g-ink);
		/* Voller Kanalname, kein Truncate. */
		white-space: nowrap;
	}
	.counter {
		padding: 2px 6px;
		font-size: 10px;
		border-radius: var(--g-radius-pill);
		background: var(--g-surface-1);
		color: var(--g-ink-muted);
		font-weight: 600;
		/* Badge nur so breit wie sein Inhalt; "X/Y Spalten" stets vollständig. */
		align-self: flex-start;
		white-space: nowrap;
		flex-shrink: 0;
	}
	.counter.warn {
		background: color-mix(in srgb, var(--g-warning) 15%, transparent);
		color: var(--g-warning);
	}
	.hint {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		margin-top: var(--g-s-1);
		letter-spacing: var(--g-track-wide);
	}
	.card-body {
		padding: var(--g-s-3);
		flex: 1;
		font-size: var(--g-text-xs);
		display: flex;
		flex-direction: column;
	}
	.mini-table {
		background: var(--g-paper-deep);
		border-radius: var(--g-radius-xs);
		padding: var(--g-s-1) var(--g-s-2);
		font-size: 10px;
		line-height: 1.5;
		overflow-x: auto;
		white-space: pre;
		color: var(--g-ink);
	}
	.detail {
		margin-top: var(--g-s-2);
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		line-height: 1.5;
		font-style: italic;
		/* Detail-Bereich nimmt den Rest-Platz, damit alle 4 Karten gleich hoch
		   wirken; lange Detail-Zeilen (Email) werden auf 5 Zeilen geclamped. */
		flex: 1;
		display: -webkit-box;
		-webkit-box-orient: vertical;
		-webkit-line-clamp: 5;
		line-clamp: 5;
		overflow: hidden;
	}
	.sms-line {
		flex: 1;
	}
	.detail-eyebrow {
		font-size: 9px;
		color: var(--g-ink-muted);
		letter-spacing: var(--g-track-caps);
		text-transform: uppercase;
		margin-right: var(--g-s-1);
	}
	.sms-line {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		line-height: 1.5;
	}
	.ellipsis {
		color: var(--g-ink-muted);
	}
	.demote-badge {
		/* mt:auto schiebt den Warn-Hinweis unten bündig → Karten gleich hoch. */
		margin-top: auto;
		padding: var(--g-s-1) var(--g-s-2);
		background: color-mix(in srgb, var(--g-warning) 8%, transparent);
		border-left: 2px solid var(--g-warning);
		font-size: var(--g-text-xs);
		color: var(--g-warning);
		font-weight: 600;
	}
</style>
