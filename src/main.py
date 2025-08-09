import pandas as pd
import streamlit as st

import fargate as fg
from fargate import Resource

TITLE = "AWS Fargate Calculator"
PADDING_HEIGHT = 68


st.set_page_config(page_title=TITLE, layout="wide", initial_sidebar_state="expanded")


def calculate_resource_utilization(
    cpu_request_service: float,
    memory_request_service: float,
    memory_reserved_k8s: float,
    cpu_request_sidecar: float = 0.0,
    memory_request_sidecar: float = 0.0,
) -> list[Resource]:
    cpu_total = cpu_request_service + cpu_request_sidecar
    memory_total = memory_request_service + memory_reserved_k8s + memory_request_sidecar

    fargate_provision = fg.get_resource(cpu_total, memory_total)
    cpu_surplus = fargate_provision.cpu - cpu_total
    memory_surplus = fargate_provision.memory - memory_total

    alt_fargate_provision = fg.get_resource(cpu_total, memory_total, alt_tier=True)
    alt_cpu_surplus = alt_fargate_provision.cpu - cpu_total
    alt_memory_surplus = alt_fargate_provision.memory - memory_total

    return [
        Resource(details="Resources requested", cpu=cpu_total, memory=memory_total),
        Resource(
            details="Fargate resources tier provisioned",
            cpu=fargate_provision.cpu,
            memory=fargate_provision.memory,
        ),
        Resource(details="Resources surplus", cpu=cpu_surplus, memory=memory_surplus),
        Resource(
            details="Alt Fargate resources tier provisioned",
            cpu=alt_fargate_provision.cpu,
            memory=alt_fargate_provision.memory,
        ),
        Resource(
            details="Alt resources surplus",
            cpu=alt_cpu_surplus,
            memory=alt_memory_surplus,
        ),
    ]


def display_resource_table(provision_result: list[Resource]):
    result_df = pd.DataFrame(provision_result)
    result_df["value"] = result_df.apply(
        lambda x: f"{x['cpu']:.2f} vCPU, {x['memory']:.2f} GB", axis=1
    )

    surplus_resources = provision_result[2]
    if surplus_resources.cpu > 0 or surplus_resources.memory > 0:
        result_df.loc[2, "value"] = (
            f"{surplus_resources.cpu:.2f} vCPU, {surplus_resources.memory:.2f} GB ⚠️"
        )
    else:
        result_df.loc[2, "value"] = (
            f"{surplus_resources.cpu:.2f} vCPU, {surplus_resources.memory:.2f} GB ✅"
        )

    result_display_df = result_df.drop(["cpu", "memory"], axis=1)
    result_display_df = result_display_df[:3]
    st.dataframe(result_display_df, use_container_width=True, hide_index=True)


def evaluate_resource_provision(
    cpu_request_service: float,
    memory_request_service: float,
    provision_result: list[Resource],
):
    (
        _,
        fargate_provision,
        surplus_resources,
        alt_fargate_provision,
        alt_surplus_resources,
    ) = provision_result

    if surplus_resources.cpu == 0 and surplus_resources.memory == 0:
        fargate_cost_per_day = fg.get_cost_per_day(
            fargate_provision.cpu, fargate_provision.memory
        )
        fargate_tier = rf"Fargate tier {fargate_provision.cpu:.2f} vCPU, {fargate_provision.memory:.2f} GB [\${fargate_cost_per_day:.2f}/day]"
        st.success(
            f"The resources requested and provisioned are optimal ✅  \n  - {fargate_tier}"
        )
    else:
        option_1 = derive_optimal_request_options(
            cpu_request_service=cpu_request_service,
            memory_request_service=memory_request_service,
            fargate_provision=fargate_provision,
            surplus_resources=surplus_resources,
        )
        option_2 = derive_optimal_request_options(
            cpu_request_service=cpu_request_service,
            memory_request_service=memory_request_service,
            fargate_provision=alt_fargate_provision,
            surplus_resources=alt_surplus_resources,
        )

        if option_1 == option_2:
            option_2 = ""

        st.warning(
            "The resources requested and provisioned are not optimal ⚠️  \n"
            "Choose one of the following options:  \n"
            f"{option_1}"
            f"{option_2}"
        )


def derive_optimal_request_options(
    cpu_request_service: float,
    memory_request_service: float,
    fargate_provision: Resource,
    surplus_resources: Resource,
):
    optimal_cpu_request = cpu_request_service + surplus_resources.cpu
    optimal_memory_request = memory_request_service + surplus_resources.memory
    fargate_cost_per_day = fg.get_cost_per_day(
        fargate_provision.cpu, fargate_provision.memory
    )
    fargate_tier = rf"Fargate tier {fargate_provision.cpu:.2f} vCPU, {fargate_provision.memory:.2f} GB [\${fargate_cost_per_day:.2f}/day]"

    delta_cpu = optimal_cpu_request - cpu_request_service
    delta_memory = optimal_memory_request - memory_request_service

    deltas = []
    if delta_cpu != 0:
        deltas.append(f"{'+' if delta_cpu > 0 else ''}{delta_cpu:.2f} vCPU")
    if delta_memory != 0:
        deltas.append(f"{'+' if delta_memory > 0 else ''}{delta_memory:.2f} GB")
    delta = ", ".join(deltas)

    return (
        f"- {fargate_tier} \n"
        f"   - **Set request for {optimal_cpu_request} vCPU, {optimal_memory_request} GB**  \n"
        f"   - {delta}\n"
    )


