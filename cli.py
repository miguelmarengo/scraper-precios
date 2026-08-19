"""Uso desde la terminal (útil para automatizar con cron).

    python cli.py https://tienda.com --csv salida.csv
    python cli.py https://tienda.com --sheet "https://docs.google.com/spreadsheets/d/XXXX" --modo agregar
"""

from __future__ import annotations

import argparse
import csv
import sys

import sheets
from scraper import a_tabla, scrapear


def main():
    ap = argparse.ArgumentParser(description="Scraper de precios de tiendas en línea")
    ap.add_argument("url")
    ap.add_argument("--filtro", default="", help='qué buscar, p. ej. "sillones blancos" o "sofa | loveseat -piel"')
    ap.add_argument("--precio-min", type=float, default=None)
    ap.add_argument("--precio-max", type=float, default=None)
    ap.add_argument("--solo-disponibles", action="store_true")
    ap.add_argument("--max", type=int, default=300, help="máximo de productos (300)")
    ap.add_argument("--csv", help="ruta del CSV de salida")
    ap.add_argument("--sheet", default="", help="URL, ID o nombre de la hoja de Google")
    ap.add_argument("--pestana", default="Productos")
    ap.add_argument("--modo", default="reemplazar",
                    choices=["sincronizar", "reemplazar", "nueva", "agregar"],
                    help="sincronizar = actualizar tu hoja respetando lo que ya tiene")
    ap.add_argument("--emparejar", default="auto", choices=["auto", "sku", "url"],
                    help="cómo reconocer que un producto es el mismo de antes")
    ap.add_argument("--sin-respaldo", action="store_true",
                    help="no copiar el contenido anterior a la pestaña de respaldo")
    ap.add_argument("--compartir", default="", help="correo con el que compartir una hoja nueva")
    ap.add_argument("--creds", default=None, help="ruta del JSON de credenciales")
    ap.add_argument("--delay", type=float, default=0.6)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--rapido", action="store_true", help="no abrir cada producto (sin inventario ni entrega)")
    ap.add_argument("--ignorar-robots", action="store_true")
    args = ap.parse_args()

    def progreso(msg, pct=None):
        print(f"  {msg}", file=sys.stderr)

    productos, informe = scrapear(
        args.url,
        filtro=args.filtro,
        precio_min=args.precio_min,
        precio_max=args.precio_max,
        solo_disponibles=args.solo_disponibles,
        max_productos=args.max,
        detalle_inventario=not args.rapido,
        respetar_robots=not args.ignorar_robots,
        delay=args.delay,
        workers=args.workers,
        progreso=progreso,
    )

    print(
        f"\nPlataforma: {informe['plataforma']} | filas: {informe['filas']} | "
        f"con precio: {informe['con_precio']} | con foto: {informe['con_foto']} | "
        f"con medidas: {informe['con_medidas']} | con inventario: {informe['con_inventario']} | "
        f"con entrega: {informe['con_entrega']}",
        file=sys.stderr,
    )

    if not productos:
        print("Sin resultados.", file=sys.stderr)
        return 1

    tabla = a_tabla(productos)

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8-sig") as fh:
            csv.writer(fh).writerows(tabla)
        print(f"CSV guardado en {args.csv}", file=sys.stderr)

    if args.modo == "sincronizar":
        from sincronizar import construir_plan

        contexto = sheets.leer_hoja(args.sheet, args.pestana, args.creds)
        plan = construir_plan(contexto["encabezado"], contexto["filas"], productos,
                              estrategia=args.emparejar)
        if plan.aviso:
            print(f"Aviso: {plan.aviso}", file=sys.stderr)
        res = sheets.aplicar_plan(contexto, plan, respaldar=not args.sin_respaldo, pestana=args.pestana)
        print(
            f"Hoja sincronizada: {res['nuevos']} nuevos, {res['cambiados']} actualizados, "
            f"{res['faltantes']} no encontrados, {res['iguales']} sin cambios\n{res['url']}",
            file=sys.stderr,
        )
    elif args.sheet or (not args.csv):
        res = sheets.escribir(
            tabla,
            destino=args.sheet,
            pestana=args.pestana,
            modo=args.modo,
            compartir_con=args.compartir,
            ruta_creds=args.creds,
        )
        print(f"Hoja actualizada: {res['url']}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
