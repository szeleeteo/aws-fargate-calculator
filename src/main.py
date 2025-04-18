# Import third-party library modules
import pandas as pd
import streamlit as st

# Import local modules
from fargate import (
    PER_GB_COST_PER_HOUR,
    PER_VCPU_COST_PER_HOUR,
    RESOURCES_TABLE_MD,
    get_fargate_provision,
)

TITLE = "AWS Fargate Calculator for Resource Optimization"
DEFAULT_SERVICE_CPU = 2.0
DEFAULT_SERVICE_MEMORY = 3.75
DEFAULT_RESERVED_CPU = 0.0
DEFAULT_RESERVED_MEMORY = 0.25
DEFAULT_SIDECAR_CPU = 0.5
DEFAULT_SIDECAR_MEMORY = 0.5
PADDING_HEIGHT = 68


st.set_page_config(
    page_title=TITLE,
    page_icon=":material/calculate:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def calculate_resource_utilization(
    cpu_request_service: float,
    memory_request_service: float,
    memory_reserved_k8s: float,
    cpu_request_sidecar: float = 0.0,
    memory_request_sidecar: float = 0.0,
) -> list[dict]:
    cpu_total = cpu_request_service + cpu_request_sidecar
    memory_total = memory_request_service + memory_reserved_k8s + memory_request_sidecar

    fargate_provision = get_fargate_provision(cpu_total, memory_total)
    cpu_surplus = fargate_provision["cpu"] - cpu_total
    memory_surplus = fargate_provision["memory"] - memory_total

    alt_fargate_provision = get_fargate_provision(
        cpu_total, memory_total, lower_tier=True
    )
    alt_cpu_surplus = alt_fargate_provision["cpu"] - cpu_total
    alt_memory_surplus = alt_fargate_provision["memory"] - memory_total

    return [
        {
            "Resources details": "Total resources required",
            "cpu": cpu_total,
            "memory": memory_total,
        },
        {
            "Resources details": "Fargate resource tier provisioned",
            "cpu": fargate_provision["cpu"],
            "memory": fargate_provision["memory"],
        },
        {
            "Resources details": "Resources surplus",
            "cpu": cpu_surplus,
            "memory": memory_surplus,
        },
        {
            "Resources details": "Fargate resource (lower) tier provisioned",
            "cpu": alt_fargate_provision["cpu"],
            "memory": alt_fargate_provision["memory"],
        },
        {
            "Resources details": "Resources surplus lower",
            "cpu": alt_cpu_surplus,
            "memory": alt_memory_surplus,
        },
    ]


def display_resource_table(provision_result: list[dict]):
    result_df = pd.DataFrame(provision_result)
    result_df["Resources value"] = result_df.apply(
        lambda x: f"{x['cpu']:.2f} vCPU, {x['memory']:.2f} GB", axis=1
    )

    surplus = provision_result[2]
    if surplus["cpu"] > 0.0 or surplus["memory"] > 0.0:
        result_df.loc[2, "Resources value"] = (
            f"{surplus['cpu']:.2f} vCPU, {surplus['memory']:.2f} GB ⚠️"
        )
    else:
        result_df.loc[2, "Resources value"] = (
            f"{surplus['cpu']:.2f} vCPU, {surplus['memory']:.2f} GB ✅"
        )

    result_display_df = result_df.drop(["cpu", "memory"], axis=1)
    result_display_df = result_display_df[:3]
    st.dataframe(result_display_df, use_container_width=True, hide_index=True)


