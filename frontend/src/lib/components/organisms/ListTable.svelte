<script lang="ts">
	// Issue #1277 — ListTable: geteiltes Tabellen-Organism für die Desktop-
	// Übersichten von Trips UND Orts-Vergleichen.
	//
	// Chassis + Kopf + Zebra + Hover + Zeilen-Klick + Empty-State sind hier
	// identisch; die Fachlogik lebt AUSSCHLIESSLICH in den vom Screen
	// injizierten `columns`/`rowActions`/`rowPrimary`-Props. Kein Fork je
	// Screen (Trip/Compare-Teilungs-Invariante, CLAUDE.md).
	//
	// Bauplan: AlertMetricTable.svelte (Card-Wrapper + Grid-Header + separate
	// Row-Komponente). Overflow-Menü: ListActionsMenu.svelte.
	//
	// Spec: docs/specs/feature/issue_1277_list_table_unify.md

	import { Card } from '$lib/components/atoms';
	import ListTableRow from './ListTableRow.svelte';

	interface NameCell {
		name: string;
		statusLabel?: string;
		dotColor?: string;
	}
	type CellResult = string | { nameCell: NameCell } | { pills: string[] } | { lines: string[] };

	interface Column {
		key: string;
		header: string;
		align?: 'left' | 'right' | 'center';
		width?: string;
		mono?: boolean;
		render: (row: unknown) => CellResult;
	}
	interface Action {
		key: string;
		label: string;
		danger?: boolean;
		testid?: string;
	}

	let {
		columns,
		rows,
		getRowId,
		onRowClick,
		rowActions,
		rowPrimary,
		onAction,
		emptyText = 'Keine Einträge.',
		rowTestid,
		menuTestid
	}: {
		columns: Column[];
		rows: unknown[];
		getRowId: (row: unknown) => string;
		onRowClick?: (row: unknown) => void;
		rowActions?: (row: unknown) => Action[] | null;
		rowPrimary?: (row: unknown) => { label: string; onClick: () => void } | null;
		onAction?: (key: string, row: unknown) => void;
		emptyText?: string;
		// Optionale Testid-Fabriken für E2E-Selektoren (Desktop-ListTable-Zeilen).
		rowTestid?: (row: unknown) => string;
		menuTestid?: (row: unknown) => string;
	} = $props();

	// Spaltenbreiten → CSS grid-template; rechte "Aktionen"-Spalte immer auto.
	const gridTemplate = $derived(
		columns.map((c) => c.width ?? '1fr').join(' ') + ' auto'
	);
</script>

<Card padding={0} style="overflow: hidden;">
	<!-- Tabellenkopf: mono-caps auf --g-paper-deep; rechte Spalte "Aktionen" -->
	<div
		style="display: grid; grid-template-columns: {gridTemplate}; gap: 0; padding: 12px 20px; background: var(--g-paper-deep); font-size: 11px; font-family: var(--g-font-mono); letter-spacing: 0.18em; text-transform: uppercase; color: var(--g-ink-3); font-weight: 500; border-bottom: 1px solid var(--g-rule);"
	>
		{#each columns as col (col.key)}
			<div style="text-align: {col.align ?? 'left'};">{col.header}</div>
		{/each}
		<div style="text-align: right;">Aktionen</div>
	</div>

	{#each rows as row, i (getRowId(row))}
		<ListTableRow
			{row}
			{columns}
			index={i}
			{gridTemplate}
			{onRowClick}
			{onAction}
			primary={rowPrimary ? rowPrimary(row) : null}
			actions={rowActions ? rowActions(row) : null}
			rowTestid={rowTestid ? rowTestid(row) : undefined}
			menuTestid={menuTestid ? menuTestid(row) : undefined}
		/>
	{/each}

	{#if rows.length === 0}
		<div style="padding: 40px; text-align: center; color: var(--g-ink-3); font-size: 13px;">
			{emptyText}
		</div>
	{/if}
</Card>
