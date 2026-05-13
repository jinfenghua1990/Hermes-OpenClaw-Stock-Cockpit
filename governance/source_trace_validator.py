"""
Phase-2.7D Source Trace Validator
检查所有 runtime/replay/report 数据是否具备来源可溯源字段。
"""

REQUIRED_FIELDS = [
    "source_agent",
    "source_module",
    "data_source",
    "data_as_of",
    "trace_id",
]

CRITICAL_FIELDS = [
    "data_as_of",
]


def validate_source_trace(payload: dict):
    missing = []
    critical_missing = []

    for field in REQUIRED_FIELDS:
        if not payload.get(field):
            missing.append(field)

    for field in CRITICAL_FIELDS:
        if not payload.get(field):
            critical_missing.append(field)

    status = "PASS"

    if critical_missing:
        status = "CRITICAL"
    elif missing:
        status = "WARNING"

    return {
        "status": status,
        "missing_fields": missing,
        "critical_missing_fields": critical_missing,
        "source_trace_valid": status == "PASS",
        "schema": "phase_2_7d_source_trace_validator"
    }
