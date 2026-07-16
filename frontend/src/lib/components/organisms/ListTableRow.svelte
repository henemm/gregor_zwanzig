<script lang="ts">
	// Issue #1277 — ListTableRow: eine Zeile der geteilten ListTable.
	//
	// Rendert die Namens-Zelle (ListNameCell), die dynamischen Spalten aus
	// `columns[].render(row)`, die inline Quick-Action (`primary`) und den
	// Overflow-Trigger (ListActionsMenu). Ganze Zeile klickbar → onRowClick;
	// Zebra-Streifen auf ungeraden Zeilen, Hover-Highlight, Chevron rechts.
	//
	// `render(row)` liefert entweder einen String (einfache Text-Zelle) oder
	// ein Descriptor-Objekt: { nameCell } · { pills } · { lines }. Damit bleibt
	// die Spec-API `render(row)` erhalten, ohne dass die Spalten Svelte-
	// Komponenten direkt zurückgeben müssen.
	//
	// Spec: docs/specs/feature/issue_1277_list_table_unify.md

	import ListNameCell from './ListNameCell.svelte';
	import ListActionsMenu from './ListActionsMenu.svelte';

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
		row,
		columns,
		index,
		gridTemplate,
		onRowClick,
		primary = null,
		actions = null,
		onAction,
		rowTestid,
		menuTestid
	}: {
		row: unknown;
		columns: Column[];
		index: number;
		gridTemplate: string;
		onRowClick?: (row: unknown) => void;
		primary?: { label: string; onClick: () => void } | null;
		actions?: Action[] | null;
		onAction?: (key: string, row: unknown) => void;
		rowTestid?: string;
		menuTestid?: string;
	} = $props();

	const zebra = $derived(index % 2 === 1 ? 'var(--g-paper-deep)' : 'transparent');

	function isNameCell(c: CellResult): c is { nameCell: NameCell } {
		return typeof c === 'object' && c !== null && 'nameCell' in c;
	}
	function isPills(c: CellResult): c is { pills: string[] } {
		return typeof c === 'object' && c !== null && 'pills' in c;
	}
	function isLines(c: CellResult): c is { lines: string[] } {
		return typeof c === 'object' && c !== null && 'lines' in c;
	}
</script>

<div
	role="button"
	tabindex="0"
	data-testid={rowTestid}
	onclick={() => onRowClick?.(row)}
	onkeydown={(e) => {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			onRowClick?.(row);
		}
	}}
	style="display: grid; grid-template-columns: {gridTemplate}; align-items: center; padding: 16px 20px; background: {zebra}; border-bottom: 1px solid var(--g-rule-soft); gap: 0; cursor: pointer; transition: background 120ms;"
	onmouseenter={(e) => {
		(e.currentTarget as HTMLElement).style.background = 'var(--g-card-alt, #f1eee6)';
	}}
	onmouseleave={(e) => {
		(e.currentTarget as HTMLElement).style.background = zebra;
	}}
>
	{#each columns as col (col.key)}
		{@const cell = col.render(row)}
		<div
			style="min-width: 0; text-align: {col.align ?? 'left'}; font-size: 13px; color: var(--g-ink-2); {col.mono
				? 'font-family: var(--g-font-mono); letter-spacing: 0.02em;'
				: ''}"
		>
			{#if isNameCell(cell)}
				<ListNameCell
					name={cell.nameCell.name}
					statusLabel={cell.nameCell.statusLabel}
					dotColor={cell.nameCell.dotColor}
				/>
			{:else if isPills(cell)}
				<div style="display: flex; flex-wrap: wrap; gap: 5px;">
					{#if cell.pills.length === 0}
						<span style="font-family: var(--g-font-mono); font-size: 11px; color: var(--g-ink-4);"
							>—</span
						>
					{:else}
						{#each cell.pills as pill (pill)}
							<span
								style="font-family: var(--g-font-mono); padding: 2px 7px; font-size: 10px; letter-spacing: 0.04em; border: 1px solid var(--g-rule); border-radius: var(--g-r-pill); background: var(--g-card-alt); color: var(--g-ink-2);"
								>{pill}</span
							>
						{/each}
					{/if}
				</div>
			{:else if isLines(cell)}
				<div style="display: flex; flex-direction: column; gap: 2px;">
					<span>{cell.lines[0]}</span>
					{#if cell.lines[1]}
						<span style="font-size: 11px; color: var(--g-ink-4); font-family: var(--g-font-mono);"
							>{cell.lines[1]}</span
						>
					{/if}
				</div>
			{:else}
				{cell}
			{/if}
		</div>
	{/each}

	<!-- Aktionen-Spalte (stopPropagation verhindert Zeilen-Navigation) -->
	<div
		role="presentation"
		onclick={(e) => e.stopPropagation()}
		style="display: flex; gap: 8px; justify-content: flex-end; align-items: center; position: relative;"
	>
		{#if primary}
			<button
				onclick={(e) => {
					e.stopPropagation();
					primary?.onClick();
				}}
				style="display: inline-flex; align-items: center; gap: 6px; padding: 0 12px; height: 32px; background: transparent; border: 1px solid var(--g-rule); border-radius: var(--g-r-2); cursor: pointer; font-size: 13px; font-family: var(--g-font-sans); color: var(--g-ink); white-space: nowrap;"
			>
				<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink)" stroke-width="1.7" stroke-linecap="round"><path d="M7 5l12 7-12 7z" /></svg>
				{primary.label}
			</button>
		{/if}
		{#if actions && actions.length > 0}
			<ListActionsMenu {actions} testid={menuTestid} onSelect={(key) => onAction?.(key, row)} />
		{/if}
		<span style="display: inline-flex; color: var(--g-ink-4); margin-left: 2px;">
			<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6" /></svg>
		</span>
	</div>
</div>
