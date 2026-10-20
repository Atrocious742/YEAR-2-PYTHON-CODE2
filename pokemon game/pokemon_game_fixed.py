import csv
import random
import time
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

def load_csv(filename):
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {filename}. Put it in the same folder as pokemon.py."
        )
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))

class PokemonData:
    """Loads Pokémon, base stats, learnable moves and move power from the CSV files."""

    def __init__(self):
        self.pokemon_rows = load_csv("pokemon.csv")
        self.stat_rows = load_csv("pokemon_stats.csv")
        self.pokemon_move_rows = load_csv("pokemon_moves.csv")
        self.move_rows = load_csv("moves.csv")
        self.stat_name_rows = load_csv("stat_names.csv")
        self.stats_rows = load_csv("stats.csv")

        self.pokemon_by_id = {
            int(row["id"]): row for row in self.pokemon_rows
            if row.get("id", "").isdigit()
        }
        self.moves_by_id = {
            int(row["id"]): row for row in self.move_rows
            if row.get("id", "").isdigit()
        }
        self.stat_names = {}
        for row in self.stats_rows:
            if row.get("id", "").isdigit():
                self.stat_names[int(row["id"])] = row["identifier"].lower()

        self.stats_by_pokemon = {}
        for row in self.stat_rows:
            pid = int(row["pokemon_id"])
            stat_id = int(row["stat_id"])
            self.stats_by_pokemon.setdefault(pid, {})[
                self.stat_names.get(stat_id, str(stat_id))
            ] = int(row["base_stat"])

        self.moves_by_pokemon = {}
        # Keep level-up moves only, preferring the lowest level each Pokémon learns them.
        for row in self.pokemon_move_rows:
            if row.get("pokemon_move_method_id") != "1":
                continue
            pid = int(row["pokemon_id"])
            mid = int(row["move_id"])
            move = self.moves_by_id.get(mid)
            if not move:
                continue
            power = move.get("power", "")
            # Skip status moves and moves without numeric power for this simple battle system.
            if not power or not power.isdigit() or int(power) <= 0:
                continue
            level = int(row.get("level") or 1)
            self.moves_by_pokemon.setdefault(pid, {})
            previous = self.moves_by_pokemon[pid].get(mid)
            if previous is None or level < previous[0]:
                self.moves_by_pokemon[pid][mid] = (level, move)

    def get_pokemon(self, pokemon_id):
        row = self.pokemon_by_id[pokemon_id]
        stats = self.stats_by_pokemon.get(pokemon_id, {})
        learnable = self.moves_by_pokemon.get(pokemon_id, {})
        # Pick up to four usable moves. Prefer moves learned at low levels.
        candidates = sorted(learnable.values(), key=lambda item: (item[0], int(item[1]["id"])))
        chosen = []
        seen = set()
        for _, move in candidates:
            name = move["identifier"].replace("-", " ").title()
            if name not in seen:
                chosen.append((name, max(1, int(float(move["power"])))))
                seen.add(name)
            if len(chosen) == 4:
                break
        if not chosen:
            chosen = [("Tackle", 10)]
        return {
            "id": pokemon_id,
            "name": row["identifier"].replace("-", " ").title(),
            "hp": max(1, stats.get("hp", 50)),
            "attack": max(1, stats.get("attack", 50)),
            "moves": dict(chosen),
        }

    def available_kanto_ids(self):
        # Use the original 151 Pokémon, excluding alternate/non-default forms.
        return [
            pid for pid, row in self.pokemon_by_id.items()
            if 1 <= pid <= 151 and row.get("is_default", "1") == "1"
            and pid in self.stats_by_pokemon
        ]

class ActivePokemon:
    def __init__(self, data):
        self.id = data["id"]
        self.name = data["name"]
        self.max_hp = data["hp"]
        self.current_hp = self.max_hp
        self.attack_power = data["attack"]
        self.moves = data["moves"]

    def use_attack(self, move_name, opponent):
        move_damage = self.moves[move_name]
        total_damage = max(1, move_damage + int(self.attack_power * 0.2))
        print(f"\n💥 {self.name} used {move_name}!")
        opponent.take_damage(total_damage)

    def take_damage(self, amount):
        self.current_hp = max(0, self.current_hp - amount)
        print(f"❤️ {self.name} lost {amount} HP! (Remaining: {self.current_hp}/{self.max_hp})")
        if self.current_hp == 0:
            print(f"💀 {self.name} fainted!")

