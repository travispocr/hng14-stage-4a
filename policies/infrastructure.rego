package swiftdeploy.infrastructure

import rego.v1

default allow := false

allow if {
    count(violations) == 0
}

violations contains msg if {
    input.disk_free_gb < data.thresholds.min_disk_free_gb
    msg := sprintf(
        "Disk free %.1fGB is below minimum %.1fGB",
        [input.disk_free_gb, data.thresholds.min_disk_free_gb]
    )
}

violations contains msg if {
    input.cpu_load > data.thresholds.max_cpu_load
    msg := sprintf(
        "CPU load %.2f exceeds maximum %.2f",
        [input.cpu_load, data.thresholds.max_cpu_load]
    )
}

violations contains msg if {
    input.mem_free_percent < data.thresholds.min_mem_free_percent
    msg := sprintf(
        "Memory free %.1f%% is below minimum %.1f%%",
        [input.mem_free_percent, data.thresholds.min_mem_free_percent]
    )
}

decision := {
    "allow": allow,
    "violations": violations,
    "domain": "infrastructure",
    "checked_at": input.timestamp,
}
