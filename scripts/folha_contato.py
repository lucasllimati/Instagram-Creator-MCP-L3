"""Monta previa.jpg com miniaturas do post, para o QA visual gastar menos tokens.

Uso: python scripts/folha_contato.py fila/2026-11-09/FIN [...]
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image

LARGURA = 320
COLUNAS = 5
ESPACO = 8
ALTURA_CELULA = 570


def miniaturas(pasta: Path) -> list[str]:
    return [p.name for p in sorted(pasta.glob("slide_*.jpg")) + sorted(pasta.glob("story_*.jpg"))]


def gerar(pasta: Path) -> Path:
    nomes = miniaturas(pasta)
    if not nomes:
        raise ValueError(f"nenhuma imagem em {pasta}")
    colunas = min(COLUNAS, len(nomes))
    linhas = math.ceil(len(nomes) / colunas)
    folha = Image.new("RGB", (colunas * LARGURA + (colunas + 1) * ESPACO, linhas * ALTURA_CELULA + (linhas + 1) * ESPACO), "#808080")
    for i, nome in enumerate(nomes):
        with Image.open(pasta / nome) as im:
            mini = im.convert("RGB")
            mini.thumbnail((LARGURA, ALTURA_CELULA))
            folha.paste(mini, (ESPACO + (i % colunas) * (LARGURA + ESPACO), ESPACO + (i // colunas) * (ALTURA_CELULA + ESPACO)))
    saida = pasta / "previa.jpg"
    folha.save(saida, "JPEG", quality=80)
    return saida


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(gerar(Path(arg)))
