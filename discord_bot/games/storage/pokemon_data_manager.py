import sqlite3

class PokemonDataManager:
    def __init__(self, db_path="pokemon_data.db"):
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        with self.conn:
            self.conn.execute("""
            CREATE TABLE IF NOT EXISTS pokemon_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                api_source TEXT NOT NULL,
                base_experience INTEGER,
                height INTEGER,
                weight INTEGER,
                stats TEXT
            );
            """)

    def insert_pokemon_data(self, name, api_source, base_experience, height, weight, stats):
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO pokemon_data (name, api_source, base_experience, height, weight, stats)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (name, api_source, base_experience, height, weight, stats)
            )

    def get_repeating_pokemon(self):
        """Identify Pokémon with the same name but different stats."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT name, COUNT(*) as count
            FROM pokemon_data
            GROUP BY name
            HAVING count > 1
            """
        )
        return cursor.fetchall()

    def get_pokemon_comparison(self, name):
        """Retrieve all entries for a specific Pokémon name to compare stats."""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM pokemon_data
            WHERE name = ?
            """,
            (name,)
        )
        return cursor.fetchall()