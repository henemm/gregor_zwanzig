<script lang="ts">
	// Issue #496 — Schicht 2 (SMS): Token-Stream + Mapping-Tabelle.
	// SMS ist KEIN Spalten-Kanal — der Renderer uebersetzt nur
	// entscheidungskritische Metriken in kompakte Tokens (sms_format.md v2.0).
	import type { MetricEntry } from './metricsEditor.ts';

	interface Props {
		primary: string[];
		secondary: string[];
		metricById: Record<string, MetricEntry>;
	}
	let { primary, secondary, metricById }: Props = $props();

	const SMS_TOK: Record<string, string> = {
		temperature: 'N8 D11',
		precipitation: 'R3.2',
		rain_probability: 'PR53%@12',
		wind: 'W12@11(24@13)',
		gust: 'G25@12(43@14)',
		thunder: 'TH5%@12',
	};
	const SMS_TOKEN_MEANING: Record<string, string> = {
		temperature: 'N/D = Nacht-Tief / Tag-Hoch °C',
		precipitation: 'R = Regen mm (R- = keiner)',
		rain_probability: 'PR = Regen-Wahrsch. %@Stunde',
		wind: 'W = Wind km/h@Std(Max@Std)',
		gust: 'G = Böen km/h@Std(Max@Std)',
		thunder: 'TH = Gewitter %@Stunde',
	};
	const SMS_PREFIX = 'KHW03:';
	const SMS_TAIL = 'Z:WATCH:2447';
	const SMS_MAX = 140;

	function smsRender(prim: string[], sec: string[]) {
		const order = [...prim, ...sec];
		const carried: string[] = [];
		const noCode: string[] = [];
		const overflow: string[] = [];
		let tokens: string[] = [];
		const lenWith = (toks: string[]) =>
			`${SMS_PREFIX} ${[...toks, SMS_TAIL].join(' ')}`.length;
		for (const id of order) {
			const tok = SMS_TOK[id];
			if (!tok) { noCode.push(id); continue; }
			if (lenWith([...tokens, tok]) > SMS_MAX) { overflow.push(id); continue; }
			tokens.push(tok);
			carried.push(id);
		}
		const line = `${SMS_PREFIX} ${[...tokens, SMS_TAIL].join(' ')}`;
		return { line, carried, noCode, overflow, len: line.length };
	}

	function labelOf(id: string): string {
		return metricById[id]?.label ?? id;
	}

	const render = $derived(smsRender(primary, secondary));
	const dropped = $derived([...render.noCode, ...render.overflow]);
	const overLimit = $derived(render.len > SMS_MAX);
</script>

<div class="fidelity" data-testid="channel-fidelity-sms">
	<div class="chat">
		<div class="bubble">
			<pre class="mono line">{render.line}</pre>
		</div>
	</div>

	<div class="counter mono" class:over={overLimit}>
		{render.len}/{SMS_MAX} Zeichen · gesendet 06:00
	</div>

	<div class="grid">
		<div class="col">
			<div class="col-head mono ok">✓ {render.carried.length} mit SMS-Code</div>
			{#if render.carried.length === 0}
				<div class="empty mono">— keine —</div>
			{:else}
				{#each render.carried as id}
					<div class="row">
						<span class="row-label">{labelOf(id)}</span>
						<span class="row-token mono">{SMS_TOK[id]}</span>
					</div>
				{/each}
			{/if}
		</div>
		<div class="col">
			<div class="col-head mono warn">✕ {dropped.length} fallen weg</div>
			{#if dropped.length === 0}
				<div class="empty mono">— keine —</div>
			{:else}
				{#each dropped as id}
					<div class="row">
						<span class="row-label">{labelOf(id)}</span>
						<span class="row-token mono muted">
							{render.noCode.includes(id) ? 'kein Code' : 'Zeichenlimit'}
						</span>
					</div>
				{/each}
			{/if}
		</div>
	</div>

	<div class="banner">
		SMS ist <strong>kein Spalten-Kanal</strong>: der Renderer uebersetzt nur
		entscheidungskritische Metriken in kompakte Tokens. Alles, was keinen Code
		hat oder die 140-Zeichen-Grenze sprengt, faellt heraus.
	</div>

	<div class="legend mono">
		{#each render.carried as id}
			<div>{SMS_TOKEN_MEANING[id]}</div>
		{/each}
		<div>Z = Ziel-Risiko:Höhe · '-' = kein Wert</div>
	</div>
</div>

<style>
	.fidelity {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
	}
	.chat {
		background: #e9e6dc;
		border-radius: var(--g-r-3, 16px);
		padding: var(--g-s-4);
	}
	.bubble {
		background: #e5e5ea;
		border-radius: 14px;
		padding: var(--g-s-3);
		max-width: 320px;
	}
	.line {
		margin: 0;
		font-size: var(--g-text-xs);
		line-height: 1.5;
		word-break: break-all;
		white-space: pre-wrap;
		color: var(--g-ink);
	}
	.counter {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
	}
	.counter.over {
		color: var(--g-danger, #c83e3e);
		font-weight: 600;
	}
	.grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--g-s-3);
	}
	@media (max-width: 600px) {
		.grid { grid-template-columns: 1fr; }
	}
	.col {
		display: flex;
		flex-direction: column;
		gap: 4px;
	}
	.col-head {
		font-size: var(--g-text-xs);
		font-weight: 700;
		letter-spacing: var(--g-track-wide);
		padding-bottom: 4px;
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.col-head.ok {
		color: var(--g-success, #2f7d4f);
	}
	.col-head.warn {
		color: var(--g-warning);
	}
	.row {
		display: flex;
		justify-content: space-between;
		gap: var(--g-s-2);
		font-size: var(--g-text-xs);
		padding: 2px 0;
	}
	.row-label {
		color: var(--g-ink);
	}
	.row-token {
		color: var(--g-ink-muted);
	}
	.row-token.muted {
		font-style: italic;
		font-size: 10px;
	}
	.empty {
		font-size: var(--g-text-xs);
		color: var(--g-ink-muted);
		font-style: italic;
		padding: 2px 0;
	}
	.banner {
		padding: var(--g-s-2) var(--g-s-3);
		border-radius: var(--g-radius-sm);
		font-size: var(--g-text-xs);
		line-height: 1.5;
		background: color-mix(in srgb, var(--g-warning) 8%, transparent);
		border-left: 3px solid var(--g-warning);
		color: var(--g-ink);
	}
	.legend {
		font-size: 10px;
		line-height: 1.6;
		color: var(--g-ink-muted);
		display: flex;
		flex-direction: column;
		gap: 2px;
	}
</style>
