"""
Tests for tool formatter functions — no API keys required.
Run with: uv run pytest tests/
"""

import pytest
from backend.tools.flights import parse_flights, format_flights_for_marco
from backend.tools.hotels import parse_hotels, format_hotels_for_marco
from backend.tools.places import parse_places, format_places_for_marco
from backend.tools.weather import format_weather_for_marco


# ── Flights ───────────────────────────────────────────────────────────────────

SAMPLE_RAW_FLIGHTS = [
    {
        "flights": [
            {
                "airline": "Air India",
                "flight_number": "AI123",
                "airline_logo": "https://example.com/logo.png",
                "departure_airport": {"id": "AMS", "time": "2026-09-01 10:00"},
                "arrival_airport": {"id": "DEL", "time": "2026-09-01 22:00"},
                "often_delayed_by_over_30_min": False,
                "overnight": False,
            }
        ],
        "layovers": [],
        "total_duration": 480,
        "price": 350,
        "type": "One way",
    },
    {
        "flights": [
            {
                "airline": "KLM",
                "flight_number": "KL456",
                "airline_logo": "https://example.com/klm.png",
                "departure_airport": {"id": "AMS", "time": "2026-09-01 07:00"},
                "arrival_airport": {"id": "DEL", "time": "2026-09-01 19:30"},
                "often_delayed_by_over_30_min": False,
                "overnight": False,
            }
        ],
        "layovers": [],
        "total_duration": 390,
        "price": 520,
        "type": "One way",
    },
]


class TestParseFlight:
    def test_parse_returns_correct_count(self):
        result = parse_flights(SAMPLE_RAW_FLIGHTS)
        assert len(result) == 2

    def test_parse_extracts_airline(self):
        result = parse_flights(SAMPLE_RAW_FLIGHTS)
        assert result[0]["airline"] == "Air India"

    def test_parse_extracts_price(self):
        result = parse_flights(SAMPLE_RAW_FLIGHTS)
        assert result[0]["price"] == 350

    def test_parse_calculates_duration(self):
        result = parse_flights(SAMPLE_RAW_FLIGHTS)
        assert result[0]["duration"] == "8h 0m"

    def test_parse_direct_flight_label(self):
        result = parse_flights(SAMPLE_RAW_FLIGHTS)
        assert result[0]["stop_label"] == "Direct"

    def test_parse_empty_list(self):
        assert parse_flights([]) == []

    def test_parse_skips_malformed_entry(self):
        bad = [{"flights": []}]  # no legs — should be skipped
        result = parse_flights(bad)
        assert result == []


class TestFormatFlightsForMarco:
    def test_format_empty_returns_no_flights_message(self):
        text = format_flights_for_marco([], "Amsterdam", "Delhi")
        assert "No flights found" in text

    def test_format_includes_airline(self):
        flights = parse_flights(SAMPLE_RAW_FLIGHTS)
        text = format_flights_for_marco(flights, "Amsterdam", "Delhi")
        assert "Air India" in text

    def test_format_highlights_cheapest(self):
        flights = parse_flights(SAMPLE_RAW_FLIGHTS)
        text = format_flights_for_marco(flights, "Amsterdam", "Delhi")
        assert "Cheapest" in text
        assert "€350" in text

    def test_format_highlights_fastest(self):
        flights = parse_flights(SAMPLE_RAW_FLIGHTS)
        text = format_flights_for_marco(flights, "Amsterdam", "Delhi")
        assert "Fastest" in text

    def test_format_single_flight_no_fastest_line(self):
        # When only one flight, cheapest == fastest — fastest line should be omitted
        one_flight = parse_flights([SAMPLE_RAW_FLIGHTS[0]])
        text = format_flights_for_marco(one_flight, "Amsterdam", "Delhi")
        assert "Fastest" not in text


# ── Hotels ────────────────────────────────────────────────────────────────────

SAMPLE_RAW_HOTELS = [
    {
        "name": "Old Town Hostel",
        "rate_per_night": {"lowest": "€25", "extracted_lowest": 25},
        "total_rate": {"lowest": "€75"},
        "overall_rating": 4.2,
        "reviews": 320,
        "type": "Hostel",
        "amenities": ["Free WiFi", "Breakfast", "Lockers"],
    },
    {
        "name": "Grand Hotel Krakow",
        "rate_per_night": {"lowest": "€110", "extracted_lowest": 110},
        "total_rate": {"lowest": "€330"},
        "overall_rating": 4.8,
        "reviews": 1200,
        "type": "Hotel",
        "amenities": ["Pool", "Spa", "Restaurant", "Free WiFi", "Bar"],
    },
]


class TestParseHotels:
    def test_parse_returns_correct_count(self):
        result = parse_hotels(SAMPLE_RAW_HOTELS)
        assert len(result) == 2

    def test_parse_extracts_name(self):
        result = parse_hotels(SAMPLE_RAW_HOTELS)
        assert result[0]["name"] == "Old Town Hostel"

    def test_parse_extracts_rating(self):
        result = parse_hotels(SAMPLE_RAW_HOTELS)
        assert result[1]["rating"] == 4.8

    def test_parse_amenities_capped_at_5(self):
        result = parse_hotels(SAMPLE_RAW_HOTELS)
        assert len(result[1]["amenities"]) <= 5


