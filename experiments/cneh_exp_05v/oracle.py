"""Independent scalar transition oracle for the frozen EXP05D discrete plant."""
from functools import lru_cache
from fractions import Fraction
import hashlib
import json
import math
import struct

MODES = ((1, 0), (0, 1), (1, 1), (0, 0))
ARMS = ("WAIT", "G0", "G1", "ALTERNATE")
ARRAYS = ("V", "w", "g_ampa", "g_nmda", "g_gabaa", "I_ext")
CONFIG = {
    "adex": {"C_pF": 150., "DeltaT_mV": 2., "EL_mV": -70., "VT_mV": -55.,
             "Vpeak_mV": 30., "Vreset_mV": -58., "a_nS": 2., "b_pA": 80.,
             "gL_nS": 10., "tauw_ms": 200.},
    "backend": "reference",
    "criticality": {"eta_sigma": .001, "gain_max": 5., "gain_min": .2, "sigma_target": 1.},
    "dt_ms": (.1).hex(), "nE": 24, "nI": 8,
    "network": {"N": 32, "V_max_mV": 50., "V_min_mV": -100., "ext_rate_hz": 2.,
                "ext_w_nS": .3, "frac_inhib": .25, "p_conn": 0., "w_exc_nS": .5,
                "w_inh_nS": 1.},
    "rng_class": "PCG64",
    "synapse": {"E_AMPA_mV": 0., "E_GABAA_mV": -70., "E_NMDA_mV": 0.,
                "delay_ms": 1., "mg_mM": 1., "tau_AMPA_ms": 2.5,
                "tau_GABAA_ms": 6., "tau_NMDA_ms": 100.},
}


def need(c, message):
    if not c:
        raise ValueError(message)


