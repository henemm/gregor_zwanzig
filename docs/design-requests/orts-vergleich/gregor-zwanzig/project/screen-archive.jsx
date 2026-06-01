/* Screen: Archiv — vergangene Trips, retrospektiv.
 *
 * Was hier landet:
 *   Trips, deren Enddatum vorbei ist. Auto-Verschiebung beim Tag-Wechsel.
 *   Ortsvergleiche werden NICHT archiviert (sind keine Zeitobjekte).
 *
 * Was die Seite leistet:
 *   1. Liste aller vergangenen Trips mit retrospektiver Genauigkeit:
 *      »Forecast-Treffer« = % der Briefings, deren Hauptkennzahl (Niederschlag,
 *      Gewitterrisiko, max-Wind) tatsächlich eingetreten ist.
 *   2. Pro Trip drei Aktionen:
 *        · Briefing-Verlauf öffnen   (alle gesendeten Briefings + Soll-Ist)
 *        · Als Vorlage neu anlegen   (kopiert Wegpunkte + Alerts)
 *        · Endgültig löschen
 *   3. Stats oben: Gesamt / Briefings gesendet / Genauigkeit Ø / Alarme ausgelöst
 *
 * Trip kann aus dem Archiv NICHT zurück in »Meine Trips« — wer einen
 * vergangenen Trip wiederholen will, nutzt »Als Vorlage neu anlegen«.
 */

const ARCHIVE_LIST = [
  {
    id: "ortler-2025",
    name: "Ortler-Überquerung",
    stages: 4,
    from: "2025-09-12", to: "2025-09-15",
    briefings: 12,
    accuracy: 92,
    alerts: 1,
    headline: "Gewitter Tag 2 wie prognostiziert — Aufstieg vorgezogen",
  },
  {
    id: "zillertal-2025",
    name: "Zillertal mit Steffi",
    stages: 1,
    from: "2025-12-28", to: "2025-12-30",
    briefings: 6,
    accuracy: 88,
    alerts: 0,
    headline: "Sonnig wie vorhergesagt, leichter Föhn ab Mittag",
  },
  {
    id: "rofan-2025",
    name: "Rofan Tageswanderung",
    stages: 1,
    from: "2025-08-23", to: "2025-08-23",
    briefings: 3,
    accuracy: 76,
    alerts: 1,
    headline: "Niederschlag 4 h früher als prognostiziert eingetroffen",
  },
  {
    id: "venediger-2024",
    name: "Großvenediger Rundtour",
    stages: 5,
    from: "2024-07-18", to: "2024-07-22",
    briefings: 18,
    accuracy: 94,
    alerts: 0,
    headline: "Stabile Schönwetter-Phase, Briefings ohne Korrektur",
  },
  {
    id: "stubai-2024",
    name: "Stubaier Höhenweg",
    stages: 8,
    from: "2024-08-30", to: "2024-09-06",
    briefings: 22,
    accuracy: 81,
    alerts: 2,
    headline: "Kaltlufteinbruch Tag 5 erkannt, Etappe 6 umgeplant",
  },
  {
    id: "khw-402",
    name: "KHW 402",
    stages: 13,
    from: "2024-05-05", to: "2024-05-18",
    briefings: 38,
    accuracy: 86,
    alerts: 3,
    headline: "Drei Gewitter-Tage, davon zwei Tage vorher avisiert",
  },
  {
    id: "gardasee-2024",
    name: "Gardasee Klettersteige",
    stages: 3,
    from: "2024-04-19", to: "2024-04-21",
    briefings: 9,
    accuracy: 71,
    alerts: 1,
    headline: "Wind unterschätzt, Bocchette gesperrt — kurzfristig umgeplant",
  },
  {
    id: "dachstein-2023",
    name: "Dachstein Überschreitung",
    stages: 2,
    from: "2023-09-08", to: "2023-09-09",
    briefings: 6,
    accuracy: 95,
    alerts: 0,
    headline: "Bilderbuch-Bedingungen — präzise getroffen",
  },
];

function ScreenArchive() {
  return (
    <div style={{ display: "flex", height: "100%", background: "var(--g-paper)" }}>
      <Sidebar active="archive"/>
      <ArchiveContent/>
    </div>
  );
}

