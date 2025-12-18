import sys
#import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Callable
import json
import random

melee_second_person_verbs = ["slashes", "strikes", "bashes", "hits", "smashes", "pummels", "kicks", "punches", "attacks", "swings at", "jabs"]
melee_first_person_verbs = ["slash", "strike", "bash", "hit", "smash", "pummel", "kick", "punch", "attack", "swing at", "jab"]
def clamp(v, a, b): return max(a, min(b, v))
def chance(chance_percent): return random.random() < chance_percent / 100.0
# Stats data class
@dataclass
class Stats:
    health: int = 20
    max_health: int = 20
    mana: int = 0
    max_mana: int = 0
    strength: int = 3
    dexterity: int = 3
    intelligence: int = 3
    level: int = 1
    experience: int = 0

    def gain_experience(self, amount: int):
        self.experience += amount
        while self.experience >= self.xp_to_next_level():
            self.experience -= self.xp_to_next_level()
            self.level_up()


    def xp_to_next_level(self):
        return 10 + 5 * self.level

    def level_up(self):
        self.level += 1
        self.max_health += 5
        self.health = self.max_health
        if not self.max_mana == 0:
            self.max_mana += 2
            self.mana = self.max_mana
        self.strength += 1
        self.dexterity += 1
        self.intelligence += 1

# Item data class
@dataclass
class Item:
    id: str # Id
    name: str # Name
    description: str # Description of item
    type: str = 'misc' # Type of item e.g: 'misc', 'equipable', 'consumable'
    power: Optional[int] = None # Power level (for equipable items)
    equip_slot: Optional[str] = None # Slot to equip to e.g: 'weapon', 'armor' (for equipable items)
    func: Optional[Callable] = None # Function to call when used (for consumables)

# Object data class
@dataclass
class Object:
    id: str
    name: str
    description: str

@dataclass
class DialogueOption:
    text: str
    response: Optional[str] = None

@dataclass
class DialogueNode:
    id: str
    text: str
    next: Optional[str] = None
    func: Optional[Callable] = None
    options: Dict[str, 'DialogueNode'] = field(default_factory=dict)

@dataclass
class DialogueTree:
    start_id: str
    nodes: Dict[str, DialogueNode] = field(default_factory=dict)


@dataclass
class Actor:
    id: str
    name: str
    description: Optional[str] = None
    stats: Stats = field(default_factory=Stats())
    ai: str = 'aggressive' # Behaviour of actor e.g: 'passive', 'aggressive'
    equip: Dict[str, Optional[Item]] = field(default_factory=lambda: {"weapon": None, "armor": None})
    items: List[Item] = field(default_factory=list)
    skills: List['Skill'] = field(default_factory=list)
    dialogue: Optional['Dialogue'] = None

    def take_damage(self, amount: int):
        self.stats.health = clamp(self.stats.health - amount, 0, self.stats.max_health)
    
    def heal(self, amount: int):
        self.stats.health = clamp(self.stats.health + amount, 0, self.stats.max_health)

    def add_item(self, item: Item):
        self.items.append(item)

    def consume_item(self, item_id):
        for i,it in enumerate(self.items):
            if it.id == item_id and it.type == "consumable":
                if it.func:
                    it.func(self)
                return self.items.pop(i)
        return None

    def equip_item(self, item_id):
        for it in self.items:
            if it.id == item_id and it.type == "equipable" and it.equip_slot:
                slot = it.equip_slot
                self.equip[slot] = it
                return f"{self.name} equips {it.name}."
        return "Cannot equip."

    def unequip(self, slot):
        if slot in self.equip:
            name = self.equip[slot].name
            self.equip[slot] = None
            return f"{self.name} unequips {name}"
        return "Nothing to unequip"
    
    def remove_item(self, item_id):
        for i,it in enumerate(self.items):
            if it.id == item_id:
                return self.items.pop(i)
        return None
    
    def is_alive(self):
        return self.stats.health > 0

    def attack_power(self):
        base = self.stats.strength
        weapon = self.equip.get("weapon")
        if weapon and weapon.power:
            base += weapon.power
        return base

    def defense(self):
        base = int(self.stats.dexterity / 2)
        armor = self.equip.get("armor")
        if armor and armor.power:
            base += armor.power
        return base

    def use_skill(self, skill_id: str, target: 'Actor'):
        for sk in self.skills:
            if sk.id == skill_id:
                if self.stats.mana >= sk.mana_cost:
                    self.stats.mana -= sk.mana_cost
                    sk.func(self, target)
                else:
                    return "Not enough mana."
        return "Skill not found."

