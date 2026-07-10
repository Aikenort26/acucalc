"""Extrae la hoja DANE de una memoria xlsx al dataset embebido de ACUCALC.

Uso:
    python scripts/extract_dane.py [ruta_xlsx] [nombre_hoja]

Escribe data/dane.csv.gz (DP,DPNOM,DPMP,MPIO,ANO,AREA,POBLACION) y
data/dane_meta.json (fuente, fecha, rango de años, municipios).
"""
import gzip
import json
import sys
import datetime as dt
from pathlib import Path

import openpyxl

DEFAULT_XLSX = (r"C:\Users\aiken\OneDrive - AGUAS DE BOLIVAR S.A E.S.P\Formulación"
                r"\ESTUDIOS Y DISEÑOS\SALADO\ACU\V01-15042026\04_TECNICO"
                r"\03_HIDRAULICA\02_MEMORIAS\DIS-ACU-SALADO.xlsx")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

HEADER = ["DP", "DPNOM", "DPMP", "MPIO", "AÑO", "ÁREA GEOGRÁFICA", "Población"]


def extract(xlsx_path: str, sheet: str = "DANE") -> dict:
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)
    ws = wb[sheet]
    rows_iter = ws.iter_rows(values_only=True)
    header_idx = None
    for row in rows_iter:
        cells = [str(c).strip() if c is not None else "" for c in row]
        if cells[:7] == HEADER:
            header_idx = True
            break
    if not header_idx:
        raise ValueError(f"No se encontró la fila de encabezado {HEADER} en la hoja '{sheet}'")

    out_rows = []
    years, mpios = set(), set()
    for row in rows_iter:
        dp, dpnom, dpmp, mpio, ano, area, pob = (row + (None,) * 7)[:7]
        if dpnom is None or ano is None or pob is None:
            continue
        ano = int(ano)
        out_rows.append((str(dp), str(dpnom).strip(), str(dpmp), str(mpio).strip(),
                         ano, str(area).strip(), int(pob)))
        years.add(ano)
        mpios.add((str(dpnom).strip(), str(mpio).strip()))
    wb.close()
    if not out_rows:
        raise ValueError("La hoja DANE no contiene filas de datos")

    DATA_DIR.mkdir(exist_ok=True)
    with gzip.open(DATA_DIR / "dane.csv.gz", "wt", encoding="utf-8", newline="") as f:
        f.write("DP,DPNOM,DPMP,MPIO,ANO,AREA,POBLACION\n")
        for r in out_rows:
            f.write(",".join(f'"{v}"' if "," in str(v) else str(v) for v in r) + "\n")

    meta = {
        "fuente": Path(xlsx_path).name,
        "fecha_extraccion": dt.date.today().isoformat(),
        "anos": [min(years), max(years)],
        "municipios": len(mpios),
        "filas": len(out_rows),
    }
    (DATA_DIR / "dane_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_XLSX
    sheet = sys.argv[2] if len(sys.argv) > 2 else "DANE"
    print(json.dumps(extract(path, sheet), ensure_ascii=False, indent=1))
