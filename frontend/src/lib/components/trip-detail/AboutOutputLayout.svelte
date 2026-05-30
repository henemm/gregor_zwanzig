<script lang="ts">
	// Issue #364 — Erklär-Dialog "Wie kommt was wohin": Spalte/Detail/Aus +
	// Kanal-Tabelle (Email ∞ / Telegram 8 / Signal 6 / SMS 0).
	// Design: docs/design/epic_331_output_layout/screen-metrics-editor.jsx
	import * as Dialog from '$lib/components/ui/dialog/index.js';
	import { Eyebrow } from '$lib/components/atoms';

	interface Props {
		open: boolean;
		onClose: () => void;
	}
	let { open = $bindable(false), onClose }: Props = $props();

	// Gesamt-Spalten inkl. Uhrzeit (User-Sicht, deckt sich mit #360).
	const channels = [
		{ label: 'Email', max: '∞', behavior: 'Alles als Spalten + Detail-Zeile darunter' },
		{ label: 'Telegram', max: '8', behavior: 'Erste 8 als Spalten, Rest wandert in Detail' },
		{ label: 'Signal', max: '6', behavior: 'Erste 6 als Spalten, Rest in Detail' },
		{ label: 'SMS', max: '0', behavior: 'Keine Tabelle, alles in flacher Zeile bis 140 Zeichen' },
	];
</script>

<Dialog.Root bind:open onOpenChange={(o) => { if (!o) onClose(); }}>
	<Dialog.Content data-testid="about-output-layout" class="about-dialog">
		<Dialog.Header>
			<Eyebrow>Output-Layout-System</Eyebrow>
			<Dialog.Title>Wie kommt was wohin</Dialog.Title>
		</Dialog.Header>

		<div class="about-body">
			<p>Du verwaltest die Metriken eines Trips an <strong>einer Stelle</strong>. Pro Metrik entscheidest du:</p>
			<ul>
				<li><strong>Spalte</strong> — eigene Tabellen-Spalte im Briefing</li>
				<li><strong>Detail</strong> — kompakter Zusatz-Wert in einer Zeile unter der Tabelle</li>
				<li><strong>Aus</strong> — wird für diesen Trip nicht ausgegeben</li>
			</ul>
			<p>Jeder Kanal hat eigene Constraints. Der Renderer wendet sie automatisch an:</p>
			<table>
				<thead>
					<tr>
						<th>Kanal</th>
						<th>Max Spalten</th>
						<th>Verhalten</th>
					</tr>
				</thead>
				<tbody>
					{#each channels as c}
						<tr>
							<td class="ch">{c.label}</td>
							<td class="mono">{c.max}</td>
							<td>{c.behavior}</td>
						</tr>
					{/each}
				</tbody>
			</table>
			<p class="note">
				Pro-Kanal-Overrides sind in einer späteren Version möglich — Default ist eine
				Konfiguration für alle Kanäle, die der Renderer kanalspezifisch anpasst.
			</p>
		</div>

		<Dialog.Footer>
			<button type="button" class="btn-primary" data-testid="about-close" onclick={() => { open = false; onClose(); }}>
				Verstanden
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