function ArchiveContent() {
  const [query, setQuery] = React.useState("");
  const [sort, setSort]   = React.useState("recent");
  const filtered = ARCHIVE_LIST
    .filter(t => t.name.toLowerCase().includes(query.toLowerCase()))
    .sort((a, b) => {
      if (sort === "recent")   return b.to.localeCompare(a.to);
      if (sort === "accuracy") return b.accuracy - a.accuracy;
      if (sort === "stages")   return b.stages - a.stages;
      return 0;
    });

  const totalBriefings = ARCHIVE_LIST.reduce((s, t) => s + t.briefings, 0);
  const avgAccuracy    = Math.round(
    ARCHIVE_LIST.reduce((s, t) => s + t.accuracy, 0) / ARCHIVE_LIST.length
  );
  const totalAlerts    = ARCHIVE_LIST.reduce((s, t) => s + t.alerts, 0);

  return (
    <main style={{ flex: 1, padding: "32px 40px", overflow: "auto" }}>

        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28 }}>
          <div>
            <Eyebrow>Workspace · Vergangene Trips</Eyebrow>
            <div style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.025em", marginTop: 4 }}>Archiv</div>
            <div style={{ fontSize: 14, color: "var(--g-ink-3)", marginTop: 6, maxWidth: 620, lineHeight: 1.5 }}>
              Trips, deren Enddatum vorbei ist. Hier siehst du nachträglich, wie gut
              die Briefings getroffen haben, und kannst einen Trip als Vorlage für
              eine neue Planung übernehmen.
            </div>
          </div>
        </div>

        {/* Search + sort */}
        <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 20 }}>
          <div style={{ position: "relative", flex: "0 0 380px" }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-4)" strokeWidth="2"
                 style={{ position: "absolute", top: 11, left: 12 }}>
              <circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>
            </svg>
            <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Suchen…"
                   style={{
                     width: "100%", padding: "9px 14px 9px 34px",
                     border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-pill)",
                     background: "var(--g-card)", fontSize: 13, fontFamily: "var(--g-font-sans)",
                     color: "var(--g-ink)", outline: "none",
                   }}/>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 8,
                        fontSize: 11, fontFamily: "var(--g-font-mono)",
                        letterSpacing: "0.16em", textTransform: "uppercase",
                        color: "var(--g-ink-3)" }}>
            <span>Sortieren</span>
            <ArchiveSortTab id="recent"   sort={sort} setSort={setSort}>Neueste</ArchiveSortTab>
            <ArchiveSortTab id="accuracy" sort={sort} setSort={setSort}>Genauigkeit</ArchiveSortTab>
            <ArchiveSortTab id="stages"   sort={sort} setSort={setSort}>Etappen</ArchiveSortTab>
          </div>
        </div>

        {/* Stats summary */}
        <div style={{ display: "flex", gap: 32, marginBottom: 20, paddingBottom: 16,
                      borderBottom: "1px solid var(--g-rule-soft)" }}>
          <Stat layout="inline" label="Trips"               value={ARCHIVE_LIST.length}/>
          <Stat layout="inline" label="Briefings gesendet" value={totalBriefings}/>
          <Stat layout="inline" label="Forecast-Treffer Ø" value={avgAccuracy + "%"} tone="accent"/>
          <Stat layout="inline" label="Alarme ausgelöst"   value={totalAlerts}/>
        </div>

        {/* Table */}
        <Card padding={0} style={{ overflow: "hidden" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1.7fr 0.7fr 1.1fr 0.9fr 1.6fr auto", gap: 0,
                        padding: "12px 20px", background: "var(--g-paper-deep)",
                        fontSize: 11, fontFamily: "var(--g-font-mono)", letterSpacing: "0.18em",
                        textTransform: "uppercase", color: "var(--g-ink-3)", fontWeight: 500,
                        borderBottom: "1px solid var(--g-rule)" }}>
            <div>Name</div>
            <div>Etappen</div>
            <div>Zeitraum</div>
            <div>Treffer</div>
            <div>Was passiert ist</div>
            <div style={{ textAlign: "right" }}>Aktionen</div>
          </div>
          {filtered.map((t, i) => (
            <ArchiveRow key={t.id} trip={t} alt={i % 2 === 1}/>
          ))}
          {filtered.length === 0 && (
            <div style={{ padding: 40, textAlign: "center", color: "var(--g-ink-3)", fontSize: 13 }}>
              Keine archivierten Trips für »{query}« gefunden.
            </div>
          )}
        </Card>

        <div style={{ marginTop: 14, fontSize: 11, color: "var(--g-ink-4)",
                      fontFamily: "var(--g-font-mono)", letterSpacing: "0.06em" }}>
          {filtered.length} von {ARCHIVE_LIST.length} archivierten Trips · auto-archiviert nach Trip-Ende
        </div>
      </main>
  );
}

