"""Inngangspunkt for den pakkede tjenesten.

PyInstaller kjorer inngangsskriptet som __main__ uten pakkekontekst, saa
backend/__main__.py kan ikke brukes direkte - de relative importene der ville
feilet. Denne fila importerer pakken pa vanlig vis og kaller videre.
"""
from backend.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
