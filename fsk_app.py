
import pathlib
import pandas as pd
import streamlit as st

DATA_FILE = "fsk_build_options_generated_v6_stocked_only_rich.csv"

SHAFT_CUTOFF_IN = 2.75  # <= 2.75\" => 375, >= 3.0\" => 500

PRIORITY_MAP = {
    1: "US Recommended",
    2: "No stretch (ideal fit)",
    3: "Stretch at FSA backend only",
    4: "Straight hose (no stretch)",
    5: "Stretch at stern tube",
    6: "Stretch at both ends",
}

@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    required = [
        "ShaftSize","ShaftUnits","SternSize","SternUnits",
        "Priority","FSA_Template","Hose_Code",
        "Clamp1_Code","Clamp1_Qty","Clamp2_Code","Clamp2_Qty",
        "Is_US_Recommended","Stretch_Type","Comments"
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"CSV missing columns: {missing}")

    # numeric columns (if present)
    for c in ["ShaftSize","SternSize","Priority","Clamp1_Qty","Clamp2_Qty","Stretch_Backend_in","Stretch_Stern_in"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df["Is_US_Recommended"] = df["Is_US_Recommended"].astype(str).str.lower().isin(["true","1","yes","y"])
    for c in ["ShaftUnits","SternUnits","FSA_Template","Hose_Code","Clamp1_Code","Clamp2_Code","Stretch_Type","Comments"]:
        df[c] = df[c].astype("string").str.strip()

    df = df.dropna(subset=["ShaftSize","SternSize","Priority","FSA_Template","Hose_Code"])
    df["Priority"] = df["Priority"].astype(int)

    # Derived measurement system for UI
    df["Measurement_System"] = df["ShaftUnits"].map(lambda u: "Metric" if u == "mm" else "Imperial")
    return df

def shaft_in_inches(shaft: float, units: str) -> float:
    return float(shaft) / 25.4 if units == "mm" else float(shaft)

def fmt(v: float, units: str) -> str:
    return f"{v:.0f} {units}" if units == "mm" else f"{v:.3f} {units}"

def crossover_label(shaft: float, units: str) -> str:
    si = shaft_in_inches(shaft, units)
    return "Crossover Kit 375" if si <= SHAFT_CUTOFF_IN else "Crossover Kit 500"

def clamp_total(row) -> int:
    q1 = int(row["Clamp1_Qty"]) if pd.notna(row["Clamp1_Qty"]) else 0
    q2 = int(row["Clamp2_Qty"]) if pd.notna(row["Clamp2_Qty"]) else 0
    return q1 + q2

def option_rows(row):
    backend = f'{row["Clamp1_Code"]} × {int(row["Clamp1_Qty"]) if pd.notna(row["Clamp1_Qty"]) else "—"}'
    stern = f'{row["Clamp2_Code"]} × {int(row["Clamp2_Qty"]) if pd.notna(row["Clamp2_Qty"]) else "—"}'
    priority = int(row["Priority"])
    meaning = PRIORITY_MAP.get(priority, "Custom rule")

    return [
        ("FSA", str(row["FSA_Template"])),
        ("Hose", str(row["Hose_Code"])),
        ("Clamp (Backend)", backend),
        ("Clamp (Stern)", stern),
        ("Total clamps / kit", str(clamp_total(row))),
        ("Priority", str(priority)),
        ("Priority meaning", meaning),
    ]

def main():
    st.set_page_config(page_title="FSK Warehouse Builder", layout="wide")
    st.title("FSK Warehouse Builder")

    path = pathlib.Path(DATA_FILE)
    if not path.exists():
        st.error(f"Missing data file: {path.resolve()}")
        st.stop()

    try:
        df = load_data(str(path))
    except Exception as e:
        st.error(f"Could not load CSV: {e}")
        st.stop()

    # --- Sidebar filters ---
    st.sidebar.header("Measurements (dropdowns)")

    ms_options = sorted(df["Measurement_System"].dropna().unique().tolist())
    default_idx = ms_options.index("Imperial") if "Imperial" in ms_options else 0
    ms = st.sidebar.selectbox("Measurement system", ms_options, index=default_idx)

    dms = df[df["Measurement_System"] == ms].copy()
    if dms.empty:
        st.warning(f"No {ms} data found in the CSV.")
        st.stop()

    shaft_units = dms["ShaftUnits"].dropna().iloc[0]
    stern_units = dms["SternUnits"].dropna().iloc[0]

    shaft_vals = sorted(dms["ShaftSize"].unique().tolist())
    shaft = st.sidebar.selectbox("Shaft size", shaft_vals, format_func=lambda x: f"{x:.0f}" if shaft_units=="mm" else f"{x:.3f}")

    dshaft = dms[dms["ShaftSize"] == shaft]
    stern_vals = sorted(dshaft["SternSize"].unique().tolist())
    stern = st.sidebar.selectbox("Stern tube OD", stern_vals, format_func=lambda x: f"{x:.0f}" if stern_units=="mm" else f"{x:.3f}")

    cand = dshaft[dshaft["SternSize"] == stern].copy()
    if cand.empty:
        st.warning("No build options found for this shaft/stern combination.")
        st.stop()

    cand = cand.sort_values(["Priority","Is_US_Recommended"], ascending=[True, False]).reset_index(drop=True)

    st.subheader("Build options")
    st.write(f"**Shaft:** {fmt(shaft, shaft_units)}  |  **Stern OD:** {fmt(stern, stern_units)}")
    st.caption(f"If twin engines + crossover hose needed: **{crossover_label(shaft, shaft_units)}**")

    # --- Card style options (parts as rows) ---
    for i, row in cand.iterrows():
        title = f"Option {i+1}  ·  Priority {int(row['Priority'])}"
        with st.container(border=True):
            st.markdown(f"### {title}")
            card = pd.DataFrame(option_rows(row), columns=["Part", "Value"])
            st.table(card)

            with st.expander("Advanced", expanded=False):
                adv_items = []
                adv_items.append(("US recommended", "Yes" if bool(row["Is_US_Recommended"]) else ""))
                adv_items.append(("Stretch type", str(row.get("Stretch_Type",""))))
                if "Stretch_Backend_in" in cand.columns:
                    adv_items.append(("Stretch backend (in)", str(row.get("Stretch_Backend_in",""))))
                if "Stretch_Stern_in" in cand.columns:
                    adv_items.append(("Stretch stern (in)", str(row.get("Stretch_Stern_in",""))))
                adv_items.append(("Notes", str(row.get("Comments",""))))
                adv_df = pd.DataFrame(adv_items, columns=["Field","Value"])
                st.table(adv_df)

if __name__ == "__main__":
    main()