# Skill data class
@dataclass
class Skill:
    id: str
    name: str
    description: str
    mana_cost: int
    power: int
    source_func: Optional[Callable] = None

    def func(self, user: Actor, target: Actor):
        if self.source_func:
            self.source_func(self, user, target)

@dataclass
class Room:
    id: str
    name: str
    description: str
    exits: List[str]
    items: List[Item]
    enemies: List[Actor]
    npcs: List[Actor]
    objects: List[Object]

class Combat:
    def __init__(self, player: Actor, enemies: List[Actor]):
        self.player = player
        self.enemies = enemies
        self.defeated_enemies: List[Actor] = []
    
    def player_turn(self):
        print(f"Your HP: {self.player.stats.health}/{self.player.stats.max_health}  MP: {self.player.stats.mana}/{self.player.stats.max_mana} \n")
        print("Enemies:")
        for i,e in enumerate(self.enemies, 1):
            print(f" {i} - {e.name} L{e.stats.level} HP: {e.stats.health}/{e.stats.max_health}")
        cmd = input("Action (attack <n>/skill <name>/use <item>/flee): ").strip().lower().split()
        if not cmd: return
        if cmd[0] == "attack":
            idx = int(cmd[1])-1 if len(cmd)>1 and cmd[1].isdigit() else 0
            if 0 <= idx < len(self.enemies):
                target = self.enemies[idx]
                damage = max(0, self.player.attack_power() - target.defense() + random.randint(-2,2))
                crit = chance(10 + self.player.stats.dexterity)
                if crit:
                    damage = int(damage * 1.5) + 1
                    print("Critical Hit!")
                target.take_damage(damage)
                if self.player.equip.get("weapon"):
                    print(f"You attack {target.name} with {self.equip['weapon'].name} for {damage} damage.")
                else:
                    verb = random.choice(melee_first_person_verbs)
                    print(f"You {verb} {target.name} for {damage} damage.")
                if not target.is_alive():
                    print(f"You have defeated L{target.stats.level} {target.name}!")
            else:
                print("No such target.")
        elif cmd[0] == "use":
            if len(cmd) < 2:
                print("Use what?")
                return
            item_name = " ".join(cmd[1:])
            for it in self.player.items:
                if item_name in it.name.lower() and it.type == "consumable":
                    self.player.consume_item(it.id)
                    print(f"You used {it.name}.")
                    return
            print("Item not found or not usable.")
        elif cmd[0] == "flee":
            if chance(50 + self.player.stats.dexterity * 2):
                print("You successfully fled the combat!")
                return "fled"
            else:
                print("Failed to flee!")
        else:
            print("Unknown action.")
    
    def enemies_turn(self):
        for i,e in enumerate(self.enemies):
            if not e.is_alive():
                self.defeated_enemies.append(e)
                self.enemies.pop(i)
                continue
            if chance(10):
                print(f"{e.name} hesitates.")
                continue
            damage = max(0, e.attack_power() - self.player.defense() + random.randint(-2,2))
            crit = chance(5 + e.stats.dexterity)
            if crit:
                damage = int(damage * 1.5) + 1
                print("Critical Hit!")
            if damage > 0:
                self.player.take_damage(damage)
                if e.equip.get("weapon"):
                    print(f"L{e.stats.level} {e.name} attacks you with {e.equip['weapon'].name} for {damage} damage.")
                else:
                    verb = random.choice(melee_second_person_verbs)
                    print(f"L{e.stats.level} {e.name} {verb} you for {damage} damage.")
            else:
                print(f"{e.name} attacks but fails to hurt you.")
                break
            if not self.player.is_alive():
                print(f"You have been defeated by L{e.stats.level} {e.name}!")
                break
    
    def run(self):
        print("Combat started!")
        while self.player.is_alive() and len(self.enemies) > 0:
            result = self.player_turn()
            if result == "fled":
                break
            self.enemies_turn()
        if not self.player.is_alive():
            print("Game Over.")
        elif len(self.enemies) == 0:
            print("You have defeated all enemies! \n")
            total_exp = sum(en.stats.level * 5 for en in self.defeated_enemies)
            self.player.stats.gain_experience(total_exp)
            print(f"You gained {total_exp} experience points!")
        print("Combat ended.")

class Dialogue:
    def __init__(self, player: Actor, npc: Actor):
        self.npc = npc
        self.player = player

