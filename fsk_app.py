import pathlib
import pandas as pd
import streamlit as st

CSV_STOCKED = "fsk_build_options_generated_v17_stocked_only_with_hats.csv"
CSV_STOCKED_OR_ORDERABLE = "fsk_build_options_generated_v17_stocked_or_orderable_with_hats.csv"

TIDES_BLUE = "#0b5072"
TIDES_TEAL = "#038e84"
TIDES_GREY = "#808080"
SHAFT_CUTOFF_IN = 2.75

SHORT_PRIORITY_MAP = {
    1: "US Recommended",
    2: "Ideal fit",
    3: "Stretch at FSA backend",
    4: "Straight hose",
    5: "Stretch at stern tube",
    6: "Stretch at both ends",
}

FULL_PRIORITY_MAP = {
    1: "US Recommended",
    2: "No stretch (ideal fit)",
    3: "Stretch at FSA backend only",
    4: "Straight hose (no stretch)",
    5: "Stretch at stern tube",
    6: "Stretch at both ends",
}


@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    required = [
        "FSK_SKU", "ShaftSize", "ShaftUnits", "SternSize", "SternUnits",
        "Priority", "FSA_Template", "Hose_Code",
        "Clamp1_Code", "Clamp1_Qty", "Clamp2_Code", "Clamp2_Qty",
        "Hat_SKU", "Hat_Qty",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"CSV missing columns: {missing}")

    for c in ["ShaftSize", "SternSize", "Priority", "Clamp1_Qty", "Clamp2_Qty", "Hat_Qty", "Stretch_Backend_in", "Stretch_Stern_in"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    for c in ["ShaftUnits", "SternUnits", "FSA_Template", "Hose_Code", "Clamp1_Code", "Clamp2_Code", "Hat_SKU", "Stretch_Type", "Comments", "Hose_Orientation"]:
        if c in df.columns:
            df[c] = df[c].astype("string").str.strip()

    df = df.dropna(subset=["FSK_SKU", "ShaftSize", "SternSize", "Priority", "FSA_Template", "Hose_Code"]).copy()
    df["Priority"] = df["Priority"].astype(int)
    df["Measurement_System"] = df["ShaftUnits"].map(lambda u: "Metric" if str(u).strip().lower() == "mm" else "Imperial")
    return df


def inject_css():
    css = f"""
    <style>
    :root {{
      --tides-blue: {TIDES_BLUE};
      --tides-teal: {TIDES_TEAL};
      --tides-grey: {TIDES_GREY};
    }}
    h1, h2, h3 {{ color: var(--tides-blue) !important; }}
    .small-muted {{ color: var(--tides-grey); font-size: 0.95rem; }}
    div[data-testid='stExpander'] summary {{
      border-left: 4px solid var(--tides-teal);
      padding-left: 0.5rem;
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def safe_index(options, value, fallback=0):
    try:
        return options.index(value)
    except Exception:
        return fallback


def shaft_in_inches(shaft: float, units: str) -> float:
    return float(shaft) / 25.4 if str(units).strip().lower() == "mm" else float(shaft)


def fmt_value(v: float, units: str) -> str:
    return f"{v:.0f} {units}" if str(units).strip().lower() == "mm" else f"{v:.3f} {units}"


def crossover_label(shaft: float, units: str) -> str:
    return "Crossover Kit 375" if shaft_in_inches(shaft, units) <= SHAFT_CUTOFF_IN else "Crossover Kit 500"


def pipe_plug_label(shaft: float, units: str) -> str:
    return "Pipe Plug 375" if shaft_in_inches(shaft, units) <= SHAFT_CUTOFF_IN else "Pipe Plug 500"


def build_fsk_display_sku(ms: str, shaft: float, stern: float, injection_choice: str) -> str:
    suffix = "0" if injection_choice == "Single - 0" else "1"
    if ms == "Metric":
        return f"FSKM-{int(shaft)}M-{int(stern)}M-{suffix}"
    return f"FSK-{int(round(shaft * 1000)):04d}-{int(round(stern * 1000)):04d}-{suffix}"


def filter_by_injection(df: pd.DataFrame, injection_choice: str) -> pd.DataFrame:
    wanted = "0" if injection_choice == "Single - 00" else "1"
    return df[df["FSK_SKU"].astype(str).str.strip().str.endswith(f"-{wanted}")].copy()


def final_dedupe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["Priority", "FSA_Template", "Hose_Code"], ascending=[True, True, True]).copy()
    dedupe_cols = [
        "FSK_SKU",
        "FSA_Template",
        "Hose_Code",
        "Clamp1_Code", "Clamp1_Qty",
        "Clamp2_Code", "Clamp2_Qty",
        "Hat_SKU", "Hat_Qty",
    ]
    df = df.drop_duplicates(subset=dedupe_cols, keep="first").copy()
    return df.reset_index(drop=True)


def option_parts_df(row: pd.Series, injection_choice: str) -> pd.DataFrame:
    parts = [
        ("FSA", str(row["FSA_Template"])),
        ("Hose", str(row["Hose_Code"])),
        ("Clamp (Backend)", f'{row["Clamp1_Code"]} × {int(row["Clamp1_Qty"]) if pd.notna(row["Clamp1_Qty"]) else "—"}'),
        ("Clamp (Stern)", f'{row["Clamp2_Code"]} × {int(row["Clamp2_Qty"]) if pd.notna(row["Clamp2_Qty"]) else "—"}'),
        ("Hat", f'{row["Hat_SKU"]} × {int(row["Hat_Qty"]) if pd.notna(row["Hat_Qty"]) else 1}'),
    ]
    if injection_choice == "Single - 00":
        parts.append(("Pipe Plug Needed", pipe_plug_label(float(row["ShaftSize"]), str(row["ShaftUnits"]))))
    parts.extend([
        ("Priority", str(int(row["Priority"]))),
        ("Priority meaning", FULL_PRIORITY_MAP.get(int(row["Priority"]), "")),
    ])
    return pd.DataFrame(parts, columns=["Part", "Value"])


def converter_ui():
    with st.sidebar.container(border=True):
        st.markdown("**Quick converter**  \n<span class='small-muted'>mm ↔ inches</span>", unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            mm = st.number_input("mm", min_value=0.0, value=0.0, step=0.1, key="conv_mm")
        with col2:
            inch = st.number_input("in", min_value=0.0, value=0.0, step=0.01, key="conv_in")
        mm_from_in = inch * 25.4
        in_from_mm = mm / 25.4 if mm else 0.0
        st.info(f"**{mm:.1f} mm** = **{in_from_mm:.4f} in**  \n**{inch:.4f} in** = **{mm_from_in:.1f} mm**")


def main():
    st.set_page_config(page_title="FSK Builder", layout="wide")
    inject_css()
    st.title("FSK Builder")

    p_stocked = pathlib.Path(CSV_STOCKED)
    p_orderable = pathlib.Path(CSV_STOCKED_OR_ORDERABLE)

    if not p_stocked.exists():
        st.error(f"Missing data file: {p_stocked.resolve()}")
        st.stop()
    if not p_orderable.exists():
        st.error(f"Missing data file: {p_orderable.resolve()}")
        st.stop()

    df_stocked = load_csv(str(p_stocked))
    df_orderable = load_csv(str(p_orderable))

    st.sidebar.header("Measurements (dropdowns)")

    if "ms" not in st.session_state:
        st.session_state["ms"] = "Imperial"
    if "mode" not in st.session_state:
        st.session_state["mode"] = "Stocked by us"
    if "inj" not in st.session_state:
        st.session_state["inj"] = "Dual - 1"

    ms_union = sorted(set(df_stocked["Measurement_System"].unique()).union(set(df_orderable["Measurement_System"].unique())))
    if st.session_state["ms"] not in ms_union:
        st.session_state["ms"] = ms_union[0] if ms_union else "Imperial"

    ms = st.sidebar.selectbox("Measurement system", ms_union, index=safe_index(ms_union, st.session_state["ms"]), key="ms")

    df_mode = df_stocked if st.session_state["mode"] == "Stocked by us" else df_orderable
    dms_mode = df_mode[df_mode["Measurement_System"] == ms].copy()
    if dms_mode.empty:
        st.warning(f"No {ms} data found for {st.session_state['mode']}.")
        st.stop()

    shaft_units = dms_mode["ShaftUnits"].dropna().iloc[0]
    stern_units = dms_mode["SternUnits"].dropna().iloc[0]

    shaft_vals = sorted(dms_mode["ShaftSize"].unique().tolist())
    if "shaft" not in st.session_state or st.session_state["shaft"] not in shaft_vals:
        st.session_state["shaft"] = shaft_vals[0]

    shaft = st.sidebar.selectbox(
        "Shaft size",
        shaft_vals,
        index=safe_index(shaft_vals, st.session_state["shaft"]),
        format_func=lambda x: f"{x:.0f}" if str(shaft_units).strip().lower() == "mm" else f"{x:.3f}",
        key="shaft",
    )

    stern_vals = sorted(dms_mode[dms_mode["ShaftSize"] == shaft]["SternSize"].unique().tolist())
    if not stern_vals:
        st.warning("No stern tube values available for that shaft size.")
        st.stop()
    if "stern" not in st.session_state or st.session_state["stern"] not in stern_vals:
        st.session_state["stern"] = stern_vals[0]

    stern = st.sidebar.selectbox(
        "Stern tube OD",
        stern_vals,
        index=safe_index(stern_vals, st.session_state["stern"]),
        format_func=lambda x: f"{x:.0f}" if str(stern_units).strip().lower() == "mm" else f"{x:.3f}",
        key="stern",
    )

    injection_choice = st.sidebar.radio(
        "Injection fitting?",
        ["Single - 0", "Dual - 1"],
        index=0 if st.session_state["inj"] == "Single - 0" else 1,
        key="inj",
    )

    mode = st.sidebar.radio(
        "Parts availability",
        ["Stocked by us", "Stocked + Can order"],
        index=0 if st.session_state["mode"] == "Stocked by us" else 1,
        key="mode",
    )

    converter_ui()

    df = df_stocked if mode == "Stocked by us" else df_orderable
    dms = df[df["Measurement_System"] == ms].copy()
    if dms.empty:
        st.warning(f"No {ms} data found.")
        st.stop()

    shaft_vals2 = sorted(dms["ShaftSize"].unique().tolist())
    if shaft not in shaft_vals2:
        shaft = shaft_vals2[0]
        st.session_state["shaft"] = shaft

    stern_vals2 = sorted(dms[dms["ShaftSize"] == shaft]["SternSize"].unique().tolist())
    if stern not in stern_vals2:
        stern = stern_vals2[0]
        st.session_state["stern"] = stern

    cand = dms[(dms["ShaftSize"] == shaft) & (dms["SternSize"] == stern)].copy()
    cand = filter_by_injection(cand, injection_choice)
    cand = final_dedupe(cand)

    if cand.empty:
        st.warning("No build options found for this shaft/stern/injection combination.")
        st.stop()

    display_fsk_sku = build_fsk_display_sku(ms, float(shaft), float(stern), injection_choice)

    st.subheader(f"{display_fsk_sku} Build Options")
    st.write(f"**Shaft:** {fmt_value(float(shaft), shaft_units)}  |  **Stern OD:** {fmt_value(float(stern), stern_units)}")
    st.caption(f"If crossover hose needed: **{crossover_label(float(shaft), shaft_units)}**")
    if injection_choice == "Single - 00":
        st.caption(f"If pipe plug needed: **{pipe_plug_label(float(shaft), shaft_units)}**")

    for i, row in cand.iterrows():
        short_label = SHORT_PRIORITY_MAP.get(int(row["Priority"]), f"Priority {int(row['Priority'])}")
        option_num = f"{i + 1:02d}"
        title = f"Option {option_num} - {short_label} - {row['FSA_Template']}"

        with st.expander(title, expanded=(i == 0)):
            st.table(option_parts_df(row, injection_choice))

            with st.expander("Advanced", expanded=False):
                adv_items = [
                    ("FSK SKU (source row)", str(row.get("FSK_SKU", ""))),
                    ("Hose orientation", str(row.get("Hose_Orientation", ""))),
                ]
                if "Stretch_Backend_in" in cand.columns:
                    adv_items.append(("Stretch backend (in)", str(row.get("Stretch_Backend_in", ""))))
                if "Stretch_Stern_in" in cand.columns:
                    adv_items.append(("Stretch stern (in)", str(row.get("Stretch_Stern_in", ""))))
                adv_items.append(("Notes", str(row.get("Comments", ""))))
                st.table(pd.DataFrame(adv_items, columns=["Field", "Value"]))

    st.markdown(
        "<div class='small-muted'>Mobile note: Streamlit select boxes are searchable; on some phones that opens the keyboard. Streamlit doesn’t currently provide a way to disable that.</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
