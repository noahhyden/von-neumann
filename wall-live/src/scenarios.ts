/**
 * The two example factories, transcribed verbatim from closure-sim's YAML
 * scenarios (scenarios/*.yaml). Kept as data so the live explainer ships no
 * YAML parser and stays a single client bundle. If the Python scenarios change,
 * re-transcribe here (the parity test pins the numbers that matter).
 */
import type { Factory } from "./model.js";

export const LUNAR_REGOLITH_SEED: Factory = {
  name: "Lunar Regolith Seed Factory",
  subsystems: [
    { name: "Structure & supports (cast regolith/metal)", mass_kg: 4000, category: "structure", producible_locally: true, processes: ["casting", "machining"], energy_to_produce_kwh_per_kg: 5.0 },
    { name: "Solar power arrays (Si refined from regolith)", mass_kg: 2500, category: "power", producible_locally: true, processes: ["refining", "additive"], energy_to_produce_kwh_per_kg: 50.0 },
    { name: "Thermal radiators", mass_kg: 800, category: "thermal", producible_locally: true, processes: ["casting", "machining"], energy_to_produce_kwh_per_kg: 3.0 },
    { name: "Actuators & motors (cast + wound wire)", mass_kg: 1500, category: "actuators", producible_locally: true, processes: ["casting", "machining", "wire_drawing"], energy_to_produce_kwh_per_kg: 15.0 },
    { name: "Robotic manipulators", mass_kg: 1200, category: "actuators", producible_locally: true, processes: ["machining", "additive"], energy_to_produce_kwh_per_kg: 18.0 },
    { name: "Refining / chemical plant", mass_kg: 1500, category: "structure", producible_locally: true, processes: ["casting", "machining"], energy_to_produce_kwh_per_kg: 7.0 },
    { name: "Basic sensors (machined optics/housings)", mass_kg: 150, category: "sensors", producible_locally: true, processes: ["machining"], energy_to_produce_kwh_per_kg: 60.0 },
    { name: "Control electronics / compute (chips)", mass_kg: 60, category: "compute", producible_locally: false, processes: ["semiconductor_fab"], energy_to_produce_kwh_per_kg: 8000.0 },
    { name: "Power electronics (inverters, driver ICs)", mass_kg: 90, category: "electronics", producible_locally: false, processes: ["semiconductor_fab"], energy_to_produce_kwh_per_kg: 2500.0 },
    { name: "Precision bearings & special alloys", mass_kg: 200, category: "structure", producible_locally: false, processes: ["machining"], energy_to_produce_kwh_per_kg: 35.0 },
  ],
  replication: {
    seed_mass_kg: 12000,
    local_build_rate_kg_per_day: 20.0,
    vitamin_resupply_mass_kg: 50.0,
    resupply_cadence_days: 30.0,
    available_power_kw: 4000.0,
    target_output_kg_per_day: 1000.0,
    duration_days: 14600,
    dt_days: 1.0,
  },
};

export const LOW_CLOSURE_OUTPOST: Factory = {
  name: "Low-Closure Outpost Factory",
  subsystems: [
    { name: "Structure (cast/printed metal)", mass_kg: 2000, category: "structure", producible_locally: true, processes: ["casting", "machining"], energy_to_produce_kwh_per_kg: 5.0 },
    { name: "Power arrays (assembled locally)", mass_kg: 1000, category: "power", producible_locally: true, processes: ["assembly"], energy_to_produce_kwh_per_kg: 50.0 },
    { name: "Compute & control electronics (chips)", mass_kg: 1500, category: "compute", producible_locally: false, processes: ["semiconductor_fab"], energy_to_produce_kwh_per_kg: 8000.0 },
    { name: "Power electronics & ICs", mass_kg: 800, category: "electronics", producible_locally: false, processes: ["semiconductor_fab"], energy_to_produce_kwh_per_kg: 2500.0 },
    { name: "Precision actuators (imported)", mass_kg: 700, category: "actuators", producible_locally: false, processes: ["machining"], energy_to_produce_kwh_per_kg: 40.0 },
    { name: "Electronic sensors / instruments", mass_kg: 500, category: "sensors", producible_locally: false, processes: ["semiconductor_fab", "assembly"], energy_to_produce_kwh_per_kg: 4000.0 },
    { name: "Specialty alloys & seals", mass_kg: 500, category: "structure", producible_locally: false, processes: ["machining"], energy_to_produce_kwh_per_kg: 35.0 },
  ],
  replication: {
    seed_mass_kg: 7000,
    local_build_rate_kg_per_day: 15.0,
    vitamin_resupply_mass_kg: 80.0,
    resupply_cadence_days: 30.0,
    available_power_kw: 2000.0,
    target_output_kg_per_day: 100.0,
    duration_days: 29200,
    dt_days: 1.0,
  },
};

export const SCENARIOS: Record<string, Factory> = {
  lunar: LUNAR_REGOLITH_SEED,
  outpost: LOW_CLOSURE_OUTPOST,
};
