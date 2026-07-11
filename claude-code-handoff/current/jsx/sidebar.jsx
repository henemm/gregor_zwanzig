/* Sidebar — Web-App-Navigation.
 *
 * Delegiert vollständig an das Grundgesetz (brand-kit.jsx::BrandSidebar).
 * Hier wird nichts mehr gemalt — Änderungen am Sidebar-Aussehen oder an
 * den Navigations-Items passieren in brand-kit.jsx.
 *
 * Bestandscode kann <Sidebar active="trips"/> weiter verwenden.
 *
 * Mapping alter → neuer Items (für Screens, die noch alte IDs nutzen):
 *   home    → home
 *   trips   → trips
 *   compare → compare
 *   archive → archive
 *   channels / settings → kein Eintrag mehr in der Sidebar
 *       (über User-Badge-Menü erreichbar; bis das Menü existiert,
 *        fällt die Aktiv-Markierung auf 'home' zurück)
 */

function Sidebar({ active = "home", counts }) {
  const ACTIVE_MAP = {
    home: "home", trips: "trips", compare: "compare", archive: "archive",
  };
  const mapped = ACTIVE_MAP[active] || "home";
  return <window.BrandSidebar active={mapped} counts={counts}/>;
}

window.Sidebar = Sidebar;