def main():
    st.header(TITLE)

    with st.sidebar:
        if st.toggle("Show Fargate tiers"):
            st.markdown(fg.RESOURCES_TABLE_MD)
            st.caption(fg.RESOURCES_TABLE_CAPTION)
        if st.toggle("Show Fargate pricing"):
            st.markdown(fg.FARGATE_PRICING_MD)
            st.caption(fg.FARGATE_PRICING_CAPTION)
        show_sidecar_config = st.toggle("Enable comparison with sidecar", value=True)

    default_col, sidecar_col = st.columns(2)
    default_tile = default_col.container(border=True)
    sidecar_tile = sidecar_col.container(border=True)

    with default_tile:
        default_tile.subheader("Default")
        default_left_col, default_right_col = st.columns(2)

        with default_left_col:
            cpu_request_service = st.number_input(
                label="CPU request (service)",
                value=fg.CPU_SERVICE_DEFAULT,
                min_value=fg.CPU_MIN,
                max_value=fg.CPU_MAX,
                step=fg.CPU_MEMORY_STEP,
                key="cpu_request_service",
            )
            st.number_input(
                label="CPU reserved (k8s components)",
                value=fg.CPU_RESERVED_DEFAULT,
                min_value=fg.CPU_RESERVED_DEFAULT,
                max_value=fg.CPU_RESERVED_DEFAULT,
                key="cpu_reserved_k8s",
            )
        with default_right_col:
            memory_request_service = st.number_input(
                label="Memory request (service)",
                value=fg.MEMORY_SERVICE_DEFAULT,
                min_value=fg.MEMORY_MIN,
                max_value=fg.MEMORY_MAX,
                step=fg.CPU_MEMORY_STEP,
                key="memory_request_service",
            )
            memory_reserved_k8s = st.number_input(
                label="Memory reserved (k8s components)",
                value=fg.MEMORY_RESERVED_DEFAULT,
                min_value=fg.MEMORY_RESERVED_DEFAULT,
                max_value=fg.MEMORY_RESERVED_DEFAULT,
                key="memory_reserved_k8s",
            )

        st.container(height=PADDING_HEIGHT, border=False)
        try:
            result_default = calculate_resource_utilization(
                cpu_request_service=cpu_request_service,
                memory_request_service=memory_request_service,
                memory_reserved_k8s=memory_reserved_k8s,
            )
            display_resource_table(result_default)
            evaluate_resource_provision(
                cpu_request_service, memory_request_service, result_default
            )
        except ValueError as exc:
            st.error(str(exc))

    if show_sidecar_config:
        sidecar_tile.subheader("With sidecar")

        with sidecar_tile:
            sidecar_left_col, sidecar_right_col = st.columns(2)
            with sidecar_left_col:
                cpu_request_service_new = st.number_input(
                    label="CPU request (service)",
                    value=cpu_request_service,
                    min_value=fg.CPU_MIN,
                    max_value=fg.CPU_MAX,
                    step=fg.CPU_MEMORY_STEP,
                    key="cpu_request_service_new",
                )
                st.number_input(
                    label="CPU reserved (k8s components)",
                    value=fg.CPU_RESERVED_DEFAULT,
                    min_value=fg.CPU_RESERVED_DEFAULT,
                    max_value=fg.CPU_RESERVED_DEFAULT,
                    key="cpu_reserved_k8s_new",
                )
                cpu_reserved_sidecar = st.number_input(
                    label="CPU reserved (sidecar)",
                    value=fg.CPU_SIDECAR_DEFAULT,
                    min_value=fg.CPU_SIDECAR_MIN,
                    max_value=fg.CPU_SIDECAR_MAX,
                    step=fg.CPU_MEMORY_SIDECAR_STEP,
                    key="cpu_reserved_sidecar",
                )
            with sidecar_right_col:
                memory_request_service_new = st.number_input(
                    label="Memory request (service)",
                    value=memory_request_service,
                    min_value=fg.MEMORY_MIN,
                    max_value=fg.MEMORY_MAX,
                    step=fg.CPU_MEMORY_STEP,
                    key="memory_request_service_new",
                )
                memory_reserved_k8s_new = st.number_input(
                    label="Memory reserved (k8s components)",
                    value=fg.MEMORY_RESERVED_DEFAULT,
                    min_value=fg.MEMORY_RESERVED_DEFAULT,
                    max_value=fg.MEMORY_RESERVED_DEFAULT,
                    key="memory_reserved_k8s_new",
                )
                memory_reserved_sidecar = st.number_input(
                    label="Memory reserved (sidecar)",
                    value=fg.MEMORY_SIDECAR_DEFAULT,
                    min_value=fg.MEMORY_SIDECAR_MIN,
                    max_value=fg.MEMORY_SIDECAR_MAX,
                    step=fg.CPU_MEMORY_SIDECAR_STEP,
                    key="memory_reserved_sidecar",
                )

            try:
                result_with_sidecar = calculate_resource_utilization(
                    cpu_request_service=cpu_request_service_new,
                    memory_request_service=memory_request_service_new,
                    memory_reserved_k8s=memory_reserved_k8s_new,
                    cpu_request_sidecar=cpu_reserved_sidecar,
                    memory_request_sidecar=memory_reserved_sidecar,
                )
                display_resource_table(result_with_sidecar)
                evaluate_resource_provision(
                    cpu_request_service_new,
                    memory_request_service_new,
                    result_with_sidecar,
                )
            except ValueError as exc:
                st.error(str(exc))


if __name__ == "__main__":
    main()
