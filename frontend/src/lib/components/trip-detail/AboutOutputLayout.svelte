<script lang="ts">
	// Issue #364 — Erklär-Dialog "Wie kommt was wohin": Spalte/Detail/Aus +
	// Kanal-Tabelle (Email ∞ / Telegram 8 / SMS 0).
	// Design: docs/design/epic_331_output_layout/screen-metrics-editor.jsx
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Eyebrow } from '$lib/components/atoms';
	import { t, type MessageKey } from '$lib/i18n';

	interface Props {
		open: boolean;
		onClose: () => void;
	}
	let { open = $bindable(false), onClose }: Props = $props();

	// Gesamt-Spalten inkl. Uhrzeit (User-Sicht, deckt sich mit #360). Signal entfernt (#610).
	const channels: { label: string; max: string; behavior: MessageKey }[] = [
		{ label: 'Email', max: '∞', behavior: 'trip.about.email' },
		{ label: 'Telegram', max: '8', behavior: 'trip.about.telegram' },
		{ label: 'SMS', max: '0', behavior: 'trip.about.sms' },
	];
</script>

<Dialog.Root bind:open onOpenChange={(o) => { if (!o) onClose(); }}>
	<Dialog.Content data-testid="about-output-layout" class="about-dialog">
		<Dialog.Header>
			<Eyebrow>{$t('trip.about.eyebrow')}</Eyebrow>
			<Dialog.Title>{$t('trip.about.titel')}</Dialog.Title>
		</Dialog.Header>

		<div class="about-body">
			<p>{$t('trip.about.intro_vor')} <strong>{$t('trip.about.intro_stark')}</strong>{$t('trip.about.intro_nach')}</p>
			<ul>
				<li><strong>{$t('trip.about.spalte')}</strong> {$t('trip.about.spalte_text')}</li>
				<li><strong>{$t('trip.about.detail')}</strong> {$t('trip.about.detail_text')}</li>
				<li><strong>{$t('wertebereiche.reihenfolge.aus')}</strong> {$t('trip.about.aus_text')}</li>
			</ul>
			<p>{$t('trip.about.constraints')}</p>
			<table>
				<thead>
					<tr>
						<th>{$t('trip.about.kanal')}</th>
						<th>{$t('trip.about.max_spalten')}</th>
						<th>{$t('trip.about.verhalten')}</th>
					</tr>
				</thead>
				<tbody>
					{#each channels as c}
						<tr>
							<td class="ch">{c.label}</td>
							<td class="mono">{c.max}</td>
							<td>{$t(c.behavior)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
			<p class="note">
				{$t('trip.about.hinweis')}
			</p>
		</div>

		<Dialog.Footer>
			<button type="button" class="btn-primary" data-testid="about-close" onclick={() => { open = false; onClose(); }}>
				{$t('trip.about.verstanden')}
			</button>
		</Dialog.Footer>
	</Dialog.Content>
</Dialog.Root>

<style>
	.about-body {
		font-size: var(--g-text-sm);
		line-height: 1.6;
		color: var(--g-ink-muted);
		padding: var(--g-s-2) 0;
	}
	.about-body ul {
		padding-left: var(--g-s-4);
		margin: var(--g-s-3) 0;
	}
	.about-body table {
		width: 100%;
		border-collapse: collapse;
		margin: var(--g-s-3) 0;
		font-size: var(--g-text-sm);
	}
	.about-body thead tr {
		background: var(--g-surface-1);
		border-bottom: 1px solid var(--g-ink-faint);
	}
	.about-body th {
		text-align: left;
		padding: var(--g-s-2) var(--g-s-3);
		font-weight: 600;
		color: var(--g-ink);
	}
	.about-body td {
		padding: var(--g-s-2) var(--g-s-3);
		border-bottom: 1px solid var(--g-rule-soft);
	}
	.about-body td.ch {
		font-weight: 600;
		color: var(--g-ink);
	}
	.note {
		margin-top: var(--g-s-3);
		color: var(--g-ink-muted);
	}
	.btn-primary {
		padding: var(--g-s-2) var(--g-s-4);
		border-radius: var(--g-radius-sm);
		font-size: var(--g-text-sm);
		font-weight: 500;
		cursor: pointer;
		border: 1px solid transparent;
		background: var(--g-accent);
		color: var(--g-paper);
	}
</style>
