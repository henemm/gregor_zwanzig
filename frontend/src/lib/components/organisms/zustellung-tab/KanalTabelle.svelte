<script lang="ts">
	// Issue #2795 S3b, Teilschritt 1b (AC-11 bis AC-21): Warnboxen und EINE Kanal-Tabelle fuer alle
	// vier Kanaele (Kanal · Briefing · Alarme · Alarm schon ab Dringlichkeit). Status, Sperren,
	// Konto-Link und Dringlichkeit kommen aus dem Modell (zustellungModell.ts), die Kanal-Zustaende
	// aus der EINEN Profil-Antwort des Reiters (AC-36). Speichert nicht selbst.
	import { Btn, Dot, Segmented, Switch } from '$lib/components/atoms';
	import { t, locale } from '$lib/i18n';
	import {
		KANAELE,
		KANAL_NAME_KEYS,
		dringlichkeitZelle,
		tabellenKopf,
		warnboxen,
		zaehler,
		type Dringlichkeit,
		type KanalId,
		type KanalStatus,
		type ZustellungStand
	} from '../../shared/zustellung-tab/zustellungModell.ts';

	interface Props {
		stand: ZustellungStand;
		/** null, solange das Profil laedt. */
		status: Record<KanalId, KanalStatus> | null;
		onaendern: (neu: ZustellungStand) => void;
	}
	let { stand, status, onaendern }: Props = $props();

	const TON = { ok: 'good', warn: 'warn', off: 'neutral' } as const;

	const z = $derived(status ? zaehler(stand, status) : null);
	const kopf = $derived.by(() => (void $locale, z ? tabellenKopf(z) : ''));
	const warn = $derived.by(() => (void $locale, z ? warnboxen(z) : { briefing: null, alarme: null }));
	const zellen = $derived.by(() => (void $locale, status ? Object.fromEntries(KANAELE.map((k) => [k, dringlichkeitZelle(k, stand, status)])) : {}));

	function setzeBriefing(k: KanalId, an: boolean): void {
		onaendern({ ...stand, briefing: { ...stand.briefing, [k]: an } });
	}
	function setzeAlarm(k: KanalId, an: boolean): void {
		onaendern({ ...stand, alarme: { ...stand.alarme, [k]: an } });
	}
	function setzeDringlichkeit(k: KanalId, wert: string): void {
		onaendern({ ...stand, dringlichkeit: { ...stand.dringlichkeit, [k]: wert as Dringlichkeit } });
	}
</script>

