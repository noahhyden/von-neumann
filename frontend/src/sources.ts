/**
 * The project-wide bibliography, consolidated from every module's REFERENCES.md into
 * one sourced list. Pure data, zero pimas imports (Layer A testable, CLAUDE.md 7):
 * the reactive skin (a <Cite> marker and the Sources surface in main.tsx) reads this,
 * it never writes it.
 *
 * Every entry is a source that already exists in a module REFERENCES.md - nothing here
 * is invented (CLAUDE.md 1). `url: null` means the repo cites the work by journal /
 * report reference without a link (a textbook, an IAU resolution, a paywalled DOI), not
 * that a link was dropped. `strength` records how a reviewer should weigh it, so the
 * public bibliography is honest about which numbers rest on peer-reviewed work and which
 * on a vendor page or a wiki.
 */

export type SourceCategory =
  | "Self-replicating machines"
  | "Manufacturing and embodied energy"
  | "Power, computation and thermodynamics"
  | "Launch and propulsion"
  | "Solar and planetary environment"
  | "Swarm dynamics and slingshots"
  | "Coordination and communication delay";

export type SourceStrength =
  | "primary" // peer-reviewed paper, standards RFC, or agency technical report
  | "reference" // textbook, definitional constant body (CODATA/IAU/BIPM), agency fact sheet
  | "grey" // think-tank / preprint / non-refereed but serious
  | "vendor" // manufacturer or company-published figure
  | "wiki"; // community-edited, weakest; used only for cross-checks

export interface Source {
  id: string;
  /** Author-year short label used in the inline marker and the list, e.g. "Kopp & Lean 2011". */
  short: string;
  authors: string;
  year: string;
  title: string;
  venue: string;
  /** The exact URL from the module REFERENCES.md, or null when the repo cites it without a link. */
  url: string | null;
  category: SourceCategory;
  strength: SourceStrength;
  /** Which module(s) cite this source. */
  modules: string[];
  /** Plain-language: the specific quantity or idea this source grounds in the project. */
  grounds: string;
}

/**
 * Ordered by category so the citation numbers group logically in the bibliography. The
 * number a reader sees ([n]) is 1-based position in this array (see `sourceNumber`), so
 * do not reorder without accepting that the numbers shift.
 */