class TestFormatHotelsForMarco:
    def test_format_empty_returns_no_hotels_message(self):
        text = format_hotels_for_marco([], "Krakow", "2026-05-01", "2026-05-04")
        assert "No hotels found" in text

    def test_format_includes_hotel_name(self):
        hotels = parse_hotels(SAMPLE_RAW_HOTELS)
        text = format_hotels_for_marco(hotels, "Krakow", "2026-05-01", "2026-05-04")
        assert "Grand Hotel Krakow" in text

    def test_format_highlights_cheapest(self):
        hotels = parse_hotels(SAMPLE_RAW_HOTELS)
        text = format_hotels_for_marco(hotels, "Krakow", "2026-05-01", "2026-05-04")
        assert "Cheapest" in text
        assert "Old Town Hostel" in text

    def test_format_highlights_top_rated(self):
        hotels = parse_hotels(SAMPLE_RAW_HOTELS)
        text = format_hotels_for_marco(hotels, "Krakow", "2026-05-01", "2026-05-04")
        assert "Top rated" in text
        assert "Grand Hotel Krakow" in text


# ── Places ────────────────────────────────────────────────────────────────────

SAMPLE_RAW_PLACES = [
    {
        "title": "Hawelka Restaurant",
        "rating": 4.5,
        "reviews": 1800,
        "type": "Polish restaurant",
        "address": "Rynek Główny 34, Kraków",
        "hours": "12:00 PM – 10:00 PM",
        "price": "$$",
        "description": "Traditional Polish cuisine in a historic setting.",
    },
    {
        "title": "Wierzynek",
        "rating": 4.3,
        "reviews": 950,
        "type": "Fine dining",
        "address": "Rynek Główny 15, Kraków",
        "hours": "1:00 PM – 11:00 PM",
        "price": "$$$",
        "description": "One of Europe's oldest restaurants.",
    },
]


class TestParsePlaces:
    def test_parse_returns_correct_count(self):
        result = parse_places(SAMPLE_RAW_PLACES)
        assert len(result) == 2

    def test_parse_extracts_name(self):
        result = parse_places(SAMPLE_RAW_PLACES)
        assert result[0]["name"] == "Hawelka Restaurant"

    def test_parse_extracts_rating(self):
        result = parse_places(SAMPLE_RAW_PLACES)
        assert result[0]["rating"] == 4.5


class TestFormatPlacesForMarco:
    def test_format_empty_returns_no_results_message(self):
        text = format_places_for_marco([], "restaurants", "Krakow")
        assert "No places data available" in text

    def test_format_includes_place_name(self):
        places = parse_places(SAMPLE_RAW_PLACES)
        text = format_places_for_marco(places, "traditional restaurants", "Krakow")
        assert "Hawelka Restaurant" in text

    def test_format_includes_address(self):
        places = parse_places(SAMPLE_RAW_PLACES)
        text = format_places_for_marco(places, "traditional restaurants", "Krakow")
        assert "Rynek Główny" in text

    def test_format_includes_hours(self):
        places = parse_places(SAMPLE_RAW_PLACES)
        text = format_places_for_marco(places, "traditional restaurants", "Krakow")
        assert "12:00 PM" in text


# ── Weather ───────────────────────────────────────────────────────────────────

SAMPLE_WEATHER = {
    "city": "Krakow",
    "country": "PL",
    "forecast": [
        {"date": "2026-05-01", "condition": "Clear", "min_temp": 10.0, "max_temp": 22.0, "avg_temp": 16.0, "rain_expected": False},
        {"date": "2026-05-02", "condition": "Rain", "min_temp": 8.0, "max_temp": 15.0, "avg_temp": 11.0, "rain_expected": True},
        {"date": "2026-05-03", "condition": "Clouds", "min_temp": 9.0, "max_temp": 18.0, "avg_temp": 13.5, "rain_expected": False},
    ],
}


class TestFormatWeatherForMarco:
    def test_format_includes_city(self):
        text = format_weather_for_marco(SAMPLE_WEATHER)
        assert "Krakow" in text

    def test_format_includes_all_dates(self):
        text = format_weather_for_marco(SAMPLE_WEATHER)
        assert "2026-05-01" in text
        assert "2026-05-02" in text
        assert "2026-05-03" in text

    def test_format_marks_rain_days(self):
        text = format_weather_for_marco(SAMPLE_WEATHER)
        assert "☔" in text

    def test_format_includes_temperature_range(self):
        text = format_weather_for_marco(SAMPLE_WEATHER)
        assert "10.0" in text
        assert "22.0" in text

    def test_format_error_dict(self):
        text = format_weather_for_marco({"error": "Could not find location: XYZ"})
        assert "unavailable" in text.lower() or "error" in text.lower()
