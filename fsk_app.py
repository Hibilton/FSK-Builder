import pathlib
import pandas as pd
import streamlit as st

# Stocked-only dataset (deduped)
DATA_FILE = "fsk_build_options_generated_v5_stocked_only.csv"

# Free add-on SKUs
CROSSOVER_3_8_SKU = "CROSSOVER KITF"   # 3/8"
CROSSOVER_1_2_SKU = "CROSSOVER KIT2F"  # 1/2"
SHAFT_CUTOFF_IN = 2.75  # <= 2.75" -> 3/8, >= 3.0" -> 1/2


@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    # Minimal required columns for the warehouse UI
    required = [
        "System", "ShaftSize", "ShaftUnits", "SternSize", "SternUnits",
        "Priority", "FSA_Template", "Hose_Code",
        "Clamp1_Code", "Clamp1_Qty", "Clamp2_Code", "Clamp2_Qty",
        "Is_US_Recommended", "Stretch_Type", "Comments"
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"CSV is missing required columns: {missing}")

    # Type cleanup
    text_cols = ["System","ShaftUnits","SternUnits","FSA_Template","Hose_Code","Clamp1_Code","Clamp2_Code","Stretch_Type","Comments"]
    for c in text_cols:
        df[c] = df[c].astype("string").str.strip()

    num_cols = ["ShaftSize","SternSize","Priority","Clamp1_Qty","Clamp2_Qty"]
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["Is_US_Recommended"] = df["Is_US_Recommended"].astype(str).str.lower().isin(["true","1","yes","y"])
    df = df.dropna(subset=["System","ShaftSize","SternSize","Priority","FSA_Template","Hose_Code"])
    df["Priority"] = df["Priority"].astype(int)
    return df


def shaft_in_inches(shaft_size: float, shaft_units: str) -> float:
    return float(shaft_size) / 25.4 if shaft_units == "mm" else float(shaft_size)


def crossover_sku_for_shaft(shaft_size: float, shaft_units: str) -> str:
    si = shaft_in_inches(shaft_size, shaft_units)
    return CROSSOVER_3_8_SKU if si <= SHAFT_CUTOFF_IN else CROSSOVER_1_2_SKU


def fmt(value: float, units: str) -> str:
    return f"{value:.0f} {units}" if units == "mm" else f"{value:.3f} {units}"


def main():
    st.set_page_config(page_title="FSK Warehouse Builder", layout="wide")
    st.title("FSK Warehouse Builder")

    csv_path = pathlib.Path(DATA_FILE)
    if not csv_path.exists():
        st.error(f"Missing data file: {csv_path.resolve()}")
        st.stop()

    try:
        df = load_data(str(csv_path))
    except Exception as e:
        st.error(f"Could not load CSV: {e}")
        st.stop()

    # Inputs (dropdowns)
    st.sidebar.header("Measurements (dropdowns)")
    systems = sorted(df["System"].dropna().unique().tolist())
    system = st.sidebar.selectbox("System", systems, index=0)

    df_sys = df[df["System"] == system].copy()
    shaft_units = df_sys["ShaftUnits"].dropna().iloc[0]
    stern_units = df_sys["SternUnits"].dropna().iloc[0]

    shaft_sizes = sorted(df_sys["ShaftSize"].dropna().unique().tolist())
    shaft_size = st.sidebar.selectbox(
        f"Shaft size ({shaft_units})",
        shaft_sizes,
        format_func=lambda x: f"{x:.0f}" if shaft_units == "mm" else f"{x:.3f}",
    )

    df_shaft = df_sys[df_sys["ShaftSize"] == shaft_size].copy()
    stern_sizes = sorted(df_shaft["SternSize"].dropna().unique().tolist())
    stern_size = st.sidebar.selectbox(
        f"Stern tube OD ({stern_units})",
        stern_sizes,
        format_func=lambda x: f"{x:.0f}" if stern_units == "mm" else f"{x:.3f}",
    )

    candidates = df_shaft[df_shaft["SternSize"] == stern_size].copy()
    if candidates.empty:
        st.warning("No stocked-only build options found for this shaft/stern combination.")
        st.stop()

    candidates = candidates.sort_values(["Priority","Is_US_Recommended"], ascending=[True, False]).reset_index(drop=True)

    st.subheader("Results")
    st.write(f"**System:** {system}  |  **Shaft:** {fmt(shaft_size, shaft_units)}  |  **Stern tube OD:** {fmt(stern_size, stern_units)}")

    crossover_sku = crossover_sku_for_shaft(shaft_size, shaft_units)
    st.caption(f"Crossover kit (if twin engines + crossover needed): **{crossover_sku}**")

    view = candidates.copy()
    view["Option"] = [f"Option {i+1}" for i in range(len(view))]

    # Clamp totals per kit (useful "2 vs 3" hint)
    def clamp_total(r):
        q1 = int(r["Clamp1_Qty"]) if pd.notna(r["Clamp1_Qty"]) else 0
        q2 = int(r["Clamp2_Qty"]) if pd.notna(r["Clamp2_Qty"]) else 0
        return q1 + q2
    view["Total_Clamps_Per_Kit"] = view.apply(clamp_total, axis=1)

    view["Clamp_Backend"] = view.apply(lambda r: f"{r['Clamp1_Code']} × {int(r['Clamp1_Qty']) if pd.notna(r['Clamp1_Qty']) else '—'}", axis=1)
    view["Clamp_Stern"] = view.apply(lambda r: f"{r['Clamp2_Code']} × {int(r['Clamp2_Qty']) if pd.notna(r['Clamp2_Qty']) else '—'}", axis=1)

    table_cols = ["Option","Priority","FSA_Template","Hose_Code","Clamp_Backend","Clamp_Stern","Total_Clamps_Per_Kit"]
    st.dataframe(view[table_cols], use_container_width=True, hide_index=True)

    with st.expander("Advanced", expanded=False):
        adv_cols = ["Option","Is_US_Recommended","Stretch_Type","Comments"]
        st.dataframe(view[adv_cols], use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
