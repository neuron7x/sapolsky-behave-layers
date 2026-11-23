"""Causal matched-budget packet policy; no plant access or latent data."""
from __future__ import annotations

import itertools
import math
from fractions import Fraction

from experiments.cneh_exp_04c import qualification as q
from experiments.cneh_exp_04d import run as d

ARMS = ("RESPONSE_ROLLING", "EXACT_EMULATOR", "ALTERNATE_ROLLING", "RESPONSE_RESET", "ALTERNATE_RESET")
PACKET = 320
ON = 160
LEASE = 400
ALL = d.ALL
EXPIRY = "EVIDENCE_EXPIRY"


def is_on(t: int) -> bool:
    return 0 <= t < d.STEPS and t % PACKET < ON


class Policy:
    def __init__(self, arm: str):
        if arm not in ARMS:
            raise ValueError("unknown arm")
        self.rolling = arm in ARMS[:3]
        self.response = arm in (ARMS[0], ARMS[1], ARMS[3])
        self.previous: d.Observation | None = None
        self.last_action_tick: int | None = None
        self.last_action_group: int | None = None
        self.instant = ALL
        self.candidates = (0,)
        self.exclusion: list[int | None] = [None, 0, 0, 0]
        self.expired: tuple[int, ...] = ()
        self.event = "INITIAL"
        self.epoch = 0
        self.ones = [0, 0]
        self.seen = [0, 0]
        self.last_packet = [-3, -3]
        self.verifications = 0
        self.packet_group: int | None = None
        self.purpose = "REST"

    def observe(self, obs: d.Observation) -> None:
        self.expired = ()
        self.event = "INITIAL" if self.previous is None else "NONE"
        t = obs.tick
        if self.previous is None:
            if t != 0:
                raise ValueError("missing initial observation")
        else:
            if t != self.previous.tick+1 or self.last_action_tick != t-1:
                raise ValueError("missing causal action/observation")
            if self.last_action_group is not None:
                g = self.last_action_group
                bits = obs.bits[4*g:4*g+4]
                self.ones[g] += bits.count(1)
                self.seen[g] += sum(x is not None for x in bits)
            self.instant = q.support(ALL, self.previous.bits,
                                     q.observed_residual(self.previous.gaba, obs.gaba))
            if not self.instant:
                raise ValueError("MODEL_SET_VIOLATION")
            if self.rolling:
                self.expired = tuple(i for i,stamp in enumerate(self.exclusion)
                                     if stamp is not None and t-stamp >= LEASE)
                for i in self.expired:
                    self.exclusion[i] = None
                if self.expired:
                    self.event = EXPIRY
                remaining = tuple(i for i in ALL if self.exclusion[i] is None)
                if not set(remaining).intersection(self.instant):
                    self.exclusion = [None]*4
                    self.event = d.CONTRADICTION
                    self.epoch += 1
            else:
                if t % LEASE == 0:
                    self.exclusion = [None]*4
                    self.event = d.RENEWAL
                    self.epoch += 1
                elif not set(self.candidates).intersection(self.instant):
                    self.exclusion = [None]*4
                    self.event = d.CONTRADICTION
                    self.epoch += 1
            for i in ALL:
                if i not in self.instant:
                    self.exclusion[i] = t
            self.candidates = tuple(i for i in ALL if self.exclusion[i] is None)
            if not self.candidates or not set(self.candidates) <= set(self.instant):
                raise ValueError("invalid conditional support")
        self.previous = obs

    def connected(self) -> tuple[int, ...]:
        if len(self.candidates)!=1:
            return ()
        return tuple(g for g in range(2) if q.MODES[self.candidates[0]][g])

    def below_goal(self) -> bool:
        if self.previous is None:
            raise ValueError("missing observation")
        return math.fsum(self.previous.gaba)/len(d.B) < d.GOAL

    def choose_packet(self, packet: int) -> dict:
        connected = self.connected()
        candidates = self.candidates if len(self.candidates)>1 else ALL
        weights = [sum(q.MODES[i][g] != q.MODES[j][g]
                       for i,j in itertools.combinations(candidates,2)) for g in range(2)]
        scores = [Fraction(weights[g]*(1+self.ones[g]), 2+self.seen[g]) for g in range(2)]
        info = {"weights":weights, "scores":[[s.numerator,s.denominator] for s in scores],
                "ones":list(self.ones), "seen":list(self.seen), "prior_last_packet":list(self.last_packet),
                "verification_counter":self.verifications}
        if packet%2 and connected and self.below_goal():
            self.packet_group = connected[0]
            self.purpose, reason = "TRACK_PACKET", "CONDITIONAL_TRACK"
        else:
            self.purpose = "VERIFY_PACKET"
            if not self.response:
                self.packet_group = self.verifications%2
                reason = "ALTERNATE"
            else:
                eligible = [g for g in range(2) if weights[g]>0]
                if not eligible:
                    raise ValueError("no discriminating group")
                overdue = [g for g in eligible if packet-self.last_packet[g]>2]
                if overdue:
                    self.packet_group = min(overdue,key=lambda g:(self.last_packet[g],g))
                    reason = "OVERDUE"
                else:
                    self.packet_group = max(eligible,key=lambda g:(scores[g],-self.last_packet[g],-g))
                    reason = "RESPONSE_WEIGHTED"
            self.verifications += 1
        self.last_packet[self.packet_group] = packet
        return {**info,"group":self.packet_group,"purpose":self.purpose,"reason":reason}

    def act(self) -> tuple[int | None,str,dict | None]:
        if self.previous is None or self.previous.tick>=d.STEPS or self.last_action_tick==self.previous.tick:
            raise ValueError("invalid action timing")
        t = self.previous.tick
        info = None
        if not is_on(t):
            group, kind = None, "REST"
        else:
            if t%PACKET==0:
                info = self.choose_packet(t//PACKET)
            group = self.packet_group
            if group is None:
                raise ValueError("missing packet group")
            if self.purpose=="VERIFY_PACKET":
                kind = "PROBE"
            else:
                kind = "TRACK" if group in self.connected() and self.below_goal() else "PACKET_CONTINUATION"
        self.last_action_tick, self.last_action_group = t,group
        return group,kind,info

    def snapshot(self) -> dict:
        return {"instant":list(self.instant),"candidates":list(self.candidates),
                "exclusion":list(self.exclusion),"expired":list(self.expired),
                "event":self.event,"epoch":self.epoch,"ones":list(self.ones),"seen":list(self.seen),
                "last_packet":list(self.last_packet),"verifications":self.verifications,
                "packet_group":self.packet_group,"purpose":self.purpose}


def audit_tape(rows: list[dict], arm: str) -> None:
    if len(rows)!=d.STEPS+1 or [r["tick"] for r in rows]!=list(range(d.STEPS+1)):
        raise ValueError("incomplete trace")
    policy = Policy(arm)
    for row in rows:
        policy.observe(d.parse_obs(row))
        if row["policy"]!=policy.snapshot():
            raise ValueError("policy evidence mismatch")
        if row["tick"]<d.STEPS:
            if (row["group"],row["kind"],row["packet_decision"])!=policy.act():
                raise ValueError("policy action mismatch")
