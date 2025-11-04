from cachetools import TTLCache
from games.storage.game_storage_engine import GameStorageEngine

class GameStorageEngineWithCache:
    def __init__(self, db_path="data/game_data.db"):
        self.storage = GameStorageEngine(db_path)
        self.cache = TTLCache(maxsize=1000, ttl=300)  # Cache with 1000 items and 5-minute TTL

    def get_user_cookies(self, user_id):
        if user_id in self.cache:
            return self.cache[user_id]

        # Fetch from database and update cache
        cookies = self.storage.get_user_cookies(user_id)
        self.cache[user_id] = cookies
        return cookies

    def update_cookies(self, user_id, total_cookies=None, cookies_left=None):
        # Update database
        self.storage.update_cookies(user_id, total_cookies, cookies_left)

        # Update cache
        if user_id in self.cache:
            current_cookies = self.cache[user_id]
            updated_cookies = (
                total_cookies if total_cookies is not None else current_cookies[0],
                cookies_left if cookies_left is not None else current_cookies[1]
            )
            self.cache[user_id] = updated_cookies
        else:
            self.cache[user_id] = (total_cookies, cookies_left)

    def invalidate_cache(self, user_id):
        if user_id in self.cache:
            del self.cache[user_id]