/** Serve the built dist/ over http://localhost for local preview; see README, "Preview a change before merge". */
import { context } from "esbuild";
import { join } from "node:path";

const DIST = join(import.meta.dirname, "..", "dist");

const ctx = await context({});
// No port given: esbuild picks an open one (starting at 8000) and returns it.
const { host, port } = await ctx.serve({ servedir: DIST });
const shown = host === "0.0.0.0" || host === "::" ? "localhost" : host;
console.log(`Serving dist/ at http://${shown}:${port}  (Ctrl-C to stop)`);
