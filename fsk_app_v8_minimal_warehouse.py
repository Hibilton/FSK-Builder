
import streamlit as st
import pandas as pd

st.set_page_config(page_title="FSK Warehouse Builder", layout="wide")

DATA_FILE = "fsk_build_options_generated_v5_stocked_only.csv"

@st.cache_data
def load_data():
    df = pd.read_csv(DATA_FILE)
    return df

df = load_data()

st.title("FSK Warehouse Builder")

# --- Dropdowns ---
systems = sorted(df["measurement_System"].dropna().unique())
system = st.selectbox("Measurement System", systems)

shaft_values = sorted(df[df["measurement_System"] == system]["shaft_Value"].dropna().unique())
shaft = st.selectbox("Shaft Size", shaft_values)

stern_values = sorted(
    df[
        (df["measurement_System"] == system) &
        (df["shaft_Value"] == shaft)
    ]["stern_Value"].dropna().unique()
)
stern = st.selectbox("Stern Tube OD", stern_values)

filtered = df[
    (df["measurement_System"] == system) &
    (df["shaft_Value"] == shaft) &
    (df["stern_Value"] == stern)
]

if filtered.empty:
    st.warning("No build options available for this combination.")
else:
    st.subheader("Available Build Combinations")

    display_cols = [
        "Priority",
        "FSA_SKU",
        "Hose_SKU",
        "Clamp_Backend_SKU",
        "Clamp_Backend_Qty_Per_End",
        "Clamp_Stern_SKU",
        "Clamp_Stern_Qty_Per_End",
        "Total_Clamps_Per_Kit"
    ]

    display_df = filtered[display_cols].sort_values("Priority")
    st.dataframe(display_df, use_container_width=True)

    # --- Subtle crossover suggestion ---
    try:
        shaft_float = float(shaft)
        if system == "Imperial":
            if shaft_float <= 2.75:
                crossover = "CROSSOVER KITF (3/8\")"
            else:
                crossover = "CROSSOVER KIT2F (1/2\")"
        else:
            if shaft_float <= 70:
                crossover = "CROSSOVER KITF (3/8\")"
            else:
                crossover = "CROSSOVER KIT2F (1/2\")"
        st.caption(f"Suggested crossover kit (if twin engines): {crossover}")
    except:
        pass

    # --- Advanced Section ---
    with st.expander("Advanced"):
        adv_cols = [
            "US_Recommended",
            "Stretch_Backend_In",
            "Stretch_Stern_In",
            "FSK_SKU"
        ]
        adv_existing = [c for c in adv_cols if c in filtered.columns]
        if adv_existing:
            st.dataframe(filtered[adv_existing].sort_values("Priority"), use_container_width=True)
        else:
            st.info("No advanced data available.")
