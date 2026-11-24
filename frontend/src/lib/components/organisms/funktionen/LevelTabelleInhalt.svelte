<script lang="ts">
	// Issue #3319 (AC-2/AC-6) — EINE Level-Tabelle fuer Startseite (Kurzform)
	// und Funktionsuebersicht /funktionen (voll). Zahlen ausschliesslich aus
	// `level_grenzen.json` (ueber $lib/levelGrenzen), Texte aus dem Katalog.
	import { t, type MessageKey } from '$lib/i18n';
	import {
		FELDER_KURZ,
		FELDER_VOLL,
		LEVEL_NAMEN,
		levelWert,
		type LevelFeld,
		type LevelName
	} from '$lib/levelGrenzen';

	let { umfang = 'voll' }: { umfang?: 'kurz' | 'voll' } = $props();

	const NAME: Record<LevelName, MessageKey> = {
		free: 'level.name.free',
		standard: 'level.name.standard',
		premium: 'level.name.premium'
	};

	const ZEILE: Record<LevelFeld, MessageKey> = {
		trips: 'level.zeile.trips',
		ortsvergleiche: 'level.zeile.ortsvergleiche',
		orte: 'level.zeile.orte',
		email: 'level.zeile.email',
		telegram: 'level.zeile.telegram',
		sms_pro_tag: 'level.zeile.sms_pro_tag',
		premium_sms_pro_tag: 'level.zeile.premium_sms_pro_tag',
		premium_sms_antworten_pro_tag: 'level.zeile.premium_sms_antworten_pro_tag',
		alarme_pro_tag: 'level.zeile.alarme_pro_tag'
	};

	const felder = $derived(umfang === 'kurz' ? FELDER_KURZ : FELDER_VOLL);

	function zelle(level: LevelName, feld: LevelFeld): string {
		const w = levelWert(level, feld);
		if (w === null) return $t('level.wert.unbegrenzt');
		if (w === true) return $t('level.wert.enthalten');
		if (w === false) return $t('level.wert.nicht_enthalten');
		return String(w);
	}
</script>

<div class="rahmen">
	<table data-testid="level-tabelle">
		<caption>{$t('level.tabelle.beschriftung')}</caption>
		<thead>
			<tr>
				<th scope="col">{$t('level.spalte.funktion')}</th>
				{#each LEVEL_NAMEN as l (l)}
					<th scope="col">{$t(NAME[l])}</th>
				{/each}
			</tr>
		</thead>
		<tbody>
			{#each felder as f (f)}
				<tr data-feld={f}>
					<th scope="row">{$t(ZEILE[f])}</th>
					{#each LEVEL_NAMEN as l (l)}
						<td>{zelle(l, f)}</td>
					{/each}
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	/* 375 px: die Tabelle bricht um; bleibt sie breiter, scrollt nur der Rahmen. */
	.rahmen {
		max-width: 100%;
		overflow-x: auto;
	}
	table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--g-text-md);
		color: var(--g-ink);
		background: var(--g-card);
	}
	caption {
		text-align: left;
		font-size: var(--g-text-sm);
		color: var(--g-ink-2);
		padding: 0 0 var(--g-s-2);
	}
	th,
	td {
		padding: var(--g-s-2) var(--g-size-6px);
		border-bottom: 1px solid var(--g-rule);
		text-align: left;
		vertical-align: top;
		overflow-wrap: anywhere;
	}
	thead th {
		font-weight: 600;
		border-bottom: var(--g-size-2px) solid var(--g-ink);
	}
	tbody th {
		font-weight: 500;
		color: var(--g-ink);
	}
	td {
		font-variant-numeric: tabular-nums;
		color: var(--g-ink);
	}
</style>
