/** Bundle src/main.tsx into dist/app.js with pimas inlined; see README, "Develop". */
import { build as esbuild } from "esbuild";
import { gzipSync } from "node:zlib";
import { mkdir, writeFile, rm, readFile, cp, readdir } from "node:fs/promises";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { execFileSync } from "node:child_process";

const ROOT = import.meta.dirname;
const OUT = join(ROOT, "dist");

// Generate the gitignored src/papers-versions.ts at build time (see README, "Build-time generation").
execFileSync("node", [join(ROOT, "..", "papers", "scripts", "gen-versions.mjs")], { stdio: "inherit" });

await rm(OUT, { recursive: true, force: true });
await mkdir(OUT, { recursive: true });

const result = await esbuild({
  entryPoints: [join(ROOT, "src/main.tsx")],
  bundle: true,
  format: "esm",
  target: "es2022",
  jsx: "automatic",
  jsxImportSource: "pimas",
  outfile: join(OUT, "app.js"),
  // A /*! banner survives minification, so the bundle carries pimas' MIT notice (THIRD_PARTY_NOTICES).
  banner: { js: "/*! The Arithmetic of Self-Replication - (c) 2026 Noah Hydén. Code: PolyForm Strict 1.0.0. Bundles pimas (MIT, (c) 2026 Noah Hydén). See THIRD_PARTY_NOTICES. */" },
  minify: true,
  legalComments: "none",
  metafile: true,
});

// design.ts is build-only, so compile it into the gitignored .cache and import it.
const DESIGN = join(ROOT, ".cache", "design.mjs");
await esbuild({ entryPoints: [join(ROOT, "src/design.ts")], outfile: DESIGN, bundle: true, format: "esm", platform: "node", logLevel: "warning" });
const { BASE_CSS } = await import(pathToFileURL(DESIGN).href);
const PLACEHOLDER = "/*__DESIGN_TOKENS__*/";
const html = await readFile(join(ROOT, "index.html"), "utf8");
if (!html.includes(PLACEHOLDER)) throw new Error(`build: index.html has no ${PLACEHOLDER} placeholder; the design tokens would not ship`);
await writeFile(join(OUT, "index.html"), html.replace(PLACEHOLDER, () => BASE_CSS));
// Static assets referenced by index.html (the social-card image for link unfurls).
await cp(join(ROOT, "og.svg"), join(OUT, "og.svg"));
// GitHub Pages custom domain: the CNAME must live in the published artifact.
await cp(join(ROOT, "CNAME"), join(OUT, "CNAME"));
// Self-hosted woff2 fonts referenced by index.html.
await cp(join(ROOT, "fonts"), join(OUT, "fonts"), { recursive: true });

// Report shipped size.
const js = await readFile(join(OUT, "app.js"));
const gz = gzipSync(js).length;
console.log(`dist/app.js  ${(js.length / 1024).toFixed(1)} KB raw  ·  ${(gz / 1024).toFixed(1)} KB gz`);
const files = await readdir(OUT);
console.log(`dist/: ${files.join(", ")}`);
