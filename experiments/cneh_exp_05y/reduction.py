"""Independent Fraction oracle for the R1 embedded-error dot product."""
from __future__ import annotations

import hashlib
import json
import math
from fractions import Fraction as F
from pathlib import Path
import struct
import zipfile

import numpy as np

from experiments.cneh_exp_05x import worlds as w

ANCHORS=(
    (14901052141,"2fb01767d13c5b0398f0ffc9f567a3d356c9a4d62d083ceee84682cb6953fec8"),
    (14901860095,"eb2ecf43f5e43541b9ec9cf0eaa10fc0697ab91a9099746eee41acb6b4225e21"),
)
# Frozen binary64 coefficients, independently transcribed from SciPy tableau.
E=tuple(map(float.fromhex,("-0x1.4320fedcba987p-10","0x0p+0","0x1.16b5a550abfc4p-8",
                         "-0x1.2eeeeeeeeeeefp-5","0x1.a0ad1d2ca1858p-5",
                         "-0x1.5748a7bdaf0e2p-5","0x1.999999999999ap-6")))


def terms(K,i):
    return tuple(F(E[k])*F(float(K[k,i])) for k in range(7))


def exact(K,i):
    return sum(terms(K,i),F(0))


def ordered(K,i):
    value=0.
    for k in range(7):
        product=E[k]*float(K[k,i])
        value=value+product
    return value


def rational_sqrt(value):
    """Verify rounding of sqrt by exact rational midpoint comparisons."""
    w.need(math.isfinite(value) and value>=0.,"sqrt domain")
    if value==0.:
        return 0.
    q=math.sqrt(value)
    lower=(F(math.nextafter(q,-math.inf))+F(q))/2
    upper=(F(math.nextafter(q,math.inf))+F(q))/2
    x=F(value)
    even=struct.unpack(">Q",struct.pack(">d",q))[0]%2==0
    w.need((lower*lower<x or (even and lower*lower==x))
           and (x<upper*upper or (even and x==upper*upper)),"independent sqrt rounding")
    return q


def norm(K,h,scale):
    sq=0.
    for i in range(2):
        z=(h*float(exact(K,i)))/float(scale[i])
        product=z*z
        sq=sq+product
    return rational_sqrt(sq/2.)


def witness_records(root):
    result=[]
    for aid,expected in ANCHORS:
        path=root/f"{aid}.zip"
        w.need(path.is_file() and not path.is_symlink() and w.sha(path.read_bytes())==expected,"forensic outer anchor")
        with zipfile.ZipFile(path) as z:
            w.need(set(z.namelist())=={"report.json","SHA256SUMS"} and len(z.namelist())==2,"forensic roster")
            raw=z.read("report.json")
            w.need(z.read("SHA256SUMS")==f"{w.sha(raw)}  report.json\n".encode(),"forensic inner manifest")
        value=json.loads(raw)
        w.need(value["matches_sealed"] is True and value["accepted_steps"]==64 and value["trial_records"]==64
               and w.sha(b"".join(bytes.fromhex(r) for r in value["records"]))==value["sealed_chunk_sha256"],"historical raw trace")
        trials=[]
        for record in value["records"]:
            raw=bytes.fromhex(record)
            if raw[:1]!=b"T":
                continue
            w.need(len(raw)==153,"trial raw record size")
            v=struct.unpack(">19d",raw[1:])
            trials.append((v[0],v[1],v[2],np.array(v[3:17],dtype=np.float64).reshape(7,2),np.array(v[17:],dtype=np.float64)))
        w.need(len(trials)==64,"witness trial roster")
        result.append(trials)
    w.need(result[0][0][0:2]==result[1][0][0:2]
           and np.array_equal(result[0][0][3],result[1][0][3])
           and np.array_equal(result[0][0][4],result[1][0][4]),"common first trial operands")
    return result


def fixture(index):
    # SHA-derived exact binary64 stage inputs; no RNG/native transcendental.
    out=np.empty((7,2),dtype=np.float64)
    for i in range(2):
        base=hashlib.sha256(f"CNEH-EXP-05Y-R1:{index}:{i}".encode()).digest()
        exponent=int.from_bytes(base[:2],"big")%2001-1000
        for k in range(7):
            raw=hashlib.sha256(base+bytes([k])).digest()
            sign=-1. if raw[0]&1 else 1.
            m=int.from_bytes(raw[1:8],"big")&((1<<52)-1)
            if index%4==0:
                # Nearly constant stages intentionally magnify cancellation.
                m=int.from_bytes(base[2:9],"big")&((1<<51)-1)
                m+=k
                sign=-1. if base[0]&1 else 1.
            elif index%4==1:
                exponent=int.from_bytes(raw[9:11],"big")%2001-1000
            out[k,i]=math.ldexp(sign*(1.+m*2.**-52),exponent)
    return out


