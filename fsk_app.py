import pathlib

import pandas as pd
import streamlit as st


DATA_FILE = "fsk_build_options_generated.csv"


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    # Basic sanity checks to avoid KeyErrors if Sheets has mangled things
    expected_cols = [
        "System", "ShaftSize", "ShaftUnits", "SternSize", "SternUnits",
        "FSK_Template", "FSK_Notes", "Priority", "RuleType",
        "FSA_Template", "FSA_Tail_OD_in", "Hose_Code",
        "Hose_End1_in", "Hose_End2_in", "Clamp1_Code", "Clamp2_Code",
        "Comments",
    ]
    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns in CSV: {missing}")

    # Normalise numeric fields
    numeric_cols = [
        "ShaftSize", "SternSize", "Priority",
        "FSA_Tail_OD_in", "Hose_End1_in", "Hose_End2_in",
    ]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df


def format_size(value: float, units: str) -> str:
    if pd.isna(value):
        return "—"
    if units == "mm":
        return f"{value:.0f} {units}"
    return f"{value:.3f} {units}"


def main():
    st.set_page_config(
        page_title="FSK Builder",
        layout="wide",
    )

    st.title("FSK Builder")

    csv_path = pathlib.Path(DATA_FILE)
    if not csv_path.exists():
        st.error(f"Could not find data file: {csv_path.resolve()}")
        st.stop()

    df = load_data(str(csv_path))

    # Sidebar controls
    st.sidebar.header("Filters")

    systems = sorted(df["System"].dropna().unique().tolist())
    system = st.sidebar.radio("System", systems, horizontal=True)

    df_sys = df[df["System"] == system].copy()

    # Shaft dropdown
    shaft_sizes = sorted(df_sys["ShaftSize"].dropna().unique().tolist())
    if not shaft_sizes:
        st.error("No shaft sizes available.")
        st.stop()

    shaft_units = df_sys["ShaftUnits"].dropna().iloc[0]

    shaft_size = st.sidebar.selectbox(
        "Shaft size",
        options=shaft_sizes,
        format_func=lambda x: format_size(x, shaft_units),
    )

    df_shaft = df_sys[df_sys["ShaftSize"] == shaft_size].copy()

    # Stern dropdown
    stern_sizes = sorted(df_shaft["SternSize"].dropna().unique().tolist())
    if not stern_sizes:
        st.error("No stern sizes available.")
        st.stop()

    stern_units = df_shaft["SternUnits"].dropna().iloc[0]

    stern_size = st.sidebar.selectbox(
        "Stern tube size",
        options=stern_sizes,
        format_func=lambda x: format_size(x, stern_units),
    )

    # Filter final
    candidates = df_shaft[df_shaft["SternSize"] == stern_size].copy()

    st.subheader("Selection summary")
    st.write(
        f"**System:** {system} &nbsp;&nbsp; "
        f"**Shaft:** {format_size(shaft_size, shaft_units)} &nbsp;&nbsp; "
        f"**Stern tube:** {format_size(stern_size, stern_units)}"
    )

    if candidates.empty:
        st.warning("No FSK builds found for this combination.")
        st.stop()

    # Sort by Priority
    candidates_sorted = candidates.sort_values(["Priority", "FSK_Template"])

    # Best recommended row
    best_overall = candidates_sorted.iloc[0]

    # -------------------------------
    # Recommended Build Section
    # -------------------------------
    st.markdown("### Recommended FSK build")

    # FSK
    st.markdown("**FSK**")
    st.markdown(str(best_overall["FSK_Template"]))
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # FSA
    st.markdown("**FSA**")
    st.markdown(str(best_overall.get("FSA_Template", "—")))
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # Hose
    st.markdown("**Hose**")
    st.markdown(str(best_overall.get("Hose_Code", "—")))
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # Details
    st.write("**Rule type:**", best_overall.get("RuleType", "—"))
    st.write("**Priority:**", int(best_overall["Priority"]))

    if isinstance(best_overall.get("FSK_Notes"), str) and best_overall["FSK_Notes"].strip():
        st.write("**FSK notes:**", best_overall["FSK_Notes"])

    hose_desc = []
    if not pd.isna(best_overall.get("Hose_End1_in")):
        hose_desc.append(f"End 1: {best_overall['Hose_End1_in']:.3f} in")
    if not pd.isna(best_overall.get("Hose_End2_in")):
        hose_desc.append(f"End 2: {best_overall['Hose_End2_in']:.3f} in")
    if hose_desc:
        st.write("**Hose ends:**", ", ".join(hose_desc))

    if not pd.isna(best_overall.get("FSA_Tail_OD_in")):
        st.write(f"**FSA tail OD:** {best_overall['FSA_Tail_OD_in']:.3f} in")

    if isinstance(best_overall.get("Comments"), str) and best_overall["Comments"].strip():
        st.caption(best_overall["Comments"])

    st.markdown("---")

    # -------------------------------
    # All Builds Table
    # -------------------------------
    st.markdown("### All builds for this combination")

    # Columns to display (in priority order)
    display_cols = [
        "FSK_Template",
        "Priority",
        "FSA_Template",
        "Hose_Code",
        "RuleType",
        "FSK_Notes",    
    ]

    # Ensure missing columns exist
    for col in display_cols:
        if col not in candidates_sorted.columns:
            candidates_sorted[col] = ""

    table = (
        candidates_sorted[display_cols]
        .sort_values(["Priority", "FSK_Template"])
        .reset_index(drop=True)
    )

    st.dataframe(table, use_container_width=True)

if __name__ == "__main__":
    main()
