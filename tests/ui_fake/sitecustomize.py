"""Sustituye a Google por un doble, para poder probar la interfaz completa
sin credenciales ni red.

Se activa arrancando la app con PYTHONPATH apuntando a esta carpeta. Python
importa `sitecustomize` solo, antes que cualquier otra cosa, así que aquí se
registran módulos falsos de `gspread` y `google.oauth2.service_account`. El
código de la app no se toca: cree que está hablando con Google de verdad.
"""

import sys
import types

ENCABEZADO = ["estado", "cambios", "revisado_en", "sku", "nombre", "precio", "foto", "notas"]
FILAS = [
    ["⚪ sin cambios", "", "2026-08-01 09:00", "SO-BL", "Sillón Oslo", "11999.00",
     '=IMAGE("https://cdn.test/viejo.jpg")', "pedir muestra"],
    ["⚪ sin cambios", "", "2026-08-01 09:00", "Z-9", "Sillón descontinuado", "8000.00",
     '=IMAGE("https://cdn.test/z.jpg")', "ya no lo traen"],
]


class WorksheetNotFound(Exception):
    pass


class Worksheet:
    _id = 500

    def __init__(self, title, valores=None):
        self.title = title
        Worksheet._id += 1
        self.id = Worksheet._id
        self._valores = [list(f) for f in (valores or [])]
        self.row_count = max(len(self._valores), 20)
        self.col_count = 60

    def get_values(self, **kw):
        return [list(f) for f in self._valores]

    def clear(self):
        self._valores = []

    def update(self, values=None, range_name=None, **kw):
        self._valores = [list(f) for f in values]

    def add_rows(self, n):
        self.row_count += n

    def add_cols(self, n):
        self.col_count += n

    def freeze(self, rows=0):
        pass

    def format(self, *a, **k):
        pass


class Spreadsheet:
    url = "https://docs.google.com/spreadsheets/d/DEMO"
    title = "Hoja de demostración"

    def __init__(self):
        self._hojas = {"Productos": Worksheet("Productos", [ENCABEZADO] + FILAS)}

    def worksheet(self, title):
        if title not in self._hojas:
            raise WorksheetNotFound(title)
        return self._hojas[title]

    def add_worksheet(self, title, rows=100, cols=26):
        self._hojas[title] = Worksheet(title)
        return self._hojas[title]

    def worksheets(self):
        return list(self._hojas.values())

    def batch_update(self, cuerpo):
        return {}

    def share(self, *a, **k):
        pass


LIBRO = Spreadsheet()


class Cliente:
    def open_by_key(self, key):
        return LIBRO

    def open(self, nombre):
        return LIBRO

    def create(self, titulo):
        return LIBRO


gspread = types.ModuleType("gspread")
gspread.WorksheetNotFound = WorksheetNotFound
gspread.authorize = lambda creds: Cliente()
sys.modules["gspread"] = gspread

# Ojo: `google` es un paquete de espacio de nombres real (lo usa protobuf, del que
# depende Streamlit). Sustituirlo entero rompe la app. Solo se registran los
# submódulos concretos que interesan.
oauth2 = types.ModuleType("google.oauth2")
cuenta = types.ModuleType("google.oauth2.service_account")


class Credentials:
    @staticmethod
    def from_service_account_file(ruta, scopes=None):
        return object()


cuenta.Credentials = Credentials
oauth2.service_account = cuenta
sys.modules.setdefault("google.oauth2", oauth2)
sys.modules["google.oauth2.service_account"] = cuenta