class Game():
    def __init__(self):
        self.rooms: dict[str, Room] = {}
        self.player: Actor = self.create_player()
        self.current_room: Optional[Room] = None
        self.init_world()

    def init_world(self):
        arguments = sys.argv
        if len(arguments) < 2:
            raise Exception("Usage: python3 main.py <example/world_file>")
        worldfile = arguments[1]
        try:
            #if os.path.isdir(worldfile) == False:
            #    raise Exception("World path is not a directory.")
            functions = {}
            with open(worldfile + "/functions.py", "r") as f:
                code = f.read()
                exec(code, {}, data := {})
                for key in data['export']:
                    functions[key] = data['export'][key]
            with open(worldfile + "/data.json", "r") as f:
                data = json.load(f)
                for room in data['rooms']:
                    # Reformat items
                    items_data = room['items']
                    items = []
                    for it in items_data:
                        new_it = Item(id=it['id'], name=it['name'], description=it['description'], type=it['type'])
                        if 'equip_slot' in it:
                            new_it['equip_slot'] = it['equip_slot']
                        if new_it.type == "consumable":
                            if 'func' in it:
                                func_name = it['func']
                                if func_name in functions:
                                    new_it.func = functions[func_name]
                        items.append(new_it)
                    
                    # Reformat enemies
                    enemies = []
                    for en in room['enemies']:
                        stats_data = en['stats']
                        stats = Stats(
                            health=stats_data['health'], 
                            max_health=stats_data['max_health'], 
                            mana=stats_data['mana'],
                            max_mana=stats_data['max_mana'], 
                            strength=stats_data["strength"],
                            dexterity=stats_data["dexterity"],
                            intelligence=stats_data["intelligence"],
                            level=stats_data["level"],
                        )
                        en_items = []
                        for it in en['items']:
                            new_it = Item(id=it['id'], name=it['name'], description=it['description'], type=it['type'])
                            if 'equip_slot' in it:
                                new_it.equip_slot = it['equip_slot']
                            if new_it.type == "consumable":
                                if 'func' in it:
                                    func_name = it['func']
                                    if func_name in functions:
                                        new_it.func = functions[func_name]
                            en_items.append(new_it)
                        new_en = Actor(id=en['id'], name=en['name'], description=en['description'], stats=stats, ai="aggressive", items=en_items)
                        if 'equip' in en:
                            for key in en['equip']:
                                new_en.equip_item(en['equip'][key])
                        enemies.append(new_en)
                    
                    # Reformat objects
                    objects = []
                    for ob in room['objects']:
                        new_ob = Object(id=ob['id'], name=ob['name'], description=ob['description'])
                        objects.append(new_ob)
                    
                    # Reformat npcs
                    npcs = []
                    for npc in room['npcs']:
                        stats_data = npc['stats']
                        stats = Stats(
                            health=stats_data['health'], 
                            max_health=stats_data['max_health'], 
                            mana=stats_data['mana'],
                            max_mana=stats_data['max_mana'], 
                            strength=stats_data["strength"],
                            dexterity=stats_data["dexterity"],
                            intelligence=stats_data["intelligence"],
                            level=stats_data["level"],
                        )
                        npc_items = []
                        for it in npc['items']:
                            new_it = Item(id=it['id'], name=it['name'], description=it['description'], type=it['type'])
                            if 'equip_slot' in it:
                                new_it.equip_slot = it['equip_slot']
                            if new_it.type == "consumable":
                                if 'func' in it:
                                    func_name = it['func']
                                    if func_name in functions:
                                        new_it.func = functions[func_name]
                            npc_items.append(new_it)
                        new_npc = Actor(id=npc['id'], name=npc['name'], description=npc['description'], stats=stats, ai="passive", items=npc_items)
                        if 'equip' in npc:
                            for key in npc['equip']:
                                new_npc.equip_item(npc['equip'][key])
                        npcs.append(new_npc)

                    # Reformat room
                    r = Room(id=room['id'], name=room['name'], description=room['description'], exits=room['exits'], items=items, enemies=enemies, objects=objects, npcs=npcs)
                    self.rooms[room['id']] = r
                    if room['id'] == data['start_room']:
                        self.current_room = r
        except Exception as e:
            print("Error:", e)
        print(f"You find yourself in {self.current_room.name}")

    def create_player(self) -> Actor:
        s = Stats(health=10, max_health=10, mana=5, max_mana=5)
        p = Actor(id="player_1", name="Player", ai="player", stats=s)
        return p

    def set_current_room(self, room_id):
            for rid in self.rooms:
                if rid == room_id:
                    self.current_room = self.rooms[rid]

    def help(self):
        print("\nUsage: '$ <Command> [<Arguments>]'\n")
        print("Commands:\n")
        print("     $ help                                 : Prints all commands")
        print("     $ look <any/Any>                       : Look at something")
        print("     $ pickup [Item Name]                   : Picks up items")
        print("     $ (go/move) [north/east/south/west]    : Picks up items")
        print("     $ (inv/inventory) <Item Name>          : Shows all your items or just a specific item")
        print("     $ attack [Enemy Name]                  : Starts combat with an enemy")
        print("     $ status                               : Shows your current status")
        print("     $ quit                                 : Quits the engine")
        print("\n")

    def look(self, arguments):
        if len(arguments) > 1:
            arg1 = " ".join(arguments[1:])
            for it in self.current_room.items:
                if arg1.lower() in it.name.lower():
                    print(it.name)
                    print("   ", it.description)
                    return
            for obj in self.current_room.objects:
                if arg1.lower() in obj.name.lower():
                    print(obj.name)
                    print("   ", obj.description)
                    return
            for enm in self.current_room.enemies:
                if arg1.lower() in enm.name.lower():
                    print(enm.name, "Level:", enm.stats.level, "Health:", enm.stats.health, "/", enm.stats.max_health)
                    print("   ", enm.description)
                    return
            print("Couldn't find:", arg1)
        else:
            print("You are in", self.current_room.name)
            print("    ", self.current_room.description, "\n")

            print("There is:")
            everything = [*self.current_room.items, *self.current_room.objects, *self.current_room.enemies]
            for th in everything:
                print("    ", th.name)
            print("\n")

            print("You can go:")
            for key in self.current_room.exits:
                print("    ", key)

    def go(self, arguments):
        if len(arguments) > 1:
            arg1 = " ".join(arguments[1:]).lower()
            for ex in self.current_room.exits:
                if arg1 == ex:
                    self.set_current_room(self.current_room.exits[ex])
                    print(f"{self.player.name} went {arg1} to {self.current_room.name}.")
                    if len(self.current_room.enemies) > 0:
                        combat = Combat(self.player, self.current_room.enemies)
                        combat.run()
                    return
            print(f"Exit: {arg1} not found.")
            return
        else:
            print("Usage: $ (go/move) <Exit Name>")

    def attack(self, arguments):
        if len(arguments) > 1:
            arg1 = " ".join(arguments[1:]).lower()
            for enm in self.current_room.enemies:
                if arg1 in enm.name.lower():
                    combat = Combat(self.player, [enm])
                    combat.run()
                    return
            print(f"Enemy: {arg1} not found.")
        else:
            print("Usage: $ attack [Enemy Name]")

    def pickup(self, arguments):
        if len(arguments) > 1:
            arg1 = " ".join(arguments[1:])
            for i, it in enumerate(self.current_room.items):
                if arg1.lower() in it.name.lower():
                    self.player.add_item(it)
                    self.current_room.items.pop(i)
                    print(f"{self.player.name} picked up {it.name}.")
                    return
            print(f"{arg1} not found.")
        else:
            print("Usage: $ pickup [Item Name]")
    
    def inventory(self, arguments):
        items = self.player.items
        if len(arguments) > 1:
            arg1 = " ".join(arguments[1:]).lower()
            for it in items:
                if arg1 in it.name.lower():
                    print(f"{it.name}\n    desc: {it.description}\n    type: {it.type}\n")
                    return
            print(f"Couldn't find: {arg1}.")
            return
        else:
            if len(items) == 0:
                print(f"{self.player.name}'s inventory is empty.")
            else:
                print("You have: \n")
                for it in items:
                    print("     ", it.name)
                print("\n")
            return

    def status(self):
        print(f"--- Name: {self.player.name} --- Lvl: {self.player.stats.level} --- Exp: {self.player.stats.experience} / {self.player.stats.xp_to_next_level()} ---")
        print(f"STR: {self.player.stats.strength} \nDEX: {self.player.stats.dexterity} \nINT: {self.player.stats.intelligence}")

    def run_command(self, arguments):
        cmd = arguments[0].lower()
        match cmd:
            case "help": self.help()
            case "quit":
                print("Goodbye!")
                sys.exit(0)
            case "look": self.look(arguments)
            case "pickup": self.pickup(arguments)
            case "move": self.go(arguments)
            case "go": self.go(arguments)
            case "attack": self.attack(arguments)
            case "inventory": self.inventory(arguments)
            case "inv": self.inventory(arguments)
            case "status": self.status()
            case _: print("Command not found:", cmd)
                

    def repl(self):
        while True:
            try:
                line = input("$ ")
                self.run_command(line.split(" "))
            except EOFError:
                print("Exiting.")
                break
            except Exception as e:
                print("Error:", e)

if __name__ == "__main__":
    game = Game()
    game.repl()