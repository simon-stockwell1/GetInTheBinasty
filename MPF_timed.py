import schedule
import time
import datetime
from threading import Thread
import requests
import pandas as pd

# Sleeper league information
league_id = '1070076580350734336'

# Function to get players info from Sleeper API
def get_players_info():
    print("Fetching player information from Sleeper API...")
    response = requests.get("https://api.sleeper.app/v1/players/nfl")
    if response.status_code == 200:
        print("Player information fetched successfully.")
    else:
        print("Failed to fetch player information.")
    return response.json()

# Function to get the league rosters, including taxi squad players
def get_rosters(league_id):
    print(f"Fetching rosters for league ID {league_id}...")
    response = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/rosters")
    if response.status_code == 200:
        print("Rosters fetched successfully.")
    else:
        print("Failed to fetch rosters.")
        return []

    return response.json()

# Function to get the league users (for team names)
def get_league_users(league_id):
    print(f"Fetching users for league ID {league_id} to get team names...")
    response = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/users")
    if response.status_code == 200:
        print("Users fetched successfully.")
    else:
        print("Failed to fetch users.")
    return response.json()

# Function to get the league matchups for the specified year and week
def get_matchups(league_id, year, week):
    print(f"Fetching matchups for league ID {league_id} for year {year}, week {week}...")
    response = requests.get(f"https://api.sleeper.app/v1/league/{league_id}/matchups/{week}?season={year}")
    if response.status_code == 200:
        print("Matchups fetched successfully.")
    else:
        print("Failed to fetch matchups.")
    return response.json()

# Function to calculate the max possible points (PF) for each team
def calculate_max_pf(df):
    max_pf_by_team = {}
    optimal_lineups = []

    # Get unique team names from column 'Team Name'
    team_names = df['Team Name'].unique()

    for team_name in team_names:
        team_df = df[df['Team Name'] == team_name]  # Filter data for the team

        # Split the team data by position
        qbs = team_df[team_df['Position'] == 'QB']
        rbs = team_df[team_df['Position'] == 'RB']
        wrs = team_df[team_df['Position'] == 'WR']
        tes = team_df[team_df['Position'] == 'TE']
        ks = team_df[team_df['Position'] == 'K']
        defs = team_df[team_df['Position'] == 'DEF']

        # Check if the team has enough players to meet the roster requirements
        if qbs.empty or rbs.shape[0] < 2 or wrs.shape[0] < 3 or tes.empty or ks.empty or defs.empty:
            print(f"Team {team_name} does not have enough players to meet the roster requirements.")
            continue

        # Get the top 1 QB
        top_qb = qbs.nlargest(1, 'Points')

        # Get the top 2 RBs
        top_rbs = rbs.nlargest(2, 'Points')

        # Get the top 3 WRs
        top_wrs = wrs.nlargest(3, 'Points')

        # Get the top 1 TE
        top_te = tes.nlargest(1, 'Points')

        # Get the top 1 K
        top_k = ks.nlargest(1, 'Points')

        # Get the top 1 DEF
        top_def = defs.nlargest(1, 'Points')

        # Combine remaining RBs, WRs, and TEs for FLEX
        remaining_flex_players = pd.concat([rbs[~rbs.index.isin(top_rbs.index)],
                                            wrs[~wrs.index.isin(top_wrs.index)],
                                            tes[~tes.index.isin(top_te.index)]])

        # Get the top 3 FLEX players
        top_flex = remaining_flex_players.nlargest(3, 'Points')

        # Calculate total max points for the team
        total_points = (top_qb['Points'].sum() +
                        top_rbs['Points'].sum() +
                        top_wrs['Points'].sum() +
                        top_te['Points'].sum() +
                        top_k['Points'].sum() +
                        top_def['Points'].sum() +
                        top_flex['Points'].sum())

        # Store the result using team name
        max_pf_by_team[team_name] = total_points

        # Append optimal lineup
        optimal_lineup = pd.concat([top_qb, top_rbs, top_wrs, top_te, top_k, top_def, top_flex])
        optimal_lineup['Team Name'] = team_name
        optimal_lineups.append(optimal_lineup)

    return max_pf_by_team, pd.concat(optimal_lineups)

