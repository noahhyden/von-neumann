"""Sourced distributions - a citable spread for each input.

Issue #35 (Depth track, Tier 1 UQ): the cardinal rule (every number sourced) is
completed by giving every number a **spread**, not just a mean. Each distribution
below carries that spread. The mean cites its source, and the spread is itself a
citable claim (a measurement uncertainty, a literature range, an [ESTIMATE]
reasoning) - it must be documented in REFERENCES.md, not invented (CLAUDE.md §1).

The API is intentionally tiny: every distribution exposes `quantile(u)`, the
inverse CDF at u in [0, 1). Monte Carlo and Sobol both consume distributions
through this single method - a stream of uniforms in [0, 1) pushed through each
input's quantile - which means the RNG discipline lives in one place (a seeded
generator that yields uniforms) and each distribution stays a pure map. This is
the CLAUDE.md §7 rule for randomness: seeded state, threaded through the fold, no
wall clock, no Math.random.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@runtime_checkable
class Distribution(Protocol):
    """A univariate distribution consumed by inverse-CDF sampling."""

    mean: float

    def quantile(self, u: float) -> float:
        """Inverse CDF at u in [0, 1) - returns a sample when u is a uniform draw."""
        ...


def _check_u(u: float) -> None:
    if not (0.0 <= u < 1.0):
        raise ValueError(f"quantile input u must be in [0, 1), got {u!r}")


@dataclass(frozen=True)
class Fixed:
    """A point value - zero spread.

    Use for inputs whose spread is either truly negligible (e.g. a defined
    constant like an AU) or an unresolved [GAP] we refuse to fake. Sampling a
    Fixed always returns the same value, so it contributes zero variance and any
    Sobol total-order index will read as ~0.
    """

    value: float

    @property
    def mean(self) -> float:
        return self.value

    def quantile(self, u: float) -> float:
        _check_u(u)
        return self.value


@dataclass(frozen=True)
class Uniform:
    """Uniform on [low, high]. Use when a source gives a range but no shape."""

    low: float
    high: float

    def __post_init__(self) -> None:
        if not self.high > self.low:
            raise ValueError(f"Uniform requires high > low, got [{self.low}, {self.high}]")

    @property
    def mean(self) -> float:
        return 0.5 * (self.low + self.high)

    def quantile(self, u: float) -> float:
        _check_u(u)
        return self.low + u * (self.high - self.low)


@dataclass(frozen=True)
class Normal:
    """Gaussian(mean, std). Use when a source gives a measurement uncertainty.

    Sampling uses math.erfinv via the inverse standard normal CDF, so it is a
    pure map and identical across processes.
    """

    mean: float
    std: float

    def __post_init__(self) -> None:
        if self.std < 0:
            raise ValueError(f"Normal std must be >= 0, got {self.std!r}")

    def quantile(self, u: float) -> float:
        _check_u(u)
        if self.std == 0:
            return self.mean
        # Standard inverse normal CDF: Phi^-1(u) = sqrt(2) * erfinv(2u - 1).
        # Guard u=0 by nudging away from the boundary (matches half-open [0,1)).
        u_safe = max(u, 1e-15)
        z = math.sqrt(2.0) * _erfinv(2.0 * u_safe - 1.0)
        return self.mean + self.std * z


@dataclass(frozen=True)
class LogUniform:
    """LogUniform on [low, high]: each order of magnitude is equally likely.

    The honest read on sources that give a *range* spanning multiple orders
    of magnitude (e.g. sintered regolith strength ~2.5-355 MPa across
    techniques, compute-chip embodied energy 3000-15000 kWh/kg): each decade
    is equally likely, matching how the source presents the choice of
    technique / basis rather than the linear numeric distance.

    quantile(u) = low * (high/low)^u.
    """

    low: float
    high: float

    def __post_init__(self) -> None:
        if not self.low > 0:
            raise ValueError(f"LogUniform low must be > 0, got {self.low!r}")
        if not self.high > self.low:
            raise ValueError(f"LogUniform requires high > low, got [{self.low}, {self.high}]")

    @property
    def mean(self) -> float:
        # Analytic mean: (high - low) / ln(high / low).
        return (self.high - self.low) / math.log(self.high / self.low)

    def quantile(self, u: float) -> float:
        _check_u(u)
        return self.low * math.exp(u * math.log(self.high / self.low))


@dataclass(frozen=True)
class LogNormal:
    """LogNormal with the geometric mean and geometric std (ratio) as parameters.

    Use when a source's spread is naturally multiplicative - e.g. "efficiency is
    somewhere between 0.28 and 0.32", better read as a factor-of-1.07 spread than
    an additive one. gmean is exp(mu), gstd is exp(sigma); the ordinary mean is
    exp(mu + sigma^2 / 2) - `mean` returns that so downstream code can still
    compare against a nominal.
    """

    gmean: float
    gstd: float

    def __post_init__(self) -> None:
        if not self.gmean > 0:
            raise ValueError(f"LogNormal gmean must be > 0, got {self.gmean!r}")
        if not self.gstd >= 1:
            raise ValueError(f"LogNormal gstd must be >= 1, got {self.gstd!r}")

    @property
    def mean(self) -> float:
        mu = math.log(self.gmean)
        sigma = math.log(self.gstd)
        return math.exp(mu + 0.5 * sigma * sigma)

    def quantile(self, u: float) -> float:
        _check_u(u)
        if self.gstd == 1:
            return self.gmean
        u_safe = max(u, 1e-15)
        z = math.sqrt(2.0) * _erfinv(2.0 * u_safe - 1.0)
        return self.gmean * math.exp(math.log(self.gstd) * z)


def _erfinv(x: float) -> float:
    """Inverse error function. Winitzki's approximation with a Halley refinement.

    Accurate to ~1e-9 on [-0.999999, 0.999999]. Pure Python, no numpy - the point
    of this module is that a Fold + UQ stays framework- and dep-light (CLAUDE.md §5).
    """
    if not -1.0 < x < 1.0:
        raise ValueError(f"_erfinv domain is (-1, 1), got {x!r}")
    if x == 0.0:
        return 0.0
    # Winitzki's initial guess (Sergei Winitzki, "A handy approximation for the
    # error function and its inverse", 2008).
    a = 0.147
    ln = math.log(1.0 - x * x)
    part = 2.0 / (math.pi * a) + ln / 2.0
    y = math.copysign(1.0, x) * math.sqrt(math.sqrt(part * part - ln / a) - part)
    # One Halley step against the true erf for ~1e-9 accuracy.
    for _ in range(2):
        err = math.erf(y) - x
        dy = err * math.sqrt(math.pi) / 2.0 * math.exp(y * y)
        y -= dy
    return y
