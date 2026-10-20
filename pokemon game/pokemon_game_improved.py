import csv
import random
from pathlib import Path

# Your six CSV files are stored in the "data" folder beside this script.
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"


def load_csv(filename):
    path = DATA_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"\nCan't find: {path}\n"
            "Check that the 'data' folder is beside this Python file and "
            "contains all six CSV files."
        )
    with path.open("r", newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def pause():
    input("\nPress Enter to continue...")


class PokemonData:
    def __init__(self):
        print("Loading Pokémon data...")
        pokemon_rows = load_csv("pokemon.csv")
        stat_rows = load_csv("pokemon_stats.csv")
        pokemon_move_rows = load_csv("pokemon_moves.csv")
        move_rows = load_csv("moves.csv")
        stats_rows = load_csv("stats.csv")

        self.pokemon_by_id = {
            int(row["id"]): row for row in pokemon_rows
            if row.get("id", "").isdigit()
        }
        moves_by_id = {
            int(row["id"]): row for row in move_rows
            if row.get("id", "").isdigit()
        }
        stat_names = {
            int(row["id"]): row["identifier"].lower()
            for row in stats_rows if row.get("id", "").isdigit()
        }

        self.stats_by_pokemon = {}
        for row in stat_rows:
            try:
                pokemon_id = int(row["pokemon_id"])
                stat_id = int(row["stat_id"])
                base_stat = int(row["base_stat"])
            except (ValueError, KeyError):
                continue
            stat_name = stat_names.get(stat_id, "")
            self.stats_by_pokemon.setdefault(pokemon_id, {})[stat_name] = base_stat

        # Keep each Pokémon's earliest level-up entry for each damaging move.
        learned_moves = {}
        for row in pokemon_move_rows:
            try:
                if row.get("pokemon_move_method_id") != "1":
                    continue
                pokemon_id = int(row["pokemon_id"])
                move_id = int(row["move_id"])
                level = int(row.get("level") or 1)
            except (ValueError, KeyError):
                continue

            move = moves_by_id.get(move_id)
            if not move:
                continue
            try:
                power = int(float(move.get("power") or 0))
            except ValueError:
                continue
            if power <= 0:
                continue

            learned_moves.setdefault(pokemon_id, {})
            old = learned_moves[pokemon_id].get(move_id)
            if old is None or level < old[0]:
                learned_moves[pokemon_id][move_id] = (level, move, power)

        self.moves_by_pokemon = {}
        for pokemon_id, moves in learned_moves.items():
            ordered = sorted(moves.values(), key=lambda item: (item[0], int(item[1]["id"])))
            result = []
            used_names = set()
            for _, move, power in ordered:
                name = move["identifier"].replace("-", " ").title()
                if name not in used_names:
                    result.append((name, power))
                    used_names.add(name)
                if len(result) == 4:
                    break
            if result:
                self.moves_by_pokemon[pokemon_id] = dict(result)

        print("Pokémon data loaded!\n")

    def get_pokemon(self, pokemon_id):
        row = self.pokemon_by_id[pokemon_id]
        stats = self.stats_by_pokemon.get(pokemon_id, {})
        return {
            "id": pokemon_id,
            "name": row["identifier"].replace("-", " ").title(),
            "hp": max(1, stats.get("hp", 50)),
            "attack": max(1, stats.get("attack", 50)),
            "moves": self.moves_by_pokemon.get(pokemon_id, {"Tackle": 10}).copy(),
        }

    def available_kanto_ids(self):
        return [
            pokemon_id for pokemon_id, row in self.pokemon_by_id.items()
            if 1 <= pokemon_id <= 151
            and row.get("is_default", "1") == "1"
            and pokemon_id in self.stats_by_pokemon
        ]


class ActivePokemon:
    def __init__(self, data):
        self.id = data["id"]
        self.name = data["name"]
        self.max_hp = data["hp"]
        self.hp = data["hp"]
        self.attack = data["attack"]
        self.moves = data["moves"].copy()

    @property
    def fainted(self):
        return self.hp <= 0

    def attack_opponent(self, move_name, opponent):
        damage = max(1, self.moves[move_name] + int(self.attack * 0.2))
        opponent.hp = max(0, opponent.hp - damage)
        print(f"{self.name} used {move_name}!")
        print(f"It dealt {damage} damage to {opponent.name}.")
        print(f"{opponent.name}: {opponent.hp}/{opponent.max_hp} HP")
        if opponent.fainted:
            print(f"{opponent.name} fainted!")


class PokemonGame:
    STARTERS = {"bulbasaur": 1, "charmander": 4, "squirtle": 7}

    def __init__(self):
        self.data = PokemonData()
        self.player_name = "Trainer"
        self.rival_name = "Pedro"
        self.player_team = []
        self.rival_team = []

    def choose_number(self, prompt, minimum, maximum):
        while True:
            answer = input(prompt).strip()
            if answer.isdigit() and minimum <= int(answer) <= maximum:
                return int(answer)
            print(f"Please enter a number from {minimum} to {maximum}.")

    def setup(self):
        print("=" * 48)
        print("             POKÉMON DRAFT BATTLE")
        print("=" * 48)
        self.player_name = input("What is your trainer name? ").strip() or "Trainer"
        print(f"\nWelcome, {self.player_name}!")

        print("\nChoose your starter:")
        starter_names = list(self.STARTERS.keys())
        for number, name in enumerate(starter_names, 1):
            print(f"  {number}. {name.title()}")
        starter_choice = self.choose_number("Starter (1-3): ", 1, 3)
        starter_name = starter_names[starter_choice - 1]
        starter_id = self.STARTERS[starter_name]
        player_starter_data = self.data.get_pokemon(starter_id)

        rival_choices = [
            (name, pokemon_id) for name, pokemon_id in self.STARTERS.items()
            if pokemon_id != starter_id
        ]
        rival_starter_name, rival_starter_id = random.choice(rival_choices)
        rival_starter_data = self.data.get_pokemon(rival_starter_id)

        print(f"\nYour starter is {player_starter_data['name']}!")
        print(f"{self.rival_name}'s starter is {rival_starter_data['name']}.")
        pause()

        self.player_team = [ActivePokemon(player_starter_data)]
        self.draft_five()
        self.make_rival_team(rival_starter_data)
        self.show_teams()

    def draft_five(self):
        starter_ids = set(self.STARTERS.values())
        pool = [
            pokemon_id for pokemon_id in self.data.available_kanto_ids()
            if pokemon_id not in starter_ids
        ]
        chosen_ids = {self.player_team[0].id}

        print("\n" + "=" * 48)
        print("YOUR DRAFT: Choose 5 more Pokémon")
        print("Each round, choose ONE of the three options.")
        print("=" * 48)

        for round_number in range(1, 6):
            options = random.sample([pid for pid in pool if pid not in chosen_ids], 3)
            pokemon_options = [self.data.get_pokemon(pid) for pid in options]

            print(f"\nDRAFT PICK {round_number} OF 5")
            for number, pokemon in enumerate(pokemon_options, 1):
                moves = ", ".join(pokemon["moves"].keys())
                print(f"  {number}. {pokemon['name']}")
                print(f"     HP: {pokemon['hp']} | Attack: {pokemon['attack']}")
                print(f"     Moves: {moves}")

            choice = self.choose_number("Choose 1, 2, or 3: ", 1, 3)
            selected = pokemon_options[choice - 1]
            self.player_team.append(ActivePokemon(selected))
            chosen_ids.add(selected["id"])
            print(f"\nAdded {selected['name']} to your team.")
            print(f"Team size: {len(self.player_team)}/6")
        print("\nYour team is complete!")

    def make_rival_team(self, rival_starter_data):
        starter_ids = set(self.STARTERS.values())
        pool = [
            pokemon_id for pokemon_id in self.data.available_kanto_ids()
            if pokemon_id not in starter_ids and pokemon_id != rival_starter_data["id"]
        ]
        rival_ids = random.sample(pool, 5)
        self.rival_team = [ActivePokemon(rival_starter_data)]
        self.rival_team.extend(
            ActivePokemon(self.data.get_pokemon(pokemon_id))
            for pokemon_id in rival_ids
        )

    def show_teams(self):
        print("\n" + "=" * 48)
        print(f"{self.player_name.upper()}'S TEAM")
        print("=" * 48)
        for number, pokemon in enumerate(self.player_team, 1):
            print(f"{number}. {pokemon.name} | HP {pokemon.max_hp} | Attack {pokemon.attack}")

        print("\n" + "=" * 48)
        print(f"{self.rival_name.upper()}'S TEAM")
        print("=" * 48)
        for number, pokemon in enumerate(self.rival_team, 1):
            print(f"{number}. {pokemon.name} | HP {pokemon.max_hp} | Attack {pokemon.attack}")
        pause()

    def show_battle_status(self, player, rival):
        print("\n" + "-" * 48)
        print(f"YOUR {player.name}: {player.hp}/{player.max_hp} HP")
        print(f"{self.rival_name.upper()}'S {rival.name}: {rival.hp}/{rival.max_hp} HP")
        print("-" * 48)

    def battle(self):
        print("\n" + "=" * 48)
        print("                 BATTLE START!")
        print("=" * 48)
        player_index = 0
        rival_index = 0

        while player_index < 6 and rival_index < 6:
            player = self.player_team[player_index]
            rival = self.rival_team[rival_index]

            print(f"\nGo, {player.name}!")
            print(f"{self.rival_name} sends out {rival.name}!")

            while not player.fainted and not rival.fainted:
                self.show_battle_status(player, rival)
                print("\nChoose your move:")
                move_names = list(player.moves.keys())
                for number, move in enumerate(move_names, 1):
                    print(f"  {number}. {move} (power {player.moves[move]})")
                print("  0. View team status")

                while True:
                    answer = input("Move number: ").strip()
                    if answer == "0":
                        self.show_teams_brief(player_index, rival_index)
                        continue
                    if answer.isdigit() and 1 <= int(answer) <= len(move_names):
                        chosen_move = move_names[int(answer) - 1]
                        break
                    print(f"Choose 1-{len(move_names)}, or 0 to view team status.")

                player.attack_opponent(chosen_move, rival)
                if rival.fainted:
                    break

                rival_move = random.choice(list(rival.moves.keys()))
                print(f"\n{self.rival_name}'s turn.")
                rival.attack_opponent(rival_move, player)

            if player.fainted:
                player_index += 1
                if player_index < 6:
                    print(f"\n{player.name} is out of the battle.")
                    print(f"Your next Pokémon is {self.player_team[player_index].name}.")
            else:
                rival_index += 1
                if rival_index < 6:
                    print(f"\nYou defeated {rival.name}!")
                    print(f"{self.rival_name}'s next Pokémon is {self.rival_team[rival_index].name}.")

        print("\n" + "=" * 48)
        if player_index >= 6:
            print(f"{self.rival_name} won the battle. Better luck next time!")
        else:
            print(f"YOU WIN! You defeated {self.rival_name}!")
        print("=" * 48)

    def show_teams_brief(self, player_index, rival_index):
        print("\nYOUR TEAM:")
        for index, pokemon in enumerate(self.player_team):
            status = "FAINTED" if pokemon.fainted else f"{pokemon.hp}/{pokemon.max_hp} HP"
            active = " (ACTIVE)" if index == player_index else ""
            print(f"  {index + 1}. {pokemon.name}: {status}{active}")
        print(f"\n{self.rival_name.upper()}'S TEAM:")
        for index, pokemon in enumerate(self.rival_team):
            status = "FAINTED" if pokemon.fainted else f"{pokemon.hp}/{pokemon.max_hp} HP"
            active = " (ACTIVE)" if index == rival_index else ""
            print(f"  {index + 1}. {pokemon.name}: {status}{active}")

    def run(self):
        self.setup()
        self.battle()


if __name__ == "__main__":
    try:
        PokemonGame().run()
    except FileNotFoundError as error:
        print(error)
        input("\nPress Enter to close...")
