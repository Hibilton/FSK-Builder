import pathlib
import datetime
import io
import pandas as pd
import streamlit as st

CSV_STOCKED_ONLY = "fsk_build_options_generated_v4_stocked_only.csv"
CSV_STOCKED_OR_ORDERABLE = "fsk_build_options_generated_v4_stocked_or_orderable.csv"
SELECTION_LOG_FILE = "fsk_selection_log.csv"


@st.cache_data
def load_data(path: str):
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]

    expected_cols = [
        "System", "ShaftSize", "ShaftUnits", "SternSize", "SternUnits",
        "FSK_Template", "FSK_Notes", "Priority", "RuleType",
        "Is_US_Recommended", "Stretch_Type", "Stretch_Backend_in", "Stretch_Stern_in",
        "FSA_Template", "FSA_Tail_OD_in", "Hose_Code", "Hose_End1_in", "Hose_End2_in",
        "Clamp1_Code", "Clamp1_Qty", "Clamp2_Code", "Clamp2_Qty",
        "Comments",
    ]
    missing = [c for c in expected_cols if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns in CSV: {missing}")

    # Strip whitespace
    text_cols = [
        "System", "ShaftUnits", "SternUnits", "FSK_Template", "RuleType",
        "FSA_Template", "Hose_Code", "Clamp1_Code", "Clamp2_Code",
        "Stretch_Type", "Comments",
    ]
    for col in text_cols:
        df[col] = df[col].astype("string").str.strip()

    # Numeric coercion
    numeric_cols = [
        "ShaftSize", "SternSize", "Priority",
        "FSA_Tail_OD_in", "Hose_End1_in", "Hose_End2_in",
        "Stretch_Backend_in", "Stretch_Stern_in",
        "Clamp1_Qty", "Clamp2_Qty",
    ]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # Bool coercion
    df["Is_US_Recommended"] = df["Is_US_Recommended"].astype(str).str.lower().isin(["true", "1", "yes", "y"])

    base_mask = (
        df["System"].notna()
        & df["ShaftSize"].notna()
        & df["SternSize"].notna()
        & df["FSK_Template"].notna()
        & df["Priority"].notna()
    )
    bad_rows = df[~base_mask].copy()
    df = df[base_mask].copy()

    meta = {
        "total_rows": len(df) + len(bad_rows),
        "kept_rows": len(df),
        "dropped_rows": len(bad_rows),
    }
    return df, meta


@st.cache_data
def load_log(path: str):
    p = pathlib.Path(path)
    if not p.exists():
        return pd.DataFrame(columns=[
            "timestamp", "mode", "system", "shaft_size", "shaft_units", "stern_size", "stern_units",
            "fsk", "priority", "fsa", "hose", "clamp_backend", "clamp_backend_qty", "clamp_stern", "clamp_stern_qty",
            "is_us_recommended", "stretch_type"
        ])
    return pd.read_csv(p)


def append_log(path: str, record: dict):
    p = pathlib.Path(path)
    df = load_log(path)
    df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
    df.to_csv(p, index=False)
    load_log.clear()


def format_size(value: float, units: str) -> str:
    if pd.isna(value):
        return "—"
    if units == "mm":
        return f"{value:.0f} {units}"
    return f"{value:.3f} {units}"


def badge_stretch(stretch_type: str) -> str:
    if stretch_type == "None":
        return "🟢 None"
    if stretch_type == "Backend":
        return "🟡 Backend"
    if stretch_type == "Stern":
        return "🟠 Stern"
    if stretch_type == "Both":
        return "🔴 Both"
    return stretch_type or "—"


def build_pick_list(best: pd.Series, qty_fsk: int = 1) -> pd.DataFrame:
    """Return a simple BOM/pick list for warehouse packing."""
    qty_fsk = max(int(qty_fsk), 1)

    clamp1_qty = int(best["Clamp1_Qty"]) if pd.notna(best["Clamp1_Qty"]) else 0
    clamp2_qty = int(best["Clamp2_Qty"]) if pd.notna(best["Clamp2_Qty"]) else 0

    items = [
        {"SKU": best["FSK_Template"], "Qty": qty_fsk, "Role": "Kit (customer-facing)"},
        {"SKU": best["FSA_Template"], "Qty": qty_fsk, "Role": "Housing"},
        {"SKU": best["Hose_Code"], "Qty": qty_fsk, "Role": "Hose (cut/fit)"},
        {"SKU": best["Clamp1_Code"], "Qty": qty_fsk * clamp1_qty, "Role": "Clamps (backend)"},
        {"SKU": best["Clamp2_Code"], "Qty": qty_fsk * clamp2_qty, "Role": "Clamps (stern)"},
    ]
    df = pd.DataFrame(items)
    df["Qty"] = pd.to_numeric(df["Qty"], errors="coerce").fillna(0).astype(int)
    return df


def pick_list_text(best: pd.Series, qty_fsk: int) -> str:
    pl = build_pick_list(best, qty_fsk)
    lines = []
    lines.append(f"FSK PICK LIST — Qty FSK: {qty_fsk}")
    lines.append(f"FSK: {best['FSK_Template']}")
    lines.append(f"FSA: {best['FSA_Template']}")
    lines.append(f"Hose: {best['Hose_Code']}")
    lines.append(f"Clamps backend: {best['Clamp1_Code']} × {int(best['Clamp1_Qty']) if pd.notna(best['Clamp1_Qty']) else '—'} per kit")
    lines.append(f"Clamps stern: {best['Clamp2_Code']} × {int(best['Clamp2_Qty']) if pd.notna(best['Clamp2_Qty']) else '—'} per kit")
    lines.append("")
    lines.append("BOM totals:")
    for _, r in pl.iterrows():
        lines.append(f"- {r['SKU']} × {r['Qty']}  ({r['Role']})")
    return "\n".join(lines)


def main():
    st.set_page_config(page_title="FSK Builder", layout="wide")
    st.title("FSK Builder")

    st.sidebar.header("Build availability mode")
    mode = st.sidebar.radio(
        "Show builds using…",
        options=[
            "Stocked components only",
            "Stocked OR orderable components",
        ],
        index=0,
    )
    data_file = CSV_STOCKED_ONLY if mode == "Stocked components only" else CSV_STOCKED_OR_ORDERABLE
    st.sidebar.caption(f"Using: {data_file}")

    csv_path = pathlib.Path(data_file)
    if not csv_path.exists():
        st.error(f"Could not find data file: {csv_path.resolve()}")
        st.stop()

    try:
        df, meta = load_data(str(csv_path))
    except KeyError as e:
        st.error(f"CSV format error: {e}")
        st.stop()

    st.sidebar.header("Filters")
    systems = sorted(df["System"].dropna().unique().tolist())
    system = st.sidebar.radio("System", systems, horizontal=True)
    df_sys = df[df["System"] == system].copy()

    shaft_units = df_sys["ShaftUnits"].dropna().iloc[0]
    shaft_sizes = sorted(df_sys["ShaftSize"].dropna().unique().tolist())
    shaft_size = st.sidebar.selectbox("Shaft size", options=shaft_sizes, format_func=lambda x: format_size(x, shaft_units))
    df_shaft = df_sys[df_sys["ShaftSize"] == shaft_size].copy()

    stern_units = df_shaft["SternUnits"].dropna().iloc[0]
    stern_sizes = sorted(df_shaft["SternSize"].dropna().unique().tolist())
    stern_size = st.sidebar.selectbox("Stern tube size", options=stern_sizes, format_func=lambda x: format_size(x, stern_units))

    candidates = df_shaft[df_shaft["SternSize"] == stern_size].copy()
    if candidates.empty:
        st.error("No builds found for this exact combination in the selected availability mode.")
        st.stop()

    candidates_sorted = candidates.sort_values(["Priority", "Is_US_Recommended"], ascending=[True, False])
    best = candidates_sorted.iloc[0]

    st.subheader("Selection summary")
    st.write(
        f"**System:** {system}  |  "
        f"**Shaft:** {format_size(shaft_size, shaft_units)}  |  "
        f"**Stern tube:** {format_size(stern_size, stern_units)}  |  "
        f"**Mode:** {mode}"
    )

    st.markdown("### Recommended build (lowest Priority in selected dataset)")
    st.markdown(f"**FSK:** {best['FSK_Template']}")
    st.markdown(f"**FSA:** {best['FSA_Template']}")
    st.markdown(f"**Hose:** {best['Hose_Code']} ({best.get('Hose_End1_in', float('nan')):.3f}–{best.get('Hose_End2_in', float('nan')):.3f} in ends)")
    st.markdown(
        f"**Clamps:** "
        f"{best['Clamp1_Code']} × {int(best['Clamp1_Qty']) if pd.notna(best['Clamp1_Qty']) else '—'} (backend), "
        f"{best['Clamp2_Code']} × {int(best['Clamp2_Qty']) if pd.notna(best['Clamp2_Qty']) else '—'} (stern)"
    )
    st.write("**Rule type:**", best.get("RuleType", "—"))
    st.write("**Priority:**", int(best["Priority"]))
    st.write("**US Recommended:**", "Yes" if bool(best["Is_US_Recommended"]) else "No")
    st.write("**Stretch:**", badge_stretch(str(best.get("Stretch_Type",""))))

    st.markdown("---")
    st.markdown("## Warehouse pick list export")

    qty_fsk = st.number_input("Quantity of FSK kits to build", min_value=1, max_value=100, value=1, step=1)
    pick_df = build_pick_list(best, qty_fsk)
    st.dataframe(pick_df, use_container_width=True)

    csv_buf = io.StringIO()
    pick_df.to_csv(csv_buf, index=False)
    st.download_button(
        label="Download pick list CSV",
        data=csv_buf.getvalue().encode("utf-8"),
        file_name=f"pick_list_{best['FSK_Template']}_qty{qty_fsk}.csv".replace("/", "-"),
        mime="text/csv",
    )

    st.text_area("Copy/paste pick list", value=pick_list_text(best, qty_fsk), height=220)

    st.markdown("---")
    st.markdown("### Logging")
    if st.button("Log this selection"):
        record = {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "mode": mode,
            "system": system,
            "shaft_size": shaft_size,
            "shaft_units": shaft_units,
            "stern_size": stern_size,
            "stern_units": stern_units,
            "fsk": best["FSK_Template"],
            "priority": int(best["Priority"]),
            "fsa": best["FSA_Template"],
            "hose": best["Hose_Code"],
            "clamp_backend": best["Clamp1_Code"],
            "clamp_backend_qty": int(best["Clamp1_Qty"]) if pd.notna(best["Clamp1_Qty"]) else None,
            "clamp_stern": best["Clamp2_Code"],
            "clamp_stern_qty": int(best["Clamp2_Qty"]) if pd.notna(best["Clamp2_Qty"]) else None,
            "is_us_recommended": bool(best["Is_US_Recommended"]),
            "stretch_type": best.get("Stretch_Type",""),
        }
        append_log(SELECTION_LOG_FILE, record)
        st.success("Logged.")

    log_df = load_log(SELECTION_LOG_FILE)
    if not log_df.empty:
        st.markdown("### Most common selections (top 20)")
        top = (
            log_df.groupby(["system","shaft_units","shaft_size","stern_units","stern_size","fsk"])
            .size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .head(20)
        )
        st.dataframe(top, use_container_width=True)

        st.caption(f"Log file: {SELECTION_LOG_FILE} (stored locally where the app runs)")

    st.markdown("---")
    st.markdown("### All builds for this combination")
    display_cols = [
        "FSK_Template",
        "Priority",
        "Is_US_Recommended",
        "Stretch_Type",
        "FSA_Template",
        "Hose_Code",
        "Clamp1_Code", "Clamp1_Qty",
        "Clamp2_Code", "Clamp2_Qty",
        "RuleType",
        "Comments",
    ]
    st.dataframe(candidates_sorted[display_cols].reset_index(drop=True), use_container_width=True)


if __name__ == "__main__":
    main()
