import os
import sqlite3
from datetime import datetime, timedelta
from serpapi import GoogleSearch

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
DB_PATH = "madrid_nyc_flights.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS flight_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_timestamp TEXT NOT NULL,
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
    today = datetime.now()
    dep_date = (today + timedelta(days=60)).strftime("%Y-%m-%d")
    ret_date = (today + timedelta(days=67)).strftime("%Y-%m-%d")

    params = {
        "engine": "google_flights",
        "departure_id": "MAD",
        "arrival_id": "NYC",
        "outbound_date": dep_date,
        "return_date": ret_date,
        "currency": "EUR",
        "hl": "es",
        "api_key": SERPAPI_KEY
    }

    search = GoogleSearch(params)
    results = search.get_dict()

    best_flights = results.get("best_flights", [])
    other_flights = results.get("other_flights", [])
    all_offers = best_flights + other_flights

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    records_inserted = 0

    for flight_group in all_offers[:5]:
        price = flight_group.get("price")
        if not price:
            continue

        first_leg = flight_group.get("flights", [])[0]
        airline = first_leg.get("airline", "Desconocida")
        flight_no = first_leg.get("flight_number", "N/A")
        stops = len(flight_group.get("flights", [])) - 1

        cursor.execute("""
            INSERT INTO flight_prices (
                query_timestamp, origin, destination, departure_date,
                return_date, airline, flight_number, stops, price_eur, currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            today.strftime("%Y-%m-%d %H:%M:%S"),
            "MAD",
            "NYC",
            dep_date,
            ret_date,
            airline,
            flight_no,
            stops,
            float(price),
            "EUR"
        ))
        records_inserted += 1

    conn.commit()
    conn.close()
    print(f"Completado: {records_inserted} tarifas guardadas.")

if __name__ == "__main__":
    init_db()
    fetch_and_store_prices()
