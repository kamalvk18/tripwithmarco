TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": """Search for real-time hotel prices at a destination.
        Use when the user asks about accommodation, where to stay, or nightly costs.
        When building a budget breakdown, call this once for the main destination only.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "destination": {
                        "type": "string",
                        "description": "City or area name e.g. 'Kraków, Poland', 'Barcelona'"
                    },
                    "check_in_date": {
                        "type": "string",
                        "description": "Check-in date in YYYY-MM-DD format"
                    },
                    "check_out_date": {
                        "type": "string",
                        "description": "Check-out date in YYYY-MM-DD format"
                    }
                },
                "required": ["destination", "check_in_date", "check_out_date"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_places",
            "description": """Search for restaurants, attractions, or activities at a destination.
        Use when the user asks where to eat, what to do, or wants specific venue recommendations.
        When building an itinerary, make at most 1-2 calls total — use a broad query like 'top things to do'
        or 'restaurants and attractions' rather than separate calls per category.
        query examples: 'top things to do', 'restaurants and attractions', 'hiking trails near city centre'""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for e.g. 'traditional Polish restaurants', 'things to do', 'night markets'"
                    },
                    "location": {
                        "type": "string",
                        "description": "City or area e.g. 'Kraków, Poland', 'Barcelona, Spain'"
                    }
                },
                "required": ["query", "location"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": """Search for real-time flight prices between two airports.
        Only call this when flying is the appropriate transport mode (intercontinental routes,
        or domestic routes where a flight genuinely saves significant time).
        Do NOT call for journeys better served by train, bus, car, or ferry.
        Always use correct IATA airport codes.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin_iata": {
                        "type": "string",
                        "description": "IATA code of departure airport e.g. AMS, LHR, JFK"
                    },
                    "origin_city": {
                        "type": "string",
                        "description": "Human readable origin city name e.g. Amsterdam"
                    },
                    "destination_iata": {
                        "type": "string",
                        "description": "IATA code of destination airport e.g. MUC, BCN, LIS"
                    },
                    "destination_city": {
                        "type": "string",
                        "description": "Human readable destination city name e.g. Munich"
                    },
                    "outbound_date": {
                        "type": "string",
                        "description": "Departure date in YYYY-MM-DD format"
                    },
                    "return_date": {
                        "type": "string",
                        "description": "Return date in YYYY-MM-DD format. Omit for one-way."
                    },
                    "currency": {
                        "type": "string",
                        "description": "ISO 4217 currency code for prices e.g. EUR, USD, INR, GBP. Use the user's selected currency."
                    }
                },
                "required": [
                    "origin_iata",
                    "origin_city",
                    "destination_iata",
                    "destination_city",
                    "outbound_date",
                    "currency"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather_forecast",
            "description": """Get real-time weather forecast for a city.
        Only call this if the trip or activity starts within the next 7 days — forecasts beyond that are unreliable.
        For trips further out, use your knowledge of typical seasonal weather for that destination and time of year instead.
        Use this during companion mode to check weather for today and upcoming days.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "City name e.g. Salzburg, Munich, Barcelona"
                    },
                    "country_code": {
                        "type": "string",
                        "description": "2-letter ISO country code e.g. AT, DE, ES"
                    }
                },
                "required": ["city"]
            }
        }
    }
]
