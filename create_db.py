import sqlite3

def main():
    con = sqlite3.connect("tennis-odds.db")
    # Enable foreign key constraints
    con.execute("PRAGMA foreign_keys = ON")
    
    cur = con.cursor()

    success, error_message = create_db_tables(cur)
    if not success:
        print(error_message)
    
    con.close()

def create_db_tables(cur):
    try:
        cur.execute("DROP TABLE IF EXISTS Odds")
        cur.execute("DROP TABLE IF EXISTS Match")
        create_match_table_query = """
            CREATE TABLE Match (
                api_match_id TEXT NOT NULL,
                tournament TEXT,
                start_time TEXT,
                player_1 TEXT NOT NULL,
                player_2 TEXT NOT NULL,
                PRIMARY KEY (api_match_id, player_1, player_2)
            );
        """
        cur.execute(create_match_table_query)
    except Exception as e:
        return False, f'Failed to create Match table: {e}'
    
    try:
        create_odds_table_query = """
            CREATE TABLE Odds (
                api_match_id TEXT,
                player_1 TEXT,
                player_1_moneyline FLOAT,
                player_2 TEXT,
                player_2_moneyline FLOAT,
                last_update_time TEXT,
                FOREIGN KEY(api_match_id, player_1, player_2) REFERENCES Match(api_match_id, player_1, player_2)
            );
        """
        cur.execute(create_odds_table_query)
    except Exception as e:
        return False, f'Failed to create Odds table: {e}'
    
    return True, ''


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f'error in main(): {e}')
