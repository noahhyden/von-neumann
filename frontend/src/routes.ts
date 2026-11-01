/** The route table: pure path <-> surface mapping, shared by main.tsx (the router) and build.mjs (per-route HTML emission), so the two can never drift. */
import { SCENARIOS } from "./scenarios.ts";

export type Surface = "overview" | "wall" | "mission" | "fleet" | "swarm" | "spine" | "launch" | "power" | "probe" | "sources" | "papers";

export const VALID_SURFACES: Surface[] = [
  "overview", "mission", "fleet", "swarm", "spine", "wall", "probe", "launch", "power", "papers", "sources",
];

export const SURFACE_TITLE: Record<Surface, string> = {
  overview: "The Arithmetic of Self-Replication",
  mission: "Full mission - The Arithmetic of Self-Replication",
  fleet: "Fleet - The Arithmetic of Self-Replication",
  swarm: "Swarm - The Arithmetic of Self-Replication",
  spine: "Across scales - The Arithmetic of Self-Replication",
  wall: "Electronics wall - The Arithmetic of Self-Replication",
  probe: "Single probe - The Arithmetic of Self-Replication",
  launch: "Launch economics - The Arithmetic of Self-Replication",
  power: "Power budget - The Arithmetic of Self-Replication",
  papers: "Papers - The Arithmetic of Self-Replication",
  sources: "Sources - The Arithmetic of Self-Replication",
};

export const SCENARIO_KEYS: string[] = Object.keys(SCENARIOS);
export const DEFAULT_SCENARIO = "lunar";

export function pathForSurface(surface: Surface, scenarioKey: string): string {
  if (surface === "overview") return "/";
  if (surface === "wall" && scenarioKey && scenarioKey !== DEFAULT_SCENARIO) return `/wall/${scenarioKey}`;
  return `/${surface}`;
}

export function parsePath(pathname: string): { surface: Surface; scenarioKey: string } {
  const [s, scen] = pathname.split("/").filter(Boolean);
  const surface = s && (VALID_SURFACES as string[]).includes(s) ? (s as Surface) : "overview";
  const scenarioKey = surface === "wall" && scen && SCENARIOS[scen] ? scen : DEFAULT_SCENARIO;
  return { surface, scenarioKey };
}

/** True when the pathname's first segment names a known surface (or is the bare root) - false means a genuine 404. */
export function isKnownPath(pathname: string): boolean {
  const [s] = pathname.split("/").filter(Boolean);
  return !s || (VALID_SURFACES as string[]).includes(s);
}

/** Translates a legacy `#/<surface>[/<scenario>]` hash to its new path, or null if there is no hash to translate. */
export function pathFromLegacyHash(hash: string): string | null {
  if (!hash) return null;
  const { surface, scenarioKey } = parsePath(hash.replace(/^#\/?/, ""));
  return pathForSurface(surface, scenarioKey);
}

/** Every route a build must emit a real HTML file for: every surface (root "/" is index.html itself) plus every wall scenario, by key - so a direct hit on any of them is a real 200, not just the canonical short form. */
export function allRoutePaths(): string[] {
  const surfacePaths = VALID_SURFACES.filter((s) => s !== "overview").map((s) => pathForSurface(s, DEFAULT_SCENARIO));
  const wallScenarioPaths = SCENARIO_KEYS.map((key) => `/wall/${key}`);
  return [...new Set([...surfacePaths, ...wallScenarioPaths])];
}