def evaluate_resource_provision(
    cpu_request_service: float,
    memory_request_service: float,
    provision_result: list[dict],
):
    fargate_provision = provision_result[1]
    surplus_resources = provision_result[2]
    alt_fargate_provision = provision_result[3]
    alt_surplus_resources = provision_result[4]

    if surplus_resources["cpu"] == 0.0 and surplus_resources["memory"] == 0.0:
        fargate_cost_per_day = (
            provision_result[1]["cpu"] * PER_VCPU_COST_PER_HOUR
            + provision_result[1]["memory"] * PER_GB_COST_PER_HOUR
        ) * 24
        fargate_tier = f"Fargate tier {provision_result[1]['cpu']:.2f} vCPU, {provision_result[1]['memory']:.2f} GB [${fargate_cost_per_day:.2f}/day]"

        st.success(f"The resources provisioned are optimal ✅  \n  - {fargate_tier}")
    else:
        optimal_cpu_1, optimal_memory_1, fargate_tier_1, delta_1 = (
            calculate_optimal_request(
                cpu_request_service=cpu_request_service,
                memory_request_service=memory_request_service,
                fargate_provision=fargate_provision,
                surplus_resources=surplus_resources,
            )
        )

        optimal_cpu_2, optimal_memory_2, fargate_tier_2, delta_2 = (
            calculate_optimal_request(
                cpu_request_service=cpu_request_service,
                memory_request_service=memory_request_service,
                fargate_provision=alt_fargate_provision,
                surplus_resources=alt_surplus_resources,
            )
        )

        st.warning(
            "The resources provisioned are not optimal ⚠️  \n"
            "Choose either options:  \n"
            f"- {fargate_tier_1}\n"
            f"   - {delta_1}\n"
            f"   - Request for **{optimal_cpu_1} vCPU, {optimal_memory_1} GB**\n"
            f"- {fargate_tier_2}\n"
            f"   - {delta_2}\n"
            f"   - Request for **{optimal_cpu_2} vCPU, {optimal_memory_2} GB**  \n\n"
            "👉🏻 Note that cpu is 10x more expensive than memory per unit per hour, so it is better to choose memory increase if cpu stay put!)"
        )


def calculate_optimal_request(
    cpu_request_service: float,
    memory_request_service: float,
    fargate_provision: dict,
    surplus_resources: dict,
):
    optimal_cpu_request = cpu_request_service + surplus_resources["cpu"]
    optimal_memory_request = memory_request_service + surplus_resources["memory"]
    fargate_cost_per_day = (
        fargate_provision["cpu"] * PER_VCPU_COST_PER_HOUR
        + fargate_provision["memory"] * PER_GB_COST_PER_HOUR
    ) * 24
    fargate_tier = f"Fargate tier {fargate_provision['cpu']:.2f} vCPU, {fargate_provision['memory']:.2f} GB [${fargate_cost_per_day:.2f}/day]"

    delta_cpu = optimal_cpu_request - cpu_request_service
    delta_memory = optimal_memory_request - memory_request_service

    delta = ""
    if delta_cpu > 0.0:
        delta = f"⬆️ {delta_cpu:.2f} vCPU"
    elif delta_cpu < 0.0:
        delta = f"⬇️ {-delta_cpu:.2f} vCPU"

    if delta_memory > 0.0:
        if delta:
            delta = f"{delta}, "
        delta = f"{delta} ⬆️ {delta_memory:.2f} GB"
    elif delta_memory < 0.0:
        if delta:
            delta = f"{delta}, "
        delta = f"{delta} ⬇️ {-delta_memory:.2f} GB"

    return optimal_cpu_request, optimal_memory_request, fargate_tier, delta


