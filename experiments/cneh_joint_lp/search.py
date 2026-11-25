"""Bounded exact-rational dual proposal engine. No admission authority.

Bland pivot choices and hard arithmetic limits make the search reproducible.
The checker can validate certificates from another proposer without this module.
"""
from __future__ import annotations

from fractions import Fraction as F

from experiments.cneh_exp_06h import reference as h
from experiments.cneh_joint_lp import kernel as k

MAX_PIVOTS=128


class SearchLimit(ValueError):
    pass


class Tableau:
    def __init__(self,columns,rhs,budget):
        self.n=len(columns)
        self.m=len(rhs)
        self.budget=budget
        self.pivots=0
        self.basis=list(range(self.n,self.n+self.m))
        self.rows=[]
        for j,b in enumerate(rhs):
            sign=F(-1) if b<0 else F(1)
            self.rows.append([sign*col[j] for col in columns]+
                             [F(int(j==v)) for v in range(self.m)]+[abs(b)])
        self.guard()

    def guard(self):
        if not all(k.bounded(v) for row in self.rows for v in row):
            raise SearchLimit("RATIONAL_BIT_BUDGET")
        k.need(all(row[-1]>=0 for row in self.rows),"dual basis feasibility")

    def pivot(self,leave,enter):
        if self.pivots>=self.budget:
            raise SearchLimit("PIVOT_BUDGET")
        pivot=self.rows[leave][enter]
        k.need(pivot!=0,"zero pivot")
        r=[v/pivot for v in self.rows[leave]]
        for j,row in enumerate(self.rows):
            if j==leave:
                continue
            coefficient=row[enter]
            if coefficient:
                self.rows[j]=[a-coefficient*b for a,b in zip(row,r,strict=True)]
        self.rows[leave]=r
        self.basis[leave]=enter
        self.pivots+=1
        self.guard()

    def cost_value(self,cost):
        return sum((cost[b]*row[-1] for b,row in zip(self.basis,self.rows,strict=True)),F(0))

    def optimize(self,cost,allowed):
        """Primal simplex for the nonnegative dual-variable equality system."""
        while True:
            basic=set(self.basis)
            enter=None
            for j in allowed:
                if j in basic:
                    continue
                reduced=cost[j]-sum((cost[b]*row[j]
                                    for b,row in zip(self.basis,self.rows,strict=True)),F(0))
                if not k.bounded(reduced):
                    raise SearchLimit("REDUCED_COST_BIT_BUDGET")
                if reduced<0:
                    enter=j
                    break
            if enter is None:
                return "OPTIMAL"
            eligible=[j for j,row in enumerate(self.rows) if row[enter]>0]
            if not eligible:
                return "UNBOUNDED"
            leave=min(eligible,key=lambda j:(self.rows[j][-1]/self.rows[j][enter],
                                             self.basis[j]))
            self.pivot(leave,enter)

    def remove_artificials(self):
        j=0
        while j<len(self.basis):
            if self.basis[j]<self.n:
                j+=1
                continue
            k.need(self.rows[j][-1]==0,"nonzero artificial variable")
            basic=set(self.basis)
            enter=next((v for v in range(self.n)
                        if v not in basic and self.rows[j][v]!=0),None)
            if enter is None:
                # Row is redundant on the original variables.
                self.rows.pop(j);self.basis.pop(j)
            else:
                # Zero basic value: either pivot sign preserves primal feasibility.
                self.pivot(j,enter)
                j+=1

    def multipliers(self):
        result=[F(0)]*self.n
        for b,row in zip(self.basis,self.rows,strict=True):
            if b>=self.n:
                k.need(row[-1]==0,"positive artificial variable")
            else:
                result[b]=row[-1]
        return tuple(result)


