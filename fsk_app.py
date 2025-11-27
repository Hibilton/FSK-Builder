import pathlib

import pandas as pd
import streamlit as st


DATA_FILE = "fsk_build_options_generated.csv"


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    """Load and clean the FSK build CSV with basic validation."""
    df = pd.read_csv(path)

    # --- 1) Normalise column names ---
    df.columns = [c.strip() for c in df.columns]

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

    # --- 2) Strip whitespace from key text columns ---
    text_cols = [
        "System", "ShaftUnits", "SternUnits", "FSK_Template",
        "RuleType", "FSA_Template", "Hose_Code",
        "Clamp1_Code", "Clamp2_Code",
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    # --- 3) Normalise numeric fields ---
    numeric_cols = [
        "ShaftSize", "SternSize", "Priority",
        "FSA_Tail_OD_in", "Hose_End1_in", "Hose_End2_in",
    ]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Drop completely unusable rows (no system/shaft/stern/FSK)
    base_mask = (
        df["System"].notna()
        & df["ShaftSize"].notna()
        & df["SternSize"].notna()
        & df["FSK_Template"].notna()
    )
    bad_rows = df[~base_mask].copy()
    df = df[base_mask].copy()

    # Attach a small summary so we can show diagnostics in the UI
    meta = {
        "total_rows": len(df) + len(bad_rows),
        "kept_rows": len(df),
        "dropped_rows": len(bad_rows),
    }
    return df, meta


def format_size(value: float, units: str) -> str:
    if pd.isna(value):
        return "—"
    if units == "mm":
        return f"{value:.0f} {units}"
    return f"{value:.3f} {units}"  # inches


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

    # Load & clean
    try:
        df, meta = load_data(str(csv_path))
    except KeyError as e:
        st.error(f"CSV format error: {e}")
        st.stop()

    # --- Global data quality summary ---
    with st.expander("Data quality summary", expanded=False):
        st.write(f"**Total rows in CSV:** {meta['total_rows']}")
        st.write(f"**Usable rows after cleaning:** {meta['kept_rows']}")
        st.write(f"**Dropped rows (missing System/Shaft/Stern/FSK):** {meta['dropped_rows']}")

        # Check for combos with no Priority 1 (no recommended build)
        combo_group = df.groupby(["System", "ShaftSize", "SternSize"], dropna=True)
        no_rec_mask = combo_group["Priority"].transform(lambda s: ~(s == 1).any())
        combos_without_rec = (
            df[no_rec_mask][["System", "ShaftSize", "SternSize"]]
            .drop_duplicates()
            .sort_values(["System", "ShaftSize", "SternSize"])
        )

        if not combos_without_rec.empty:
            st.warning(
                f"There are {len(combos_without_rec)} shaft/stern combinations "
                "without a Priority 1 recommended build."
            )
            st.dataframe(combos_without_rec, use_container_width=True)
        else:
            st.success("Every System / Shaft / Stern combination has at least one Priority 1 build.")

    # Sidebar controls
    st.sidebar.header("Filters")

    systems = sorted(df["System"].dropna().unique().tolist())
    if not systems:
        st.error("No systems found in the data after cleaning.")
        st.stop()

    system = st.sidebar.radio("System", systems, horizontal=True)

    df_sys = df[df["System"] == system].copy()
    if df_sys.empty:
        st.error(f"No rows found for system '{system}'. Check System values in the CSV.")
        st.stop()

    # Shaft dropdown
    shaft_sizes = sorted(df_sys["ShaftSize"].dropna().unique().tolist())
    if not shaft_sizes:
        st.error("No shaft sizes available for this system.")
        st.stop()

    shaft_units = df_sys["ShaftUnits"].dropna().iloc[0]

    shaft_size = st.sidebar.selectbox(
        "Shaft size",
        options=shaft_sizes,
        format_func=lambda x: format_size(x, shaft_units),
    )

    df_shaft = df_sys[df_sys["ShaftSize"] == shaft_size].copy()
    if df_shaft.empty:
        st.warning("No rows found for this shaft size after filtering.")
        st.stop()

    # Stern dropdown
    stern_sizes = sorted(df_shaft["SternSize"].dropna().unique().tolist())
    if not stern_sizes:
        st.error("No stern tube sizes available for this shaft size.")
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
        st.error(
            "No FSK builds found for this exact combination after cleaning. "
            "This usually means the CSV is missing rows for this shaft/stern size."
        )
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

    display_cols = [
        "FSK_Template",
        "Priority",
        "FSA_Template",
        "Hose_Code",
        "RuleType",
    ]

    for col in display_cols:
        if col not in candidates_sorted.columns:
            candidates_sorted[col] = ""

    table = (
        candidates_sorted[display_cols]
        .sort_values(["Priority", "FSK_Template", "Hose_Code"])
        .reset_index(drop=True)
    )

    st.dataframe(table, use_container_width=True)


if __name__ == "__main__":
    main()