export const SOURCES: Source[] = [
  // -- Self-replicating machines (the foundational idea) -----------------------------
  {
    id: "nasa-cp-2255-1980",
    short: "NASA CP-2255 (1980)",
    authors: "R. Freitas, G. von Tiesenhausen et al. (NASA)",
    year: "1980",
    title: "Advanced Automation for Space Missions (Ch. 5, the self-replicating lunar factory)",
    venue: "NASA Conference Publication 2255",
    url: "https://ntrs.nasa.gov/citations/19830007081",
    category: "Self-replicating machines",
    strength: "primary",
    modules: ["closure-sim", "mission", "multi-probe"],
    grounds:
      "The canonical seed-factory study: the \"vitamins\" framing (build 90-95% locally, import the rest), 90-96% achievable mass closure, a ~1-year doubling time, and ~1.7 MW seed power.",
  },
  {
    id: "freitas-merkle-2004",
    short: "Freitas & Merkle 2004",
    authors: "R. A. Freitas Jr. & R. C. Merkle",
    year: "2004",
    title: "Kinematic Self-Replicating Machines",
    venue: "Landes Bioscience",
    url: "http://www.molecularassembler.com/KSRM.htm",
    category: "Self-replicating machines",
    strength: "primary",
    modules: ["closure-sim"],
    grounds:
      "The modern synthesis of matter / energy / information closure, and the core dynamic this project models: below full closure you wait on resupply; only near 100% does growth become self-sustaining.",
  },
  {
    id: "guided-self-replicating-factory-2021",
    short: "Shubov 2021",
    authors: "M. V. Shubov",
    year: "2021",
    title: "Guided Self-Replicating Factory for Colonization of Solar System (arXiv:2110.15198)",
    venue: "arXiv preprint",
    url: "https://arxiv.org/abs/2110.15198",
    category: "Self-replicating machines",
    strength: "grey",
    modules: ["closure-sim"],
    grounds:
      "A recent revival: sub-1-year doubling reaching a large colony in ~two decades, a near-term-realistic ~70% closure, with chips and circuitry staying Earth-sourced.",
  },
  {
    id: "freitas-1980-interstellar-probe",
    short: "Freitas 1980 (JBIS)",
    authors: "R. A. Freitas Jr.",
    year: "1980",
    title: "A Self-Reproducing Interstellar Probe",
    venue: "Journal of the British Interplanetary Society 33:251",
    url: null,
    category: "Self-replicating machines",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "Frames each interstellar probe as an independent agent acting on priors set before launch - the source for the swarm's top \"independent colonies\" coordination rung.",
  },
  {
    id: "borgue-hein-2020",
    short: "Borgue & Hein 2020",
    authors: "O. Borgue & A. M. Hein",
    year: "2020",
    title: "Near-Term Self-replicating Probes: A Concept Design (arXiv:2005.12303)",
    venue: "Acta Astronautica 187 (2021) 546-556, DOI 10.1016/j.actaastro.2021.03.004",
    url: "https://arxiv.org/abs/2005.12303",
    category: "Self-replicating machines",
    strength: "primary",
    modules: ["probe-sim", "mission", "multi-probe"],
    grounds:
      "The single-probe design: six functional modules, a 70% replicated mass fraction (the other 30% imported electronics), a sub-100 kg CubeSat scale, and solar-flux range gating (1374 W/m2 at Earth to ~50 W/m2 at Jupiter).",
  },

  // -- Manufacturing and embodied energy (the electronics wall) ----------------------
  {
    id: "williams-ayres-heller-2002",
    short: "Williams, Ayres & Heller 2002",
    authors: "E. Williams, R. Ayres & M. Heller",
    year: "2002",
    title: "The 1.7 Kilogram Microchip: Energy and Material Use in the Production of Semiconductor Devices",
    venue: "Environmental Science & Technology 36(24)",
    url: "https://pubs.acs.org/doi/10.1021/es025643o",
    category: "Manufacturing and embodied energy",
    strength: "primary",
    modules: ["closure-sim"],
    grounds:
      "The headline embodied-energy fact behind the electronics wall: the material and energy inputs to make a 2 g chip outweigh it roughly 600-fold.",
  },
  {
    id: "nagapurkar-das-2022",
    short: "Nagapurkar & Das 2022",
    authors: "P. Nagapurkar & S. Das (Oak Ridge National Laboratory)",
    year: "2022",
    title: "Economic and embodied energy analysis of integrated circuit manufacturing processes",
    venue: "Sustainable Computing: Informatics and Systems 35 (2022) 100771, DOI 10.1016/j.suscom.2022.100771",
    url: "https://www.osti.gov/servlets/purl/1884036",
    category: "Manufacturing and embodied energy",
    strength: "primary",
    modules: ["closure-sim"],
    grounds: "IC manufacturing energy of ~9-38 MJ per cm2 of wafer, grounding the chip energy-per-kg figure.",
  },
  {
    id: "ice-coefficients",
    short: "ICE embodied-energy coefficients",
    authors: "Hammond & Jones (Inventory of Carbon & Energy)",
    year: "2011",
    title: "ICE embodied-energy coefficients",
    venue: "University of Bath / Victoria University of Wellington archive",
    url: "https://www.wgtn.ac.nz/architecture/centres/cbpr/resources/pdfs/ee-coefficients.pdf",
    category: "Manufacturing and embodied energy",
    strength: "reference",
    modules: ["closure-sim"],
    grounds: "Embodied energy of smelted / cast metals and structural materials (the cheap-to-make parts).",
  },
  {
    id: "peng-2013-pv-lca",
    short: "Peng et al. 2013",
    authors: "J. Peng, L. Lu & H. Yang",
    year: "2013",
    title: "Review on life-cycle assessment of energy payback and greenhouse gas emission of solar photovoltaic systems",
    venue: "Renewable and Sustainable Energy Reviews",
    url: "https://krichlab.ca/wp-content/uploads/2014/06/Peng2013_Review-LCA-EPBTGHG-SolarPV.pdf",
    category: "Manufacturing and embodied energy",
    strength: "primary",
    modules: ["closure-sim"],
    grounds: "Embodied energy of silicon photovoltaic arrays (silicon purification dominates the 40-120 kWh/kg range).",
  },
  {
    id: "power-electronics-lca",
    short: "Spejo et al. 2023",
    authors: "L. B. Spejo, I. Akor, M. Rahimo & R. A. Minamisawa",
    year: "2023",
    title:
      "Life-cycle energy demand comparison of medium voltage Silicon IGBT and Silicon Carbide MOSFET power semiconductor modules in railway traction applications",
    venue: "Power Electronic Devices and Components (Elsevier, 2023)",
    url: "https://www.sciencedirect.com/science/article/pii/S2772370423000184",
    category: "Manufacturing and embodied energy",
    strength: "primary",
    modules: ["closure-sim"],
    grounds: "Embodied energy of power electronics and integrated circuits (the 1,000-3,000 kWh/kg band).",
  },
  {
    id: "sensor-embodied-2021",
    short: "Pirson & Bol 2021",
    authors: "T. Pirson & D. Bol",
    year: "2021",
    title:
      "Assessing the embodied carbon footprint of IoT edge devices with a bottom-up life-cycle approach (arXiv:2105.02082)",
    venue: "arXiv preprint",
    url: "https://arxiv.org/abs/2105.02082",
    category: "Manufacturing and embodied energy",
    strength: "grey",
    modules: ["closure-sim"],
    grounds: "Embodied footprint of electronic sensors and edge devices (the 2,000-8,000 kWh/kg band).",
  },
  {
    id: "csis-semiconductor-supply-chain",
    short: "CSIS semiconductor supply chain",
    authors: "Center for Strategic & International Studies",
    year: "2021",
    title: "Mapping the Semiconductor Supply Chain",
    venue: "CSIS analysis",
    url: "https://www.csis.org/analysis/mapping-semiconductor-supply-chain-critical-role-indo-pacific-region",
    category: "Manufacturing and embodied energy",
    strength: "grey",
    modules: ["closure-sim"],
    grounds:
      "Why chips are the deepest supply chain on Earth (400+ process steps, 9-nines-pure materials, an EUV monopoly) - the qualitative case that a lone factory cannot close on chips.",
  },
  {
    id: "marspedia-embodied-energy",
    short: "Marspedia: Embodied energy",
    authors: "Marspedia contributors",
    year: "n.d.",
    title: "Embodied energy",
    venue: "Marspedia (community wiki)",
    url: "https://marspedia.org/Embodied_energy",
    category: "Manufacturing and embodied energy",
    strength: "wiki",
    modules: ["closure-sim"],
    grounds: "A cross-check on embodied-energy figures only; a community wiki, weighted least and never a sole source.",
  },

  // -- Power, computation and thermodynamics -----------------------------------------
  {
    id: "landauer-1961",
    short: "Landauer 1961",
    authors: "R. Landauer",
    year: "1961",
    title: "Irreversibility and heat generation in the computing process",
    venue: "IBM J. Res. Dev. 5(3):183-191, DOI 10.1147/rd.53.0183",
    url: "https://doi.org/10.1147/rd.53.0183",
    category: "Power, computation and thermodynamics",
    strength: "primary",
    modules: ["power-budget", "mission"],
    grounds: "The Landauer limit E = kT ln2, the hard thermodynamic floor on energy per erased bit (~2.9e-21 J/bit at 300 K).",
  },
  {
    id: "berut-2012",
    short: "Berut et al. 2012",
    authors: "A. Berut et al.",
    year: "2012",
    title: "Experimental verification of Landauer's principle linking information and thermodynamics",
    venue: "Nature 483:187-189",
    url: "https://doi.org/10.1038/nature10872",
    category: "Power, computation and thermodynamics",
    strength: "primary",
    modules: ["power-budget"],
    grounds: "Experimental confirmation that the Landauer floor is real and approachable, not just theoretical.",
  },
  {
    id: "raichle-gusnard-2002",
    short: "Raichle & Gusnard 2002",
    authors: "M. E. Raichle & D. A. Gusnard",
    year: "2002",
    title: "Appraising the brain's energy budget",
    venue: "PNAS 99(16):10237-10239, DOI 10.1073/pnas.172399499",
    url: "https://doi.org/10.1073/pnas.172399499",
    category: "Power, computation and thermodynamics",
    strength: "primary",
    modules: ["power-budget"],
    grounds: "The ~20 W resting human brain, used as the reference scale for intelligence-per-watt.",
  },
  {
    id: "sandberg-bostrom-2008",
    short: "Sandberg & Bostrom 2008",
    authors: "A. Sandberg & N. Bostrom",
    year: "2008",
    title: "Whole Brain Emulation: A Roadmap",
    venue: "Future of Humanity Institute Technical Report 2008-3, University of Oxford",
    url: "https://ora.ox.ac.uk/objects/uuid:a6880196-34c7-47a0-80f1-74d32ab98788",
    category: "Power, computation and thermodynamics",
    strength: "grey",
    modules: ["power-budget"],
    grounds:
      "The ~1e18 FLOPS brain-compute estimate, tagged [ESTIMATE] with roughly +/- 2 orders of magnitude of uncertainty; used only as an order-of-magnitude scale marker.",
  },
  {
    id: "codata-si",
    short: "CODATA / BIPM SI",
    authors: "BIPM / CODATA",
    year: "2019",
    title: "SI Brochure and CODATA recommended values",
    venue: "Bureau International des Poids et Mesures",
    url: "https://www.bipm.org/en/publications/si-brochure",
    category: "Power, computation and thermodynamics",
    strength: "reference",
    modules: ["power-budget", "launch-economics"],
    grounds: "Definitional constants: the Boltzmann constant (1.380649e-23 J/K, exact) and standard gravity (9.80665 m/s2, exact).",
  },

  // -- Launch and propulsion ---------------------------------------------------------
  {
    id: "tsiolkovsky-1903",
    short: "Tsiolkovsky rocket equation",
    authors: "K. Tsiolkovsky; Curtis; Sutton & Biblarz",
    year: "1903",
    title: "The rocket equation, m0/mf = exp(dv / ve), with standard dv and Isp tables",
    venue: "Tsiolkovsky (1903); Curtis, Orbital Mechanics; Sutton & Biblarz, Rocket Propulsion Elements",
    url: null,
    category: "Launch and propulsion",
    strength: "reference",
    modules: ["launch-economics", "mission"],
    grounds: "The exponential propellant penalty with delta-v, and the representative delta-v budgets and specific-impulse ranges the scenarios use.",
  },
  {
    id: "spacex-capabilities",
    short: "SpaceX Capabilities & Services",
    authors: "SpaceX",
    year: "n.d.",
    title: "Capabilities & Services (published launch pricing)",
    venue: "SpaceX (company document)",
    url: "https://www.spacex.com/media/Capabilities&Services.pdf",
    category: "Launch and propulsion",
    strength: "vendor",
    modules: ["launch-economics", "mission"],
    grounds:
      "Representative launch cost to LEO: ~$3,000/kg (Falcon 9 reusable list price) and ~$1,500/kg (Falcon Heavy). A vendor list price, treated as a ballpark scenario input, not a precise cost.",
  },
  {
    id: "nasa-fission-surface-power",
    short: "NASA Fission Surface Power",
    authors: "NASA Glenn Research Center",
    year: "2022",
    title: "Fission Surface Power Project",
    venue: "NASA",
    url: "https://www.nasa.gov/centers-and-facilities/glenn/nasas-fission-surface-power-project-energizes-lunar-exploration/",
    category: "Launch and propulsion",
    strength: "reference",
    modules: ["closure-sim"],
    grounds: "A real near-term lunar reactor (40 kW under 6 t), the sanity check on the seed factory's power-plant mass.",
  },

  // -- Solar and planetary environment -----------------------------------------------
  {
    id: "kopp-lean-2011",
    short: "Kopp & Lean 2011",
    authors: "G. Kopp & J. L. Lean",
    year: "2011",
    title: "A new, lower value of total solar irradiance",
    venue: "Geophys. Res. Lett. 38, L01706, DOI 10.1029/2010GL045777",
    url: "https://doi.org/10.1029/2010GL045777",
    category: "Solar and planetary environment",
    strength: "primary",
    modules: ["probe-sim", "mission", "multi-probe"],
    grounds: "The total solar irradiance at 1 AU, 1360.8 +/- 0.5 W/m2, the constant all inverse-square power falls off from.",
  },
  {
    id: "nasa-planetary-fact-sheet",
    short: "NASA Planetary Fact Sheet",
    authors: "NASA / NSSDC",
    year: "n.d.",
    title: "Planetary Fact Sheet",
    venue: "NASA National Space Science Data Center",
    url: "https://nssdc.gsfc.nasa.gov/planetary/factsheet/",
    category: "Solar and planetary environment",
    strength: "reference",
    modules: ["probe-sim", "mission", "swarm"],
    grounds: "Mean heliocentric distances (Earth 1.0, Mars 1.524, Jupiter 5.203, Saturn 9.582 AU) used for the destinations and light-time anchors.",
  },

  // -- Swarm dynamics and slingshots -------------------------------------------------
  {
    id: "nicholson-forgan-2013",
    short: "Nicholson & Forgan 2013",
    authors: "A. Nicholson & D. Forgan",
    year: "2013",
    title: "Slingshot Dynamics for Self-Replicating Probes and the Effect on Exploration Timescales (arXiv:1307.1648)",
    venue: "Int. J. Astrobiology 12, 337",
    url: "https://arxiv.org/abs/1307.1648",
    category: "Swarm dynamics and slingshots",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The swarm's whole basis: powered cruise speed 3e-5 c, uniform 1 star/pc3 density, the gravitational-slingshot boost (their Eq. 3 and 4, solar u_esc ~617.5 km/s), and the finding that nearest-star slingshots beat max-boost on time.",
  },
  {
    id: "iau-2015",
    short: "IAU 2015 definitions",
    authors: "International Astronomical Union",
    year: "2015",
    title: "IAU 2015 Resolution B2 (parsec and nominal solar/planetary values)",
    venue: "IAU",
    url: "https://www.iau.org/static/resolutions/IAU2015_English.pdf",
    category: "Swarm dynamics and slingshots",
    strength: "reference",
    modules: ["swarm"],
    grounds: "The parsec definition (1 pc = 3.0856775814913673e13 km) used to derive the speed of light in pc/yr and the slingshot constants.",
  },
  {
    id: "carroll-nellenback-2019",
    short: "Carroll-Nellenback et al. 2019",
    authors: "J. Carroll-Nellenback, A. Frank, J. Wright & C. Scharf",
    year: "2019",
    title: "The Fermi Paradox and the Aurora Effect (arXiv:1902.04450)",
    venue: "Astronomical Journal",
    url: "https://arxiv.org/abs/1902.04450",
    category: "Swarm dynamics and slingshots",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The higher probe-speed range (toward 0.1 c) and the \"Aurora effect\" steady state X_eq = 1 - T_launch/T_settle that a future settlement-death term would reproduce.",
  },
  {
    id: "recons-census",
    short: "RECONS / Gaia nearby-star census",
    authors: "RECONS; Gaia",
    year: "2018",
    title: "Nearby-star census (10-parsec sample and parallaxes)",
    venue: "RECONS / ESA Gaia",
    url: "http://www.recons.org/census.posted.htm",
    category: "Swarm dynamics and slingshots",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The real solar-neighborhood stellar density (~0.14 stars/pc3, the contrast to the paper's uniform 1/pc3) and the Proxima Centauri distance (1.301 pc) used as a coordination-lag anchor.",
  },

  // -- Coordination and communication delay ------------------------------------------
  {
    id: "olfati-saber-murray-2004",
    short: "Olfati-Saber & Murray 2004",
    authors: "R. Olfati-Saber & R. M. Murray",
    year: "2004",
    title: "Consensus Problems in Networks of Agents with Switching Topology and Time-Delays",
    venue: "IEEE Trans. Automatic Control 49(9), DOI 10.1109/TAC.2004.834113",
    url: "https://doi.org/10.1109/TAC.2004.834113",
    category: "Coordination and communication delay",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The formal result that consensus among agents degrades with delay (stable only while the one-hop delay stays below a bound) - the basis for the rho = latency / decision-timescale ratio.",
  },
  {
    id: "ferrell-1965",
    short: "Ferrell 1965",
    authors: "W. R. Ferrell",
    year: "1965",
    title: "Remote Manipulation with Transmission Delay (NASA TN D-2665)",
    venue: "NASA Technical Note, NTRS 19650052768",
    url: "https://ntrs.nasa.gov/citations/19650052768",
    category: "Coordination and communication delay",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The ~1 s threshold where continuous teleoperation breaks down into \"move-and-wait\" - the lowest two coordination rungs.",
  },
  {
    id: "ferrell-sheridan-1967",
    short: "Ferrell & Sheridan 1967",
    authors: "W. R. Ferrell & T. B. Sheridan",
    year: "1967",
    title: "Supervisory Control of Remote Manipulation",
    venue: "IEEE Spectrum 4(10)",
    url: null,
    category: "Coordination and communication delay",
    strength: "primary",
    modules: ["swarm"],
    grounds: "The supervisory-control regime (send goals, the remote node executes) - the middle coordination rung.",
  },
  {
    id: "rfc-4838",
    short: "RFC 4838",
    authors: "V. Cerf, S. Burleigh et al.",
    year: "2007",
    title: "Delay-Tolerant Networking Architecture",
    venue: "IETF RFC 4838",
    url: "https://www.rfc-editor.org/info/rfc4838",
    category: "Coordination and communication delay",
    strength: "primary",
    modules: ["swarm"],
    grounds: "Store-and-forward, hop-by-hop custody transfer with no real-time path - the delay-tolerant coordination rung.",
  },
];

const BY_ID: Map<string, { source: Source; index: number }> = new Map(
  SOURCES.map((source, index) => [source.id, { source, index }]),
);

/** The source record for an id, or undefined if unknown. */
export function sourceById(id: string): Source | undefined {
  return BY_ID.get(id)?.source;
}

/** The 1-based citation number a reader sees ([n]), or 0 if the id is unknown. */
export function sourceNumber(id: string): number {
  const hit = BY_ID.get(id);
  return hit ? hit.index + 1 : 0;
}

/** The distinct categories, in the order they appear in SOURCES (for the bibliography sections). */
export function sourceCategories(): SourceCategory[] {
  const seen: SourceCategory[] = [];
  for (const s of SOURCES) if (!seen.includes(s.category)) seen.push(s.category);
  return seen;
}

/** Human-readable label for a strength tier (shown in the bibliography). */
export const STRENGTH_LABEL: Record<SourceStrength, string> = {
  primary: "peer-reviewed / standard / agency report",
  reference: "definitional or reference data",
  grey: "preprint or non-refereed",
  vendor: "vendor-published figure",
  wiki: "community wiki (cross-check only)",
};
