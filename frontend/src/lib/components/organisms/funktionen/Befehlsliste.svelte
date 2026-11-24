<script lang="ts">
	// Issue #3320 (AC-10) — Befehlsliste der Funktionsseite `befehle` aus DERSELBEN
	// Quelle wie die Hilfeseite /hilfe: hilfe.befehle.<wort>.befehl/.text im
	// Katalog (Drift-Schutz gegen command_rows(): tests/test_hilfe_befehle_drift.py).
	// Keine eigene Kopie der Befehle.
	import { t, type MessageKey } from '$lib/i18n';
	import { de } from '$lib/i18n/messages/de/index';

	// i18n-dynamic: hilfe.befehle.
	const befehle = $derived(
		Object.keys(de)
			.filter((k) => /^hilfe\.befehle\.[^.]+\.befehl$/.test(k))
			.map((k) => ({
				befehl: $t(k as MessageKey),
				text: $t(k.replace(/\.befehl$/, '.text') as MessageKey)
			}))
	);
</script>

<div class="rahmen">
	<table data-testid="befehlsliste">
		<thead>
			<tr>
				<th scope="col">{$t('funktionen.befehle.spalte.befehl')}</th>
				<th scope="col">{$t('funktionen.befehle.spalte.wirkung')}</th>
			</tr>
		</thead>
		<tbody>
			{#each befehle as b (b.befehl)}
				<tr>
					<td><code>{b.befehl}</code></td>
					<td>{b.text}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.rahmen {
		max-width: 100%;
		overflow-x: auto;
		margin-top: var(--g-s-2);
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--g-text-md);
		color: var(--g-ink);
	}
	th,
	td {
		text-align: left;
		vertical-align: top;
		padding: var(--g-size-6px) var(--g-s-2) var(--g-size-6px) 0;
		border-bottom: 1px solid var(--g-rule);
		overflow-wrap: anywhere;
	}
	th {
		font-weight: 600;
	}
	code {
		font-family: var(--g-font-mono);
		font-size: var(--g-text-sm);
		color: var(--g-ink);
	}
</style>