def main():
    st.title(TITLE)

    with st.sidebar:
        if st.toggle("Show available Fargate resources", value=False):
            st.markdown(RESOURCES_TABLE_MD)
            st.caption(
                "Based on [AWS Docs Reference](https://docs.aws.amazon.com/eks/latest/userguide/fargate-pod-configuration.html#fargate-cpu-and-memory)"
            )
        if st.toggle("Show Fargate pricing", value=False):
            st.markdown(
                f"""\
                | Resource            | Price                     |
                |---------------------|---------------------------|
                | per vCPU per hour   | ${PER_VCPU_COST_PER_HOUR} |
                | per GB per hour     | ${PER_GB_COST_PER_HOUR}   |
                """
            )
            st.caption(
                "Based on [AWS Fargate Pricing](https://aws.amazon.com/fargate/pricing/) for **Linux/x86, Asia Pacific (Singapore) region**"
            )
        show_sidecar_config = st.toggle("Show optimization with sidecar", value=False)

    left_col, right_col = st.columns(2)
    default_tile = left_col.container(border=True)
    sidecar_tile = right_col.container(border=True)

    with default_tile:
        default_tile.subheader("Default")
        default_left_col, default_right_col = st.columns(2)

        with default_left_col:
            cpu_request_service = st.number_input(
                label="CPU request (service)",
                value=DEFAULT_SERVICE_CPU,
                min_value=0.1,
                max_value=15.0,
                step=0.25,
                key="cpu_request_service",
            )
            st.number_input(
                label="CPU reserved (Kubernetes components)",
                value=DEFAULT_RESERVED_CPU,
                min_value=DEFAULT_RESERVED_CPU,
                max_value=DEFAULT_RESERVED_CPU,
                key="cpu_reserved_k8s",
            )
        with default_right_col:
            memory_request_service = st.number_input(
                label="Memory request (service)",
                value=DEFAULT_SERVICE_MEMORY,
                min_value=0.1,
                max_value=120.0,
                step=0.25,
                key="memory_request_service",
            )
            memory_reserved_k8s = st.number_input(
                label="Memory reserved (Kubernetes components)",
                value=DEFAULT_RESERVED_MEMORY,
                min_value=DEFAULT_RESERVED_MEMORY,
                max_value=DEFAULT_RESERVED_MEMORY,
                key="memory_reserved_k8s",
            )

        st.container(height=PADDING_HEIGHT, border=False)
        result_default = calculate_resource_utilization(
            cpu_request_service=cpu_request_service,
            memory_request_service=memory_request_service,
            memory_reserved_k8s=memory_reserved_k8s,
        )
        display_resource_table(result_default)
        evaluate_resource_provision(
            cpu_request_service, memory_request_service, result_default
        )

    if show_sidecar_config:
        sidecar_tile.subheader("With sidecar")

        with sidecar_tile:
            sidecar_left_col, sidecar_right_col = st.columns(2)
            with sidecar_left_col:
                cpu_request_service_new = st.number_input(
                    label="CPU request (service)",
                    value=cpu_request_service,
                    min_value=0.1,
                    max_value=15.0,
                    step=0.25,
                    key="cpu_request_service_new",
                )
                st.number_input(
                    label="CPU reserved (Kubernetes components)",
                    value=DEFAULT_RESERVED_CPU,
                    min_value=DEFAULT_RESERVED_CPU,
                    max_value=DEFAULT_RESERVED_CPU,
                    key="cpu_reserved_k8s_new",
                )
                cpu_reserved_sidecar = st.number_input(
                    label="CPU reserved (sidecar)",
                    value=DEFAULT_SIDECAR_CPU,
                    min_value=0.0,
                    max_value=0.5,
                    step=0.05,
                    key="cpu_reserved_sidecar",
                )
                with sidecar_right_col:
                    memory_request_service_new = st.number_input(
                        label="Memory request by service",
                        value=memory_request_service,
                        min_value=0.1,
                        max_value=120.0,
                        step=0.25,
                        key="memory_request_service_new",
                    )
                    memory_reserved_k8s_new = st.number_input(
                        label="Memory reserved for Kubernetes components",
                        value=DEFAULT_RESERVED_MEMORY,
                        min_value=DEFAULT_RESERVED_MEMORY,
                        max_value=DEFAULT_RESERVED_MEMORY,
                        key="memory_reserved_k8s_new",
                    )
                    memory_reserved_sidecar = st.number_input(
                        label="Memory reserved for sidecar",
                        value=DEFAULT_SIDECAR_MEMORY,
                        min_value=0.0,
                        max_value=0.5,
                        step=0.05,
                        key="memory_reserved_sidecar",
                    )

            result_with_sidecar = calculate_resource_utilization(
                cpu_request_service=cpu_request_service_new,
                memory_request_service=memory_request_service_new,
                memory_reserved_k8s=memory_reserved_k8s_new,
                cpu_request_sidecar=cpu_reserved_sidecar,
                memory_request_sidecar=memory_reserved_sidecar,
            )
            display_resource_table(result_with_sidecar)
            evaluate_resource_provision(
                cpu_request_service_new, memory_request_service_new, result_with_sidecar
            )


if __name__ == "__main__":
    main()
