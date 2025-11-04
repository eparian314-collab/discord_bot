import requests

class PokemonAPIIntegration:
    def __init__(self):
        self.pokeapi_base_url = "https://pokeapi.co/api/v2/"
        self.graphql_pokemon_url = "https://graphql-pokeapi.vercel.app/api/graphql"

    def get_pokemon_data(self, pokemon_name):
        """Fetch Pokémon data from PokéAPI."""
        response = requests.get(f"{self.pokeapi_base_url}pokemon/{pokemon_name}")
        if response.status_code == 200:
            return response.json()
        return None

    def get_pokemon_graphql(self, query):
        """Fetch Pokémon data using GraphQL Pokémon API."""
        response = requests.post(self.graphql_pokemon_url, json={"query": query})
        if response.status_code == 200:
            return response.json()
        return None

    def get_pokemon_showdown_data(self):
        """Fetch Pokémon competitive data from Pokémon Showdown."""
        # Placeholder for Pokémon Showdown integration
        # You can use the Pokémon Showdown data repository or API for this
        return "Competitive data integration is pending."

