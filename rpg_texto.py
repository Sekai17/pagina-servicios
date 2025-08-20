"""Juego RPG de texto por consola.

Uso rápido:
    python rpg_texto.py

Comandos clave: ayuda, mirar, ir, inventario, estado, atacar,
misiones, santuario, guardar, cargar, salir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
import json
import random
from pathlib import Path

# === CONSTANTES ===
SANTUARIO_COSTO_ESTADO = 5
SANTUARIO_DESCUENTO = 0.8
ARCHIVO_GUARDADO = Path("partida.json")

ESTADOS_ICONOS = {
    "veneno": "[\u2620]",
    "quemadura": "[\uD83D\uDD25]",
    "aturdido": "[\u2716]",
    "sangrado": "[\uD83E\uDE78]",
}


# === UTILIDADES ===
def parsear_comando(linea: str) -> Tuple[str, List[str]]:
    """Divide una línea en comando y argumentos.

    >>> parsear_comando("ir norte")
    ('ir', ['norte'])
    >>> parsear_comando("  MIRAR  ")
    ('mirar', [])
    >>> parsear_comando("")
    ('', [])
    """
    tokens = linea.strip().lower().split()
    if not tokens:
        return "", []
    return tokens[0], tokens[1:]


def calcular_dano(atq: int, defensa: int) -> int:
    """Calcula daño simple con variación aleatoria y críticos.

    >>> random.seed(0); calcular_dano(10, 5)
    6
    >>> random.seed(1); calcular_dano(5, 8) > 0
    True
    """
    variacion = random.randint(-2, 2)
    dano_base = max(1, atq + variacion - defensa)
    if random.random() < 0.1:
        dano_base = int(dano_base * 1.5)
    return dano_base


COMANDOS: Dict[str, Callable] = {}


def comando(nombre: str, *alias: str) -> Callable:
    """Registra un comando en el mapa global."""

    def decorador(func: Callable) -> Callable:
        COMANDOS[nombre] = func
        for a in alias:
            COMANDOS[a] = func
        return func

    return decorador


# === DATACLASSES ===
@dataclass
class Objeto:
    nombre: str
    tipo: str  # consumible|equipable|clave
    efectos: Dict[str, int]
    precio: int
    descripcion: str
    slot: Optional[str] = None
    duracion: int = 0


@dataclass
class Enemigo:
    nombre: str
    nivel: int
    vida: int
    ataque: int
    defensa: int
    oro: int
    xp: int
    botin: List[str]
    personalidad: List[str]
    jefe: bool = False
    estados: Dict[str, int] = field(default_factory=dict)


@dataclass
class Sala:
    id: str
    nombre: str
    descripcion: str
    conexiones: Dict[str, str]
    objetos: List[str] = field(default_factory=list)
    enemigos: List[Enemigo] = field(default_factory=list)
    npcs: Dict[str, List[str]] = field(default_factory=dict)
    santuario: bool = False


@dataclass
class Mision:
    id: str
    tipo: str
    objetivo: str
    cantidad: int
    recompensa: Dict[str, int]
    narrativa: str
    progreso: int = 0
    completada: bool = False


@dataclass
class Jugador:
    nombre: str
    nivel: int = 1
    xp: int = 0
    vida: int = 30
    vida_max: int = 30
    mana: int = 10
    mana_max: int = 10
    oro: int = 0
    ataque: int = 5
    defensa: int = 3
    inventario: List[str] = field(default_factory=list)
    estados: Dict[str, int] = field(default_factory=dict)
    equipo: Dict[str, Optional[str]] = field(
        default_factory=lambda: {"arma": None, "armadura": None, "accesorio": None}
    )

    def modificar_salud(self, delta: int) -> None:
        self.vida = max(0, min(self.vida_max, self.vida + delta))


# === JUEGO ===
class Juego:
    def __init__(self, datos: Dict) -> None:
        self.datos = datos
        self.objetos = {k: Objeto(**v) for k, v in datos["objetos"].items()}
        self.salones = self._crear_salas(datos["salas"])  # id -> Sala
        self.misiones = [Mision(**m) for m in datos["misiones"].values()]
        self.jugador = Jugador(nombre="")
        self.sala_actual = "pueblo"
        self.en_combate: Optional[Enemigo] = None
        self.config = {"verboso": True}

    def _crear_salas(self, salas: Dict[str, Dict]) -> Dict[str, Sala]:
        res: Dict[str, Sala] = {}
        for sid, info in salas.items():
            enemigos = [self._crear_enemigo(eid) for eid in info.get("enemigos", [])]
            res[sid] = Sala(
                id=sid,
                nombre=info["nombre"],
                descripcion=info["descripcion"],
                conexiones=info.get("conexiones", {}),
                objetos=info.get("objetos", []),
                enemigos=enemigos,
                npcs=info.get("npcs", {}),
                santuario=info.get("santuario", False),
            )
        return res

    def _crear_enemigo(self, eid: str) -> Enemigo:
        datos = self.datos["enemigos"][eid]
        return Enemigo(**datos)

    # === LOOP PRINCIPAL ===
    def iniciar(self) -> None:
        print("=== RPG de Texto ===")
        nombre = input("Nombre del héroe: ").strip() or "Héroe"
        self.jugador.nombre = nombre
        print(f"Saludos, {nombre}. Escribe 'ayuda' para comandos.")
        while True:
            linea = input("> ")
            verbo, args = parsear_comando(linea)
            if not verbo:
                continue
            if verbo not in COMANDOS:
                print("No entiendo. Escribe 'ayuda'.")
                continue
            try:
                COMANDOS[verbo](self, args)
            except Exception as exc:  # pragma: no cover
                print(f"Error: {exc}")

    # === FUNCIONES DE APOYO ===
    def sala(self) -> Sala:
        return self.salones[self.sala_actual]

    def obtener_objeto(self, nombre: str) -> Optional[Objeto]:
        return self.objetos.get(nombre)

    def avanzar_misiones(self, tipo: str, objetivo: str) -> None:
        for m in self.misiones:
            if m.completada:
                continue
            if m.tipo == tipo and m.objetivo == objetivo:
                m.progreso += 1
                if m.progreso >= m.cantidad:
                    m.completada = True
                    self.jugador.xp += m.recompensa.get("xp", 0)
                    self.jugador.oro += m.recompensa.get("oro", 0)
                    print(f"Misión '{m.id}' completada!")

    def aplicar_estados(self, personaje: Jugador | Enemigo) -> None:
        for estado in list(personaje.estados):
            personaje.estados[estado] -= 1
            if estado == "veneno":
                personaje.modificar_salud(-2)
                print(f"{personaje.nombre} sufre veneno.")
            if estado == "quemadura":
                personaje.modificar_salud(-3)
                print(f"{personaje.nombre} arde.")
            if estado == "sangrado":
                personaje.modificar_salud(-2)
                print(f"{personaje.nombre} sangra.")
            if personaje.estados[estado] <= 0:
                del personaje.estados[estado]

    # === GUARDADO/CARGA ===
    def guardar(self, _args: List[str]) -> None:
        datos = {
            "jugador": self.jugador.__dict__,
            "sala_actual": self.sala_actual,
            "misiones": [m.__dict__ for m in self.misiones],
            "salas": {
                sid: {
                    "objetos": s.objetos,
                    "enemigos": [e.__dict__ for e in s.enemigos],
                }
                for sid, s in self.salones.items()
            },
            "version": 1,
        }
        ARCHIVO_GUARDADO.write_text(json.dumps(datos, ensure_ascii=False, indent=2))
        print("Partida guardada.")

    def cargar(self, _args: List[str]) -> None:
        try:
            datos = json.loads(ARCHIVO_GUARDADO.read_text())
            if datos.get("version") != 1:
                print("Versión de guardado incompatible.")
                return
            self.jugador = Jugador(**datos["jugador"])
            self.sala_actual = datos["sala_actual"]
            self.misiones = [Mision(**m) for m in datos["misiones"]]
            for sid, info in datos["salas"].items():
                sala = self.salones[sid]
                sala.objetos = info["objetos"]
                sala.enemigos = [Enemigo(**e) for e in info["enemigos"]]
            print("Partida cargada.")
        except Exception:
            print("No se pudo cargar la partida.")


# === COMANDOS ===
@comando("ayuda")
def cmd_ayuda(juego: Juego, _args: List[str]) -> None:
    print(
        "Comandos: ayuda, mirar, ir <dir>, hablar <npc>, tomar <obj>, soltar <obj>,\n"
        "inventario, usar <obj>, equipar <obj>, desequipar <slot>, estado, atacar <enemigo>,\n"
        "huir, misiones, santuario, guardar, cargar, config, salir"
    )


@comando("mirar", "examinar", "m")
def cmd_mirar(juego: Juego, _args: List[str]) -> None:
    sala = juego.sala()
    print(f"{sala.nombre}: {sala.descripcion}")
    if sala.objetos:
        print("Ves: " + ", ".join(sala.objetos))
    if sala.enemigos:
        print("Enemigos: " + ", ".join(e.nombre for e in sala.enemigos))
    if sala.npcs:
        print("NPCs: " + ", ".join(sala.npcs))
    print("Salidas: " + ", ".join(sala.conexiones))


@comando("ir")
def cmd_ir(juego: Juego, args: List[str]) -> None:
    if not args:
        print("¿Hacia dónde?")
        return
    dir = args[0]
    sala = juego.sala()
    if dir not in sala.conexiones:
        print("No puedes ir por ahí.")
        return
    juego.sala_actual = sala.conexiones[dir]
    cmd_mirar(juego, [])
    juego.avanzar_misiones("visitar", juego.sala_actual)


@comando("hablar")
def cmd_hablar(juego: Juego, args: List[str]) -> None:
    if not args:
        print("¿Con quién?")
        return
    sala = juego.sala()
    npc = args[0]
    if npc not in sala.npcs:
        print("No está aquí.")
        return
    for linea in sala.npcs[npc]:
        print(f"{npc}: {linea}")


@comando("tomar")
def cmd_tomar(juego: Juego, args: List[str]) -> None:
    if not args:
        print("¿Qué tomas?")
        return
    obj = args[0]
    sala = juego.sala()
    if obj not in sala.objetos:
        print("No ves eso aquí.")
        return
    sala.objetos.remove(obj)
    juego.jugador.inventario.append(obj)
    print(f"Has tomado {obj}.")
    juego.avanzar_misiones("recolectar", obj)


@comando("soltar")
def cmd_soltar(juego: Juego, args: List[str]) -> None:
    if not args:
        print("¿Qué sueltas?")
        return
    obj = args[0]
    if obj not in juego.jugador.inventario:
        print("No lo llevas.")
        return
    juego.jugador.inventario.remove(obj)
    juego.sala().objetos.append(obj)
    print(f"Has soltado {obj}.")


@comando("inventario")
def cmd_inventario(juego: Juego, _args: List[str]) -> None:
    inv = juego.jugador.inventario
    if not inv:
        print("Inventario vacío.")
    else:
        print("Inventario: " + ", ".join(inv))


@comando("usar")
def cmd_usar(juego: Juego, args: List[str]) -> None:
    if not args:
        print("¿Qué usas?")
        return
    nombre = args[0]
    if nombre not in juego.jugador.inventario:
        print("No lo tienes.")
        return
    obj = juego.obtener_objeto(nombre)
    if not obj or obj.tipo != "consumible":
        print("No es consumible.")
        return
    juego.jugador.inventario.remove(nombre)
    if "vida" in obj.efectos:
        juego.jugador.modificar_salud(obj.efectos["vida"])
        print("Recuperas vida.")
    if "curar" in obj.efectos:
        juego.jugador.estados.pop(obj.efectos["curar"], None)
        print("Estado curado.")


@comando("equipar")
def cmd_equipar(juego: Juego, args: List[str]) -> None:
    if not args:
        print("¿Qué equipas?")
        return
    nombre = args[0]
    if nombre not in juego.jugador.inventario:
        print("No lo tienes.")
        return
    obj = juego.obtener_objeto(nombre)
    if not obj or obj.tipo != "equipable" or not obj.slot:
        print("No puedes equipar eso.")
        return
    juego.jugador.inventario.remove(nombre)
    anterior = juego.jugador.equipo.get(obj.slot)
    if anterior:
        juego.jugador.inventario.append(anterior)
        prev = juego.obtener_objeto(anterior)
        for stat, val in prev.efectos.items():
            setattr(juego.jugador, stat, getattr(juego.jugador, stat) - val)
    juego.jugador.equipo[obj.slot] = nombre
    for stat, val in obj.efectos.items():
        setattr(juego.jugador, stat, getattr(juego.jugador, stat) + val)
    print(f"Equipado {nombre} en {obj.slot}.")


@comando("desequipar")
def cmd_desequipar(juego: Juego, args: List[str]) -> None:
    if not args:
        print("¿Qué slot?")
        return
    slot = args[0]
    actual = juego.jugador.equipo.get(slot)
    if not actual:
        print("Nada equipado.")
        return
    obj = juego.obtener_objeto(actual)
    juego.jugador.inventario.append(actual)
    juego.jugador.equipo[slot] = None
    for stat, val in obj.efectos.items():
        setattr(juego.jugador, stat, getattr(juego.jugador, stat) - val)
    print(f"Has quitado {actual}.")


@comando("estado")
def cmd_estado(juego: Juego, _args: List[str]) -> None:
    j = juego.jugador
    est = " ".join(ESTADOS_ICONOS[e] for e in j.estados) if j.estados else ""
    print(
        f"Nivel {j.nivel} Vida {j.vida}/{j.vida_max} Mana {j.mana}/{j.mana_max} Oro {j.oro} {est}"
    )
    print("Equipo: " + ", ".join(f"{k}:{v}" for k, v in j.equipo.items()))


@comando("atacar")
def cmd_atacar(juego: Juego, args: List[str]) -> None:
    if juego.en_combate:
        print("Ya estás en combate.")
        return
    if not args:
        print("¿A quién?")
        return
    nombre = args[0]
    sala = juego.sala()
    enemigo = next((e for e in sala.enemigos if e.nombre == nombre), None)
    if not enemigo:
        print("No está aquí.")
        return
    juego.en_combate = enemigo
    if enemigo.jefe:
        plantilla = random.choice([
            "{enemigo} se materializa criticando tu peinado, {jugador}.",
            "{enemigo} aplaude tu arma {arma}." ,
            "{enemigo} llega bostezando en {lugar}.",
        ])
        arma = juego.jugador.equipo.get("arma") or "manos vacías"
        print(
            plantilla.format(
                enemigo=enemigo.nombre,
                jugador=juego.jugador.nombre,
                arma=arma,
                lugar=sala.nombre,
            )
        )
    combate(juego, enemigo)
    juego.en_combate = None


def combate(juego: Juego, enemigo: Enemigo) -> None:
    j = juego.jugador
    while enemigo.vida > 0 and j.vida > 0:
        juego.aplicar_estados(j)
        juego.aplicar_estados(enemigo)
        if j.vida <= 0 or enemigo.vida <= 0:
            break
        accion = input("[atacar/habilidad/usar/huir]> ").strip().lower()
        if accion == "atacar":
            dano = calcular_dano(j.ataque, enemigo.defensa)
            enemigo.vida -= dano
            print(f"Golpeas por {dano}.")
        elif accion.startswith("habilidad") and j.mana >= 5:
            enemigo.vida -= j.ataque * 2
            j.mana -= 5
            print("Habilidad devastadora!")
        elif accion.startswith("usar"):
            _, *rest = accion.split()
            cmd_usar(juego, rest)
        elif accion == "huir":
            if random.random() < 0.5:
                print("Escapas!")
                return
            else:
                print("No logras escapar.")
        else:
            print("Acción inválida.")
        if enemigo.vida <= 0:
            break
        dano = calcular_dano(enemigo.ataque, j.defensa)
        j.modificar_salud(-dano)
        print(f"{enemigo.nombre} golpea por {dano}.")
    if j.vida <= 0:
        print("Has caído...")
    else:
        print(f"Venciste a {enemigo.nombre}.")
        j.xp += enemigo.xp
        j.oro += enemigo.oro
        for bot in enemigo.botin:
            j.inventario.append(bot)
        juego.sala().enemigos.remove(enemigo)
        juego.avanzar_misiones("derrotar", enemigo.nombre)
        if enemigo.jefe:
            print("El jefe suelta una frase sarcástica final.")


@comando("huir")
def cmd_huir(juego: Juego, _args: List[str]) -> None:
    print("Solo puedes huir durante el combate.")


@comando("misiones")
def cmd_misiones(juego: Juego, _args: List[str]) -> None:
    for m in juego.misiones:
        estado = "completada" if m.completada else f"{m.progreso}/{m.cantidad}"
        print(f"{m.id}: {estado} - {m.narrativa}")


@comando("santuario")
def cmd_santuario(juego: Juego, _args: List[str]) -> None:
    sala = juego.sala()
    if not sala.santuario:
        print("Aquí no hay santuario.")
        return
    j = juego.jugador
    if not j.estados:
        print("No tienes estados que curar.")
        return
    costo_unit = SANTUARIO_COSTO_ESTADO
    estados = list(j.estados)
    print("Estados:")
    for i, e in enumerate(estados, 1):
        print(f"{i}. {e} {costo_unit} oro")
    print(f"{len(estados)+1}. Curar todo {int(costo_unit*len(estados)*SANTUARIO_DESCUENTO)} oro")
    eleccion = input("Elige: ").strip()
    if not eleccion.isdigit():
        return
    idx = int(eleccion)
    if idx == len(estados) + 1:
        costo = int(costo_unit * len(estados) * SANTUARIO_DESCUENTO)
        if j.oro < costo:
            print("No tienes oro suficiente.")
            return
        j.oro -= costo
        j.estados.clear()
        print("Una fuerza divina te limpia de todo mal.")
    elif 1 <= idx <= len(estados):
        if j.oro < costo_unit:
            print("No tienes oro suficiente.")
            return
        estado = estados[idx - 1]
        j.oro -= costo_unit
        j.estados.pop(estado, None)
        print(f"Un rayo cura {estado} entre chistes malos.")


@comando("guardar")
def cmd_guardar(juego: Juego, args: List[str]) -> None:
    juego.guardar(args)


@comando("cargar")
def cmd_cargar(juego: Juego, args: List[str]) -> None:
    juego.cargar(args)


@comando("config")
def cmd_config(juego: Juego, _args: List[str]) -> None:
    juego.config["verboso"] = not juego.config["verboso"]
    estado = "ON" if juego.config["verboso"] else "OFF"
    print(f"Mensajes verbosos {estado}")


@comando("salir")
def cmd_salir(juego: Juego, _args: List[str]) -> None:
    if input("¿Seguro? s/n ").strip().lower() == "s":
        raise SystemExit


# === SEED DEFECTO ===
SEED_DEFECTO = {
    "salas": {
        "pueblo": {
            "nombre": "Pueblo Inicial",
            "descripcion": "Un lugar tranquilo con un banco y un pozo.",
            "conexiones": {"norte": "bosque"},
            "objetos": ["pocion"],
            "enemigos": [],
            "npcs": {"anciano": ["Bienvenido, héroe", "Busca en el bosque."]},
            "santuario": True,
        },
        "bosque": {
            "nombre": "Bosque Susurrante",
            "descripcion": "Los árboles parecen hablar entre sí.",
            "conexiones": {"sur": "pueblo", "este": "cueva"},
            "objetos": ["hongo"],
            "enemigos": ["slime", "goblin"],
            "npcs": {},
        },
        "cueva": {
            "nombre": "Cueva Oscura",
            "descripcion": "Huele a dragón y a sarcasmo.",
            "conexiones": {"oeste": "bosque"},
            "objetos": [],
            "enemigos": ["murcielago", "dragon"],
            "npcs": {},
        },
    },
    "objetos": {
        "pocion": {
            "nombre": "pocion",
            "tipo": "consumible",
            "efectos": {"vida": 20},
            "precio": 5,
            "descripcion": "Restaura vida",
        },
        "antidoto": {
            "nombre": "antidoto",
            "tipo": "consumible",
            "efectos": {"curar": "veneno"},
            "precio": 4,
            "descripcion": "Cura veneno",
        },
        "espada_oxida": {
            "nombre": "espada_oxida",
            "tipo": "equipable",
            "efectos": {"ataque": 2},
            "precio": 10,
            "descripcion": "Mejora ataque",
            "slot": "arma",
        },
        "armadura_cuero": {
            "nombre": "armadura_cuero",
            "tipo": "equipable",
            "efectos": {"defensa": 2},
            "precio": 12,
            "descripcion": "Mejora defensa",
            "slot": "armadura",
        },
        "anillo_chistoso": {
            "nombre": "anillo_chistoso",
            "tipo": "equipable",
            "efectos": {"ataque": 1, "defensa": 1},
            "precio": 20,
            "descripcion": "Te hace ver gracioso",
            "slot": "accesorio",
        },
        "hongo": {
            "nombre": "hongo",
            "tipo": "clave",
            "efectos": {},
            "precio": 1,
            "descripcion": "Un hongo brillante",
        },
    },
    "enemigos": {
        "slime": {
            "nombre": "slime",
            "nivel": 1,
            "vida": 10,
            "ataque": 3,
            "defensa": 1,
            "oro": 3,
            "xp": 5,
            "botin": ["pocion"],
            "personalidad": ["burbujea felizmente"],
        },
        "goblin": {
            "nombre": "goblin",
            "nivel": 2,
            "vida": 15,
            "ataque": 4,
            "defensa": 2,
            "oro": 5,
            "xp": 8,
            "botin": ["antidoto"],
            "personalidad": ["gruñe y muestra los dientes"],
        },
        "murcielago": {
            "nombre": "murcielago",
            "nivel": 1,
            "vida": 8,
            "ataque": 4,
            "defensa": 1,
            "oro": 4,
            "xp": 6,
            "botin": [],
            "personalidad": ["chilla desde la oscuridad"],
        },
        "dragon": {
            "nombre": "dragón sarcástico",
            "nivel": 5,
            "vida": 40,
            "ataque": 8,
            "defensa": 5,
            "oro": 20,
            "xp": 40,
            "botin": ["anillo_chistoso"],
            "personalidad": ["te mira con desprecio"],
            "jefe": True,
        },
    },
    "misiones": {
        "hongos": {
            "id": "hongos",
            "tipo": "recolectar",
            "objetivo": "hongo",
            "cantidad": 3,
            "recompensa": {"xp": 10, "oro": 5},
            "narrativa": "Recoge hongos para el guiso.",
        },
        "goblin": {
            "id": "goblin",
            "tipo": "derrotar",
            "objetivo": "goblin",
            "cantidad": 1,
            "recompensa": {"xp": 12, "oro": 7},
            "narrativa": "Derrota al goblin del bosque.",
        },
        "dragon": {
            "id": "dragon",
            "tipo": "jefe",
            "objetivo": "dragon",
            "cantidad": 1,
            "recompensa": {"xp": 50, "oro": 30},
            "narrativa": "Vence al dragón sarcástico.",
        },
    },
}


if __name__ == "__main__":  # pragma: no cover
    juego = Juego(SEED_DEFECTO)
    juego.iniciar()

# === SEED DE EJEMPLO ===
# {
#   "salas": {
#     "pueblo": {...},
#     "bosque": {...},
#     "cueva": {...}
#   },
#   "objetos": {
#     "pocion": {...},
#     "antidoto": {...},
#     "espada_oxida": {...},
#     "armadura_cuero": {...},
#     "anillo_chistoso": {...},
#     "hongo": {...}
#   },
#   "enemigos": {
#     "slime": {...},
#     "goblin": {...},
#     "murcielago": {...},
#     "dragon": {...}
#   },
#   "misiones": {
#     "hongos": {...},
#     "goblin": {...},
#     "dragon": {...}
#   }
# }
# Ejecuta: python rpg_texto.py
# Comandos iniciales sugeridos: ayuda, mirar, estado, misiones