<div class="zt-kanaele" data-abschnitt="kanaele">
	{#if warn.briefing}
		<div class="zt-warnbox" role="alert" data-testid="zustellung-warnung-briefing">
			<b>{warn.briefing.titel}</b> <span>{warn.briefing.text}</span>
		</div>
	{/if}
	{#if warn.alarme}
		<div class="zt-warnbox" role="alert" data-testid="zustellung-warnung-alarme">
			<b>{warn.alarme.titel}</b> <span>{warn.alarme.text}</span>
		</div>
	{/if}

	<div class="zt-karte">
		{#if !status}
			<p class="zt-laedt" role="status">{$t('zustellung.kanaele.laedt')}</p>
		{:else}
			<div class="zt-kopf">
				<b data-testid="zustellung-kanaele-kopf">{kopf}</b>
				<small data-testid="zustellung-kanaele-unterzeile">{$t('zustellung.kanaele.unterzeile')}</small>
			</div>
			<div class="zt-tabelle-huelle">
				<table class="zt-tabelle" data-testid="zustellung-kanal-tabelle">
					<thead>
						<tr>
							<th>{$t('zustellung.spalte.kanal')}</th>
							<th>{$t('zustellung.spalte.briefing')}</th>
							<th>{$t('zustellung.spalte.alarme')}</th>
							<th>{$t('zustellung.spalte.dringlichkeit')}</th>
						</tr>
					</thead>
					<tbody>
						{#each KANAELE as k (k)}
							{@const st = status[k]}
							{@const name = $t(KANAL_NAME_KEYS[k])}
							{@const zelle = zellen[k]}
							<tr data-testid="zustellung-kanal-{k}">
								<td>
									<b>{name}</b>
									<div class="zt-status" data-testid="zustellung-kanal-{k}-status">
										<Dot tone={TON[st.ton]} size={8} />
										<span>{st.statusText}{st.ziel ? ` · ${st.ziel}` : ''}</span>
									</div>
									{#if st.grund}
										<div class="zt-hinweis" data-testid="zustellung-kanal-{k}-hinweis">
											<span>{st.grund}</span>
											{#if st.kontoLink}
												<Btn href="/account" variant="link" size="xs" data-testid="zustellung-kanal-{k}-konto">{st.kontoLink.text}</Btn>
											{/if}
										</div>
									{/if}
								</td>
								<td>
									<Switch
										checked={stand.briefing[k] && !st.briefingGesperrt}
										disabled={st.briefingGesperrt}
										tap
										aria-label={$t('zustellung.kanal.briefing_aria', { kanal: name })}
										testid="zustellung-kanal-{k}-briefing"
										onchange={(an) => setzeBriefing(k, an)}
									/>
								</td>
								<td data-spalte={$t('zustellung.spalte.alarme')}>
									{#if st.alarmGesperrt}
										<span class="zt-gesperrt" data-testid="zustellung-kanal-{k}-alarm-gesperrt">{st.alarmSperre}</span>
									{:else}
										<Switch
											checked={stand.alarme[k]}
											tap
											aria-label={$t('zustellung.kanal.alarm_aria', { kanal: name })}
											testid="zustellung-kanal-{k}-alarm"
											onchange={(an) => setzeAlarm(k, an)}
										/>
									{/if}
								</td>
								<td data-testid="zustellung-kanal-{k}-dringlichkeit" data-spalte={$t('zustellung.spalte.dringlichkeit')}>
									{#if zelle && zelle.art === 'segment'}
										<Segmented
											variant="kompakt"
											rolle="radio"
											ariaLabel={$t('zustellung.kanal.dringlichkeit_aria', { kanal: name })}
											items={zelle.optionen.map((o) => ({ id: o.wert, label: o.text, testid: `zustellung-kanal-${k}-dringlichkeit-${o.wert}` }))}
											value={zelle.wert}
											onChange={(w: string) => setzeDringlichkeit(k, w)}
										/>
									{:else}
										<span class="zt-strich">–</span>
									{/if}
								</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
			<p class="zt-legende" data-testid="zustellung-legende">{$t('zustellung.legende')}</p>
		{/if}
	</div>
</div>

<style>
	.zt-kanaele {
		display: flex;
		flex-direction: column;
		gap: var(--g-s-3);
	}
	.zt-warnbox {
		display: flex;
		flex-wrap: wrap;
		gap: var(--g-s-1);
		padding: var(--g-s-3) var(--g-s-4);
		border: 1px solid var(--g-danger);
		border-radius: var(--g-r-3);
		background: var(--g-danger-bg);
		color: var(--g-danger-fg);
		font-size: var(--g-size-13px);
	}
	.zt-karte {
		border: 1px solid var(--g-rule);
		border-radius: var(--g-r-3);
		background: var(--g-card);
	}
	.zt-kopf {
		display: flex;
		flex-direction: column;
		gap: var(--g-size-2px);
		padding: var(--g-size-14px) var(--g-s-5);
	}
	.zt-kopf small,
	.zt-laedt {
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	.zt-laedt {
		margin: 0;
		padding: var(--g-size-14px) var(--g-s-5);
	}
	.zt-tabelle-huelle {
		overflow-x: auto;
	}
	.zt-tabelle {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--g-size-14px);
	}
	/* Mockup `.kt th` (Z. 149): Mono 10px, Grossbuchstaben per CSS, Zeichenabstand, gedaempft. */
	.zt-tabelle th {
		text-align: left;
		font-family: var(--g-font-mono);
		font-size: var(--g-size-10px);
		letter-spacing: var(--g-size-0-1em);
		text-transform: uppercase;
		font-weight: 500;
		color: var(--g-ink-3);
		padding: var(--g-s-3) var(--g-s-5) var(--g-s-2);
	}
	/* Mockup `.kt td` (Z. 150). Die Kanal-Spalte nimmt den Rest der Breite, die Spalten Briefing,
	   Alarme und Dringlichkeit stehen so breit wie ihr Kopf direkt nebeneinander (Bild Mockup). */
	.zt-tabelle td {
		vertical-align: middle;
		padding: var(--g-s-3) var(--g-s-5);
		border-top: 1px solid var(--g-rule-soft);
	}
	.zt-tabelle :is(th, td):first-child {
		width: 100%;
	}
	.zt-tabelle th:not(:first-child) {
		white-space: nowrap;
	}
	/* Dringlichkeits-Segment bleibt einzeilig (die Spalte ist so schmal wie moeglich). */
	.zt-tabelle td :global([data-slot='segmented']) {
		flex-wrap: nowrap;
	}
	.zt-tabelle td b {
		display: block;
		font-size: var(--g-size-14px);
		font-weight: 600;
	}
	.zt-status,
	.zt-hinweis {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--g-s-1);
		margin-top: var(--g-size-2px);
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	/* Punkt bleibt neben dem Statustext (nicht auf eigener Zeile). */
	.zt-status {
		flex-wrap: nowrap;
	}
	.zt-status span {
		min-width: 0;
		overflow-wrap: anywhere;
	}
	.zt-hinweis {
		color: var(--g-danger-fg);
	}
	.zt-gesperrt,
	.zt-strich {
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
	/* Gesperrt-Satz: eigene Mindestbreite statt fast wortweisem Umbruch in schmaler Spalte. */
	.zt-gesperrt {
		display: block;
		min-width: var(--g-size-160px);
	}
	/* Handy/Tablet: je Kanal oben Kanal (volle Restbreite) | Briefing-Schalter (wie Mockup-
	   Handyfassung), darunter Alarme und Dringlichkeit je ueber die volle Breite, damit beide ohne
	   waagerechtes Wischen erreichbar bleiben und Texte an Wortgrenzen umbrechen. Der Tabellenkopf
	   bleibt fuer Screenreader im DOM, steht aber nicht doppelt zu den Zellbeschriftungen. */
	@media (max-width: 899px) {
		.zt-tabelle-huelle {
			position: relative;
		}
		.zt-tabelle,
		.zt-tabelle tbody {
			display: block;
		}
		.zt-tabelle thead {
			position: absolute;
			width: var(--g-size-2px);
			height: var(--g-size-2px);
			overflow: hidden;
			clip-path: inset(50%);
			white-space: nowrap;
		}
		.zt-tabelle tbody tr {
			display: grid;
			grid-template-columns: minmax(0, 1fr) auto;
			gap: var(--g-s-2) var(--g-s-4);
			align-items: center;
			padding: var(--g-s-3) var(--g-s-5);
			border-top: 1px solid var(--g-rule-soft);
		}
		.zt-tabelle td {
			display: block;
			width: auto;
			min-width: 0;
			padding: 0;
			border-top: 0;
		}
		.zt-tabelle td:first-child {
			width: auto;
			overflow-wrap: anywhere;
		}
		.zt-tabelle td:nth-child(2) {
			justify-self: end;
		}
		/* Alarme und Dringlichkeit: eigene Zeile ueber die volle Breite, Beschriftung links,
		   Schalter bzw. Segment rechts; laengere Inhalte (Sperrsatz) brechen darunter um. */
		.zt-tabelle td[data-spalte] {
			grid-column: 1 / -1;
			display: flex;
			flex-wrap: wrap;
			align-items: center;
			justify-content: space-between;
			gap: var(--g-s-1) var(--g-s-3);
		}
		.zt-tabelle td[data-spalte]::before {
			content: attr(data-spalte);
			font-family: var(--g-font-mono);
			font-size: var(--g-size-10px);
			letter-spacing: var(--g-size-0-1em);
			text-transform: uppercase;
			color: var(--g-ink-3);
		}
		.zt-gesperrt {
			flex: 1 1 100%;
			min-width: 0;
		}
	}
	.zt-legende {
		margin: 0;
		padding: var(--g-s-3) var(--g-s-5) var(--g-size-14px);
		border-top: 1px solid var(--g-rule-soft);
		font-size: var(--g-size-12-5px);
		color: var(--g-ink-2);
	}
</style>