def canonical(x):
    return (json.dumps(x, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(x):
    return hashlib.sha256(canonical(x)).hexdigest()


def f(x):
    need(type(x) is str, "float encoding")
    a = float.fromhex(x)
    need(math.isfinite(a) and a.hex() == x, "nonfinite/noncanonical float")
    return a


def ceildiv(x, y):
    return -(-x // y)


@lru_cache(maxsize=524288)
def _certificate(x):
    # Exact |x|/64 <= 1/2. Directed fixed-point bounds on each positive Taylor
    # term; after K terms tail <= 2*next_term. Six directed squarings and
    # reciprocal for negative x preserve containment. Round both endpoints.
    n, d = abs(x).as_integer_ratio()
    d *= 64
    for p in (96, 160, 256, 512):
        scale = 1 << p
        tl = tu = lo = hi = scale
        K = p // 3 + 8
        for k in range(1, K + 1):
            tl = tl*n//(d*k)
            tu = ceildiv(tu*n, d*k)
            lo += tl
            hi += tu
        hi += 2*ceildiv(tu*n, d*(K+1))
        for _ in range(6):
            lo = lo*lo//scale
            hi = ceildiv(hi*hi, scale)
        if x < 0:
            lo, hi = scale*scale//hi, ceildiv(scale*scale, lo)
        a, b = float(Fraction(lo, scale)), float(Fraction(hi, scale))
        if a.hex() == b.hex():
            return a, p
    raise ValueError("rounding unresolved")


def certificate(x):
    need(type(x) is float and math.isfinite(x) and -32 <= x <= 32, "exp domain")
    return _certificate(x)


class Arithmetic:
    def __init__(self):
        self.count = 0
        self.precisions = {}

    def exp(self, x):
        v, p = certificate(x)
        self.count += 1
        self.precisions[str(p)] = self.precisions.get(str(p), 0) + 1
        return v


def mode_before(t):
    return sum(t > k for k in (128, 256, 384))


def group_at(arm, t):
    need(arm in ARMS, "arm")
    return None if arm == "WAIT" else 0 if arm == "G0" else 1 if arm == "G1" else (t//64)%2


def matrix_sha(m):
    values = [0.]*768 + [.5*MODES[m][j//4] if i < 16 else 0.
                         for i in range(32) for j in range(8)]
    return hashlib.sha256(struct.pack(">1024d", *values)).hexdigest()


MATRICES = tuple(matrix_sha(i) for i in range(4))


def physical_sha(s):
    data = b"".join(struct.pack(">32d", *(f(v) for v in s["arrays"][k])) for k in ARRAYS[:5])
    return hashlib.sha256(data + bytes(s["spikes"]) + struct.pack(">d", f(s["gain"]))).hexdigest()


def random32(rng):
    need(set(rng) == {"bit_generator", "has_uint32", "state", "uinteger"}
         and rng["bit_generator"] == "PCG64", "rng type")
    need(set(rng["state"]) == {"state", "inc"} and all(type(v) is int and 0 <= v < 2**128
         for v in rng["state"].values()), "rng state")
    x, inc = rng["state"]["state"], rng["state"]["inc"]
    need(inc % 2 == 1 and type(rng["has_uint32"]) is int and rng["has_uint32"] in (0, 1)
         and type(rng["uinteger"]) is int and 0 <= rng["uinteger"] < 2**32, "rng metadata")
    vals = []
    mask = (1 << 64) - 1
    for _ in range(32):
        x = (x*47026247687942121848144207491837523525 + inc) % 2**128
        z = ((x >> 64) ^ x) & mask
        rot = x >> 122
        z = ((z >> rot) | (z << ((-rot) & 63))) & mask
        vals.append((z >> 11) * 2.**-53)
    return vals, {**rng, "state": {"state": x, "inc": inc}}


def validate_state(s, t):
    need(set(s) == {"A_prev", "arrays", "branch", "configuration", "gain", "is_inhib",
                   "matrix_sha256", "mode", "physical_sha256", "rng", "sigma_gain",
                   "spikes", "tick"}, "state roster")
    need(type(s["tick"]) is int and s["tick"] == t and type(s["mode"]) is int
         and s["mode"] == mode_before(t), "tick/mode")
    need(canonical(s["configuration"]) == canonical(CONFIG), "configuration drift")
    need(s["matrix_sha256"] == MATRICES[s["mode"]], "matrix")
    need(s["is_inhib"] == [False]*24+[True]*8 and all(type(x) is bool for x in s["is_inhib"]), "population")
    need(len(s["spikes"]) == 32 and all(type(x) is bool for x in s["spikes"]), "spike roster")
    need(set(s["arrays"]) == set(ARRAYS), "array roster")
    for x in s["arrays"].values():
        need(type(x) is list and len(x) == 32, "array shape")
        for v in x:
            f(v)
    need(set(s["branch"]) == {"eps", "ema_alpha", "_sigma_ema"}
         and s["branch"]["eps"] == (1e-9).hex() and s["branch"]["ema_alpha"] == (.05).hex(), "branch config")
    for x in (s["A_prev"], s["gain"], s["sigma_gain"], s["branch"]["_sigma_ema"]):
        f(x)
    need(s["gain"] == s["sigma_gain"], "gain binding")
    need(s["physical_sha256"] == physical_sha(s), "physical digest")


def transition(s, arm, arithmetic):
    t = s["tick"]
    validate_state(s, t)
    need(0 <= t < 512, "transition tick")
    group = group_at(arm, t)
    mode = mode_before(t+1)
    randoms, rng = random32(s["rng"])
    old = {k: [f(v) for v in s["arrays"][k]] for k in ARRAYS}
    new = {k: [] for k in ARRAYS}
    spikes = []
    exp = arithmetic.exp
    da, dn, dg = [exp(-.1/tau) for tau in (2.5, 100., 6.)]
    arrival = .5 * sum(MODES[mode][(j-24)//4] for j in range(24, 32) if s["spikes"][j])
    for i in range(32):
        ext = float(randoms[i] < 2.*(.1/1000.))*.3
        ga = (old["g_ampa"][i] + (.7*0. + .7*ext))*da
        gn = (old["g_nmda"][i] + (.3*0. + .3*ext))*dn
        gg = (old["g_gabaa"][i] + (arrival if i < 16 else 0.))*dg
        V, w = old["V"][i], old["w"][i]
        u = 300. if i < 16 else 500. if group is not None and 24+4*group <= i < 28+4*group else 0.
        block = 1./(1. + (1./3.57)*exp(-.062*V))
        syn = ga*(V-0.) + gn*block*(V-0.) + gg*(V-(-70.))
        iexp = 10.*2.*exp(min((V-(-55.))/2., 20.))
        dv = (-10.*(V-(-70.))+iexp-w-syn+u)/150.
        dw = (2.*(V-(-70.))-w)/200.
        v, wn = V+.1*dv, w+.1*dw
        spike = v >= 30.
        if spike:
            v, wn = -58., wn+80.
        for k, value in zip(ARRAYS, (v, wn, ga, gn, gg, u), strict=True):
            new[k].append(value.hex())
        spikes.append(spike)
    A, A1 = float(sum(s["spikes"])), float(sum(spikes))
    sigma = (1.-.05)*f(s["branch"]["_sigma_ema"]) + .05*(max(A1, 1.)/max(A, 1.))
    gain = min(5., max(.2, f(s["sigma_gain"])-.001*(sigma-1.)))
    post = {**s, "A_prev": A1.hex(), "arrays": new,
            "branch": {**s["branch"], "_sigma_ema": sigma.hex()},
            "gain": gain.hex(), "sigma_gain": gain.hex(), "matrix_sha256": MATRICES[mode],
            "mode": mode, "rng": rng, "spikes": spikes, "tick": t+1}
    post["physical_sha256"] = physical_sha(post)
    metrics = {"A_t": A.hex(), "A_t1": A1.hex(), "sigma": sigma.hex(), "gain": gain.hex(),
               "spike_rate_hz": (A1/32/(.1/1000.)).hex()}
    return post, metrics


def check_transition(s, actual, metrics, arm, arithmetic):
    predicted, expected = transition(s, arm, arithmetic)
    validate_state(actual, s["tick"]+1)
    for k in predicted:
        if predicted[k] != actual[k]:
            if k == "arrays":
                for name in ARRAYS:
                    for i, (a, b) in enumerate(zip(predicted[k][name], actual[k][name], strict=True)):
                        if a != b:
                            raise ValueError(f"tick {actual['tick']}: {name}[{i}] expected {a} got {b}")
            raise ValueError(f"tick {actual['tick']}: mismatch {k}")
    need(canonical(metrics) == canonical(expected), f"tick {s['tick']}: metric mismatch")
