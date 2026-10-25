import os
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Monitor de Vuelos: NYC & Edimburgo",
    page_icon="✈️",
    layout="wide"
)

DB_PATH = "madrid_nyc_flights.db"

st.title("✈️ Monitor de Vuelos Vacacionales (4 Pasajeros)")
st.caption("Rastreo diario de vuelos directos desde Madrid (MAD) · Estancias de 8 días")

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
    st.warning("No se han encontrado registros en la base de datos todavía.")
    st.info("Espera a la ejecución del flujo de GitHub Actions o lánzalo manualmente.")
    st.stop()

if "price_per_passenger" not in df.columns:
    df["price_per_passenger"] = (df["price_eur"] / 4).round(2)

df["query_day"] = df["query_timestamp"].str.slice(0, 10)

# Selector de destino principal
available_cities = sorted(df["destination_city"].unique().tolist())
selected_city = st.radio(
    "Selecciona el destino a analizar:",
    options=["Todos los destinos"] + available_cities,
    horizontal=True
)

if selected_city != "Todos los destinos":
    df_city = df[df["destination_city"] == selected_city].copy()
else:
    df_city = df.copy()

if df_city.empty:
    st.info(f"Aún no hay datos registrados para {selected_city}.")
    st.stop()

# Análisis de la mejor tarifa histórica
min_row = df_city.loc[df_city["price_eur"].idxmin()]
min_total = min_row["price_eur"]
min_pax = min_row["price_per_passenger"]
avg_total = df_city["price_eur"].mean()

# Fecha en la que se encontró ese precio mínimo
min_query_date = min_row["query_timestamp"][:10]  # Formato YYYY-MM-DD
min_query_days_ago = min_row["days_before_flight"]

# Ventana recomendada según el destino
best_dep = pd.to_datetime(min_row["departure_date"])
is_europe = "Edimburgo" in min_row["destination_city"]
days_window_start = 90 if is_europe else 160
days_window_end = 60 if is_europe else 130

window_start = (best_dep - pd.Timedelta(days=days_window_start)).strftime("%d/%m/%Y")
window_end = (best_dep - pd.Timedelta(days=days_window_end)).strftime("%d/%m/%Y")

# Tarjeta destacada de recomendación
st.success(f"""
### 🎯 Recomendación de Compra ({min_row['destination_city']})
* **Fecha ideal para reservar:** entre el **{window_start}** y el **{window_end}** (antelación recomendada de ~{days_window_end}-{days_window_start} días).  
* **Tarifa más baja registrada:** Salida el **{min_row['departure_date']}** hacia **{min_row['arrival_airport']}** con **{min_row['airline']}** por **{min_total:,.0f} €** total (**{min_pax:,.0f} €/persona**).  
* **Detectada el:** **{min_query_date}** (a {min_query_days_ago} días de antelación).
""")

# Tarjetas KPI
col1, col2, col3, col4 = st.columns(4)

# Aquí se añade la fecha de detección del precio mínimo en el subtítulo del KPI
col1.metric(
    label="Mínimo Total (4 pax)",
    value=f"{min_total:,.0f} €",
    delta=f"Visto el {min_query_date} ({min_pax:,.0f} €/pax)",
    delta_color="off"
)
col2.metric("Promedio Total (4 pax)", f"{avg_total:,.0f} €", f"{(avg_total / 4):,.0f} €/persona")
col3.metric("Mejor Salida", min_row["departure_date"], f"{min_row['airline']} ({min_row['arrival_airport']})")
col4.metric("Ofertas Analizadas", len(df_city), f"Última consulta: {df_city['query_timestamp'].iloc[0][:10]}")

st.divider()

# Gráficos interactivos
g1, g2 = st.columns([3, 2])

with g1:
    st.subheader(f"Evolución del Precio Mínimo Diario ({selected_city})")
    daily_min = df_city.groupby(["query_day", "destination_city"])["price_eur"].min().reset_index()
    fig_timeline = px.line(
        daily_min,
        x="query_day",
        y="price_eur",
        color="destination_city" if selected_city == "Todos los destinos" else None,
        labels={"query_day": "Fecha Consulta", "price_eur": "Precio Total (€)", "destination_city": "Destino"},
        markers=True
    )
    fig_timeline.update_layout(margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_timeline, use_container_width=True)

with g2:
    st.subheader("Comparativa de Precios por Fecha de Salida")
    date_avg = df_city.groupby(["departure_date", "destination_city"])["price_eur"].mean().round(0).reset_index()
    fig_dates = px.bar(
        date_avg,
        x="departure_date",
        y="price_eur",
        color="destination_city" if selected_city == "Todos los destinos" else None,
        barmode="group",
        labels={"departure_date": "Fecha Salida", "price_eur": "Media (€)", "destination_city": "Destino"},
        text_auto=True
    )
    fig_dates.update_layout(margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig_dates, use_container_width=True)

# Tabla interactiva
st.subheader("Listado Detallado de Vuelos Directos")

c1, c2 = st.columns(2)
with c1:
    selected_airlines = st.multiselect("Aerolínea:", options=df_city["airline"].unique(), default=df_city["airline"].unique())
with c2:
    selected_dates = st.multiselect("Fecha de salida:", options=df_city["departure_date"].unique(), default=df_city["departure_date"].unique())

df_filtered = df_city[df_city["airline"].isin(selected_airlines) & df_city["departure_date"].isin(selected_dates)]

display_cols = [
    "query_timestamp", "destination_city", "departure_date", "return_date",
    "arrival_airport", "airline", "flight_number", "days_before_flight",
    "price_per_passenger", "price_eur"
]
rename_cols = {
    "query_timestamp": "Fecha Consulta",
    "destination_city": "Destino",
    "departure_date": "Ida",
    "return_date": "Vuelta",
    "arrival_airport": "Aeropuerto",
    "airline": "Aerolínea",
    "flight_number": "Vuelo",
    "days_before_flight": "Antelación (días)",
    "price_per_passenger": "Precio/Pax (€)",
    "price_eur": "Total 4 Pax (€)"
}

st.dataframe(
    df_filtered[display_cols].rename(columns=rename_cols),
    use_container_width=True,
    hide_index=True
)
