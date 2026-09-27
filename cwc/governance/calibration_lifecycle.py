from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from cwc.governance.compute_value import ValueOfComputationEstimate
from cwc.governance.statistical_authority import StatisticalInferenceCertificate, StatisticalScope, certify_statistical_inference_authority


class CalibrationState(str, Enum):
    ACTIVE = "ACTIVE"
    INVALIDATED_DRIFT = "INVALIDATED_DRIFT"
    SHADOW_RECALIBRATION = "SHADOW_RECALIBRATION"


@dataclass(frozen=True, slots=True)
class CalibrationAuthority:
    state: CalibrationState
    generation: int
    calibration_digest: str
    risk_control_digest: str
    source_trace_digest: str
    drift_guard_digest: str
    invalidation_digest: str | None = None
    preregistration_digest: str | None = None
    candidate_source_trace_digest: str | None = None

    @property
    def digest(self) -> str:
        payload={"state":self.state.value,"generation":self.generation,"calibration_digest":self.calibration_digest,"risk_control_digest":self.risk_control_digest,"source_trace_digest":self.source_trace_digest,"drift_guard_digest":self.drift_guard_digest,"invalidation_digest":self.invalidation_digest,"preregistration_digest":self.preregistration_digest,"candidate_source_trace_digest":self.candidate_source_trace_digest}
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(",", ":")).encode()).hexdigest()


def _required(name:str,value:str)->str:
    if not value or not value.strip(): raise ValueError(f"{name} required")
    return value.strip()


def activate_initial_calibration(*,calibration_digest:str,risk_control_digest:str,source_trace_digest:str,drift_guard_digest:str,preregistration_digest:str,risk_control_passed:bool,independent_holdout_passed:bool)->CalibrationAuthority:
    if not (risk_control_passed and independent_holdout_passed):
        raise ValueError("initial calibration activation obligations not satisfied")
    return CalibrationAuthority(CalibrationState.ACTIVE,0,_required("calibration_digest",calibration_digest),_required("risk_control_digest",risk_control_digest),_required("source_trace_digest",source_trace_digest),_required("drift_guard_digest",drift_guard_digest),preregistration_digest=_required("preregistration_digest",preregistration_digest))


def invalidate_calibration_on_drift(authority:CalibrationAuthority,*,drift_alarm_digest:str,alarm_detected:bool)->CalibrationAuthority:
    if authority.state is not CalibrationState.ACTIVE: raise ValueError("only active calibration can be invalidated")
    if not alarm_detected: raise ValueError("calibration invalidation requires a positive drift alarm")
    alarm=_required("drift_alarm_digest",drift_alarm_digest)
    return CalibrationAuthority(CalibrationState.INVALIDATED_DRIFT,authority.generation,authority.calibration_digest,authority.risk_control_digest,authority.source_trace_digest,alarm,invalidation_digest=alarm,preregistration_digest=authority.preregistration_digest)


def begin_shadow_recalibration(authority:CalibrationAuthority,*,new_source_trace_digest:str,preregistration_digest:str)->CalibrationAuthority:
    if authority.state is not CalibrationState.INVALIDATED_DRIFT: raise ValueError("shadow recalibration requires drift-invalidated authority")
    source=_required("new_source_trace_digest",new_source_trace_digest); prereg=_required("preregistration_digest",preregistration_digest)
    if source==authority.source_trace_digest: raise ValueError("recalibration requires a distinct source trace")
    if prereg==authority.preregistration_digest: raise ValueError("recalibration requires a new preregistration")
    return CalibrationAuthority(CalibrationState.SHADOW_RECALIBRATION,authority.generation,authority.calibration_digest,authority.risk_control_digest,authority.source_trace_digest,authority.drift_guard_digest,invalidation_digest=authority.invalidation_digest,preregistration_digest=prereg,candidate_source_trace_digest=source)


def promote_shadow_recalibration(authority:CalibrationAuthority,*,new_calibration_digest:str,new_risk_control_digest:str,new_drift_guard_digest:str,risk_control_passed:bool,independent_holdout_passed:bool,source_trace_disjoint_attested:bool)->CalibrationAuthority:
    if authority.state is not CalibrationState.SHADOW_RECALIBRATION: raise ValueError("promotion requires shadow recalibration state")
    if not (risk_control_passed and independent_holdout_passed and source_trace_disjoint_attested): raise ValueError("recalibration promotion obligations not satisfied")
    cal=_required("new_calibration_digest",new_calibration_digest); risk=_required("new_risk_control_digest",new_risk_control_digest); guard=_required("new_drift_guard_digest",new_drift_guard_digest)
    if cal==authority.calibration_digest or risk==authority.risk_control_digest: raise ValueError("new generation must not reuse invalidated calibration/risk-control artifact")
    if guard==authority.drift_guard_digest: raise ValueError("new generation requires a fresh drift guard")
    assert authority.candidate_source_trace_digest is not None
    return CalibrationAuthority(CalibrationState.ACTIVE,authority.generation+1,cal,risk,authority.candidate_source_trace_digest,guard,preregistration_digest=authority.preregistration_digest)


def certify_estimate_from_active_calibration(*,estimate:ValueOfComputationEstimate,authority:CalibrationAuthority,scope:StatisticalScope,sampling_policy_digest:str,sampling_trace_digest:str)->StatisticalInferenceCertificate:
    if authority.state is not CalibrationState.ACTIVE: raise ValueError("only ACTIVE calibration may mint statistical inference authority")
    return certify_statistical_inference_authority(estimate=estimate,scope=scope,sampling_policy_digest=sampling_policy_digest,sampling_trace_digest=sampling_trace_digest,calibration_digest=authority.digest,drift_guard_digest=authority.drift_guard_digest,invalidated_by_drift=False)
