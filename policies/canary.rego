package swiftdeploy.canary

import rego.v1

default allow := false

allow if {
    count(violations) == 0
}

violations contains msg if {
    input.error_rate_percent > data.thresholds.max_error_rate_percent
    msg := sprintf(
        "Error rate %.2f%% exceeds maximum %.2f%%",
        [input.error_rate_percent, data.thresholds.max_error_rate_percent]
    )
}

violations contains msg if {
    input.p99_latency_ms > data.thresholds.max_p99_latency_ms
    msg := sprintf(
        "P99 latency %.0fms exceeds maximum %.0fms",
        [input.p99_latency_ms, data.thresholds.max_p99_latency_ms]
    )
}

violations contains msg if {
    input.chaos_active != 0
    msg := sprintf(
        "Chaos mode is active (%d) — recover before promoting",
        [input.chaos_active]
    )
}

decision := {
    "allow": allow,
    "violations": violations,
    "domain": "canary",
    "checked_at": input.timestamp,
}
