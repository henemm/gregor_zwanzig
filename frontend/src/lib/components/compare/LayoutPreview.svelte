<script lang="ts">
	// Issue #681 — Compare-Editor Slice 4: Kanal-spezifische Layout-Vorschau.
	// Reine UI-Komponente, keine API-Calls, statische Dummy-Daten.

	type ChannelId = 'email' | 'telegram' | 'sms';

	interface Props {
		channel: ChannelId;
		pickedIds: string[];
	}

	let { channel, pickedIds }: Props = $props();

	const DUMMY_LOCATIONS = [
		{ id: 'loc-01', name: 'Hintertux', score: 87, snow: 180, newSnow: 22, wind: 18, gust: 31, dir: 'NW', feels: -3, sun: 4.5 },
		{ id: 'loc-07', name: 'Ischgl',    score: 74, snow: 140, newSnow: 12, wind: 24, gust: 40, dir: 'W',  feels: -5, sun: 2.1 },
		{ id: 'loc-08', name: 'Zermatt',   score: 71, snow: 210, newSnow:  8, wind: 31, gust: 55, dir: 'SW', feels: -7, sun: 5.8 },
	];

	const rows = $derived(
		pickedIds.length > 0
			? DUMMY_LOCATIONS.filter(d => pickedIds.includes(d.id)).slice(0, 5)
			: DUMMY_LOCATIONS
	);

	const cols = $derived(
		channel === 'email'
			? ['Score', 'Schnee', 'Neuschnee', 'Wind/Böen', 'Temp', 'Sonne']
			: ['Score', 'Schnee', 'Neuschnee', 'Wind', 'Temp']
	);

	function signedTemp(t: number): string {
		return t > 0 ? `+${t}°` : `${t}°`;
	}
</script>

