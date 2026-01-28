import os
import requests
import sqlite3
import json
import smtplib
import ssl
from datetime import datetime
from dateutil.parser import parse
from dateutil.tz import tzutc
from dotenv import load_dotenv

load_dotenv()


def main():
    conn = sqlite3.connect("tennis-odds.db")
    conn.execute("PRAGMA foreign_keys = ON")  # enable foreign key constraints
    cur = conn.cursor()

    tournament = 'tennis_wta_aus_open_singles'
    api_base_url = f'https://api.the-odds-api.com/v4/sports/{tournament}/odds/'
    general_params = {
        'apiKey': os.getenv('ODDS_API_KEY'),
        'markets': 'h2h',
        'bookmakers': 'draftkings',
    }
    tournaments = ['tennis_atp_aus_open_singles',
                   'tennis_atp_canadian_open',
                   'tennis_atp_china_open',
                   'tennis_atp_cincinnati_open',
                   'tennis_atp_dubai',
                   'tennis_atp_french_open',
                   'tennis_atp_indian_wells',
                   'tennis_atp_italian_open',
                   'tennis_atp_madrid_open',
                   'tennis_atp_miami_open',
                   'tennis_atp_monte_carlo_masters',
                   'tennis_atp_paris_masters',
                   'tennis_atp_qatar_open',
                   'tennis_atp_shanghai_masters',
                   'tennis_atp_us_open',
                   'tennis_atp_wimbledon',
                   'tennis_wta_aus_open_singles',
                   'tennis_wta_canadian_open',
                   'tennis_wta_china_open',
                   'tennis_wta_cincinnati_open',
                   'tennis_wta_dubai',
                   'tennis_wta_french_open',
                   'tennis_wta_indian_wells',
                   'tennis_wta_italian_open',
                   'tennis_wta_madrid_open',
                   'tennis_wta_miami_open',
                   'tennis_wta_qatar_open',
                   'tennis_wta_us_open',
                   'tennis_wta_wimbledon',
                   'tennis_wta_wuhan_open']

    matches_json = get_api_response(api_base_url, general_params)
    # matches_json = [
    #     {
    #         "id": "1d4a419bd92c0388bb01a6835b9b13ad",
    #         "sport_key": "tennis_wta_aus_open_singles",
    #         "sport_title": "WTA Australian Open",
    #         "commence_time": "2026-01-28T00:30:00Z",
    #         "home_team": "Elena Rybakina",
    #         "away_team": "Iga Swiatek",
    #         "bookmakers": [
    #             {
    #                 "key": "draftkings",
    #                 "title": "DraftKings",
    #                 "last_update": "2026-01-28T01:32:31Z",
    #                 "markets": [
    #                     {
    #                         "key": "h2h",
    #                         "last_update": "2026-01-28T01:32:31Z",
    #                         "outcomes": [
    #                             {
    #                                 "name": "Elena Rybakina",
    #                                 "price": 1.68
    #                             },
    #                             {
    #                                 "name": "Iga Swiatek",
    #                                 "price": 2.2
    #                             }
    #                         ]
    #                     }
    #                 ]
    #             }
    #         ]
    #     },
    #     {
    #         "id": "28f70894092e11447f05729cea3da348",
    #         "sport_key": "tennis_wta_aus_open_singles",
    #         "sport_title": "WTA Australian Open",
    #         "commence_time": "2026-01-28T02:10:00Z",
    #         "home_team": "Jessica Pegula",
    #         "away_team": "Amanda Anisimova",
    #         "bookmakers": [
    #             {
    #                 "key": "draftkings",
    #                 "title": "DraftKings",
    #                 "last_update": "2026-01-28T01:32:31Z",
    #                 "markets": [
    #                     {
    #                         "key": "h2h",
    #                         "last_update": "2026-01-28T01:32:31Z",
    #                         "outcomes": [
    #                             {
    #                                 "name": "Amanda Anisimova",
    #                                 "price": 1.81
    #                             },
    #                             {
    #                                 "name": "Jessica Pegula",
    #                                 "price": 2.01
    #                             }
    #                         ]
    #                     }
    #                 ]
    #             }
    #         ]
    #     },
    #     {
    #         "id": "3d22d20c45bd321a748c441dee6d20ac",
    #         "sport_key": "tennis_wta_aus_open_singles",
    #         "sport_title": "WTA Australian Open",
    #         "commence_time": "2026-01-29T00:00:21Z",
    #         "home_team": "Aryna Sabalenka",
    #         "away_team": "Elina Svitolina",
    #         "bookmakers": [
    #             {
    #                 "key": "draftkings",
    #                 "title": "DraftKings",
    #                 "last_update": "2026-01-28T01:32:31Z",
    #                 "markets": [
    #                     {
    #                         "key": "h2h",
    #                         "last_update": "2026-01-28T01:32:31Z",
    #                         "outcomes": [
    #                             {
    #                                 "name": "Aryna Sabalenka",
    #                                 "price": 1.28
    #                             },
    #                             {
    #                                 "name": "Elina Svitolina",
    #                                 "price": 3.86
    #                             }
    #                         ]
    #                     }
    #                 ]
    #             }
    #         ]
    #     }
    # ]

    now = datetime.now(tzutc())

    for match in matches_json:
        api_match_id = match.get('id')
        player_1 = match.get('home_team')
        player_2 = match.get('away_team')
        start_time_utc = match.get('commence_time')
        create_match_entry_query = f"""
            INSERT OR REPLACE INTO Match (api_match_id, tournament, start_time, player_1, player_2)
            VALUES ("{api_match_id}", "{tournament}", "{start_time_utc}", "{player_1}", "{player_2}");
        """
        cur.execute(create_match_entry_query)

        # skip if match hasn't started
        if parse(start_time_utc) > now:
            continue

        h2h_market = deep_get(match, ['bookmakers', 0, 'markets', 0], {})
        last_update_time = h2h_market.get('last_update')
        moneylines_by_player = {outcome.get('name'): outcome.get('price') for outcome in h2h_market.get('outcomes', [])}
        player_1_moneyline = moneylines_by_player.get(player_1)
        player_2_moneyline = moneylines_by_player.get(player_2)

        create_odds_entry_query = f"""
            INSERT INTO Odds (api_match_id, player_1, player_1_moneyline, player_2, player_2_moneyline, last_update_time)
            VALUES ("{api_match_id}", "{player_1}", {player_1_moneyline}, "{player_2}", {player_2_moneyline}, "{last_update_time}");
        """
        cur.execute(create_odds_entry_query)

    conn.commit()
    conn.close()


