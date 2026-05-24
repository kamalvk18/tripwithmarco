TOOL_DEFINITIONS = [
    {
        "name": "search_hotels",
        "description": """Search for real-time hotel prices at a destination.
        Use when the user asks about accommodation, where to stay, or nightly costs.
        When building a budget breakdown, call this once for the main destination only.""",
        "input_schema": {
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
    },
    {
        "name": "search_places",
        "description": """Search for restaurants, attractions, or activities at a destination.
        Use when the user asks where to eat, what to do, or wants specific venue recommendations.
        When building an itinerary, make at most 1-2 calls total — use a broad query like 'top things to do'
        or 'restaurants and attractions' rather than separate calls per category.
        query examples: 'top things to do', 'restaurants and attractions', 'hiking trails near city centre'""",
        "input_schema": {
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
    },
    {
        "name": "search_flights",
        "description": """Search for real-time flight prices between two airports.
        Use this when the user asks about flights, how to get somewhere, 
        flight costs, or when you want to include flight prices in a budget breakdown.
        Always use correct IATA airport codes.""",
        "input_schema": {
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
                }
            },
            "required": [
                "origin_iata",
                "origin_city",
                "destination_iata",
                "destination_city",
                "outbound_date"
            ]
        }
    },
    {
        "name": "get_weather_forecast",
        "description": """Get real-time weather forecast for a city.
        Use this during trip companion mode to check weather for today and upcoming days.
        Also use during planning if the user asks about weather at their destination.""",
        "input_schema": {
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
]