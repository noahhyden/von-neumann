"""System-size sweep of the lightspeed coordination tax at the resolved (event) limit."""
from __future__ import annotations
import statistics, sys
from swarm import SwarmParams, simulate_swarm
from experiments.stats_util import sign_test_positive

SEEDS_ALL = [0x9E3779B9 + 2654435761 * k for k in range(32)]
POLICIES = ("powered", "slingshot_nearest", "slingshot_maxboost")

# seeds per N (reduce at large N; maxboost is O(N^2))
def seeds_for(n):
    if n <= 300:
        return SEEDS_ALL
    if n == 600:
        return SEEDS_ALL[:16]
    return SEEDS_ALL[:8]

N_LIST = (30, 50, 100, 200, 300, 600, 1200)
COV = ("t50", "t90", "t100")


def med(xs):
    return statistics.median(xs) if xs else float("nan")


def pct(xs):
    """median, q25, q75"""
    if not xs:
        return float("nan"), float("nan"), float("nan")
    s = sorted(xs)
    return statistics.median(s), s[len(s) // 4], s[(3 * len(s)) // 4]


def run():
    # results[pol][n] = dict of metric lists
    out = {}
    for n in N_LIST:
        seeds = seeds_for(n)
        for pol in POLICIES:
            key = (pol, n)
            # per-seed paired deltas
            time_delta_pct = {c: [] for c in COV}   # (ls-inst)/inst*100
            time_delta_abs = {c: [] for c in COV}
            fuel_delta_abs = []   # wasted_arrivals ls - inst
            fuel_delta_pct = []   # (ls-inst)/max(1,inst)*100
            wasted_inst = []
            wasted_ls = []
            n_valid = {c: 0 for c in COV}
            fill_ls = []
            fill_inst = []
            for seed in seeds:
                inst = simulate_swarm(SwarmParams(n_stars=n, policy=pol, coordination="instant", stepping="event"), seed=seed)
                ls = simulate_swarm(SwarmParams(n_stars=n, policy=pol, coordination="lightspeed", stepping="event"), seed=seed)
                for c in COV:
                    ti = getattr(inst, f"{c}_years")
                    tl = getattr(ls, f"{c}_years")
                    if ti is not None and tl is not None and ti > 0:
                        time_delta_pct[c].append((tl - ti) / ti * 100.0)
                        time_delta_abs[c].append(tl - ti)
                        n_valid[c] += 1
                fuel_delta_abs.append(ls.wasted_arrivals - inst.wasted_arrivals)
                fuel_delta_pct.append((ls.wasted_arrivals - inst.wasted_arrivals) / max(1, inst.wasted_arrivals) * 100.0)
                wasted_inst.append(inst.wasted_arrivals)
                wasted_ls.append(ls.wasted_arrivals)
                fill_ls.append(ls.final_settled == ls.n_stars)
                fill_inst.append(inst.final_settled == inst.n_stars)
            out[key] = dict(
                seeds=len(seeds),
                time_delta_pct=time_delta_pct, time_delta_abs=time_delta_abs,
                n_valid=n_valid,
                fuel_delta_abs=fuel_delta_abs, fuel_delta_pct=fuel_delta_pct,
                wasted_inst=wasted_inst, wasted_ls=wasted_ls,
                fill_ls=fill_ls, fill_inst=fill_inst,
            )
            # progress line
            m100, _, _ = pct(time_delta_pct["t100"])
            k100, nn100, p100 = sign_test_positive(time_delta_pct["t100"])
            fm = med(fuel_delta_abs)
            kf, nf, pf = sign_test_positive([float(x) for x in fuel_delta_abs])
            print(f"[done] {pol:<18} N={n:<5} time100 med={m100:+6.2f}% sign={k100}/{nn100} p={p100:.1e} | fuel med={fm:+.1f} sign={kf}/{nf} p={pf:.1e}", flush=True)
    return out


def report(out):
    print("\n" + "=" * 100)
    print("HEADLINE: TIME-TAX  (lightspeed - instant), paired per seed")
    print("=" * 100)
    for pol in POLICIES:
        print(f"\n--- {pol} ---")
        print(f"{'N':>6}{'K':>4} | {'t50 med%':>9}{'sign':>8}{'p':>9} | {'t90 med%':>9}{'sign':>8}{'p':>9} | {'t100 med%':>10}{'sign':>8}{'p':>9}{'nvalid':>7}")
        for n in N_LIST:
            d = out[(pol, n)]
            cells = []
            for c in COV:
                xs = d["time_delta_pct"][c]
                m, _, _ = pct(xs)
                k, nn, p = sign_test_positive(xs)
                cells.append((m, k, nn, p))
            nv = d["n_valid"]["t100"]
            print(f"{n:>6}{d['seeds']:>4} | "
                  f"{cells[0][0]:>+8.2f} {f'{cells[0][1]}/{cells[0][2]}':>7}{cells[0][3]:>9.1e} | "
                  f"{cells[1][0]:>+8.2f} {f'{cells[1][1]}/{cells[1][2]}':>7}{cells[1][3]:>9.1e} | "
                  f"{cells[2][0]:>+9.2f} {f'{cells[2][1]}/{cells[2][2]}':>7}{cells[2][3]:>9.1e}{nv:>7}")

    print("\n" + "=" * 100)
    print("HEADLINE: FUEL-TAX  (wasted_arrivals: lightspeed - instant), paired per seed")
    print("=" * 100)
    for pol in POLICIES:
        print(f"\n--- {pol} ---")
        print(f"{'N':>6}{'K':>4} | {'w_inst':>8}{'w_ls':>8} | {'d_abs med':>10}{'d% med':>9}{'sign':>8}{'p':>9}")
        for n in N_LIST:
            d = out[(pol, n)]
            wi = med(d["wasted_inst"]); wl = med(d["wasted_ls"])
            da = med(d["fuel_delta_abs"])
            dp = med(d["fuel_delta_pct"])
            k, nn, p = sign_test_positive([float(x) for x in d["fuel_delta_abs"]])
            print(f"{n:>6}{d['seeds']:>4} | {wi:>8.0f}{wl:>8.0f} | {da:>+10.1f}{dp:>+8.1f}% {f'{k}/{nn}':>7}{p:>9.1e}")

    # completion check
    print("\nCompletion (all seeds fill 100%?):")
    for pol in POLICIES:
        bad = [(n, sum(out[(pol,n)]['fill_ls']), out[(pol,n)]['seeds']) for n in N_LIST if not all(out[(pol,n)]['fill_ls'])]
        print(f"  {pol:<18}: {'all fill' if not bad else bad}")


if __name__ == "__main__":
    out = run()
    report(out)
