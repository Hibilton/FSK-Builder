import pathlib
import pandas as pd
import streamlit as st

DATA_FILE = "fsk_build_options_generated_v6_stocked_only_rich.csv"

SHAFT_CUTOFF_IN = 2.75  # <= 2.75" => 3/8 (375), >= 3.0" => 1/2 (500)

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
    missing=[c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"CSV missing columns: {missing}")

    # types
    for c in ["ShaftSize","SternSize","Priority","Clamp1_Qty","Clamp2_Qty","Stretch_Backend_in","Stretch_Stern_in"]:
        if c in df.columns:
            df[c]=pd.to_numeric(df[c], errors="coerce")
    df["Is_US_Recommended"]=df["Is_US_Recommended"].astype(str).str.lower().isin(["true","1","yes","y"])
    for c in ["ShaftUnits","SternUnits","FSA_Template","Hose_Code","Clamp1_Code","Clamp2_Code","Stretch_Type","Comments"]:
        df[c]=df[c].astype("string").str.strip()

    df=df.dropna(subset=["ShaftSize","SternSize","Priority","FSA_Template","Hose_Code"])
    df["Priority"]=df["Priority"].astype(int)
    return df

def shaft_in_inches(shaft: float, units: str) -> float:
    return float(shaft)/25.4 if units=="mm" else float(shaft)

def fmt(v: float, units: str) -> str:
    return f"{v:.0f}{units}" if units=="mm" else f"{v:.3f}{units}"

def crossover_label(shaft: float, units: str) -> str:
    si=shaft_in_inches(shaft, units)
    return "Crossover Kit 375" if si <= SHAFT_CUTOFF_IN else "Crossover Kit 500"

def main():
    st.set_page_config(page_title="FSK Warehouse Builder", layout="wide")
    st.title("FSK Warehouse Builder")

    path=pathlib.Path(DATA_FILE)
    if not path.exists():
        st.error(f"Missing data file: {path.resolve()}")
        st.stop()

    try:
        df=load_data(str(path))
    except Exception as e:
        st.error(f"Could not load CSV: {e}")
        st.stop()

    # Measurement system dropdown (derived)
    df["Measurement_System"]=df["ShaftUnits"].map(lambda u: "Metric" if u=="mm" else "Imperial")
    ms=st.sidebar.selectbox("Measurement System", ["Imperial","Metric"], index=0)

    dms=df[df["Measurement_System"]==ms].copy()
    if dms.empty:
        st.warning("No data for this measurement system.")
        st.stop()

    shaft_units=dms["ShaftUnits"].iloc[0]
    stern_units=dms["SternUnits"].iloc[0]

    shaft_vals=sorted(dms["ShaftSize"].unique().tolist())
    shaft=st.sidebar.selectbox("Shaft size", shaft_vals, format_func=lambda x: f"{x:.0f}" if shaft_units=="mm" else f"{x:.3f}")

    dshaft=dms[dms["ShaftSize"]==shaft]
    stern_vals=sorted(dshaft["SternSize"].unique().tolist())
    stern=st.sidebar.selectbox("Stern tube OD", stern_vals, format_func=lambda x: f"{x:.0f}" if stern_units=="mm" else f"{x:.3f}")

    cand=dshaft[dshaft["SternSize"]==stern].copy()
    if cand.empty:
        st.warning("No build options found for this shaft/stern combination.")
        st.stop()

    # sort
    cand=cand.sort_values(["Priority","Is_US_Recommended"], ascending=[True, False]).reset_index(drop=True)

    st.subheader("Build options")
    st.write(f"**Shaft:** {fmt(shaft, shaft_units)}  |  **Stern OD:** {fmt(stern, stern_units)}")
    st.caption(f"If twin engines + crossover hose needed: **{crossover_label(shaft, shaft_units)}**")

    view=cand.copy()
    view["Option"]=[f"Option {i+1}" for i in range(len(view))]

    # totals
    def clamp_total(r):
        q1=int(r["Clamp1_Qty"]) if pd.notna(r["Clamp1_Qty"]) else 0
        q2=int(r["Clamp2_Qty"]) if pd.notna(r["Clamp2_Qty"]) else 0
        return q1+q2
    view["Total_Clamps_Per_Kit"]=view.apply(clamp_total, axis=1)

    view["Clamp_Backend"]=view.apply(lambda r: f"{r['Clamp1_Code']} × {int(r['Clamp1_Qty']) if pd.notna(r['Clamp1_Qty']) else '—'}", axis=1)
    view["Clamp_Stern"]=view.apply(lambda r: f"{r['Clamp2_Code']} × {int(r['Clamp2_Qty']) if pd.notna(r['Clamp2_Qty']) else '—'}", axis=1)

    # main table (no US rec)
    table_cols=["Option","Priority","FSA_Template","Hose_Code","Clamp_Backend","Clamp_Stern","Total_Clamps_Per_Kit"]
    st.dataframe(view[table_cols], use_container_width=True, hide_index=True)

    with st.expander("Advanced", expanded=False):
        adv_cols=["Option","Is_US_Recommended","Stretch_Type","Stretch_Backend_in","Stretch_Stern_in","Comments"]
        adv_cols=[c for c in adv_cols if c in view.columns]
        st.dataframe(view[adv_cols], use_container_width=True, hide_index=True)

if __name__=="__main__":
    main()