def send_email(message):
    # TODO: rewrite this
    smtp_server = "smtp.gmail.com"
    port = 587
    sender_email = "scottldev9@gmail.com"
    password = input("Type your password and press enter: ")
    receiver_email = "scottldev9@gmail.com"

    # Create a secure SSL context
    context = ssl.create_default_context()

    # Try to log in to server and send email
    try:
        server = smtplib.SMTP(smtp_server, port)
        server.starttls(context=context)  # Secure the connection
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message)
    except Exception as e:
        print(e)
    finally:
        server.quit()


def get_api_response(api_base_url, params_dict):
    headers = {'Content-Type': 'application/json'}
    params_str = '&'.join(
        [f'{param[0]}={param[1]}' for param in params_dict.items()])

    r = requests.get(f'{api_base_url}?{params_str}', headers=headers)
    if r.status_code != 200:
        raise Exception(f'request failed: {r.text.strip()}')

    response_text = r.text.strip()
    json_data = json.loads(response_text)

    return json_data


def deep_get(dictionary, keys, default=None):
    """
    Safely traverse a nested dictionary or list and return a value.

    Args:
        dictionary (dict or list): The dictionary or list to traverse.
        keys (list): A list of keys or indices representing the path to the desired value.
        default: The value to return if any key or index is missing, or the value is None.

    Returns:
        The value found at the specified path, or the default value.
    """
    current = dictionary
    for key in keys:
        if isinstance(current, dict):  # If current is a dictionary
            current = current.get(key, default)
        elif isinstance(current, list):  # If current is a list
            if isinstance(key, int) and -1 <= key < len(current):  # Ensure key is a valid index
                current = current[key]
            else:
                return default
        else:  # Neither dict nor list
            return default
        if current is None:
            return default
    return current


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f'error in main(): {e}')
