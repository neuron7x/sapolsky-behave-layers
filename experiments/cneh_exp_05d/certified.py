"""Bounded correctly rounded binary64 exp with interval acceptance."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction
from functools import lru_cache
import importlib
import math
import struct
from unittest.mock import patch

PRECISIONS = (24, 40, 64, 100, 160, 256)
LOW, HIGH = -32., 32.


def need(condition, message):
    if not condition:
        raise ValueError(message)


def bits(value):
    return struct.unpack(">Q", struct.pack(">d", value))[0]


def from_bits(value):
    return struct.unpack(">d", struct.pack(">Q", value))[0]


def rational_bits(num, den):
    """Exact RN-even for positive, normal binary64 results only."""
    need(type(num) is int and type(den) is int and num > 0 and den > 0,
         "invalid positive rational")
    e = num.bit_length() - den.bit_length()
    if (num < (den << e)) if e >= 0 else ((num << -e) < den):
        e -= 1
    need(-1022 <= e <= 1023, "non-normal rounding domain")
    shift = 52 - e
    n, d = (num << shift, den) if shift >= 0 else (num, den << -shift)
    q, rem = divmod(n, d)
    if 2 * rem > d or (2 * rem == d and q & 1):
        q += 1
    if q == 1 << 53:
        q >>= 1
        e += 1
    need(-1022 <= e <= 1023 and (1 << 52) <= q < (1 << 53), "rounding overflow")
    return ((e + 1023) << 52) | (q - (1 << 52))


def check_input(x):
    need(type(x) is float and math.isfinite(x) and LOW <= x <= HIGH, "exp input outside certified binary64 domain")


@lru_cache(maxsize=131072)
def _certificate(x):
    exact = Decimal.from_float(x)
    for precision in PRECISIONS:
        with localcontext(Context(prec=precision, rounding=ROUND_HALF_EVEN,
                                  Emin=-999999, Emax=999999)) as ctx:
            y = ctx.exp(exact)
            lo, hi = ctx.next_minus(y), ctx.next_plus(y)
        lower = rational_bits(*lo.as_integer_ratio())
        upper = rational_bits(*hi.as_integer_ratio())
        if lower == upper:
            return lower, precision
    raise ValueError("binary64 rounding ambiguity after precision cap")


def certificate(x):
    check_input(x)
    return _certificate(x)


def certified_exp(x):
    return from_bits(certificate(x)[0])


def independent_taylor(x):
    """Exact rational positive Taylor terms and geometric remainder.

    Uses Python Fraction-to-float rounding independently of rational_bits.
    No Decimal, libm or NumPy exp is used.
    """
    check_input(x)
    z = Fraction.from_float(abs(x))
    term = total = Fraction(1)
    for k in range(513):
        if k + 2 > z:
            next_term = term * z / (k + 1)
            tail = next_term / (1 - z / (k + 2))
            lo, hi = total, total + tail
            if x < 0.:
                lo, hi = 1 / hi, 1 / lo
            a, b = bits(float(lo)), bits(float(hi))
            if a == b:
                return a, k
        term = term * z / (k + 1)
        total += term
    raise ValueError("independent Taylor enclosure unresolved")


class ModuleProxy:
    def __init__(self, original, replacement):
        self.original = original
        self.exp = replacement

    def __getattr__(self, name):
        return getattr(self.original, name)


@contextmanager
def corrected_backend(rt):
    """Scoped replacement of three named module-local exp bindings only."""
    np = rt["np"]
    adex = importlib.import_module("bnsyn.neuron.adex")
    conductance = importlib.import_module("bnsyn.synapse.conductance")
    integrators = importlib.import_module("bnsyn.numerics.integrators")
    originals = (adex.np, conductance.np, integrators.math)
    need(originals == (np, np, math), "unexpected native module binding")
    counts = {k: 0 for k in ("ADEX", "NMDA", "DECAY")}
    precisions = {str(p): 0 for p in PRECISIONS}

    def scalar(x, label):
        bits_value, precision = certificate(float(x))
        counts[label] += 1
        precisions[str(precision)] += 1
        return from_bits(bits_value)

    def vector(x, label):
        value = np.asarray(x)
        need(value.dtype == np.float64 and np.isfinite(value).all(), "invalid vector exp input")
        return np.array([scalar(v, label) for v in value.ravel()], dtype=np.float64).reshape(value.shape)

    with ExitStack() as stack:
        stack.enter_context(patch.object(adex, "np", ModuleProxy(np, lambda x: vector(x, "ADEX"))))
        stack.enter_context(patch.object(conductance, "np", ModuleProxy(np, lambda x: vector(x, "NMDA"))))
        stack.enter_context(patch.object(integrators, "math", ModuleProxy(math, lambda x: scalar(x, "DECAY"))))
        yield {"operation_counts": counts, "certificate_precisions": precisions}
    need((adex.np, conductance.np, integrators.math) == originals, "module binding restore failure")
