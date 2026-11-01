"""Sourced distributions - a citable spread for each input."""

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
    """A point value - zero spread."""

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
    """Gaussian(mean, std). Use when a source gives a measurement uncertainty."""

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
        u_safe = max(u, 1e-15)
        z = math.sqrt(2.0) * _erfinv(2.0 * u_safe - 1.0)
        return self.mean + self.std * z


@dataclass(frozen=True)
class LogUniform:
    """LogUniform on [low, high]: each order of magnitude is equally likely."""

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
    """LogNormal with the geometric mean and geometric std (ratio) as parameters."""

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
    """Inverse error function. Winitzki's approximation with a Halley refinement."""
    if not -1.0 < x < 1.0:
        raise ValueError(f"_erfinv domain is (-1, 1), got {x!r}")
    if x == 0.0:
        return 0.0
    # Winitzki's initial guess with a = 0.147 (S. Winitzki, A handy approximation for the error function and its inverse, 2008); see REFERENCES.md.
    a = 0.147
    ln = math.log(1.0 - x * x)
    part = 2.0 / (math.pi * a) + ln / 2.0
    y = math.copysign(1.0, x) * math.sqrt(math.sqrt(part * part - ln / a) - part)
    # Two Halley steps against the true erf polish the guess to the stated ~1e-9 accuracy.
    for _ in range(2):
        err = math.erf(y) - x
        dy = err * math.sqrt(math.pi) / 2.0 * math.exp(y * y)
        y -= dy
    return y
