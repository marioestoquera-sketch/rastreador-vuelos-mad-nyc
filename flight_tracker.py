import os
import sqlite3
from datetime import datetime
from serpapi import GoogleSearch

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
DB_PATH = "madrid_nyc_flights.db"

# Fechas fijas de tu viaje objetivo (por ejemplo, salida el 11 de junio y regreso el 25 de junio de 2027)
TARGET_DEP_DATE = "2027-06-11"
TARGET_RET_DATE = "2027-06-25"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flight_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_timestamp TEXT NOT NULL,
            days_before_flight INTEGER NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            departure_date TEXT NOT NULL,
            return_date TEXT,
            airline TEXT,
            flight_number TEXT,
            stops INTEGER,
            price_eur REAL,
            currency TEXT
        )
    """)
    conn.commit()
    conn.close()

def fetch_and_store_prices():
    if not SERPAPI_KEY:
        print("ERROR: No se encontró la variable SERPAPI_KEY.")
        return

    today = datetime.now()
    dep_datetime = datetime.strptime(TARGET_DEP_DATE, "%Y-%m-%d")
    
    # Días de antelación con los que se realiza la consulta hoy
    days_in_advance = (dep_datetime - today).days

    if days_in_advance < 0:
        print("La fecha del viaje ya ha pasado.")
        return

    params = {
        "engine": "google_flights",
        "departure_id": "MAD",
        "arrival_id": "JFK",
        "outbound_date": TARGET_DEP_DATE,
        "return_date": TARGET_RET_DATE,
        "currency": "EUR",
        "hl": "es",
        "api_key": SERPAPI_KEY
    }

    print(f"[{today.strftime('%Y-%m-%d')}] Consultando tarifas MAD -> JFK para {TARGET_DEP_DATE} (Antelación: {days_in_advance} días)...")
    
    search = GoogleSearch(params)
    results = search.get_dict()

    if "error" in results:
        print(f"Error de SerpApi: {results['error']}")
        return

    best_flights = results.get("best_flights", [])
    other_flights = results.get("other_flights", [])
    all_offers = best_flights + other_flights

    print(f"Ofertas encontradas: {len(all_offers)}")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    records_inserted = 0

    for flight_group in all_offers[:10]:
        price = flight_group.get("price")
        if not price:
            continue

        flights_list = flight_group.get("flights", [])
        if not flights_list:
            continue

        first_leg = flights_list[0]
        airline = first_leg.get("airline", "Desconocida")
        flight_no = first_leg.get("flight_number", "N/A")
        stops = len(flights_list) - 1

        cursor.execute("""
            INSERT INTO flight_prices (
                query_timestamp, days_before_flight, origin, destination,
                departure_date, return_date, airline, flight_number, stops, price_eur, currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            today.strftime("%Y-%m-%d %H:%M:%S"),
            days_in_advance,
            "MAD",
            "JFK",
            TARGET_DEP_DATE,
            TARGET_RET_DATE,
            airline,
            flight_no,
            stops,
            float(price),
            "EUR"
        ))
        records_inserted += 1

    conn.commit()
    conn.close()
    print(f"Éxito: {records_inserted} tarifas guardadas.")

if __name__ == "__main__":
    init_db()
    fetch_and_store_prices()