function ArchiveSortTab({ id, sort, setSort, children }) {
  const active = sort === id;
  return (
    <button onClick={() => setSort(id)} style={{
      padding: "4px 10px", background: active ? "var(--g-ink)" : "transparent",
      color: active ? "var(--g-paper)" : "var(--g-ink-3)",
      border: active ? "none" : "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-pill)",
      fontSize: 10, fontFamily: "var(--g-font-mono)",
      letterSpacing: "0.16em", textTransform: "uppercase",
      cursor: "pointer", fontWeight: 500,
    }}>{children}</button>
  );
}

function ArchiveRow({ trip, alt }) {
  const range = `${trip.from} → ${trip.to}`;
  const tone = trip.accuracy >= 90 ? "good"
             : trip.accuracy >= 80 ? "ok"
             : "warn";
  const toneColor = { good: "#3d6b3a", ok: "var(--g-ink-2)", warn: "#c08a1a" }[tone];

  return (
    <div style={{
      display: "grid", gridTemplateColumns: "1.7fr 0.7fr 1.1fr 0.9fr 1.6fr auto",
      alignItems: "center", padding: "16px 20px",
      background: alt ? "var(--g-paper-deep)" : "transparent",
      borderBottom: "1px solid var(--g-rule-soft)", gap: 0,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%",
                       background: "var(--g-ink-4)", flexShrink: 0 }}/>
        <span style={{ fontSize: 14, fontWeight: 600, letterSpacing: "-0.01em",
                       whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{trip.name}</span>
        {trip.alerts > 0 && (
          <span style={{ fontSize: 10, fontFamily: "var(--g-font-mono)",
                         color: "var(--g-accent)", textTransform: "uppercase",
                         letterSpacing: "0.16em" }}>· {trip.alerts} alert{trip.alerts > 1 ? "s" : ""}</span>
        )}
      </div>
      <div style={{ fontSize: 13, color: "var(--g-ink-2)", fontVariantNumeric: "tabular-nums" }}>
        {trip.stages} {trip.stages === 1 ? "Etappe" : "Etappen"}
      </div>
      <div style={{ fontSize: 13, color: "var(--g-ink-2)",
                    fontFamily: "var(--g-font-mono)", letterSpacing: "0.02em" }}>
        {range}
      </div>
      <AccuracyBar value={trip.accuracy} color={toneColor}/>
      <div style={{ fontSize: 12, color: "var(--g-ink-3)", lineHeight: 1.4, paddingRight: 16,
                    whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
        {trip.headline}
      </div>
      <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
        <ArchiveAction kind="history"  title="Briefing-Verlauf öffnen"/>
        <ArchiveAction kind="duplicate" title="Als Vorlage neu anlegen"/>
        <span style={{ width: 1, height: 18, background: "var(--g-rule)", margin: "0 4px" }}/>
        <ArchiveAction kind="trash"     title="Endgültig löschen" danger/>
      </div>
    </div>
  );
}

function AccuracyBar({ value, color }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, paddingRight: 16 }}>
      <div style={{ flex: 1, height: 4, background: "var(--g-rule-soft)",
                    borderRadius: "var(--g-r-pill)", overflow: "hidden", maxWidth: 80 }}>
        <div style={{ width: value + "%", height: "100%", background: color }}/>
      </div>
      <span style={{ fontFamily: "var(--g-font-mono)", fontSize: 12, fontWeight: 600,
                     fontVariantNumeric: "tabular-nums", color }}>{value}%</span>
    </div>
  );
}

function ArchiveAction({ kind, title, danger }) {
  const c = danger ? "var(--g-ink-3)" : "var(--g-ink-2)";
  const ic = {
    history:   <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/><path d="M12 8v4l3 2"/></svg>,
    duplicate: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><rect x="8" y="8" width="12" height="12" rx="1.5"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/></svg>,
    trash:     <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M4 7h16M9 7V4h6v3M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13"/></svg>,
  };
  return (
    <button title={title} style={{
      width: 30, height: 30, display: "inline-flex", alignItems: "center", justifyContent: "center",
      background: "transparent", border: "1px solid var(--g-rule-soft)",
      borderRadius: "var(--g-r-2)", cursor: "pointer",
    }}>{ic[kind]}</button>
  );
}

window.ScreenArchive   = ScreenArchive;
window.ArchiveContent  = ArchiveContent;
window.ARCHIVE_LIST    = ARCHIVE_LIST;
