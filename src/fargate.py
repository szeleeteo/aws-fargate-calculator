# Based on https://aws.amazon.com/fargate/pricing/ for Linux/x86 for Asia Pacific (Singapore) region
PER_VCPU_COST_PER_HOUR = 0.05056
PER_GB_COST_PER_HOUR = 0.00553


# Based on https://docs.aws.amazon.com/eks/latest/userguide/fargate-pod-configuration.html#fargate-cpu-and-memory
RESOURCES = [
    {"name": "0.25 vCPU, 0.5 GB", "cpu": 0.25, "memory": 0.5},
    {"name": "0.25 vCPU, 1 GB", "cpu": 0.25, "memory": 1},
    {"name": "0.25 vCPU, 2 GB", "cpu": 0.25, "memory": 2},
    {"name": "0.5 vCPU, 1 GB", "cpu": 0.5, "memory": 1},
    {"name": "0.5 vCPU, 2 GB", "cpu": 0.5, "memory": 2},
    {"name": "0.5 vCPU, 3 GB", "cpu": 0.5, "memory": 3},
    {"name": "0.5 vCPU, 4 GB", "cpu": 0.5, "memory": 4},
    # 1 vCPU: 2 to 8 GB in 1-GB increments
    *[{"name": f"1 vCPU, {i} GB", "cpu": 1, "memory": i} for i in range(2, 9)],
    # 2 vCPU: 4 to 16 GB in 1-GB increments
    *[{"name": f"2 vCPU, {i} GB", "cpu": 2, "memory": i} for i in range(4, 17)],
    # 4 vCPU: 8 to 30 GB in 1-GB increments
    *[{"name": f"4 vCPU, {i} GB", "cpu": 4, "memory": i} for i in range(8, 31)],
    # 8 vCPU: 16 to 60 GB in 4-GB increments
    *[{"name": f"8 vCPU, {i} GB", "cpu": 8, "memory": i} for i in range(16, 61, 4)],
    # 16 vCPU: 32 to 120 GB in 8-GB increments
    *[{"name": f"16 vCPU, {i} GB", "cpu": 16, "memory": i} for i in range(32, 121, 8)],
]

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


def get_fargate_provision(
    total_cpu: float, total_memory: float, lower_tier: bool = False
) -> dict:
    for resource in RESOURCES:
        if resource["cpu"] >= total_cpu and resource["memory"] >= total_memory:
            if lower_tier:
                return get_lower_fargate_tier(resource, total_cpu, total_memory)
            return resource

    raise ValueError(
        "Requested resources exceed the maximum available resources for Fargate."
    )


def get_lower_fargate_tier(
    fargate_resource: dict, total_cpu: float, total_memory: float
):
    # fargate cpu matches total cpu requested, minmax the memory
    if fargate_resource["cpu"] == total_cpu:
        candidate_resources = []
        for resource in RESOURCES:
            if resource["cpu"] == total_cpu and resource["memory"] < total_memory:
                candidate_resources.append(resource)

        if candidate_resources:
            candidate_resources.sort(key=lambda x: x["memory"])
            return candidate_resources[-1]

    # fargate cpu more than total cpu requested, minmax the cpu followed by memory
    elif (
        fargate_resource["cpu"] > total_cpu
        and fargate_resource["memory"] >= total_memory
    ):
        candidate_resources = []
        for resource in RESOURCES:
            if resource["cpu"] < fargate_resource["cpu"]:
                candidate_resources.append(resource)

        if candidate_resources:
            candidate_resources.sort(key=lambda x: x["cpu"])
            lower_cpu = candidate_resources[-1]["cpu"]

            lower_candidate_resources = []
            for resource in RESOURCES:
                if (
                    resource["cpu"] == lower_cpu
                    and -1 < resource["memory"] - total_memory < 1
                ):
                    lower_candidate_resources.append(resource)

            if lower_candidate_resources:
                lower_candidate_resources.sort(key=lambda x: x["memory"])
                return lower_candidate_resources[-1]

    return fargate_resource
