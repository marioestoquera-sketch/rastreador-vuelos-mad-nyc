import os
import sqlite3
from datetime import datetime, timedelta
from serpapi import GoogleSearch

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
DB_PATH = "madrid_nyc_flights.db"

# Destinos y fechas objetivo (4 personas, estancias de 8 días directos)
TARGETS = [
    {
        "city": "Nueva York",
        "arrival_id": "/m/02_286",  # JFK / EWR / LGA
        "dates": [
            "2027-06-11", "2027-06-15", "2027-06-19",
            "2027-06-23", "2027-06-27", "2027-06-30"
        ]
    },
    {
        "city": "Edimburgo",
        "arrival_id": "EDI",        # Aeropuerto de Edimburgo
        "dates": [
            "2027-06-12", "2027-06-18", "2027-06-24", # Quincena de junio
            "2027-09-01", "2027-09-03", "2027-09-05"  # Primera semana de septiembre
        ]
    }
]

TRIP_DURATION_DAYS = 8
PASSENGERS = 4

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
            passengers INTEGER,
            airline TEXT,
            flight_number TEXT,
            stops INTEGER,
            price_eur REAL,
            price_per_passenger REAL,
            currency TEXT
        )
    """)
    conn.commit()
    conn.close()

def fetch_and_store_prices():
    if not SERPAPI_KEY:
        print("ERROR: Falta SERPAPI_KEY.")
        return

    today = datetime.now()
    day_of_year = today.timetuple().tm_yday

    # Para no superar la cuota mensual de SerpApi:
    # 1 consulta a NYC y 1 consulta a Edimburgo cada día (rotando fechas)
    queries_today = []
    for target in TARGETS:
        date_idx = day_of_year % len(target["dates"])
        queries_today.append((target["city"], target["arrival_id"], target["dates"][date_idx]))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    total_saved = 0

    for city, arrival_id, dep_date in queries_today:
        dep_dt = datetime.strptime(dep_date, "%Y-%m-%d")
        ret_date = (dep_dt + timedelta(days=TRIP_DURATION_DAYS)).strftime("%Y-%m-%d")
        days_in_advance = (dep_dt - today).days

        if days_in_advance < 0:
            continue

        params = {
            "engine": "google_flights",
            "departure_id": "MAD",
            "arrival_id": arrival_id,
            "outbound_date": dep_date,
            "return_date": ret_date,
            "adults": PASSENGERS,
            "stops": 1,  # Solo directos
            "currency": "EUR",
            "hl": "es",
            "api_key": SERPAPI_KEY
        }

        print(f"Consultando MAD ➔ {city} ({arrival_id}) para {dep_date}...")
        search = GoogleSearch(params)
        results = search.get_dict()

        if "error" in results:
            print(f"Aviso ({city} - {dep_date}): {results['error']}")
            continue

        best_flights = results.get("best_flights", [])
        other_flights = results.get("other_flights", [])
        all_offers = best_flights + other_flights

        for group in all_offers:
            total_price = group.get("price")
            if not total_price:
                continue

            legs = group.get("flights", [])
            if not legs:
                continue

            # Filtro directo estricto
            if len(legs) > 1:
                continue

            airline = legs[0].get("airline", "Desconocida")
            flight_no = legs[0].get("flight_number", "N/A")
            arrival_airport = legs[-1].get("arrival_airport", {}).get("id", arrival_id)
            price_pax = round(float(total_price) / PASSENGERS, 2)

            cursor.execute("""
                INSERT INTO flight_prices (
                    query_timestamp, days_before_flight, origin, destination_city,
                    arrival_airport, departure_date, return_date, trip_duration_days,
                    passengers, airline, flight_number, stops, price_eur, price_per_passenger, currency
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                today.strftime("%Y-%m-%d %H:%M:%S"),
                days_in_advance,
                "MAD",
                city,
                arrival_airport,
                dep_date,
                ret_date,
                TRIP_DURATION_DAYS,
                PASSENGERS,
                airline,
                flight_no,
                0,
                float(total_price),
                price_pax,
                "EUR"
            ))
            total_saved += 1

    conn.commit()
    conn.close()
    print(f"Finalizado: {total_saved} ofertas guardadas en total.")

if __name__ == "__main__":
    init_db()
    fetch_and_store_prices()