class Pokemon_game:
    STARTERS = {"bulbasaur": 1, "charmander": 4, "squirtle": 7}

    def __init__(self):
        self.data = PokemonData()
        self.name = ""
        self.rival_name = "Pedro"
        self.starter = None
        self.rival_starter = None
        self.player_team = []
        self.rival_team = []

    def get_name(self):
        self.name = input("Enter your name: ").strip() or "Trainer"
        print(f"Hello {self.name}, welcome to Pokémon!")

    # Keep the original method spelling so existing calls still work.
    def Get_name(self):
        return self.get_name()

    def Starter_selection(self):
        print("\nChoose your guaranteed starter:")
        print(" - Bulbasaur\n - Charmander\n - Squirtle")
        while True:
            choice = input("Enter your selection: ").strip().lower()
            if choice in self.STARTERS:
                self.starter = self.data.get_pokemon(self.STARTERS[choice])
                break
            print("Invalid selection. Choose bulbasaur, charmander, or squirtle.")

        rival_options = [
            (name, pid) for name, pid in self.STARTERS.items()
            if pid != self.starter["id"]
        ]
        rival_name, rival_id = random.choice(rival_options)
        self.rival_starter = self.data.get_pokemon(rival_id)
        print(f"\nYour starter is {self.starter['name']}!")
        return self.starter

    def Rival(self):
        print(f"Your rival {self.rival_name} has {self.rival_starter['name']} as their starter!")
        return self.rival_name, self.rival_starter

    def draft_team(self):
        all_ids = self.data.available_kanto_ids()
        starter_ids = set(self.STARTERS.values())
        pool = [pid for pid in all_ids if pid not in starter_ids]
        player_ids = {self.starter["id"]}
        self.player_team = [ActivePokemon(self.starter)]

        print("\n=== YOUR DRAFT ===")
        print("Your starter is locked in. Draft 5 more Pokémon to make a team of 6.")
        for round_number in range(1, 6):
            eligible = [pid for pid in pool if pid not in player_ids]
            options = random.sample(eligible, min(3, len(eligible)))
            print(f"\nDraft round {round_number} — choose one:")
            option_data = [self.data.get_pokemon(pid) for pid in options]
            for index, pokemon in enumerate(option_data, 1):
                print(f"{index}. {pokemon['name']} (HP {pokemon['hp']}, Attack {pokemon['attack']})")
                print(f"   Moves: {', '.join(pokemon['moves'].keys())}")
            while True:
                choice = input("Choose 1, 2, or 3: ").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(option_data):
                    selected = option_data[int(choice) - 1]
                    break
                print(f"Please enter a number from 1 to {len(option_data)}.")
            self.player_team.append(ActivePokemon(selected))
            player_ids.add(selected["id"])
            print(f"You drafted {selected['name']}!")

        # Rival always has a starter too, plus five random distinct Pokémon.
        rival_ids = {self.rival_starter["id"]}
        rival_pool = [pid for pid in pool if pid not in rival_ids]
        rival_picks = random.sample(rival_pool, min(5, len(rival_pool)))
        self.rival_team = [ActivePokemon(self.rival_starter)]
        self.rival_team.extend(ActivePokemon(self.data.get_pokemon(pid)) for pid in rival_picks)

        print("\n=== YOUR FINAL TEAM ===")
        for pokemon in self.player_team:
            print(f"- {pokemon.name} (HP {pokemon.max_hp}, Attack {pokemon.attack_power})")
        print(f"\n=== {self.rival_name.upper()}'S RANDOM TEAM ===")
        for pokemon in self.rival_team:
            print(f"- {pokemon.name} (HP {pokemon.max_hp}, Attack {pokemon.attack_power})")

    def battle(self):
        print(f"\n⚔️ {self.rival_name} challenges you to a six-on-six battle!")
        player_index = 0
        rival_index = 0

        while player_index < len(self.player_team) and rival_index < len(self.rival_team):
            player = self.player_team[player_index]
            rival = self.rival_team[rival_index]
            print(f"\n--- Your {player.name} ({player.current_hp}/{player.max_hp} HP) vs "
                  f"{rival.name} ({rival.current_hp}/{rival.max_hp} HP) ---")

            while player.current_hp > 0 and rival.current_hp > 0:
                print(f"\n{player.name}'s moves:")
                move_names = list(player.moves.keys())
                for index, move in enumerate(move_names, 1):
                    print(f"{index}. {move} (power {player.moves[move]})")
                while True:
                    choice = input("Choose a move number: ").strip()
                    if choice.isdigit() and 1 <= int(choice) <= len(move_names):
                        chosen_move = move_names[int(choice) - 1]
                        break
                    print(f"Please enter a number from 1 to {len(move_names)}.")

                player.use_attack(chosen_move, rival)
                if rival.current_hp <= 0:
                    break
                time.sleep(0.3)
                rival_move = random.choice(list(rival.moves.keys()))
                print(f"\n{self.rival_name}'s turn:")
                rival.use_attack(rival_move, player)
                time.sleep(0.3)

            if player.current_hp <= 0:
                player_index += 1
                if player_index < len(self.player_team):
                    print(f"\nGo, {self.player_team[player_index].name}!")
            else:
                rival_index += 1
                if rival_index < len(self.rival_team):
                    print(f"\n{self.rival_name} sends out {self.rival_team[rival_index].name}!")

        if player_index == len(self.player_team):
            print(f"\n💀 {self.rival_name} defeated you. Better luck next time!")
        else:
            print(f"\n🏆 You defeated {self.rival_name}! You win!")

    def start_battle(self):
        self.battle()

if __name__ == "__main__":
    game = Pokemon_game()
    game.Get_name()
    game.Starter_selection()
    game.Rival()
    game.draft_team()
    game.start_battle()
