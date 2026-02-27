import pathlib
import pandas as pd
import streamlit as st

# Data files (UPDATED to v7)
CSV_STOCKED = "fsk_build_options_generated_v8_stocked_only_rich.csv"
CSV_STOCKED_FALLBACK = "fsk_build_options_generated_v7_stocked_only_rich.csv"
CSV_STOCKED_OR_ORDERABLE = "fsk_build_options_generated_v8_stocked_or_orderable.csv"
CSV_STOCKED_OR_ORDERABLE_FALLBACK = "fsk_build_options_generated_v7_stocked_or_orderable.csv"

SHAFT_CUTOFF_IN = 2.75  # <= 2.75" => 375, >= 3.0" => 500

PRIORITY_MAP = {
    1: "US Recommended",
    2: "No stretch (ideal fit)",
    3: "Stretch at FSA backend only",
    4: "Straight hose (no stretch)",
    5: "Stretch at stern tube",
    6: "Stretch at both ends",
}


def _load_csv(preferred: str, fallback: str | None = None) -> pd.DataFrame:
    """Load a CSV by filename from the working directory. If preferred is missing, try fallback."""
    try:
        return pd.read_csv(preferred)
    except FileNotFoundError:
        if fallback is None:
            raise
        return pd.read_csv(fallback)

# Brand colors
TIDES_BLUE = "#0b5072"
TIDES_TEAL = "#038e84"
TIDES_GREY = "#808080"


