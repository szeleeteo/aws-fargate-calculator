from dataclasses import dataclass

CPU_MIN = 0.25
CPU_MAX = 16.0
CPU_MEMORY_STEP = 0.25
CPU_SERVICE_DEFAULT = 2.0
CPU_RESERVED_DEFAULT = 0.0
CPU_SIDECAR_DEFAULT = 0.5
CPU_SIDECAR_MIN = 0.0
CPU_SIDECAR_MAX = 0.5

MEMORY_MIN = 0.5
MEMORY_MAX = 120.0
MEMORY_SERVICE_DEFAULT = 3.75
MEMORY_RESERVED_DEFAULT = 0.25
MEMORY_SIDECAR_DEFAULT = 0.5
MEMORY_SIDECAR_MIN = 0.0
MEMORY_SIDECAR_MAX = 0.5

CPU_MEMORY_SIDECAR_STEP = 0.05


@dataclass
class Resource:
    details: str
    cpu: float
    memory: float


# Based on https://docs.aws.amazon.com/eks/latest/userguide/fargate-pod-configuration.html#fargate-cpu-and-memory
RESOURCES_MAPS = [
    {"details": "0.25 vCPU, 0.5 GB", "cpu": 0.25, "memory": 0.5},
    {"details": "0.25 vCPU, 1 GB", "cpu": 0.25, "memory": 1},
    {"details": "0.25 vCPU, 2 GB", "cpu": 0.25, "memory": 2},
    {"details": "0.5 vCPU, 1 GB", "cpu": 0.5, "memory": 1},
    {"details": "0.5 vCPU, 2 GB", "cpu": 0.5, "memory": 2},
    {"details": "0.5 vCPU, 3 GB", "cpu": 0.5, "memory": 3},
    {"details": "0.5 vCPU, 4 GB", "cpu": 0.5, "memory": 4},
    # 1 vCPU: 2 to 8 GB in 1-GB increments
    *[{"details": f"1 vCPU, {i} GB", "cpu": 1, "memory": i} for i in range(2, 9)],
    # 2 vCPU: 4 to 16 GB in 1-GB increments
    *[{"details": f"2 vCPU, {i} GB", "cpu": 2, "memory": i} for i in range(4, 17)],
    # 4 vCPU: 8 to 30 GB in 1-GB increments
    *[{"details": f"4 vCPU, {i} GB", "cpu": 4, "memory": i} for i in range(8, 31)],
    # 8 vCPU: 16 to 60 GB in 4-GB increments
    *[{"details": f"8 vCPU, {i} GB", "cpu": 8, "memory": i} for i in range(16, 61, 4)],
    # 16 vCPU: 32 to 120 GB in 8-GB increments
    *[
        {"details": f"16 vCPU, {i} GB", "cpu": 16, "memory": i}
        for i in range(32, 121, 8)
    ],
]
RESOURCES = [Resource(**mapping) for mapping in RESOURCES_MAPS]

RESOURCES_TABLE_MD = """\
| vCPU value | Memory value                                      |
|------------|---------------------------------------------------|
| 0.25 vCPU  | 0.5 GB, 1 GB, 2 GB                                |
| 0.5 vCPU   | 1 GB, 2 GB, 3 GB, 4 GB                            |
| 1 vCPU     | 2 GB, 3 GB, 4 GB, 5 GB, 6 GB, 7 GB, 8 GB          |
| 2 vCPU     | Between 4 GB and 16 GB in 1-GB increments         |
| 4 vCPU     | Between 8 GB and 30 GB in 1-GB increments         |
| 8 vCPU     | Between 16 GB and 60 GB in 4-GB increments        |
| 16 vCPU    | Between 32 GB and 120 GB in 8-GB increments       |
"""
RESOURCES_TABLE_CAPTION = "Based on [AWS Docs Reference](https://docs.aws.amazon.com/eks/latest/userguide/fargate-pod-configuration.html#fargate-cpu-and-memory)"

# Based on https://aws.amazon.com/fargate/pricing/ for Linux/x86 for Asia Pacific (Singapore) region
PER_VCPU_COST_PER_HOUR = 0.05056
PER_GB_COST_PER_HOUR = 0.00553
FARGATE_PRICING_MD = f"""\
                | Resource            | Price                     |
                |---------------------|---------------------------|
                | per vCPU per hour   | ${PER_VCPU_COST_PER_HOUR} |
                | per GB per hour     | ${PER_GB_COST_PER_HOUR}   |
                """
FARGATE_PRICING_CAPTION = "Based on [AWS Fargate Pricing](https://aws.amazon.com/fargate/pricing/) for **Linux/x86, Asia Pacific (Singapore) region**"


def get_resource(
    total_cpu: float, total_memory: float, alt_tier: bool = False
) -> Resource:
    for resource in RESOURCES:
        if resource.cpu >= total_cpu and resource.memory >= total_memory:
            if alt_tier:
                return get_alt_tier_resource(resource, total_cpu, total_memory)
            return resource

    raise ValueError(
        "Requested resources exceed the maximum available resources for Fargate."
    )


def get_alt_tier_resource(
    fargate_resource: Resource, total_cpu: float, total_memory: float
) -> Resource:
    # fargate cpu matches total cpu requested, minmax the memory
    if fargate_resource.cpu == total_cpu:
        candidate_resources = [
            resource
            for resource in RESOURCES
            if resource.cpu == total_cpu and resource.memory < total_memory
        ]

        if candidate_resources:
            return max(candidate_resources, key=lambda x: x.memory)

    # fargate cpu more than total cpu requested, minmax the cpu followed by memory
    elif fargate_resource.cpu > total_cpu and fargate_resource.memory >= total_memory:
        candidate_resources = [
            resource for resource in RESOURCES if resource.cpu < fargate_resource.cpu
        ]

        if candidate_resources:
            lower_cpu = max(candidate_resources, key=lambda x: x.cpu).cpu

            lower_candidate_resources = [
                resource
                for resource in RESOURCES
                if resource.cpu == lower_cpu and -1 < resource.memory - total_memory < 1
            ]

            if lower_candidate_resources:
                return max(lower_candidate_resources, key=lambda x: x.memory)

    return fargate_resource


def get_cost_per_day(cpu: float, memory: float) -> float:
    return (cpu * PER_VCPU_COST_PER_HOUR + memory * PER_GB_COST_PER_HOUR) * 24