def dual(rows,objective,budget=MAX_PIVOTS,*,farkas=False):
    n=k.system(rows)
    k.need(type(budget) is int and 0<=budget<=MAX_PIVOTS,"pivot budget")
    k.need(type(objective) is tuple and len(objective)==n and all(map(k.bounded,objective)),
           "objective domain")
    k.need(type(farkas) is bool and (not farkas or objective==(F(0),)*n),
           "Farkas objective")
    if budget==0:
        return None,{"pivots":0,"reason":"ZERO_BUDGET"}
    if farkas:
        for j,(_,coef,rhs) in enumerate(rows):
            if not any(coef) and rhs<0:
                cert=k.row_proof(rows,j);k.check_infeasible(rows,cert)
                return cert,{"pivots":0,"reason":"DIRECT_NEGATIVE_ROW"}
    columns=tuple((*coef,F(1)) if farkas else coef for _,coef,_ in rows)
    rhs=(*objective,F(1)) if farkas else objective
    t=None
    ready=False
    try:
        t=Tableau(columns,rhs,budget)
        phase1=[F(0)]*t.n+[F(1)]*t.m
        disposition=t.optimize(phase1,range(t.n+t.m))
        if disposition!="OPTIMAL" or t.cost_value(phase1)!=0:
            return None,{"pivots":t.pivots,"reason":"NO_DUAL_BASIS"}
        t.remove_artificials()
        ready=True
        phase2=[rhs for _,_,rhs in rows]+[F(0)]*t.m
        disposition=t.optimize(phase2,range(t.n))
    except SearchLimit as exc:
        return None,{"pivots":0 if t is None else t.pivots,"reason":str(exc)}
    # Even a feasible nonoptimal dual point yields a valid bound. The checker
    # is the only source of mathematical authority; no optimality is asserted.
    k.need(ready,"phase II not reached")
    weights=t.multipliers()
    try:
        cert=k.certificate(rows,objective,weights)
        value=k.check(rows,objective,cert)
    except ValueError:
        return None,{"pivots":t.pivots,"reason":"CERTIFICATE_NOT_ADMISSIBLE"}
    if farkas and value>=0:
        return None,{"pivots":t.pivots,"reason":"NO_NEGATIVE_CERTIFICATE"}
    if farkas:
        k.check_infeasible(rows,cert)
    return cert,{"pivots":t.pivots,"reason":"DUAL_CERTIFICATE_"+disposition}


def analyze(record,profile="UNVERIFIED",budget=MAX_PIVOTS):
    k.need(type(profile) is str and profile in ("UNVERIFIED",h.BOUNDED),"reference profile")
    k.need(type(budget) is int and 0<=budget<=MAX_PIVOTS,"pivot budget")
    bounds=[[None,None] for _ in range(4)]
    stats=[]
    if profile=="UNVERIFIED":
        return k.receipt(record,profile,budget,None,None,bounds),stats
    rows=k.checked_system(record)
    if budget==0:
        return k.receipt(record,profile,budget,rows,None,bounds),stats
    exclusion,cost=dual(rows,(F(0),)*k.DIM,budget,farkas=True)
    stats.append({"target":"EXCLUSION",**cost})
    if exclusion is not None:
        return k.receipt(record,profile,budget,rows,exclusion,[]),stats
    for j in range(4):
        for index,sign in enumerate((-1,1)):
            target=k.unit(k.DIM,j,sign)
            prior=k.row_proof(rows,2*j+index)
            k.need(k.check(rows,target,prior)==(0 if sign<0 else 1),"coordinate prior identity")
            proposal,cost=dual(rows,target,budget)
            stats.append({"target":f"X{j}_{sign}",**cost})
            if proposal is not None and k.check(rows,target,proposal)<k.check(rows,target,prior):
                bounds[j][index]=proposal
            else:
                bounds[j][index]=prior
        lo,hi=bounds[j]
        if k.decode(lo["bound"])+k.decode(hi["bound"])<0:
            exclusion=k.combine_exclusion(rows,lo,hi)
            return k.receipt(record,profile,budget,rows,exclusion,[]),stats
    return k.receipt(record,profile,budget,rows,None,bounds),stats