def audit(lib,ptr,root:Path):
    fixtures=0
    def check(K):
        nonlocal fixtures
        for i in range(2):
            expected=float(exact(K,i))
            actual=lib.error_dot(ptr(K),i)
            w.need(actual.hex()==expected.hex(),f"correctly rounded error dot mismatch fixture {fixtures} component {i}")
        fixtures+=1
    witnesses=witness_records(root)
    rows=[]
    for trials in witnesses:
        for t,h,old,K,scale in trials:
            check(K)
            predicted=norm(K,h,scale)
            actual=lib.error_norm(ptr(K),h,ptr(scale))
            w.need(actual.hex()==predicted.hex(),"normalized embedded error mismatch")
        t,h,old,K,scale=trials[0]
        detail=[]
        for i in range(2):
            q=exact(K,i)
            previous=ordered(K,i)
            detail.append({"component":i,"condition_number":float(sum(map(abs,terms(K,i)))/abs(q)),
                           "ordered_dot":previous.hex(),"mpfr_dot":lib.error_dot(ptr(K),i).hex(),
                           "exact_numerator":q.numerator,"exact_denominator":q.denominator,
                           "ordered_relative_error":float(abs((F(previous)-q)/q))})
        rows.append({"native_error_norm":old.hex(),"r1_error_norm":lib.error_norm(ptr(K),h,ptr(scale)).hex(),
                     "components":detail})
    for i in range(2048):
        check(fixture(i))
    tiny=2.**-1074
    edges=[]
    edges.append(("zero",np.zeros((7,2),dtype=np.float64)))
    edges.append(("constant",np.ones((7,2),dtype=np.float64)))
    edges.append(("extreme",np.array([[math.nextafter(math.inf,0.),-math.nextafter(math.inf,0.)]]*7,dtype=np.float64)))
    edges.append(("tiny",np.array([[tiny,-tiny]]*7,dtype=np.float64)))
    # Exact half and 1.5 subnormal unit; verified by rational arithmetic.
    for multiple in (1,3):
        K=np.zeros((7,2),dtype=np.float64)
        K[2]=[-2729454319582*multiple*tiny,2729454319582*multiple*tiny]
        K[3]=[-313899508465*multiple*tiny,313899508465*multiple*tiny]
        w.need(exact(K,0)==F(tiny)*F(multiple,2) and exact(K,1)==-F(tiny)*F(multiple,2),"tie fixture")
        edges.append((f"subnormal_tie_{multiple}",K))
    for _,K in edges:
        check(K)
    attacks={}
    bad=np.zeros((7,2),dtype=np.float64)
    for name,val in (("nan",math.nan),("infinity",math.inf)):
        bad[1,0]=val  # E[1]=0: still reject malformed operand.
        w.need(math.isnan(lib.error_dot(ptr(bad),0)),"nonfinite operand accepted")
        attacks[name]=True
    bad[:]=1.
    w.need(math.isnan(lib.error_dot(ptr(bad),2)),"invalid component accepted")
    attacks["invalid_component"]=True
    scale=np.array([1.,0.],dtype=np.float64)
    w.need(math.isnan(lib.error_norm(ptr(bad),.1,ptr(scale))),"zero error scale accepted")
    attacks["zero_scale"]=True
    scale[:]=tiny
    bad[6,:]=math.nextafter(math.inf,0.)
    w.need(math.isnan(lib.error_norm(ptr(bad),1.,ptr(scale))),"overflow accepted")
    attacks["norm_overflow"]=True
    w.need(fixtures==2182,"fixture roster")
    return {"method":"MPFR_CORRECTLY_ROUNDED_DOT_BINARY64_INPUTS","fixture_pairs":fixtures,
            "component_checks":2*fixtures,"sealed_trial_records":128,"sha_derived_fixtures":2048,
            "edge_fixtures":[name for name,_ in edges],"negative_controls":attacks,
            "represented_E_sum":str(sum(map(F,E))),"first_trial_witnesses":rows,
            "scientific_promotion_authorized":False}
