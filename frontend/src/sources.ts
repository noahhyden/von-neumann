/**
 * The project-wide bibliography, consolidated from every module's REFERENCES.md into
 * one sourced list. Pure data, zero pimas imports (Layer A testable, CLAUDE.md 7):
 * the reactive skin (a <Cite> marker and the Sources surface in main.tsx) reads this,
 * it never writes it.
 *
 * Two kinds of entry live here, both traced (CLAUDE.md 1), nothing invented: (1) the
 * load-bearing sources whose numbers are used in a module and recorded in that module's
 * REFERENCES.md, and (2) further-reading / cross-check sources that ground a module's
 * ideas without a number appearing in code - a bibliography is broader than the code that
 * cites it. Every entry is still attributed to the module(s) it is relevant to (`modules`)
 * and listed in that module's REFERENCES.md, so the invariant "a source here exists in a
 * REFERENCES.md" holds for both kinds. `url: null` means the repo cites the work by
 * journal / report reference without a link (a textbook, an IAU resolution, a paywalled
 * DOI), not that a link was dropped. `strength` records how a reviewer should weigh it, so
 * the public bibliography is honest about which claims rest on peer-reviewed work and which
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
  /** Which module(s) this source is relevant to (cited by, or listed as further reading). */
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

  {
    id: "von-neumann-burks-1966",
    short: "von Neumann & Burks 1966",
    authors: "J. von Neumann; ed. A. W. Burks",
    year: "1966",
    title: "Theory of Self-Reproducing Automata",
    venue: "University of Illinois Press, Urbana",
    url: "https://archive.org/details/theoryofselfrepr00vonn_0",
    category: "Self-replicating machines",
    strength: "reference",
    modules: ["closure-sim"],
    grounds:
      "The origin of the idea: von Neumann's universal constructor proved a machine can build a copy of itself if it carries both a construction description and a way to copy that description - the information-closure half of the matter / energy / information framing every seed-factory claim rests on.",
  },
  {
    id: "metzger-2013",
    short: "Metzger et al. 2013",
    authors: "P. T. Metzger, A. Muscatello, R. P. Mueller & J. Mantovani",
    year: "2013",
    title: "Affordable, Rapid Bootstrapping of the Space Industry and Solar System Civilization (arXiv:1612.03238)",
    venue: "Journal of Aerospace Engineering 26(1):18-29, DOI 10.1061/(ASCE)AS.1943-5525.0000236",
    url: "https://arxiv.org/abs/1612.03238",
    category: "Self-replicating machines",
    strength: "primary",
    modules: ["closure-sim", "mission"],
    grounds:
      "The modern quantitative counterpart to NASA CP-2255: ~12 t of landed hardware bootstrapping to 156-40,000 t of industrial assets over ~20 years via robotics and additive manufacturing, starting sub-replicating (teleoperated, importing vitamins) and spiralling toward autonomy, with electronics staying Earth-sourced. Grounds the seed-mass, doubling-time, and partial-closure-then-grow dynamics.",
  },
  {
    id: "chirikjian-2004-niac",
    short: "Chirikjian 2004 (NIAC)",
    authors: "G. S. Chirikjian",
    year: "2004",
    title: "An Architecture for Self-Replicating Lunar Factories",
    venue: "NASA Institute for Advanced Concepts (NIAC) Phase I Final Report, study 880",
    url: "https://www.niac.usra.edu/files/studies/final_report/880Chirikjian.pdf",
    category: "Self-replicating machines",
    strength: "primary",
    modules: ["closure-sim"],
    grounds:
      "A concrete subsystem architecture for exactly the object closure-sim models: a lunar factory that mines regolith, refines materials, and assembles copies of itself, decomposed into robots, refining, parts fabrication, and assembly. Grounds the what-must-a-real-factory-be-made-of breakdown and the teleoperation-to-autonomy path.",
  },
  {
    id: "moses-chirikjian-2020",
    short: "Moses & Chirikjian 2020",
    authors: "M. S. Moses & G. S. Chirikjian",
    year: "2020",
    title: "Robotic Self-Replication",
    venue: "Annual Review of Control, Robotics, and Autonomous Systems 3:1-24, DOI 10.1146/annurev-control-071819-010010",
    url: "https://www.annualreviews.org/content/journals/10.1146/annurev-control-071819-010010",
    category: "Self-replicating machines",
    strength: "primary",
    modules: ["closure-sim"],
    grounds:
      "The modern survey tying the strands together: the principles required to make self-replicating robots from raw materials, the role of 3D printing, and the key distinction between closure of parts and closure of the fabrication processes that make them.",
  },
  {
    id: "sagan-newman-1983",
    short: "Sagan & Newman 1983",
    authors: "C. Sagan & W. I. Newman",
    year: "1983",
    title: "The Solipsist Approach to Extraterrestrial Intelligence",
    venue: "Quarterly Journal of the Royal Astronomical Society 24:113-121",
    url: "https://ui.adsabs.harvard.edu/abs/1983QJRAS..24..113S/abstract",
    category: "Self-replicating machines",
    strength: "primary",
    modules: ["closure-sim"],
    grounds:
      "The canonical rebuttal to Tipler: self-replicating probes are inherently dangerous and hard to control (an unchecked replicator would consume the galaxy's mass), so a civilization would avoid or destroy them. Grounds the control / containment concerns and the sensitivity of outcomes to replication rate.",
  },
  {
    id: "zykov-lipson-2005",
    short: "Zykov et al. 2005",
    authors: "V. Zykov, E. Mytilinaios, B. Adams & H. Lipson",
    year: "2005",
    title: "Robotics: Self-Reproducing Machines",
    venue: "Nature 435(7039):163-164, DOI 10.1038/435163a",
    url: "https://www.nature.com/articles/435163a",
    category: "Self-replicating machines",
    strength: "primary",
    modules: ["closure-sim"],
    grounds:
      "A physical demonstration that mechanical self-reproduction is real, not just theory: modular molecube robots that pick up identical cubes from feeding stations and assemble a working copy. Grounds the plausibility of physical (not just computational) self-replication and the identical-modules-plus-feedstock model of closure.",
  },
  {
    id: "reprap-jones-2011",
    short: "Jones et al. 2011 (RepRap)",
    authors: "R. Jones, P. Haufe, E. Sells, P. Iravani, V. Olliver, C. Palmer & A. Bowyer",
    year: "2011",
    title: "RepRap - the Replicating Rapid Prototyper",
    venue: "Robotica 29(1):177-191, DOI 10.1017/S026357471000069X",
    url: "https://www.cambridge.org/core/journals/robotica/article/reprap-the-replicating-rapid-prototyper/5979FD7B0C066CBCE43EEAD869E871AA",
    category: "Self-replicating machines",
    strength: "primary",
    modules: ["closure-sim"],
    grounds:
      "The best real-world data point on partial self-replication: an open-source 3D printer that prints a large fraction of its own parts but not motors, electronics, or rods, with measured reproductive spread. A terrestrial echo of the electronics wall - a machine can close on structure but must import the high-tech vitamins.",
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

  {
    id: "boyd-2012",
    short: "Boyd 2012",
    authors: "S. B. Boyd",
    year: "2012",
    title: "Life-Cycle Assessment of Semiconductors",
    venue: "Springer (from the 2009 Stanford PhD dissertation), DOI 10.1007/978-1-4419-9988-7",
    url: "https://escholarship.org/uc/item/8bv2s63d",
    category: "Manufacturing and embodied energy",
    strength: "primary",
    modules: ["closure-sim"],
    grounds:
      "The most complete transparent process-level LCA of CMOS logic, DRAM, and flash across seven technology generations - the strongest independent anchor for the finished-chip embodied-energy figure behind the 8,000 kWh/kg headline, and how it moves with node and yield.",
  },
  {
    id: "gutowski-2009",
    short: "Gutowski et al. 2009",
    authors: "T. G. Gutowski, M. S. Branham, J. B. Dahmus, A. J. Jones & D. P. Sekulic",
    year: "2009",
    title: "Thermodynamic Analysis of Resources Used in Manufacturing Processes",
    venue: "Environmental Science & Technology 43(5):1584-1590, DOI 10.1021/es8016655",
    url: "https://doi.org/10.1021/es8016655",
    category: "Manufacturing and embodied energy",
    strength: "primary",
    modules: ["closure-sim"],
    grounds:
      "Across 20 processes, electricity used per kg of material rises by orders of magnitude from conventional metal shaping (casting, machining) to vapor-phase semiconductor processes - the exergy-based, physics-grounded basis for the central claim that chips cost roughly 1,000x more energy per kg than smelted metal.",
  },
  {
    id: "murphy-2003",
    short: "Murphy et al. 2003",
    authors: "C. F. Murphy, G. A. Kenig, D. T. Allen, J.-P. Laurent & D. E. Dyer",
    year: "2003",
    title: "Development of Parametric Material, Energy, and Emission Inventories for Wafer Fabrication in the Semiconductor Industry",
    venue: "Environmental Science & Technology 37(23):5373-5382, DOI 10.1021/es034434g",
    url: "https://doi.org/10.1021/es034434g",
    category: "Manufacturing and embodied energy",
    strength: "primary",
    modules: ["closure-sim"],
    grounds:
      "A bottom-up per-wafer energy and materials inventory for the fab itself - grounds the blank-wafer basis end of the chip energy range (about 1,800 kWh/kg for a bare wafer vs. thousands for a packaged part), and documents why the measurement basis you pick swings the number.",
  },
  {
    id: "kuehr-williams-2003",
    short: "Kuehr & Williams 2003",
    authors: "R. Kuehr & E. Williams (eds.)",
    year: "2003",
    title: "Computers and the Environment: Understanding and Managing their Impacts",
    venue: "Kluwer / Springer, Eco-Efficiency in Industry and Science vol. 14, DOI 10.1007/978-94-010-0033-8",
    url: "https://doi.org/10.1007/978-94-010-0033-8",
    category: "Manufacturing and embodied energy",
    strength: "reference",
    modules: ["closure-sim"],
    grounds:
      "Established the material-intensity-of-computing case (a desktop PC takes on the order of 240 kg of fossil fuel, 22 kg of chemicals, and 1,500 kg of water to make) - the broader-context companion to Williams' 1.7 Kilogram Microchip, reinforcing why electronics are the hard-to-close vitamins.",
  },
  {
    id: "ashby-2012",
    short: "Ashby 2012",
    authors: "M. F. Ashby",
    year: "2012",
    title: "Materials and the Environment: Eco-informed Material Choice (2nd ed.)",
    venue: "Butterworth-Heinemann / Elsevier, ISBN 978-0-12-385971-6",
    url: "https://shop.elsevier.com/books/materials-and-the-environment/ashby/978-0-12-385971-6",
    category: "Manufacturing and embodied energy",
    strength: "reference",
    modules: ["closure-sim"],
    grounds:
      "Standard-reference embodied-energy and carbon datasheets for common materials - grounds the cheap-to-make structural end of the per-part table (metals at single-digit to tens of kWh/kg) and is an independent cross-check on the ICE coefficients already cited.",
  },
  {
    id: "guerrero-zabel-2023",
    short: "Guerrero-Gonzalez & Zabel 2023",
    authors: "F. J. Guerrero-Gonzalez & P. Zabel",
    year: "2023",
    title: "System analysis of an ISRU production plant: Extraction of metals and oxygen from lunar regolith",
    venue: "Acta Astronautica 203:187-201, DOI 10.1016/j.actaastro.2022.11.050",
    url: "https://ui.adsabs.harvard.edu/abs/2023AcAau.203..187G/abstract",
    category: "Manufacturing and embodied energy",
    strength: "primary",
    modules: ["closure-sim"],
    grounds:
      "Detailed off-world energy and hardware budgets for molten regolith electrolysis and FFC-Cambridge processing (e.g. a ~6,776 kg plant making 25 t/yr ferrosilicon plus oxygen). Directly addresses the open caveat that the project uses terrestrial smelting energy as a stand-in - this gives the actual in-situ kWh/kg for making structural metal on the Moon.",
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

  {
    id: "lloyd-2000",
    short: "Lloyd 2000",
    authors: "S. Lloyd",
    year: "2000",
    title: "Ultimate physical limits to computation",
    venue: "Nature 406:1047-1054, DOI 10.1038/35023282",
    url: "https://doi.org/10.1038/35023282",
    category: "Power, computation and thermodynamics",
    strength: "primary",
    modules: ["power-budget"],
    grounds:
      "Extends the Landauer floor into the full physical ceiling on computation: operations-per-second bounded by available energy, memory by degrees of freedom. Grounds the hard-physical-ceiling framing beyond the per-bit erasure cost.",
  },
  {
    id: "koomey-2011",
    short: "Koomey et al. 2011",
    authors: "J. G. Koomey, S. Berard, M. Sanchez & H. Wong",
    year: "2011",
    title: "Implications of Historical Trends in the Electrical Efficiency of Computing",
    venue: "IEEE Annals of the History of Computing 33(3):46-54, DOI 10.1109/MAHC.2010.28",
    url: "https://doi.org/10.1109/MAHC.2010.28",
    category: "Power, computation and thermodynamics",
    strength: "primary",
    modules: ["power-budget"],
    grounds:
      "Koomey's law: computations per joule doubled roughly every 1.6 years for six decades. Grounds the compute-efficiency (FLOPS/W) input as a historically-quantified moving figure and sizes the gap between present hardware and the Landauer ceiling.",
  },
  {
    id: "bennett-1982",
    short: "Bennett 1982",
    authors: "C. H. Bennett",
    year: "1982",
    title: "The Thermodynamics of Computation - a Review",
    venue: "International Journal of Theoretical Physics 21(12):905-940, DOI 10.1007/BF02084158",
    url: "https://doi.org/10.1007/BF02084158",
    category: "Power, computation and thermodynamics",
    strength: "primary",
    modules: ["power-budget"],
    grounds:
      "Establishes that only logically irreversible operations (bit erasure) must dissipate kT ln2, while reversible computation can in principle dodge the floor. Grounds why compute is floored at the Landauer limit for irreversible bit-operations specifically, not for computation in general.",
  },
  {
    id: "markov-2014",
    short: "Markov 2014",
    authors: "I. L. Markov",
    year: "2014",
    title: "Limits on fundamental limits to computation (arXiv:1408.3821)",
    venue: "Nature 512:147-154, DOI 10.1038/nature13570",
    url: "https://doi.org/10.1038/nature13570",
    category: "Power, computation and thermodynamics",
    strength: "primary",
    modules: ["power-budget"],
    grounds:
      "A critical survey separating firm limits (energy, thermodynamics) from soft ones and showing which have been engineered around. Grounds the honesty that the Landauer floor is a real bound while present hardware sits many orders of magnitude above it.",
  },
  {
    id: "attwell-laughlin-2001",
    short: "Attwell & Laughlin 2001",
    authors: "D. Attwell & S. B. Laughlin",
    year: "2001",
    title: "An Energy Budget for Signaling in the Grey Matter of the Brain",
    venue: "J. Cerebral Blood Flow & Metabolism 21(10):1133-1145, DOI 10.1097/00004647-200110000-00001",
    url: "https://doi.org/10.1097/00004647-200110000-00001",
    category: "Power, computation and thermodynamics",
    strength: "primary",
    modules: ["power-budget"],
    grounds:
      "Breaks the brain's power draw down per signaling event, yielding a bottom-up energy-per-bit for neural computation. Complements the top-down ~20 W brain anchor with the mechanistic cost of one bit of neural signaling.",
  },
  {
    id: "shockley-queisser-1961",
    short: "Shockley & Queisser 1961",
    authors: "W. Shockley & H. J. Queisser",
    year: "1961",
    title: "Detailed Balance Limit of Efficiency of p-n Junction Solar Cells",
    venue: "Journal of Applied Physics 32(3):510-519, DOI 10.1063/1.1736034",
    url: "https://doi.org/10.1063/1.1736034",
    category: "Power, computation and thermodynamics",
    strength: "primary",
    modules: ["power-budget"],
    grounds:
      "The thermodynamic (detailed-balance) ceiling on single-junction photovoltaic conversion, about 30% at 1.1 eV. Grounds the solar-limited premise: only a bounded fraction of incident solar flux becomes electrical watts, setting the upper bound on the budget split among manufacturing, compute, and housekeeping.",
  },
  {
    id: "gilmore-2002",
    short: "Gilmore 2002",
    authors: "D. G. Gilmore (ed.), The Aerospace Corporation",
    year: "2002",
    title: "Spacecraft Thermal Control Handbook, Volume I: Fundamental Technologies (2nd ed.)",
    venue: "The Aerospace Press / AIAA, DOI 10.2514/4.989117",
    url: "https://arc.aiaa.org/doi/book/10.2514/4.989117",
    category: "Power, computation and thermodynamics",
    strength: "reference",
    modules: ["power-budget"],
    grounds:
      "Waste-heat rejection in vacuum is radiation-only, Q = e*sigma*A*(T^4 - T_env^4), so radiator area and temperature set what power a system can dissipate. Grounds the housekeeping / thermal side of the budget and the radiator temperature T that the Landauer floor scales with.",
  },
  {
    id: "nasa-soa-power-2024",
    short: "NASA SoA Small Spacecraft Power 2024",
    authors: "NASA Ames Research Center (Small Spacecraft Systems Virtual Institute)",
    year: "2024",
    title: "State of the Art of Small Spacecraft Technology - Power chapter",
    venue: "NASA / Ames Research Center technical report (2024 edition)",
    url: "https://www.nasa.gov/wp-content/uploads/2025/02/3-soa-power-2024.pdf",
    category: "Power, computation and thermodynamics",
    strength: "reference",
    modules: ["power-budget"],
    grounds:
      "Space solar-array specific power in W/kg (roll-out arrays about 75 W/kg; flexible arrays demonstrated toward hundreds of W/kg). Grounds the mass cost of the power source that feeds the whole budget - how many kilograms of array a solar-limited watt requires.",
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

  {
    id: "sutton-biblarz-2016",
    short: "Sutton & Biblarz 2016",
    authors: "G. P. Sutton & O. Biblarz",
    year: "2016",
    title: "Rocket Propulsion Elements (9th ed.)",
    venue: "Wiley, ISBN 978-1-118-75365-1",
    url: "https://www.wiley.com/en-us/Rocket+Propulsion+Elements,+9th+Edition-p-9781118753651",
    category: "Launch and propulsion",
    strength: "reference",
    modules: ["launch-economics", "mission"],
    grounds:
      "The standard text behind the rocket equation and the chemical specific-impulse ranges the scenarios use (LOX/RP-1 ~280-340 s, LOX/LH2 ~450 s). Pins the previously bundled Sutton & Biblarz mention to a specific edition.",
  },
  {
    id: "curtis-2020",
    short: "Curtis 2020",
    authors: "H. D. Curtis",
    year: "2020",
    title: "Orbital Mechanics for Engineering Students (4th ed.)",
    venue: "Butterworth-Heinemann (Elsevier), ISBN 978-0-12-824025-0",
    url: "https://shop.elsevier.com/books/orbital-mechanics-for-engineering-students/curtis/978-0-12-824025-0",
    category: "Launch and propulsion",
    strength: "reference",
    modules: ["launch-economics", "mission"],
    grounds:
      "Grounds the rocket-equation derivation and the representative delta-v budgets (surface-to-LEO ~9.3-10 km/s, LEO-to-TLI ~3.1 km/s, LEO-to-Mars ~3.6 km/s) that drive the mass-ratio computation.",
  },
  {
    id: "jones-2018-launch-cost",
    short: "Jones 2018",
    authors: "H. W. Jones (NASA Ames)",
    year: "2018",
    title: "The Recent Large Reduction in Space Launch Cost (ICES-2018-81)",
    venue: "48th International Conference on Environmental Systems; NASA NTRS 20200001093",
    url: "https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20200001093.pdf",
    category: "Launch and propulsion",
    strength: "primary",
    modules: ["launch-economics"],
    grounds:
      "An independent, NASA-authored cross-check on the module's $/kg-to-LEO scenario inputs: Shuttle ~$54,500/kg vs Falcon 9 ~$2,720/kg, a roughly 20x reduction. Corroborates the SpaceX vendor list price with an agency analysis.",
  },
  {
    id: "goebel-katz-2008",
    short: "Goebel & Katz 2008",
    authors: "D. M. Goebel & I. Katz (JPL)",
    year: "2008",
    title: "Fundamentals of Electric Propulsion: Ion and Hall Thrusters",
    venue: "JPL Space Science and Technology Series, Wiley, DOI 10.1002/9780470436448",
    url: "https://onlinelibrary.wiley.com/doi/book/10.1002/9780470436448",
    category: "Launch and propulsion",
    strength: "reference",
    modules: ["launch-economics"],
    grounds:
      "The standard text grounding the electric / ion specific-impulse band (~1,500-4,000 s) - the high-Isp end that makes deep-space transfer far cheaper in propellant than chemical.",
  },
  {
    id: "next-c-2021",
    short: "NEXT-C 2021",
    authors: "NASA Glenn Research Center (NEXT-C flight team)",
    year: "2021",
    title: "A Summary of the NEXT-C Flight Thruster Proto-flight Testing",
    venue: "NASA NTRS 20210018563 / AIAA",
    url: "https://ntrs.nasa.gov/api/citations/20210018563/downloads/NEXT-C%20AIAA%20Paper%202021%20FINAL.pdf",
    category: "Launch and propulsion",
    strength: "primary",
    modules: ["launch-economics"],
    grounds:
      "A flight-qualified data point at the top of the electric Isp range: ~4,190 s at 6.9 kW, flown on DART (2021). Shows the upper electric-Isp bound is a demonstrated value, not just a textbook span.",
  },
  {
    id: "borowski-2012-ntr",
    short: "Borowski et al. 2012",
    authors: "S. K. Borowski, D. R. McCurdy & T. W. Packard (NASA Glenn)",
    year: "2012",
    title: "Nuclear Thermal Rocket (NTR) Propulsion: A Proven Game-Changing Technology for Future Human Exploration Missions",
    venue: "NASA NTRS 20120009207",
    url: "https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20120009207.pdf",
    category: "Launch and propulsion",
    strength: "primary",
    modules: ["launch-economics"],
    grounds:
      "Fills the Isp gap between chemical (~450 s) and electric (thousands of s): nuclear thermal at ~900 s, an intermediate propulsion option for moving seed mass with less propellant penalty.",
  },
  {
    id: "lubin-2016",
    short: "Lubin 2016",
    authors: "P. Lubin (UC Santa Barbara)",
    year: "2016",
    title: "A Roadmap to Interstellar Flight (arXiv:1604.01356)",
    venue: "Journal of the British Interplanetary Society 69:40-72",
    url: "https://arxiv.org/abs/1604.01356",
    category: "Launch and propulsion",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The far end of the propulsion spectrum for a self-replicating seed: beamed directed-energy light-sail acceleration of gram-scale craft toward ~0.2c, sidestepping the rocket-equation penalty by leaving the energy source at home. Connects to the swarm's interstellar cruise-speed assumptions.",
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

  {
    id: "astm-e490",
    short: "ASTM E490",
    authors: "ASTM International (Subcommittee E21.04)",
    year: "2019",
    title: "Standard Solar Constant and Zero Air Mass Solar Spectral Irradiance Tables (E490-00a(2019))",
    venue: "ASTM International standard",
    url: "https://www.astm.org/e0490-00ar19.html",
    category: "Solar and planetary environment",
    strength: "reference",
    modules: ["probe-sim", "mission"],
    grounds:
      "The aerospace-community AM0 reference: the extraterrestrial solar constant (1366.1 W/m2) and the full solar spectrum at 1 AU. The standards-body cross-check on the 1-AU irradiance (complementing Kopp & Lean's measured 1360.8) and it fixes the spectrum a space solar cell actually converts.",
  },
  {
    id: "juno-solar-2016",
    short: "Juno solar-power record (JPL)",
    authors: "NASA Jet Propulsion Laboratory",
    year: "2016",
    title: "NASA's Juno Spacecraft Breaks Solar Power Distance Record",
    venue: "NASA / JPL news release",
    url: "https://www.jpl.nasa.gov/news/nasas-juno-spacecraft-breaks-solar-power-distance-record/",
    category: "Solar and planetary environment",
    strength: "reference",
    modules: ["probe-sim"],
    grounds:
      "The real deep-space anchor for the 1/d^2 range gate: Juno's ~50 m2 of cells make ~14 kW at 1 AU but only ~500 W at Jupiter (~5.2 AU). A flown validation that the inverse-square falloff and the outer-system power limit in probe-sim match a real solar-powered mission.",
  },
  {
    id: "landis-bailey-2002",
    short: "Landis & Bailey 2002",
    authors: "G. A. Landis & S. G. Bailey (NASA Glenn Research Center)",
    year: "2002",
    title: "Photovoltaic Power for Future NASA Missions (AIAA-2002-0718)",
    venue: "AIAA 40th Aerospace Sciences Meeting; NASA NTRS 20030006444",
    url: "https://ntrs.nasa.gov/citations/20030006444",
    category: "Solar and planetary environment",
    strength: "primary",
    modules: ["probe-sim"],
    grounds:
      "Space multi-junction cell performance vs distance and temperature: triple-junction GaInP/GaAs/Ge cells at ~27% AM0, and the low-intensity / low-temperature behaviour far from the Sun. Grounds probe-sim's solar-array efficiency input (currently an [ESTIMATE] at 0.30).",
  },
  {
    id: "elvis-2014",
    short: "Elvis 2014",
    authors: "M. Elvis",
    year: "2014",
    title: "How Many Ore-Bearing Asteroids? (arXiv:1312.4450)",
    venue: "Planetary and Space Science 91:20-26",
    url: "https://arxiv.org/abs/1312.4450",
    category: "Solar and planetary environment",
    strength: "primary",
    modules: ["closure-sim"],
    grounds:
      "The scarcity of minable feedstock: only about 1 in 2000 accessible near-Earth asteroids is platinum-group ore-bearing and ~1 in 1100 is water-ore-bearing. Grounds the resource-availability assumption behind a probe or seed factory that must harvest local material rather than assume any asteroid will do.",
  },
  {
    id: "demeo-carry-2014",
    short: "DeMeo & Carry 2014",
    authors: "F. E. DeMeo & B. Carry",
    year: "2014",
    title: "Solar System evolution from compositional mapping of the asteroid belt",
    venue: "Nature 505:629-634, DOI 10.1038/nature12908",
    url: "https://doi.org/10.1038/nature12908",
    category: "Solar and planetary environment",
    strength: "primary",
    modules: ["closure-sim"],
    grounds:
      "The composition of the asteroid feedstock by taxonomic class and how it is distributed by mass and heliocentric distance. Grounds what a resource-harvesting module can expect to find where - which raw materials are actually available at a given mining destination.",
  },
  {
    id: "lunar-sourcebook-1991",
    short: "Lunar Sourcebook",
    authors: "G. H. Heiken, D. T. Vaniman & B. M. French (eds.)",
    year: "1991",
    title: "Lunar Sourcebook: A User's Guide to the Moon",
    venue: "Cambridge University Press (full text hosted by LPI/USRA)",
    url: "https://www.lpi.usra.edu/publications/books/lunar_sourcebook/",
    category: "Solar and planetary environment",
    strength: "reference",
    modules: ["closure-sim"],
    grounds:
      "The definitive reference on lunar regolith and rock composition, mineralogy, and physical properties - the feedstock inventory for a factory that lands on the Moon and builds from local material. Grounds which elements (O, Si, Al, Fe, Ti, Mg) are locally available and in what abundance.",
  },
  {
    id: "moxie-hoffman-2022",
    short: "Hoffman et al. 2022 (MOXIE)",
    authors: "J. A. Hoffman, M. H. Hecht, D. Rapp et al.",
    year: "2022",
    title: "Mars Oxygen ISRU Experiment (MOXIE) - Preparing for human Mars exploration",
    venue: "Science Advances 8(35), eabp8636, DOI 10.1126/sciadv.abp8636",
    url: "https://www.science.org/doi/10.1126/sciadv.abp8636",
    category: "Solar and planetary environment",
    strength: "primary",
    modules: ["closure-sim"],
    grounds:
      "The first demonstrated in-situ resource utilization on another planet: solid-oxide electrolysis of Martian CO2 producing ~6 g O2/hr on Perseverance. Grounds the Mars-destination ISRU case - a probe can make consumables from the local atmosphere rather than importing them.",
  },
  {
    id: "nasa-mem-3",
    short: "NASA MEM 3",
    authors: "A. Moorhead et al. (NASA Meteoroid Environment Office)",
    year: "2020",
    title: "NASA Meteoroid Engineering Model (MEM) Version 3",
    venue: "NASA/TM-2020-220555; NTRS 20200000563",
    url: "https://ntrs.nasa.gov/citations/20200000563",
    category: "Solar and planetary environment",
    strength: "primary",
    modules: ["probe-sim"],
    grounds:
      "NASA's standard model of the sporadic meteoroid / micrometeoroid flux for Earth orbit, lunar orbit, and interplanetary space. Grounds the real-world-messiness hazard a long-lived probe or factory faces (impact-driven degradation and array wear) - a noise parameter, not the frictionless ideal.",
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
  {
    id: "kerr-lynden-bell-1986",
    short: "Kerr & Lynden-Bell 1986",
    authors: "F. J. Kerr & D. Lynden-Bell",
    year: "1986",
    title: "Review of galactic constants",
    venue: "Monthly Notices of the Royal Astronomical Society 221:1023-1038",
    url: "https://ui.adsabs.harvard.edu/abs/1986MNRAS.221.1023K/abstract",
    category: "Swarm dynamics and slingshots",
    strength: "reference",
    modules: ["swarm"],
    grounds:
      "The IAU-standard local circular speed (Theta0 ~220 km/s at R0 = 8.5 kpc) that grounds the ~220 km/s mean stellar speed the slingshot boost draws on and the fixed-star proper-motion caveat (a star sweeps ~225 pc per Myr).",
  },
  {
    id: "nordstrom-2004-gcs",
    short: "Nordstrom et al. 2004",
    authors: "B. Nordstrom, M. Mayor, J. Andersen and others",
    year: "2004",
    title: "The Geneva-Copenhagen survey of the solar neighbourhood",
    venue: "Astronomy & Astrophysics 418:989-1019",
    url: "https://arxiv.org/abs/astro-ph/0405198",
    category: "Swarm dynamics and slingshots",
    strength: "reference",
    modules: ["swarm"],
    grounds:
      "The local thin-disc velocity dispersion (sigma_U,V,W ~33/23/18 km/s, ~40 km/s in 3D) grounding the ~30-40 km/s peculiar-velocity spread used for the star-speed dispersion and the proper-motion limitation.",
  },

  {
    id: "forgan-papadog-kitching-2013",
    short: "Forgan, Papadogiannakis & Kitching 2013",
    authors: "D. H. Forgan, S. Papadogiannakis & T. Kitching",
    year: "2013",
    title: "The Effect of Probe Dynamics on Galactic Exploration Timescales (arXiv:1212.2371)",
    venue: "Journal of the British Interplanetary Society 66:171-178",
    url: "https://arxiv.org/abs/1212.2371",
    category: "Swarm dynamics and slingshots",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The single-probe slingshot study that Nicholson & Forgan extend to self-replicators and that swarm/REFERENCES.md defers to for the shearing-box setup and Galactic rotation speed. Establishes the headline result the swarm reproduces: slingshots cut exploration time by up to two orders of magnitude versus powered flight.",
  },
  {
    id: "bjork-2007",
    short: "Bjork 2007",
    authors: "R. Bjork",
    year: "2007",
    title: "Exploring the Galaxy using space probes (arXiv:astro-ph/0701238)",
    venue: "International Journal of Astrobiology 6(2):89-93",
    url: "https://arxiv.org/abs/astro-ph/0701238",
    category: "Swarm dynamics and slingshots",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The direct precursor to the box-of-stars exploration-timescale simulations the module runs: probes with subprobes sweeping a defined stellar volume, giving concrete fill times to sanity-check the swarm's Myr-scale fill of a finite field.",
  },
  {
    id: "newman-sagan-1981",
    short: "Newman & Sagan 1981",
    authors: "W. I. Newman & C. Sagan",
    year: "1981",
    title: "Galactic civilizations: Population dynamics and interstellar diffusion",
    venue: "Icarus 46(3):293-327",
    url: "https://www.sciencedirect.com/science/article/abs/pii/0019103581901354",
    category: "Swarm dynamics and slingshots",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The analytic settlement-front model behind the swarm's advancing boundary: colonization as a density-dependent diffusion process with a travelling-wave solution limited by carrying capacity - the continuum counterpart to the module's discrete nearest-hop front.",
  },
  {
    id: "jones-1981",
    short: "Jones 1981",
    authors: "E. M. Jones (Los Alamos Scientific Laboratory)",
    year: "1981",
    title: "Discrete calculations of interstellar migration and settlement",
    venue: "Icarus 46(3):328-336",
    url: "https://www.sciencedirect.com/science/article/abs/pii/0019103581901366",
    category: "Swarm dynamics and slingshots",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The Monte Carlo settlement model most like the swarm's own discrete fold, and a numerical check on its front speed: Jones finds a migration wavefront of ~1.4e-5 pc/yr filling the Galaxy in ~60 Myr, the same order as the swarm's front advancing at a fraction of a probe's cruise speed.",
  },
  {
    id: "hart-1975",
    short: "Hart 1975",
    authors: "M. H. Hart",
    year: "1975",
    title: "An Explanation for the Absence of Extraterrestrials on Earth",
    venue: "Quarterly Journal of the Royal Astronomical Society 16:128-135",
    url: "https://ui.adsabs.harvard.edu/abs/1975QJRAS..16..128H/abstract",
    category: "Swarm dynamics and slingshots",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The founding statement of the colonization / Fermi argument the module engages: if interstellar settlement is possible it should already be complete, so a Galaxy filling on a Myr timescale (which the swarm demonstrates) is exactly what makes the observed silence a paradox.",
  },
  {
    id: "tipler-1980",
    short: "Tipler 1980",
    authors: "F. J. Tipler",
    year: "1980",
    title: "Extraterrestrial Intelligent Beings Do Not Exist",
    venue: "Quarterly Journal of the Royal Astronomical Society 21:267-281",
    url: "https://ui.adsabs.harvard.edu/abs/1980QJRAS..21..267T/abstract",
    category: "Swarm dynamics and slingshots",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "Introduces the self-replicating (von Neumann) probe into the Fermi argument - the exact entity the swarm simulates: exponentially branching probes that saturate the Galaxy in a few million years, the few-Myr-fill claim the module makes quantitative and stress-tests under finite light-speed.",
  },
  {
    id: "cotta-morales-2009",
    short: "Cotta & Morales 2009",
    authors: "C. Cotta & A. Morales",
    year: "2009",
    title: "A Computational Analysis of Galactic Exploration with Space Probes (arXiv:0907.0345)",
    venue: "Journal of the British Interplanetary Society 62:82-88",
    url: "https://arxiv.org/abs/0907.0345",
    category: "Swarm dynamics and slingshots",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "A computational exploration model that turns fleet size, probe lifetime, and imprint persistence into bounds on how many civilizations could be quietly exploring undetected - framing the parameters (probe count, dwell / imprint time) the swarm exposes as knobs.",
  },
  {
    id: "forgan-2009",
    short: "Forgan 2009",
    authors: "D. H. Forgan",
    year: "2009",
    title: "A numerical testbed for hypotheses of extraterrestrial life and intelligence (arXiv:0810.2222)",
    venue: "International Journal of Astrobiology 8(2):121-131",
    url: "https://arxiv.org/abs/0810.2222",
    category: "Swarm dynamics and slingshots",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "Establishes the Monte Carlo, seeded-realization methodology for Fermi-paradox questions that the swarm's deterministic seeded fold follows, situating exploration timescales within a distribution of parameters rather than single-point estimates.",
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
  {
    id: "sheridan-1993",
    short: "Sheridan 1993",
    authors: "T. B. Sheridan",
    year: "1993",
    title: "Space Teleoperation Through Time Delay: Review and Prognosis",
    venue: "IEEE Trans. Robotics and Automation 9(5):592-606, DOI 10.1109/70.258052",
    url: "https://doi.org/10.1109/70.258052",
    category: "Coordination and communication delay",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The canonical review of how human control degrades as round-trip delay grows - closed-loop, then move-and-wait, then supervisory - and why beyond a delay budget you must hand autonomy to the remote node. Grounds the coordination-rung ladder and is the natural successor to the Ferrell pair already cited.",
  },
  {
    id: "olfati-saber-fax-murray-2007",
    short: "Olfati-Saber, Fax & Murray 2007",
    authors: "R. Olfati-Saber, J. A. Fax & R. M. Murray",
    year: "2007",
    title: "Consensus and Cooperation in Networked Multi-Agent Systems",
    venue: "Proceedings of the IEEE 95(1):215-233, DOI 10.1109/JPROC.2006.887293",
    url: "https://doi.org/10.1109/JPROC.2006.887293",
    category: "Coordination and communication delay",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The survey generalizing the 2004 delay-bound result into a full framework for consensus under switching topology, link failures, and delays. Grounds the rho = round-trip-latency / decision-timescale lens on when delayed agreement stays stable, and supports that a connected field still converges to 100% despite lag.",
  },
  {
    id: "burleigh-2003",
    short: "Burleigh et al. 2003",
    authors: "S. Burleigh, A. Hooke, L. Torgerson, K. Fall, V. Cerf, B. Durst, K. Scott & H. Weiss",
    year: "2003",
    title: "Delay-Tolerant Networking: An Approach to Interplanetary Internet",
    venue: "IEEE Communications Magazine 41(6):128-136, DOI 10.1109/MCOM.2003.1204759",
    url: "https://doi.org/10.1109/MCOM.2003.1204759",
    category: "Coordination and communication delay",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "Motivates delay-tolerant networking from the interplanetary case specifically - links with light-minutes to light-hours of latency and no continuous end-to-end path. Grounds the delay-tolerant rung with the actual space-communications rationale behind RFC 4838, at the Mars/Saturn latency scale the visualization anchors use.",
  },
  {
    id: "rfc-9171",
    short: "RFC 9171 (Bundle Protocol v7)",
    authors: "S. Burleigh, K. Fall & E. J. Birrane III",
    year: "2022",
    title: "Bundle Protocol Version 7",
    venue: "IETF RFC 9171 (Internet Standards Track)",
    url: "https://www.rfc-editor.org/info/rfc9171",
    category: "Coordination and communication delay",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The current Internet-standard store-and-forward protocol for delay-tolerant links, superseding the experimental RFC 5050. Grounds the delay-tolerant rung as a deployed standard - hop-by-hop custody transfer with no real-time handshake - complementing the architecture-level RFC 4838.",
  },
  {
    id: "lamport-1978",
    short: "Lamport 1978",
    authors: "L. Lamport",
    year: "1978",
    title: "Time, Clocks, and the Ordering of Events in a Distributed System",
    venue: "Communications of the ACM 21(7):558-565, DOI 10.1145/359545.359563",
    url: "https://doi.org/10.1145/359545.359563",
    category: "Coordination and communication delay",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "Establishes that when information travels at finite speed, events have only a partial (happened-before) ordering - you cannot know a remote event until its signal reaches you. Grounds the swarm's light-delayed belief model: a probe treats star i as settled only once settled_year[i] + dist/c <= Y.",
  },
  {
    id: "flp-1985",
    short: "Fischer, Lynch & Paterson 1985",
    authors: "M. J. Fischer, N. A. Lynch & M. S. Paterson",
    year: "1985",
    title: "Impossibility of Distributed Consensus with One Faulty Process",
    venue: "Journal of the ACM 32(2):374-382, DOI 10.1145/3149.214121",
    url: "https://groups.csail.mit.edu/tds/papers/Lynch/jacm85.pdf",
    category: "Coordination and communication delay",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The FLP impossibility result: in a fully asynchronous system (no bound on message delay) no protocol can guarantee agreement if even one node can fail. Grounds why the fully-independent-colonies rung is qualitatively different - guaranteed real-time consensus is not merely slow but impossible, so each node acts on pre-launch priors.",
  },
  {
    id: "gilbert-lynch-2002",
    short: "Gilbert & Lynch 2002",
    authors: "S. Gilbert & N. A. Lynch",
    year: "2002",
    title: "Brewer's Conjecture and the Feasibility of Consistent, Available, Partition-Tolerant Web Services",
    venue: "ACM SIGACT News 33(2):51-59, DOI 10.1145/564585.564601",
    url: "https://doi.org/10.1145/564585.564601",
    category: "Coordination and communication delay",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The formal CAP theorem: under network partition you must trade consistency against availability. Grounds why light-delayed probes favour availability (act now on a local view) over consistency (a single global settled-map) - the mechanism that produces the wasted long-range trips measured in the lightspeed regime.",
  },
  {
    id: "demers-1987",
    short: "Demers et al. 1987",
    authors: "A. Demers, D. Greene, C. Hauser, W. Irish, J. Larson, S. Shenker, H. Sturgis, D. Swinehart & D. Terry",
    year: "1987",
    title: "Epidemic Algorithms for Replicated Database Maintenance",
    venue: "PODC '87 (6th ACM Symp. on Principles of Distributed Computing) 1-12, DOI 10.1145/41840.41841",
    url: "https://doi.org/10.1145/41840.41841",
    category: "Coordination and communication delay",
    strength: "primary",
    modules: ["swarm"],
    grounds:
      "The foundational gossip / anti-entropy work: how state (here, which stars are settled) propagates by pairwise relay rather than central broadcast. Grounds the deferred probe-to-probe gossip-relay sibling slice named in swarm/REFERENCES.md, beyond the current omnidirectional-beacon assumption.",
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
