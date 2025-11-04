#!/usr/bin/env python3
import os
import sys
import sqlite3
import logging

def check_database(db_path):
    try:
        conn = sqlite3.connect(db_path)
        conn.execute('SELECT 1')
        conn.close()
        return True
    except Exception as e:
        logging.error(f"Database health check failed: {e}")
        return False

def check_env(env_path):
    return os.path.exists(env_path)

def main():
    logging.basicConfig(filename='health_check.log', level=logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')
    healthy = True
    # Check main database
    if not check_database('data/game_data.db'):
        logging.error('Main database check failed.')
        healthy = False
    # Check event rankings database
    if not check_database('data/event_rankings.db'):
        logging.error('Event rankings database check failed.')
        healthy = False
    # Check .env file
    if not check_env('.env'):
        logging.error('.env file missing.')
        healthy = False
    if healthy:
        logging.info('Health check passed.')
        sys.exit(0)
    else:
        logging.error('Health check failed.')
        sys.exit(1)

if __name__ == '__main__':
    main()


