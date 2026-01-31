import os
import requests
import sqlite3
import json
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime
from dateutil.parser import parse
from dateutil.tz import tzutc
from dotenv import load_dotenv
import matplotlib.pyplot as plt

load_dotenv()


def main():
    conn = sqlite3.connect("tennis-odds.db")
    conn.execute("PRAGMA foreign_keys = ON")  # enable foreign key constraints
    cur = conn.cursor()

    tournament = 'tennis_atp_aus_open_singles'
    api_base_url = f'https://api.the-odds-api.com/v4/sports/{tournament}/odds/'
    general_params = {
        'apiKey': os.getenv('ODDS_API_KEY'),
        'markets': 'h2h',
        'bookmakers': 'draftkings',
    }

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
    #                                 "price": 1.67
    #                             },
    #                             {
    #                                 "name": "Iga Swiatek",
    #                                 "price": 2.3
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
    #                                 "price": 1.82
    #                             },
    #                             {
    #                                 "name": "Jessica Pegula",
    #                                 "price": 2.03
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
    #                                 "price": 1.25
    #                             },
    #                             {
    #                                 "name": "Elina Svitolina",
    #                                 "price": 3.87
    #                             }
    #                         ]
    #                     }
    #                 ]
    #             }
    #         ]
    #     }
    # ]

    active_api_match_ids = []

    for match in matches_json:
        api_match_id = match.get('id')
        player_1 = match.get('home_team')
        player_2 = match.get('away_team')
        start_time_utc = match.get('commence_time')

        # skip if match hasn't started
        if parse(start_time_utc) > datetime.now(tzutc()):
            continue

        active_api_match_ids.append(api_match_id)

        create_match_entry_query = f"""
            INSERT OR IGNORE INTO Match (api_match_id, tournament, start_time, player_1, player_2)
            VALUES ("{api_match_id}", "{tournament}", "{start_time_utc}", "{player_1}", "{player_2}");
        """
        cur.execute(create_match_entry_query)

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

    # get finished matches (in db but not returned by api)
    get_finished_matches_query = f"""
        SELECT api_match_id, player_1, player_1_moneyline, player_2, player_2_moneyline, last_update_time 
        FROM Odds 
        WHERE api_match_id NOT IN ({", ".join([f'"{x}"' for x in active_api_match_ids])})
    """
    cur.execute(get_finished_matches_query)
    finished_match_rows = cur.fetchall()

    # process finished matches rows
    finished_match_odds_by_api_match_id = {}
    for finished_match_row in finished_match_rows:
        api_match_id, player_1, player_1_moneyline, player_2, player_2_moneyline, last_update_datetime = finished_match_row
        last_update_time = last_update_datetime[last_update_datetime.find('T') + 1: last_update_datetime.find('Z') - 3]
        if api_match_id in finished_match_odds_by_api_match_id:
            finished_match_odds_by_api_match_id[api_match_id][player_1].append(player_1_moneyline)
            finished_match_odds_by_api_match_id[api_match_id][player_2].append(player_2_moneyline)
            finished_match_odds_by_api_match_id[api_match_id]['last_update_times'].append(last_update_time)
        else:
            finished_match_odds_by_api_match_id[api_match_id] = {
                player_1: [player_1_moneyline],
                player_2: [player_2_moneyline],
                'last_update_times': [last_update_time],
            }
    
    # save images
    image_paths = []
    for match in finished_match_odds_by_api_match_id.values():
        player_1, player_2, _ = match.keys()
        player_1_odds, player_2_odds, last_update_times = match.values()
        if len(player_1_odds) > 3:
            image_path = f'plots/{player_1.replace(" ", "")}_{player_2.replace(" ", "")}.jpg'
            plt.figure()
            plt.plot(last_update_times, player_1_odds, marker='o', label=player_1)
            plt.plot(last_update_times, player_2_odds, marker='o', label=player_2)
            plt.title(f'{player_1} vs. {player_2}')
            plt.xlabel('Last update time')
            plt.ylabel('Odds')
            plt.xticks(rotation=45)
            plt.grid(True)
            plt.legend()
            plt.savefig(image_path)
            image_paths.append(image_path)
    
    if len(image_paths) > 0:
        send_email(subject="Tennis Odds", body="", attachment_paths=image_paths)

    # delete finished matches from db
    delete_finished_matches_query = f'DELETE FROM Match WHERE api_match_id NOT IN ({", ".join([f'"{x}"' for x in active_api_match_ids])})'
    cur.execute(delete_finished_matches_query)

    conn.commit()
    conn.close()


def send_email(subject, body, attachment_paths=[]):
    port = 587  # for starttls
    smtp_server = "smtp.gmail.com"
    sender_receiver_email = "scottldev9@gmail.com"
    password = os.getenv('GMAIL_APP_PSWD')

    image_p_tags = ''.join([f'<p><img src="cid:image{idx}"></p>' for idx, _ in enumerate(attachment_paths)])
    body_html = f"""
        <html>
            <body>
                {image_p_tags}
            </body>
        </html>
    """
    
    message = MIMEMultipart()
    message['From'] = sender_receiver_email
    message['To'] = sender_receiver_email
    message['Subject'] = subject
    message.attach(MIMEText(body_html, "html"))

    for idx, attachment_path in enumerate(attachment_paths):
        with open(attachment_path, 'rb') as img:
            msg_img = MIMEImage(img.read(), name=os.path.basename(attachment_path))
            msg_img.add_header('Content-ID', f'<image{idx}>')
            message.attach(msg_img)

    context = ssl.create_default_context()
    with smtplib.SMTP(smtp_server, port) as server:
        server.starttls(context=context)
        server.login(sender_receiver_email, password)
        server.sendmail(sender_receiver_email, sender_receiver_email, message.as_string())


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
