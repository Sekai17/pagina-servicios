import json
import random
import threading
import math
import struct
import os
from dataclasses import dataclass, field

try:
    import simpleaudio as sa
    HAS_AUDIO = True
except Exception:  # simpleaudio not installed or other audio error
    sa = None
    HAS_AUDIO = False


def _generate_tone(frequency: int = 440, duration: float = 1.0, volume: float = 0.3) -> bytes:
    """Generate a simple sine wave tone."""
    framerate = 44100
    amplitude = int(32767 * volume)
    samples = []
    for i in range(int(framerate * duration)):
        value = int(amplitude * math.sin(2 * math.pi * frequency * i / framerate))
        samples.append(struct.pack('<h', value))
    return b''.join(samples)


def play_music_loop():
    """Play a looping tone as background music in a daemon thread."""
    if not HAS_AUDIO:
        print("[INFO] Biblioteca de audio no disponible. Se omite la música.")
        return

    data = _generate_tone()
    wave_obj = sa.WaveObject(data, 1, 2, 44100)

    def _loop():
        while True:
            play_obj = wave_obj.play()
            play_obj.wait_done()
    threading.Thread(target=_loop, daemon=True).start()


@dataclass
class Player:
    name: str
    hp: int = 30
    attack: int = 5
    defense: int = 2
    inventory: list = field(default_factory=list)

    def is_alive(self) -> bool:
        return self.hp > 0


@dataclass
class Enemy:
    name: str
    hp: int
    attack: int
    defense: int

    def is_alive(self) -> bool:
        return self.hp > 0


def combat(player: Player, enemy: Enemy) -> bool:
    """Simple turn-based combat."""
    print(f"\n¡Combate contra {enemy.name}!")
    while player.is_alive() and enemy.is_alive():
        input("Presiona Enter para atacar...")
        dmg = max(0, player.attack + random.randint(-2, 2) - enemy.defense)
        enemy.hp -= dmg
        print(f"Golpeas a {enemy.name} por {dmg} de daño (HP enemigo: {max(0, enemy.hp)})")
        if not enemy.is_alive():
            print(f"{enemy.name} ha sido derrotado!\n")
            return True
        dmg = max(0, enemy.attack + random.randint(-2, 2) - player.defense)
        player.hp -= dmg
        print(f"{enemy.name} te golpea por {dmg} de daño (HP: {max(0, player.hp)})")
    print("Has caído en batalla...")
    return False


class Scene:
    def __init__(self, key, description, options):
        self.key = key
        self.description = description
        self.options = options  # List of dicts: {'text': str, 'next': str, 'action': callable}

    def play(self, game: "Game"):
        print(f"\n--- {self.key.upper()} ---")
        print(self.description)
        for idx, opt in enumerate(self.options, 1):
            print(f"{idx}. {opt['text']}")
        choice = 0
        while True:
            try:
                choice = int(input("> ")) - 1
                if 0 <= choice < len(self.options):
                    break
            except ValueError:
                pass
            print("Opción inválida, intenta de nuevo.")
        selected = self.options[choice]
        action = selected.get('action')
        if action:
            action(game)
        return selected.get('next')


class Game:
    def __init__(self):
        self.player = None
        self.scenes = {}
        self.current = 'intro'
        self.load_scenes()

    def load_scenes(self):
        self.scenes = {
            'intro': Scene('Introducción',
                'Despiertas en una llanura desconocida. El sol se oculta en el horizonte.',
                [
                    {'text': 'Explorar el bosque cercano', 'next': 'bosque'},
                    {'text': 'Caminar hacia la montaña', 'next': 'montana'},
                    {'text': 'Guardar partida', 'next': 'intro', 'action': self.save}
                ]),
            'bosque': Scene('Bosque',
                'Los árboles susurran con el viento. Algo se mueve entre los arbustos.',
                [
                    {'text': 'Investigar el ruido', 'next': 'bosque', 'action': lambda g: combat(g.player, Enemy('Lobo', 10, 4, 1))},
                    {'text': 'Volver a la llanura', 'next': 'intro'}
                ]),
            'montana': Scene('Montaña',
                'La subida es empinada y el aire se vuelve frío.',
                [
                    {'text': 'Subir hasta la cima', 'next': 'cima'},
                    {'text': 'Regresar a la llanura', 'next': 'intro'}
                ]),
            'cima': Scene('Cima',
                'Desde la cima ves todo el valle y un castillo lejano.',
                [
                    {'text': 'Gritar al viento', 'next': 'intro', 'action': lambda g: print('Tu voz resuena en la distancia...')},
                    {'text': 'Descansar y recuperar energía', 'next': 'cima', 'action': lambda g: setattr(g.player, 'hp', min(g.player.hp + 5, 30))},
                    {'text': 'Guardar partida', 'next': 'cima', 'action': self.save}
                ])
        }

    def save(self, *_):
        data = {'player': self.player.__dict__, 'current': self.current}
        with open('savegame.json', 'w') as f:
            json.dump(data, f)
        print('Partida guardada.')

    def load(self):
        if os.path.exists('savegame.json'):
            with open('savegame.json') as f:
                data = json.load(f)
            self.player = Player(**data['player'])
            self.current = data['current']
            print('Partida cargada.')
        else:
            print('No existe una partida guardada.')

    def start(self):
        play_music_loop()
        print('=== RPG de Texto ===')
        if os.path.exists('savegame.json'):
            if input('Cargar partida previa? (s/n) ').lower().startswith('s'):
                self.load()
        if not self.player:
            name = input('Ingresa el nombre de tu héroe: ')
            self.player = Player(name=name)
        while True:
            scene = self.scenes[self.current]
            nxt = scene.play(self)
            self.current = nxt
            if not self.player.is_alive():
                print('Fin del juego. Tu aventura termina aquí.')
                break


if __name__ == '__main__':
    Game().start()
