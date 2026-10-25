import os
import sqlite3
from datetime import datetime, timedelta
from serpapi import GoogleSearch

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
DB_PATH = "madrid_nyc_flights.db"

# Muestreo de salidas disponibles entre el 11 y el 30 de junio de 2027
DEPARTURE_DATES = [
    "2027-06-11",
    "2027-06-14",
    "2027-06-18",
    "2027-06-22",
    "2027-06-26",
    "2027-06-30"
]
TRIP_DURATION_DAYS = 8  # Estancia recomendada de 8 días

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flight_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_timestamp TEXT NOT NULL,
            days_before_flight INTEGER NOT NULL,
            origin TEXT NOT NULL,
            destination_city TEXT NOT NULL,
            arrival_airport TEXT,
            departure_date TEXT NOT NULL,
            return_date TEXT,
            trip_duration_days INTEGER,
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
    
    # Rotación: 2 consultas al día para mantenerse dentro de la cuota mensual gratuita
    day_of_year = today.timetuple().tm_yday
    idx1 = (day_of_year * 2) % len(DEPARTURE_DATES)
    idx2 = (day_of_year * 2 + 1) % len(DEPARTURE_DATES)
    dates_to_check = [DEPARTURE_DATES[idx1], DEPARTURE_DATES[idx2]]

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    total_inserted = 0

    for dep_date in dates_to_check:
        dep_dt = datetime.strptime(dep_date, "%Y-%m-%d")
        ret_date = (dep_dt + timedelta(days=TRIP_DURATION_DAYS)).strftime("%Y-%m-%d")
        days_in_advance = (dep_dt - today).days

        if days_in_advance < 0:
            continue

        # /m/02_286 consulta todos los aeropuertos de NYC (JFK, Newark, LaGuardia)
        params = {
            "engine": "google_flights",
            "departure_id": "MAD",
            "arrival_id": "/m/02_286",
            "outbound_date": dep_date,
            "return_date": ret_date,
            "currency": "EUR",
            "hl": "es",
            "api_key": SERPAPI_KEY
        }

        print(f"Buscando salida {dep_date} y vuelta {ret_date} ({TRIP_DURATION_DAYS} días)...")
        search = GoogleSearch(params)
        results = search.get_dict()

        if "error" in results:
            print(f"Aviso para {dep_date}: {results['error']}")
            continue

        best_flights = results.get("best_flights", [])
        other_flights = results.get("other_flights", [])
        all_offers = best_flights + other_flights

        for flight_group in all_offers[:5]:
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

            last_leg = flights_list[-1]
            arrival_airport = last_leg.get("arrival_airport", {}).get("id", "NYC")

            cursor.execute("""
                INSERT INTO flight_prices (
                    query_timestamp, days_before_flight, origin, destination_city,
                    arrival_airport, departure_date, return_date, trip_duration_days,
                    airline, flight_number, stops, price_eur, currency
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                today.strftime("%Y-%m-%d %H:%M:%S"),
                days_in_advance,
                "MAD",
                "NYC",
                arrival_airport,
                dep_date,
                ret_date,
                TRIP_DURATION_DAYS,
                airline,
                flight_no,
                stops,
                float(price),
                "EUR"
            ))
            total_inserted += 1

    conn.commit()
    conn.close()
    print(f"Finalizado: {total_inserted} opciones guardadas.")

if __name__ == "__main__":
    init_db()
    fetch_and_store_prices()