# Function to process the rosters and calculate the max PF
def process_rosters_and_matchups(league_id, year, week):
    players_info = get_players_info()
    rosters = get_rosters(league_id)
    matchups = get_matchups(league_id, year, week)
    users = get_league_users(league_id)

    print("Processing rosters and matchup data...")

    # Create a mapping of roster_id to team name from users data
    team_name_map = {user['user_id']: user['display_name'] for user in users}

    # Dictionary to map roster_id to points scored in the matchup
    points_by_player = {}
    for matchup in matchups:
        points_by_player.update(matchup.get('players_points', {}))

    # List to hold data for all players
    data = []
    taxi_data = []

    # Collect player data from rosters
    for roster in rosters:
        team_id = roster['roster_id']
        owner_id = roster['owner_id']
        team_name = team_name_map.get(owner_id, f"Unknown Team (ID: {team_id})")
        players = roster['players']
        taxi_players = roster.get('taxi', [])

        for player_id in players:
            player = players_info.get(player_id, {})
            player_name = player.get('full_name', f'Unknown Player (ID: {player_id})')
            position = player.get('position', 'Unknown Position')
            points = points_by_player.get(player_id, 0)  # Get points or default to 0

            # Append data to the list
            data.append({
                'Team Name': team_name,
                'Team ID': team_id,
                'Player': player_name,
                'Position': position,
                'Points': points
            })

        # Collect taxi squad data
        for taxi_player_id in taxi_players:
            taxi_player = players_info.get(taxi_player_id, {})
            taxi_player_name = taxi_player.get('full_name', f'Unknown Player (ID: {taxi_player_id})')
            position = taxi_player.get('position', 'Unknown Position')

            # Append taxi squad data
            taxi_data.append({
                'Team Name': team_name,
                'Player': taxi_player_name,
                'Position': position
            })

    df = pd.DataFrame(data)
    taxi_df = pd.DataFrame(taxi_data)

    # Calculate the max PF and get optimal lineups
    max_pf_by_team, optimal_lineups = calculate_max_pf(df)

    # Output the results
    for team_name, max_pf in max_pf_by_team.items():
        print(f"Team {team_name}: Max PF = {max_pf:.2f} points")

    # Save the optimal lineup CSV for verification
    optimal_filename = f'sleeper_{year}_week_{week}_optimal_lineups.csv'
    optimal_lineups.to_csv(optimal_filename, index=False)
    print(f"Optimal team lineups have been saved to {optimal_filename}")

    # Save the taxi squad CSV
    taxi_filename = f'sleeper_{year}_week_{week}_taxi_squads.csv'
    taxi_df.to_csv(taxi_filename, index=False)
    print(f"Taxi squad players have been saved to {taxi_filename}")

# Function to run the scheduled job
def run_scheduled_job(year, week):
    process_rosters_and_matchups(league_id, year, week)

# Function to keep the scheduler running in a separate thread
def run_scheduler_continuously():
    while True:
        schedule.run_pending()
        time.sleep(1)  # Sleep for 1 second between checks

# Main function that gets user input and sets up the scheduler
def main():
    # Request year and week before starting
    year = int(input("Enter the year (e.g., 2023): "))
    week = int(input("Enter the week number: "))

    # Schedule the job to run every Tuesday at 6:00 AM
    schedule.every().tuesday.at("07:39").do(run_scheduled_job, year, week)

    # Run the scheduler in a background thread
    scheduler_thread = Thread(target=run_scheduler_continuously)
    scheduler_thread.daemon = True
    scheduler_thread.start()

    print("Scheduler is running. Waiting for Tuesday at 6:00 AM...")
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(60)  # Sleep for 60 seconds to keep the main thread alive
    except KeyboardInterrupt:
        print("Scheduler stopped.")

if __name__ == "__main__":
    main()
