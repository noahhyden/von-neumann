## Check vn_core before writing a numeric helper

Before writing a numeric helper, distribution, sampler, RNG or integrator, check `vn_core` (core/: rng, uq, ode, linalg, imported by 9 of 10 modules) and modules/README.md; one consumer keeps it local, a second moves it to core, so copies never diverge.
