import os
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Monitor Vuelos MAD - NYC",
    page_icon="✈️",
    layout="wide"
)

DB_PATH = "madrid_nyc_flights.db"

st.title("✈️ Monitor de Vuelos: Madrid ➔ Nueva York")
st.caption("Rastreo para 4 pasajeros (2 adultos + 2 niños) · Salidas del 11 al 30 de junio de 2027 · Estancias de 8 días")

def load_data():
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql_query("SELECT * FROM flight_prices ORDER BY query_timestamp DESC, price_eur ASC", conn)
    except Exception:
        df = None
    finally:
        conn.close()
    return df

df = load_data()

if df is None or df.empty:
    st.warning("No se han encontrado registros todavía en la base de datos.")
    st.info("Asegúrate de que el flujo de GitHub Actions se haya ejecutado al menos una vez para generar datos.")
    st.stop()

# Si no existiera la columna price_per_passenger en registros antiguos, se calcula
if "price_per_passenger" not in df.columns:
    df["price_per_passenger"] = (df["price_eur"] / 4).round(2)

# Normalizar formato de fecha de consulta
df["query_day"] = df["query_timestamp"].str.slice(0, 10)

# Métrica de mejor oferta histórica
min_row = df.loc[df["price_eur"].idxmin()]
min_total = min_row["price_eur"]
min_pax = min_row["price_per_passenger"]
avg_total = df["price_eur"].mean()

# Ventana recomendada de reserva (130-160 días antes de la salida óptima)
best_dep = pd.to_datetime(min_row["departure_date"])
window_start = (best_dep - pd.Timedelta(days=160)).strftime("%d/%m/%Y")
window_end = (best_dep - pd.Timedelta(days=130)).strftime("%d/%m/%Y")

# Panel destacado de predicción de compra
st.success(f"""
### 🎯 Recomendación de Compra
Para obtener la tarifa más baja de cara a junio de 2027, el momento ideal para reservar se sitúa entre el **{window_start}** y el **{window_end}** (antelación recomendada de ~4 a 5 meses).  
**Mejor opción actual:** Salida el **{min_row['departure_date']}** con **{min_row['airline']}** ({min_row['arrival_airport']}) por **{min_total:,.0f} €** en total (**{min_pax:,.0f} €/persona**).
""")

# Tarjetas KPI
col1, col2, col3, col4 = st.columns(4)
col1.metric("Mínimo Total (4 pax)", f"{min_total:,.0f} €", f"{min_pax:,.0f} €/persona")
col2.metric("Promedio Total (4 pax)", f"{avg_total:,.0f} €", f"{(avg_total / 4):,.0f} €/persona")
col3.metric("Mejor Salida", min_row["departure_date"], f"{min_row['airline']} ({min_row['arrival_airport']})")
col4.metric("Ofertas Registradas", len(df), f"Última: {df['query_timestamp'].iloc[0][:10]}")

st.divider()

# Gráficos interactivos
g1, g2 = st.columns([3, 2])

with g1:
    st.subheader("Evolución del Precio Mínimo Diario (4 Personas)")
    daily_min = df.groupby("query_day")["price_eur"].min().reset_index()
    fig_timeline = px.line(
        daily_min,
        x="query_day",
        y="price_eur",
        labels={"query_day": "Fecha de Consulta", "price_eur": "Precio Total (€)"},
        markers=True,
        line_shape="spline"
    )
    fig_timeline.update_traces(line_color="#10b981", marker=dict(size=7))
    fig_timeline.update_layout(margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_timeline, use_container_width=True)

with g2:
    st.subheader("Precio Medio por Fecha de Salida")
    date_avg = df.groupby("departure_date")["price_eur"].mean().round(0).reset_index()
    fig_dates = px.bar(
        date_avg,
        x="departure_date",
        y="price_eur",
        labels={"departure_date": "Salida", "price_eur": "Media (€)"},
        text_auto=True
    )
    fig_dates.update_traces(marker_color="#6366f1")
    fig_dates.update_layout(margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_dates, use_container_width=True)

# Tabla interactiva con filtros
st.subheader("Historial Detallado de Vuelos Directos")

c_filtro1, c_filtro2 = st.columns(2)
with c_filtro1:
    selected_airline = st.multiselect("Filtrar por aerolínea:", options=df["airline"].unique(), default=df["airline"].unique())
with c_filtro2:
    selected_dates = st.multiselect("Filtrar por fecha de salida:", options=df["departure_date"].unique(), default=df["departure_date"].unique())

df_filtered = df[df["airline"].isin(selected_airline) & df["departure_date"].isin(selected_dates)]

display_cols = [
    "query_timestamp", "departure_date", "return_date", "arrival_airport",
    "airline", "flight_number", "days_before_flight", "price_per_passenger", "price_eur"
]
rename_cols = {
    "query_timestamp": "Consulta",
    "departure_date": "Ida",
    "return_date": "Vuelta",
    "arrival_airport": "Aeropuerto",
    "airline": "Aerolínea",
    "flight_number": "Vuelo",
    "days_before_flight": "Días Antelación",
    "price_per_passenger": "Precio/Persona (€)",
    "price_eur": "Total 4 Pax (€)"
}

st.dataframe(
    df_filtered[display_cols].rename(columns=rename_cols),
    use_container_width=True,
    hide_index=True
)