@st.cache_data
def load_csv(path: str) -> pd.DataFrame:
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

    for c in ["ShaftSize","SternSize","Priority","Clamp1_Qty","Clamp2_Qty","Stretch_Backend_in","Stretch_Stern_in"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df["Is_US_Recommended"] = df["Is_US_Recommended"].astype(str).str.lower().isin(["true","1","yes","y"])

    for c in ["ShaftUnits","SternUnits","FSA_Template","Hose_Code","Clamp1_Code","Clamp2_Code","Stretch_Type","Comments"]:
        df[c] = df[c].astype("string").str.strip()

    df = df.dropna(subset=["ShaftSize","SternSize","Priority","FSA_Template","Hose_Code"])
    df["Priority"] = df["Priority"].astype(int)

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


def option_rows(row, stocked_sets=None):
    stocked_sets = stocked_sets or {}
    fsa = str(row["FSA_Template"])
    hose = str(row["Hose_Code"])
    c1 = str(row["Clamp1_Code"])
    c2 = str(row["Clamp2_Code"])

    def badge(kind: str, sku: str) -> str:
        s = stocked_sets.get(kind, set())
        return "✅ Stocked" if sku in s else "🟨 Orderable"

    backend = f'{c1} × {int(row["Clamp1_Qty"]) if pd.notna(row["Clamp1_Qty"]) else "—"}'
    stern = f'{c2} × {int(row["Clamp2_Qty"]) if pd.notna(row["Clamp2_Qty"]) else "—"}'
    priority = int(row["Priority"])
    meaning = PRIORITY_MAP.get(priority, "Custom rule")

    rows = [
        ("FSA", fsa),
        ("Hose", hose),
        ("Clamp (Backend)", backend),
        ("Clamp (Stern)", stern),
        ("Total clamps / kit", str(clamp_total(row))),
        ("Priority", str(priority)),
        ("Priority meaning", meaning),
    ]

    if stocked_sets:
        rows.insert(1, ("FSA status", badge("FSA", fsa)))
        rows.insert(3, ("Hose status", badge("HOSE", hose)))
        rows.insert(5, ("Clamp (Backend) status", badge("CLAMP", c1)))
        rows.insert(7, ("Clamp (Stern) status", badge("CLAMP", c2)))

    return rows


def inject_css():
    css = (
        "<style>\n"
        f":root {{ --tides-blue: {TIDES_BLUE}; --tides-teal: {TIDES_TEAL}; --tides-grey: {TIDES_GREY}; }}\n"
        "h1, h2, h3 { color: var(--tides-blue) !important; }\n"
        "div[data-testid='stExpander'] summary { border-left: 4px solid var(--tides-teal); padding-left: 0.5rem; }\n"
        ".small-muted { color: var(--tides-grey); font-size: 0.95rem; }\n"
        "div[data-testid='stTable'] table { width: 100%; }\n"
        "</style>\n"
    )
    st.markdown(css, unsafe_allow_html=True)


def safe_index(options, value, fallback=0):
    try:
        return options.index(value)
    except Exception:
        return fallback


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

    # ---- Sidebar ----
    st.sidebar.header("Measurements")

    # Defaults
    if "ms" not in st.session_state:
        st.session_state["ms"] = "Imperial"

    if "mode" not in st.session_state:
        st.session_state["mode"] = "Stocked by us"

    # Availability toggle FIRST (so dropdowns reflect it)
    mode = st.sidebar.radio(
        "Parts availability",
        ["Stocked by us", "Stocked + Can order"],
        index=0 if st.session_state["mode"] == "Stocked by us" else 1,
        key="mode",
    )

    ms_union = sorted(set(df_stocked["Measurement_System"].unique()).union(set(df_orderable["Measurement_System"].unique())))
    if st.session_state["ms"] not in ms_union:
        st.session_state["ms"] = ms_union[0] if ms_union else "Imperial"
    ms = st.sidebar.selectbox("Measurement system", ms_union, index=safe_index(ms_union, st.session_state["ms"]), key="ms")

    # Use chosen mode to populate shaft/stern lists
    df_mode = df_stocked if mode == "Stocked by us" else df_orderable
    dms_mode = df_mode[df_mode["Measurement_System"] == ms].copy()
    if dms_mode.empty:
        st.warning(f"No {ms} data found for {mode}.")
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
        format_func=lambda x: f"{x:.0f}" if shaft_units == "mm" else f"{x:.3f}",
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
        format_func=lambda x: f"{x:.0f}" if stern_units == "mm" else f"{x:.3f}",
        key="stern",
    )

    # Small debug helper (toggle in sidebar)
    with st.sidebar.expander("Debug"):
        st.write("Rows (stocked):", len(df_stocked))
        st.write("Rows (orderable):", len(df_orderable))
        st.write("Mode rows:", len(dms_mode))
        st.write("Metric shaft sizes in mode:", sorted(dms_mode[dms_mode.ShaftUnits=="mm"].ShaftSize.unique().tolist()))

    converter_ui()

    # ---- After toggle: use chosen mode data but keep shaft/stern if possible ----
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
    if cand.empty:
        st.warning("No build options found for this shaft/stern combination.")
        st.stop()

    cand = cand.sort_values(["Priority", "Is_US_Recommended"], ascending=[True, False]).reset_index(drop=True)

    stocked_sets = {
        "FSA": set(df_stocked["FSA_Template"].unique().tolist()),
        "HOSE": set(df_stocked["Hose_Code"].unique().tolist()),
        "CLAMP": set(pd.concat([df_stocked["Clamp1_Code"], df_stocked["Clamp2_Code"]]).unique().tolist()),
    } if mode != "Stocked by us" else None

    st.subheader("Build options")
    st.write(f"**Shaft:** {fmt(shaft, shaft_units)}  |  **Stern OD:** {fmt(stern, stern_units)}")
    st.caption(f"If twin engines + crossover hose needed: **{crossover_label(shaft, shaft_units)}**")

    if mode != "Stocked by us":
        st.markdown("<div class='small-muted'>🟨 Orderable = not currently stocked, but can be ordered in.</div>", unsafe_allow_html=True)

    for i, row in cand.iterrows():
        priority = int(row["Priority"])
        meaning = PRIORITY_MAP.get(priority, "Custom rule")
        header = f"Option {i+1} · Priority {priority} — {meaning}"
        expanded = (i == 0)

        with st.expander(header, expanded=expanded):
            st.table(pd.DataFrame(option_rows(row, stocked_sets=stocked_sets), columns=["Part", "Value"]))

            with st.expander("Advanced", expanded=False):
                adv_items = [
                    ("US recommended", "Yes" if bool(row["Is_US_Recommended"]) else ""),
                    ("Stretch type", str(row.get("Stretch_Type", ""))),
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
