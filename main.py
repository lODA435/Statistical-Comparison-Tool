import time
import requests
from datetime import datetime
from flask import Flask, render_template, request

app = Flask(__name__)
all_players_data = []


def make_request(url):
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print("Request error:", e)
    return None


def check_profile_privacy(account_id):
    player_data = make_request(f"https://api.opendota.com/api/players/{account_id}")

    if player_data and 'profile' in player_data and player_data['profile']:
        return (
            player_data['profile'].get('personaname'),
            player_data['profile'].get('avatarfull')
        )
    return None, None


def get_player_info(account_id, limit):
    player_data = {}

    player_name, avatar_url = check_profile_privacy(account_id)

    if not player_name:
        return {
            "player_name": "Private profile",
            "avatar_url": None,
            "matches": []
        }

    player_data['player_name'] = player_name
    player_data['avatar_url'] = avatar_url

    matches_data = make_request(
        f"https://api.opendota.com/api/players/{account_id}/matches?limit={limit}"
    )

    player_data['matches'] = extract_matches(matches_data or [], account_id)
    return player_data


def extract_matches(matches_data, account_id):
    matches_list = []

    heroes_data = make_request("https://api.opendota.com/api/heroes") or []
    hero_icons = {hero['id']: hero.get('icon') for hero in heroes_data}

    for match in matches_data:
        match_details = {}

        start_time = datetime.fromtimestamp(
            match.get('start_time', 0)
        ).strftime('%d-%m-%Y %H:%M:%S')

        hero_id = match.get('hero_id', 0)

        hero_name = next(
            (hero['localized_name'] for hero in heroes_data if hero['id'] == hero_id),
            'Hero name not found'
        )

        win_status = "Won" if match['radiant_win'] == (match['player_slot'] < 128) else "Lost"

        kills = match.get('kills', 0)
        deaths = match.get('deaths', 0)
        assists = match.get('assists', 0)

        match_details['start_time'] = start_time
        match_details['hero_name'] = hero_name
        match_details['hero_icon'] = hero_icons.get(hero_id)
        match_details['win_status'] = win_status
        match_details['score'] = f"{kills}-{deaths}-{assists}"

        match_id = match.get('match_id')
        if match_id:
            match_data = make_request(f"https://api.opendota.com/api/matches/{match_id}")

            if match_data:
                player_info = next(
                    (pl for pl in match_data.get('players', [])
                     if pl.get('account_id') == int(account_id)),
                    None
                )

                if player_info:
                    match_details['gold_per_min'] = player_info.get('gold_per_min')
                    match_details['xp_per_min'] = player_info.get('xp_per_min')
                    match_details['net_worth'] = player_info.get('net_worth')

        matches_list.append(match_details)

        time.sleep(0.1)

    return matches_list


def print_player_data(player_data):
    if not player_data:
        return

    total_kills = total_deaths = total_assists = 0
    total_gold_per_min = total_xp_per_min = total_net_worth = 0
    total_score = total_wins = 0

    for match in player_data['matches']:
        k, d, a = map(int, match['score'].split('-'))

        total_kills += k
        total_deaths += d
        total_assists += a
        total_score += (k + a) / d if d != 0 else (k + a)

        total_gold_per_min += match.get('gold_per_min', 0)
        total_xp_per_min += match.get('xp_per_min', 0)
        total_net_worth += match.get('net_worth', 0)

        if match['win_status'] == 'Won':
            total_wins += 1

    n = len(player_data['matches'])
    if n == 0:
        return

    print("Average K:", total_kills / n)
    print("Average D:", total_deaths / n)
    print("Average A:", total_assists / n)
    print("Winrate:", (total_wins / n) * 100)


def process_ids(ids, limit):
    result = []
    for account_id in ids:
        result.append(get_player_info(account_id, limit))
    return result


@app.route('/', methods=['GET', 'POST'])
def index():
    global all_players_data

    if request.method == 'POST':
        count_search_matches = int(request.form['count_matches'])
        player1_id = request.form['player1_id']
        player2_id = request.form['player2_id']

        all_players_data = process_ids(
            [player1_id, player2_id],
            count_search_matches
        )

    user1_data = all_players_data[0] if len(all_players_data) > 0 else {}
    user2_data = all_players_data[1] if len(all_players_data) > 1 else {}

    return render_template(
        'index.html',
        user1_data=user1_data,
        user2_data=user2_data
    )


if __name__ == '__main__':
    app.run(debug=True)
