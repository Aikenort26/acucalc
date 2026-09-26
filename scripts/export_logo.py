"""Genera assets/acucalc_logo.png (1200 px, fondo transparente) desde el SVG.

Se ejecuta una sola vez cuando cambia el logo; el PNG queda versionado y el
informe lo usa directamente, sin agregar dependencias de runtime (LaTeX no lee
SVG sin inkscape). Requiere `pip install playwright` y un Chromium; si
Playwright no encuentra el suyo, pasa la ruta con CHROMIUM=/ruta/al/chrome."""
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

ASSETS = Path(__file__).resolve().parent.parent / "assets"
LADO_PX = 1200


def main() -> None:
    svg = (ASSETS / "acucalc_logo.svg").read_text(encoding="utf-8")
    html = ("<html><body style='margin:0;background:transparent'>"
            f"<div id='l' style='width:240px;height:240px'>{svg}</div></body></html>")
    with sync_playwright() as p:
        kw = {"executable_path": os.environ["CHROMIUM"]} if os.environ.get("CHROMIUM") else {}
        browser = p.chromium.launch(args=["--no-sandbox"], **kw)
        page = browser.new_page(viewport={"width": 240, "height": 240},
                                device_scale_factor=LADO_PX / 240)
        page.set_content(html)
        page.locator("#l").screenshot(path=str(ASSETS / "acucalc_logo.png"),
                                      omit_background=True)
        browser.close()
    print(ASSETS / "acucalc_logo.png")


if __name__ == "__main__":
    main()