<div data-testid="compare-step4-layout-preview" class="layout-preview">
	{#if channel === 'sms'}
		<!-- SMS-Branch: Monospace-Fließtext -->
		<div class="preview-inner">
			<div
				data-testid="compare-step4-preview-sms"
				class="sms-block mono"
			>
				<strong>MO 09.06 · Ortsvergleich</strong><br/>
				#1 {rows[0].name.slice(0, 22)} · {rows[0].score}p<br/>
				Schnee {rows[0].snow}cm +{rows[0].newSnow} · {signedTemp(rows[0].feels)} · {rows[0].wind}/{rows[0].gust}{rows[0].dir}
			</div>
			<div class="mono hint-text">SMS hat keine Tabelle — Fließtext.</div>
		</div>
	{:else}
		<!-- Email/Telegram-Branch: Empfehlung-Banner + Tabelle -->
		<div class="preview-inner table-branch">
			<!-- Empfehlung-Banner -->
			<div class="recommendation-banner">
				<div class="mono eyebrow-text">Empfehlung · Mo 09.06.</div>
				<div class="winner-name">{rows[0].name}</div>
				<div class="winner-reason">
					<span class="weil-label">weil</span>{rows[0].snow} cm Schnee · +{rows[0].newSnow} cm neu · {rows[0].wind} km/h Wind · gef. {signedTemp(rows[0].feels)}C
				</div>
			</div>

			<!-- Tabelle -->
			<div class="table-wrap">
				<table>
					<thead>
						<tr>
							<th class="th-ort">Ort</th>
							{#each cols as c (c)}
								<th>{c}</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each rows as r, i (r.id)}
							<tr class:top-row={i === 0}>
								<td class="td-ort">
									<span class="rank-badge mono" class:rank-top={i === 0}>#{i + 1}</span>
									{r.name}
								</td>
								{#if cols.includes('Score')}
									<td class="td-num" class:td-bold={i === 0}>{r.score}</td>
								{/if}
								{#if cols.includes('Schnee')}
									<td class="td-num">{r.snow}cm</td>
								{/if}
								{#if cols.includes('Neuschnee')}
									<td class="td-num">+{r.newSnow}</td>
								{/if}
								{#if cols.includes('Wind/Böen')}
									<td class="td-num">{r.wind}/{r.gust} {r.dir}</td>
								{/if}
								{#if cols.includes('Wind')}
									<td class="td-num">{r.wind} {r.dir}</td>
								{/if}
								{#if cols.includes('Temp')}
									<td class="td-num">{signedTemp(r.feels)}</td>
								{/if}
								{#if cols.includes('Sonne')}
									<td class="td-num">~{r.sun}h</td>
								{/if}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>

			<!-- Footer -->
			<div class="mono table-footer">
				{channel === 'email' ? 'Email · alle Spalten + Detail-Block je Ort' : `Telegram · ${cols.length} Spalten`}
			</div>
		</div>
	{/if}
</div>

<style>
	.layout-preview {
		background: var(--g-card);
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		overflow: hidden;
	}

	.preview-inner {
		display: flex;
		flex-direction: column;
	}

	/* SMS */
	.sms-block {
		padding: 12px 14px;
		background: var(--g-paper-deep, #ede9e0);
		border-radius: var(--g-r-2);
		font-size: 12.5px;
		line-height: 1.55;
		color: var(--g-ink);
		margin: 14px;
	}

	.hint-text {
		font-size: 10px;
		color: var(--g-ink-4);
		padding: 0 14px 14px;
	}

	/* Email/Telegram */
	.table-branch {
		overflow: hidden;
	}

	.recommendation-banner {
		padding: 14px 16px;
		background: linear-gradient(135deg, rgba(61,107,58,0.10), rgba(61,107,58,0.02));
		border-bottom: 1px solid rgba(61,107,58,0.20);
		border-left: 3px solid var(--g-good);
	}

	.eyebrow-text {
		font-size: 9.5px;
		color: var(--g-good);
		letter-spacing: 0.10em;
		text-transform: uppercase;
		font-weight: 600;
		margin-bottom: 4px;
	}

	.winner-name {
		font-size: 16px;
		font-weight: 600;
		color: var(--g-ink);
	}

	.winner-reason {
		font-size: 12px;
		color: var(--g-ink-2);
		margin-top: 4px;
		line-height: 1.5;
	}

	.weil-label {
		color: var(--g-good);
		font-weight: 600;
		margin-right: 4px;
	}

	.table-wrap {
		overflow-x: auto;
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-family: var(--g-font-mono);
		font-variant-numeric: tabular-nums;
	}

	th {
		padding: 8px 8px;
		text-align: center;
		font-size: 9.5px;
		color: var(--g-ink-4);
		letter-spacing: 0.08em;
		text-transform: uppercase;
		font-weight: 600;
		border-bottom: 1px solid var(--g-rule-soft);
	}

	th.th-ort {
		text-align: left;
		padding-left: 10px;
	}

	.top-row {
		background: rgba(61,107,58,0.04);
	}

	td {
		padding: 8px;
		font-size: 11.5px;
		color: var(--g-ink);
		border-bottom: 1px solid var(--g-rule-soft);
	}

	.td-ort {
		padding-left: 10px;
		font-family: var(--g-font-sans);
		font-weight: 500;
		font-size: 12px;
	}

	.td-num {
		text-align: center;
	}

	.td-bold {
		font-weight: 600;
	}

	.rank-badge {
		display: inline-block;
		width: 18px;
		height: 14px;
		line-height: 14px;
		text-align: center;
		border-radius: 2px;
		background: var(--g-ink);
		color: #fff;
		font-size: 9px;
		font-weight: 600;
		margin-right: 6px;
	}

	.rank-top {
		background: var(--g-good);
	}

	.table-footer {
		padding: 8px 14px;
		background: var(--g-paper-deep, #ede9e0);
		font-size: 10px;
		color: var(--g-ink-4);
		letter-spacing: 0.04em;
	}
</style>
