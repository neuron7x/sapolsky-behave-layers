from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from cwc.governance.compute_value import ValueOfComputationEstimate


class StatisticalScope(str, Enum):
    IID_FIXED = "IID_FIXED"
    RESTRICTED_ADAPTIVE_IPW = "RESTRICTED_ADAPTIVE_IPW"
    COVARIATE_SHIFT_WEIGHTED = "COVARIATE_SHIFT_WEIGHTED"


@dataclass(frozen=True, slots=True)
class StatisticalInferenceCertificate:
    operation_id: str
    estimate_digest: str
    scope: StatisticalScope
    sampling_policy_digest: str
    sampling_trace_digest: str
    calibration_digest: str
    drift_guard_digest: str
    invalidated_by_drift: bool
    method: str = "DGC_STATISTICAL_INFERENCE_AUTHORITY_V1"

    @property
    def digest(self) -> str:
        payload={"operation_id":self.operation_id,"estimate_digest":self.estimate_digest,"scope":self.scope.value,"sampling_policy_digest":self.sampling_policy_digest,"sampling_trace_digest":self.sampling_trace_digest,"calibration_digest":self.calibration_digest,"drift_guard_digest":self.drift_guard_digest,"invalidated_by_drift":self.invalidated_by_drift,"method":self.method}
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",", ":")).encode()).hexdigest()

    def admits(self,estimate:ValueOfComputationEstimate)->bool:
        return (not self.invalidated_by_drift and self.operation_id==estimate.operation_id and self.estimate_digest==digest_voc_estimate(estimate) and all(x.strip() for x in (self.sampling_policy_digest,self.sampling_trace_digest,self.calibration_digest,self.drift_guard_digest)))


def digest_voc_estimate(estimate:ValueOfComputationEstimate)->str:
    payload={"operation_id":estimate.operation_id,"gross_value":estimate.gross_value,"total_cost":estimate.total_cost,"voc":estimate.voc,"lower_bound":estimate.lower_bound,"upper_bound":estimate.upper_bound,"method":estimate.method,"authority":estimate.authority.value}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",", ":")).encode()).hexdigest()


def certify_statistical_inference_authority(*,estimate:ValueOfComputationEstimate,scope:StatisticalScope,sampling_policy_digest:str,sampling_trace_digest:str,calibration_digest:str,drift_guard_digest:str,invalidated_by_drift:bool)->StatisticalInferenceCertificate:
    for name,value in (("sampling_policy_digest",sampling_policy_digest),("sampling_trace_digest",sampling_trace_digest),("calibration_digest",calibration_digest),("drift_guard_digest",drift_guard_digest)):
        if not value.strip(): raise ValueError(f"{name} required")
    return StatisticalInferenceCertificate(estimate.operation_id,digest_voc_estimate(estimate),scope,sampling_policy_digest,sampling_trace_digest,calibration_digest,drift_guard_digest,bool(invalidated_by_drift))


@dataclass(frozen=True, slots=True)
class SignedStatisticalInferenceCertificate:
    certificate: StatisticalInferenceCertificate
    issuer_id: str
    signature_hex: str
    method: str = "HMAC_SHA256_STATISTICAL_AUTHORITY_V1"


def _signature_message(certificate:StatisticalInferenceCertificate,issuer_id:str)->bytes:
    issuer=issuer_id.strip()
    if not issuer: raise ValueError("issuer_id required")
    return f"{issuer}:{certificate.digest}".encode("utf-8")


def sign_statistical_inference_certificate(certificate:StatisticalInferenceCertificate,*,issuer_id:str,secret_key:bytes)->SignedStatisticalInferenceCertificate:
    import hmac
    if not isinstance(secret_key,(bytes,bytearray)) or len(secret_key)<32: raise ValueError("statistical authority key must contain at least 32 bytes")
    signature=hmac.new(bytes(secret_key),_signature_message(certificate,issuer_id),hashlib.sha256).hexdigest()
    return SignedStatisticalInferenceCertificate(certificate,issuer_id.strip(),signature)


def verify_signed_statistical_inference_certificate(signed:SignedStatisticalInferenceCertificate,*,trusted_issuer_id:str,secret_key:bytes,estimate:ValueOfComputationEstimate)->bool:
    import hmac
    if signed.issuer_id!=trusted_issuer_id.strip() or len(secret_key)<32: return False
    expected=hmac.new(bytes(secret_key),_signature_message(signed.certificate,signed.issuer_id),hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected,signed.signature_hex) and signed.certificate.admits(estimate)
