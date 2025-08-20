"""RPG de texto minimalista.

Uso rápido:
    python rpg_texto.py

Comandos clave: ayuda, mirar, ir, inventario, atacar, misiones, guardar, cargar, salir.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Tuple
import json
import os
import random
import textwrap

# === CONSTANTES ===
COSTO_ESTADO = 10
DESCUENTO_SANTUARIO = 0.8
CRITICO = 0.1
SAVE_FILE = "partida.json"
VERSION = 1
ICONOS_ESTADOS = {"veneno": "[☠]", "quemadura": "[🔥]", "aturdido": "[✖]", "sangrado": "[🩸]"}


# === DATACLASSES ===
@dataclass
class Objeto:
    id: str
    nombre: str
    tipo: str  # consumible, equipable, clave
    efecto: Dict[str, Any]
    precio: int
    descripcion: str


@dataclass
class Enemigo:
    id: str
    nombre: str
    nivel: int
    vida_max: int
    vida: int
    ataque: int
    defensa: int
    botin: List[str]
    oro: int
    personalidad: List[str]
    estados: Dict[str, int] = field(default_factory=dict)

    def esta_vivo(self) -> bool:
        return self.vida > 0


@dataclass
class Jefe(Enemigo):
    presentaciones: List[str] = field(default_factory=list)
    burlas_derrota: List[str] = field(default_factory=list)


@dataclass
class Sala:
    id: str
    nombre: str
    descripcion: str
    conexiones: Dict[str, str]
    objetos: List[str] = field(default_factory=list)
    npcs: Dict[str, str] = field(default_factory=dict)
    enemigos: List[str] = field(default_factory=list)
    santuario: bool = False


@dataclass
class Mision:
    id: str
    tipo: str  # recolectar, derrotar, visitar
    objetivo: str
    cantidad: int
    recompensa: Dict[str, Any]
    descripcion: str
    progreso: int = 0
    completada: bool = False


@dataclass
class Jugador:
    nombre: str
    nivel: int = 1
    xp: int = 0
    vida_max: int = 30
    vida: int = 30
    mana_max: int = 10
    mana: int = 10
    oro: int = 0
    ataque: int = 5
    defensa: int = 2
    inventario: Dict[str, int] = field(default_factory=dict)
    estados: Dict[str, int] = field(default_factory=dict)
    equipo: Dict[str, Optional[str]] = field(
        default_factory=lambda: {"arma": None, "armadura": None, "accesorio": None}
    )
    sala: str = "pueblo"

    def esta_vivo(self) -> bool:
        return self.vida > 0

    def modificar_vida(self, cantidad: int) -> None:
        self.vida = max(0, min(self.vida_max, self.vida + cantidad))


# === UTILIDADES ===
COMANDOS: Dict[str, Callable] = {}


def comando(nombre: str, aliases: Optional[List[str]] = None) -> Callable:
    """Registra un comando en el mapa global."""

    def decorador(func: Callable) -> Callable:
        COMANDOS[nombre] = func
        if aliases:
            for a in aliases:
                COMANDOS[a] = func
        return func

    return decorador


def parsear(texto: str) -> Tuple[str, List[str]]:
    """Analiza una línea de texto.

    >>> parsear("ir norte")
    ('ir', ['norte'])
    >>> parsear("  Mirar  ")
    ('mirar', [])
    """
    partes = texto.strip().lower().split()
    if not partes:
        return "", []
    return partes[0], partes[1:]


def calcular_dano(atq: int, defe: int) -> int:
    """Calcula el daño infligido.

    >>> random.seed(1); calcular_dano(10, 3)
    7
    """
    variacion = random.randint(-2, 2)
    dano = max(1, atq + variacion - defe)
    if random.random() < CRITICO:
        dano = int(dano * 1.5)
    return dano


# === JUEGO ===
class Juego:
    def __init__(self, datos: Dict[str, Any]):
        self.datos = datos
        self.objetos: Dict[str, Objeto] = {
            oid: Objeto(**o) for oid, o in datos["objetos"].items()
        }
        self.enemigos_template: Dict[str, Enemigo] = {}
        for eid, e in datos["enemigos"].items():
            if e.get("jefe"):
                data = e.copy()
                data.pop("jefe", None)
                self.enemigos_template[eid] = Jefe(**data)
            else:
                self.enemigos_template[eid] = Enemigo(**e)
        self.salas: Dict[str, Sala] = {
            sid: Sala(**s) for sid, s in datos["salas"].items()
        }
        self.misiones: Dict[str, Mision] = {
            mid: Mision(**m) for mid, m in datos["misiones"].items()
        }
        self.jugador: Optional[Jugador] = None
        self.enemigo_actual: Optional[Enemigo] = None
        self.running = True
        self.verbose = True

    # ----------------------- BUCLE PRINCIPAL -----------------------
    def iniciar(self) -> None:
        nombre = input("Nombre del héroe: ") or "Anónimo"
        self.jugador = Jugador(nombre=nombre)
        print(f"Bienvenido, {nombre}. Escribe 'ayuda' para ver comandos.")
        while self.running and self.jugador and self.jugador.esta_vivo():
            comando_linea = input("\n> ")
            verbo, args = parsear(comando_linea)
            if not verbo:
                continue
            funcion = COMANDOS.get(verbo)
            if funcion:
                funcion(self, args)
            else:
                print("No entiendo. Usa 'ayuda'.")

    # ----------------------- COMANDOS -----------------------
    @comando("ayuda")
    def cmd_ayuda(self, args: List[str]) -> None:
        print("Comandos disponibles:")
        for c in sorted({c for c in COMANDOS if len(c) > 1}):
            print(f"- {c}")

    @comando("mirar", aliases=["m", "examinar"])
    def cmd_mirar(self, args: List[str]) -> None:
        sala = self.sala_actual
        print(f"{sala.nombre}: {sala.descripcion}")
        if sala.objetos:
            print("Objetos visibles:", ", ".join(sala.objetos))
        if sala.npcs:
            print("Personas aquí:", ", ".join(sala.npcs))
        if sala.enemigos:
            vivos = [eid for eid in sala.enemigos if self.enemigos_template[eid].vida > 0]
            if vivos:
                print("Enemigos presentes:", ", ".join(vivos))
        print("Salidas:", ", ".join(sala.conexiones))

    @comando("ir")
    def cmd_ir(self, args: List[str]) -> None:
        if not args:
            print("¿A dónde?")
            return
        direccion = args[0]
        sala = self.sala_actual
        if direccion in sala.conexiones:
            self.jugador.sala = sala.conexiones[direccion]
            self.cmd_mirar([])
            self.actualizar_misiones("visitar", self.jugador.sala)
        else:
            print("No hay salida por ahí.")

    @comando("hablar")
    def cmd_hablar(self, args: List[str]) -> None:
        if not args:
            print("¿Con quién?")
            return
        npc = args[0]
        sala = self.sala_actual
        if npc in sala.npcs:
            print(sala.npcs[npc])
        else:
            print("No ves a esa persona aquí.")

    @comando("tomar")
    def cmd_tomar(self, args: List[str]) -> None:
        if not args:
            print("¿Qué deseas tomar?")
            return
        obj = args[0]
        sala = self.sala_actual
        if obj in sala.objetos:
            sala.objetos.remove(obj)
            self.jugador.inventario[obj] = self.jugador.inventario.get(obj, 0) + 1
            print(f"Has tomado {obj}.")
            self.actualizar_misiones("recolectar", obj)
        else:
            print("No encuentras eso.")

    @comando("soltar")
    def cmd_soltar(self, args: List[str]) -> None:
        if not args:
            print("¿Qué deseas soltar?")
            return
        obj = args[0]
        inv = self.jugador.inventario
        if inv.get(obj):
            inv[obj] -= 1
            if inv[obj] <= 0:
                del inv[obj]
            self.sala_actual.objetos.append(obj)
            print(f"Has soltado {obj}.")
        else:
            print("No tienes eso.")

    @comando("inventario")
    def cmd_inventario(self, args: List[str]) -> None:
        if not self.jugador.inventario:
            print("Inventario vacío.")
            return
        print("Inventario:")
        for obj, cant in self.jugador.inventario.items():
            print(f"- {obj} x{cant}")

    @comando("usar")
    def cmd_usar(self, args: List[str]) -> None:
        if not args:
            print("¿Qué usar?")
            return
        obj = args[0]
        inv = self.jugador.inventario
        if inv.get(obj):
            if obj in self.objetos:
                self.aplicar_objeto(self.objetos[obj])
                inv[obj] -= 1
                if inv[obj] <= 0:
                    del inv[obj]
            else:
                print("No puedes usar eso.")
        else:
            print("No lo tienes.")

    def aplicar_objeto(self, obj: Objeto) -> None:
        efecto = obj.efecto
        if "vida" in efecto:
            self.jugador.modificar_vida(efecto["vida"])
            print(f"Recuperas {efecto['vida']} de vida.")
        if "estado" in efecto:
            estado = efecto["estado"]
            if estado in self.jugador.estados:
                del self.jugador.estados[estado]
                print(f"Estado {estado} curado.")

    @comando("equipar")
    def cmd_equipar(self, args: List[str]) -> None:
        if not args:
            print("¿Qué equipar?")
            return
        obj = args[0]
        if self.jugador.inventario.get(obj) and obj in self.objetos:
            item = self.objetos[obj]
            if item.tipo != "equipable":
                print("No es equipable.")
                return
            slot = item.efecto.get("slot")
            actual = self.jugador.equipo.get(slot)
            self.jugador.equipo[slot] = obj
            print(f"Equipado {obj} en {slot}.")
            if actual:
                self.jugador.inventario[actual] = self.jugador.inventario.get(actual, 0) + 1
            self.jugador.inventario[obj] -= 1
            if self.jugador.inventario[obj] <= 0:
                del self.jugador.inventario[obj]
            self.recalcular_equipo()
        else:
            print("No lo tienes.")

    @comando("desequipar")
    def cmd_desequipar(self, args: List[str]) -> None:
        if not args:
            print("¿Qué slot?")
            return
        slot = args[0]
        actual = self.jugador.equipo.get(slot)
        if actual:
            self.jugador.inventario[actual] = self.jugador.inventario.get(actual, 0) + 1
            self.jugador.equipo[slot] = None
            print(f"Has quitado {actual} del slot {slot}.")
            self.recalcular_equipo()
        else:
            print("Nada equipado ahí.")

    def recalcular_equipo(self) -> None:
        self.jugador.ataque = 5
        self.jugador.defensa = 2
        for obj_id in self.jugador.equipo.values():
            if not obj_id:
                continue
            efecto = self.objetos[obj_id].efecto
            self.jugador.ataque += efecto.get("ataque", 0)
            self.jugador.defensa += efecto.get("defensa", 0)

    @comando("estado")
    def cmd_estado(self, args: List[str]) -> None:
        j = self.jugador
        print(
            f"Vida {j.vida}/{j.vida_max} | Mana {j.mana}/{j.mana_max} | Oro {j.oro} | Nivel {j.nivel}"
        )
        if j.estados:
            print("Estados:", " ".join(f"{ICONOS_ESTADOS[e]}:{t}" for e, t in j.estados.items()))
        if any(j.equipo.values()):
            print("Equipo:")
            for s, o in j.equipo.items():
                print(f"- {s}: {o}")

    @comando("misiones")
    def cmd_misiones(self, args: List[str]) -> None:
        for m in self.misiones.values():
            estado = "completa" if m.completada else f"{m.progreso}/{m.cantidad}"
            print(f"[{m.id}] {m.descripcion} ({estado})")

    @comando("atacar")
    def cmd_atacar(self, args: List[str]) -> None:
        if self.enemigo_actual and self.enemigo_actual.esta_vivo():
            enemigo = self.enemigo_actual
        else:
            if not args:
                print("¿A quién?")
                return
            nombre = args[0]
            sala = self.sala_actual
            if nombre not in sala.enemigos:
                print("No está aquí.")
                return
            enemigo = self.clonar_enemigo(nombre)
            self.enemigo_actual = enemigo
            if isinstance(enemigo, Jefe):
                frase = random.choice(enemigo.presentaciones).format(jugador=self.jugador.nombre)
                print(frase)
        # turno jugador
        dano = calcular_dano(self.jugador.ataque, enemigo.defensa)
        enemigo.vida -= dano
        print(f"Golpeas a {enemigo.nombre} por {dano}.")
        if not enemigo.esta_vivo():
            self.victoria(enemigo)
            return
        # aplicar estados enemigo
        self.aplicar_estados(enemigo)
        # turno enemigo
        dano_e = calcular_dano(enemigo.ataque, self.jugador.defensa)
        self.jugador.modificar_vida(-dano_e)
        print(f"{enemigo.nombre} te golpea por {dano_e}.")
        if not self.jugador.esta_vivo():
            print("Has caído. Fin del juego.")
            self.running = False
            return
        self.aplicar_estados(self.jugador)

    def aplicar_estados(self, obj: Any) -> None:
        quitar = []
        for e, t in obj.estados.items():
            if e == "veneno":
                obj.vida -= 3
                print(f"{obj.nombre} sufre veneno.")
            elif e == "quemadura":
                obj.vida -= 2
                print(f"{obj.nombre} arde.")
            elif e == "sangrado":
                dano = t
                obj.vida -= dano
                obj.estados[e] = t + 1
                print(f"{obj.nombre} sangra {dano}.")
            obj.estados[e] = obj.estados.get(e, 0) - 1
            if obj.estados[e] <= 0:
                quitar.append(e)
        for e in quitar:
            del obj.estados[e]

    def victoria(self, enemigo: Enemigo) -> None:
        print(f"Derrotaste a {enemigo.nombre}.")
        self.jugador.oro += enemigo.oro
        for item in enemigo.botin:
            self.jugador.inventario[item] = self.jugador.inventario.get(item, 0) + 1
        self.actualizar_misiones("derrotar", enemigo.id)
        if isinstance(enemigo, Jefe):
            print(random.choice(enemigo.burlas_derrota))
        sala = self.sala_actual
        if enemigo.id in sala.enemigos:
            sala.enemigos.remove(enemigo.id)
        self.enemigo_actual = None

    @comando("huir")
    def cmd_huir(self, args: List[str]) -> None:
        if self.enemigo_actual and self.enemigo_actual.esta_vivo():
            if random.random() < 0.5:
                print("Escapas con éxito.")
                self.enemigo_actual = None
            else:
                print("Fallas al huir y recibes un golpe." )
                dano = calcular_dano(self.enemigo_actual.ataque, self.jugador.defensa)
                self.jugador.modificar_vida(-dano)
        else:
            print("No estás peleando.")

    @comando("santuario")
    def cmd_santuario(self, args: List[str]) -> None:
        sala = self.sala_actual
        if not sala.santuario:
            print("Aquí no hay santuario.")
            return
        j = self.jugador
        if not j.estados:
            print("No tienes estados que curar.")
            return
        estados = list(j.estados.keys())
        for i, e in enumerate(estados, 1):
            print(f"{i}. {e} - {COSTO_ESTADO} oro")
        print(f"{len(estados)+1}. curar todo - {int(len(estados)*COSTO_ESTADO*DESCUENTO_SANTUARIO)} oro")
        eleccion = input("Elige opción: ")
        try:
            idx = int(eleccion)
        except ValueError:
            print("Opción inválida.")
            return
        if idx == len(estados) + 1:
            costo = int(len(estados) * COSTO_ESTADO * DESCUENTO_SANTUARIO)
            if j.oro < costo:
                print("Sin oro suficiente.")
                self.ofrecer_mision_micro()
                return
            j.oro -= costo
            for e in estados:
                del j.estados[e]
                print(f"Una paloma mística se lleva tu {e}.")
        elif 1 <= idx <= len(estados):
            e = estados[idx - 1]
            if j.oro < COSTO_ESTADO:
                print("Sin oro suficiente.")
                self.ofrecer_mision_micro()
                return
            j.oro -= COSTO_ESTADO
            del j.estados[e]
            print(f"Tu {e} huye al escuchar un chiste malo del santuario.")
        else:
            print("Opción inválida.")

    def ofrecer_mision_micro(self) -> None:
        r = input("¿Quieres limpiar bancos por unas monedas? (s/n) ")
        if r.lower().startswith("s"):
            print("Barres el santuario y encuentras 5 oro.")
            self.jugador.oro += 5

    @comando("guardar")
    def cmd_guardar(self, args: List[str]) -> None:
        datos = {
            "version": VERSION,
            "jugador": asdict(self.jugador),
            "salas": {sid: asdict(s) for sid, s in self.salas.items()},
            "misiones": {mid: asdict(m) for mid, m in self.misiones.items()},
        }
        with open(SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        print("Partida guardada.")

    @comando("cargar")
    def cmd_cargar(self, args: List[str]) -> None:
        if not os.path.exists(SAVE_FILE):
            print("No hay partida guardada.")
            return
        try:
            with open(SAVE_FILE, "r", encoding="utf-8") as f:
                datos = json.load(f)
        except Exception:
            print("Archivo corrupto.")
            return
        if datos.get("version") != VERSION:
            print("Versión incompatible.")
            return
        self.jugador = Jugador(**datos["jugador"])
        self.salas = {sid: Sala(**s) for sid, s in datos["salas"].items()}
        self.misiones = {mid: Mision(**m) for mid, m in datos["misiones"].items()}
        print("Partida cargada.")
        self.cmd_mirar([])

    @comando("config")
    def cmd_config(self, args: List[str]) -> None:
        self.verbose = not self.verbose
        estado = "activados" if self.verbose else "desactivados"
        print(f"Mensajes verbosos {estado}.")

    @comando("salir")
    def cmd_salir(self, args: List[str]) -> None:
        r = input("¿Seguro? (s/n) ")
        if r.lower().startswith("s"):
            self.running = False

    # ----------------------- AUXILIARES -----------------------
    @property
    def sala_actual(self) -> Sala:
        return self.salas[self.jugador.sala]

    def clonar_enemigo(self, eid: str) -> Enemigo:
        plantilla = self.enemigos_template[eid]
        if isinstance(plantilla, Jefe):
            return Jefe(**asdict(plantilla))
        return Enemigo(**asdict(plantilla))

    def actualizar_misiones(self, tipo: str, objetivo: str) -> None:
        for m in self.misiones.values():
            if m.tipo == tipo and m.objetivo == objetivo and not m.completada:
                m.progreso += 1
                if m.progreso >= m.cantidad:
                    m.completada = True
                    self.jugador.oro += m.recompensa.get("oro", 0)
                    print(f"Misión '{m.descripcion}' completada.")


# === DATOS INICIALES ===
SEED = {
    "objetos": {
        "pocion": {
            "id": "pocion",
            "nombre": "poción",
            "tipo": "consumible",
            "efecto": {"vida": 10},
            "precio": 5,
            "descripcion": "Restaura vida",
        },
        "antidoto": {
            "id": "antidoto",
            "nombre": "antídoto",
            "tipo": "consumible",
            "efecto": {"estado": "veneno"},
            "precio": 8,
            "descripcion": "Cura veneno",
        },
        "espada_oxidada": {
            "id": "espada_oxidada",
            "nombre": "espada oxidada",
            "tipo": "equipable",
            "efecto": {"ataque": 2, "slot": "arma"},
            "precio": 12,
            "descripcion": "Mejora ataque",
        },
        "armadura_cuero": {
            "id": "armadura_cuero",
            "nombre": "armadura de cuero",
            "tipo": "equipable",
            "efecto": {"defensa": 2, "slot": "armadura"},
            "precio": 15,
            "descripcion": "Protección básica",
        },
        "gema_bril": {
            "id": "gema_bril",
            "nombre": "gema brillante",
            "tipo": "clave",
            "efecto": {},
            "precio": 0,
            "descripcion": "Brilla sospechosamente",
        },
    },
    "enemigos": {
        "goblin": {
            "id": "goblin",
            "nombre": "goblin",
            "nivel": 1,
            "vida_max": 12,
            "vida": 12,
            "ataque": 4,
            "defensa": 1,
            "botin": ["pocion"],
            "oro": 5,
            "personalidad": ["grita cosas feas"],
        },
        "lobo": {
            "id": "lobo",
            "nombre": "lobo hambriento",
            "nivel": 1,
            "vida_max": 15,
            "vida": 15,
            "ataque": 5,
            "defensa": 2,
            "botin": [],
            "oro": 3,
            "personalidad": ["aulla desafinado"],
        },
        "esqueleto": {
            "id": "esqueleto",
            "nombre": "esqueleto",
            "nivel": 2,
            "vida_max": 18,
            "vida": 18,
            "ataque": 6,
            "defensa": 3,
            "botin": ["antidoto"],
            "oro": 7,
            "personalidad": ["sus huesos rechinan con ritmo"],
        },
        "dragon_grunon": {
            "id": "dragon_grunon",
            "nombre": "dragón gruñón",
            "nivel": 5,
            "vida_max": 40,
            "vida": 40,
            "ataque": 8,
            "defensa": 5,
            "botin": ["gema_bril"],
            "oro": 50,
            "personalidad": ["se queja del clima"],
            "jefe": True,
            "presentaciones": [
                "El Jefe surge criticando tu peinado, {jugador}.",
                "{jugador}, tu arma huele a derrota, dice el Jefe.",
            ],
            "burlas_derrota": [
                "El dragón cae murmurando: 'al menos mi humor era afilado'."
            ],
        },
    },
    "salas": {
        "pueblo": {
            "id": "pueblo",
            "nombre": "Pueblo inicial",
            "descripcion": "Una plaza con una fuente y pocas casas.",
            "conexiones": {"norte": "bosque", "este": "cueva"},
            "objetos": ["pocion"],
            "npcs": {"aldeano": "Bienvenido al pueblo."},
            "enemigos": [],
            "santuario": True,
        },
        "bosque": {
            "id": "bosque",
            "nombre": "Bosque",
            "descripcion": "Árboles susurrantes y caminos de tierra.",
            "conexiones": {"sur": "pueblo", "este": "ruinas"},
            "objetos": ["antidoto"],
            "npcs": {},
            "enemigos": ["goblin", "lobo"],
        },
        "ruinas": {
            "id": "ruinas",
            "nombre": "Ruinas antiguas",
            "descripcion": "Piedras cubiertas de musgo.",
            "conexiones": {"oeste": "bosque"},
            "objetos": ["espada_oxidada"],
            "npcs": {},
            "enemigos": ["esqueleto"],
        },
        "cueva": {
            "id": "cueva",
            "nombre": "Cueva oscura",
            "descripcion": "Se escucha un ronquido grave.",
            "conexiones": {"oeste": "pueblo"},
            "objetos": [],
            "npcs": {},
            "enemigos": ["dragon_grunon"],
        },
    },
    "misiones": {
        "madera": {
            "id": "madera",
            "tipo": "recolectar",
            "objetivo": "antidoto",
            "cantidad": 1,
            "recompensa": {"oro": 10},
            "descripcion": "Recoge un antídoto en el bosque.",
        },
        "cazador": {
            "id": "cazador",
            "tipo": "derrotar",
            "objetivo": "goblin",
            "cantidad": 1,
            "recompensa": {"oro": 15},
            "descripcion": "Derrota a un goblin molesto.",
        },
        "dragon": {
            "id": "dragon",
            "tipo": "derrotar",
            "objetivo": "dragon_grunon",
            "cantidad": 1,
            "recompensa": {"oro": 100},
            "descripcion": "Vence al dragón gruñón.",
        },
    },
}


def main() -> None:
    juego = Juego(SEED)
    juego.iniciar()


if __name__ == "__main__":
    main()

# === SEED DE EJEMPLO ===
{
  "salas": {
    "pueblo": {"conexiones": {"norte": "bosque", "este": "cueva"}},
    "bosque": {"conexiones": {"sur": "pueblo", "este": "ruinas"}},
    "ruinas": {"conexiones": {"oeste": "bosque"}},
    "cueva": {"conexiones": {"oeste": "pueblo"}}
  },
  "objetos": ["pocion", "antidoto", "espada_oxidada", "armadura_cuero", "gema_bril"],
  "enemigos": ["goblin", "lobo", "esqueleto", "dragon_grunon"],
  "misiones": ["madera", "cazador", "dragon"]
}

# Ejecuta: python rpg_texto.py
# Sugerencias: ayuda, mirar, estado, misiones
