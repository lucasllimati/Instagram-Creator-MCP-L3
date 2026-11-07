"""Regras técnicas das imagens de um post, sem IA.

Uso: python scripts/validar_imagem.py fila/2026-11-09/FIN [...]
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, UnidentifiedImageError

import comum
from validar import Erro


def _checar(arquivo: Path, esperado, limites) -> list[Erro]:
    max_bytes = limites["imagem"]["tamanho_max_mb"] * 1024 * 1024
    erros = []
    if arquivo.stat().st_size > max_bytes:
        erros.append(Erro("imagem.tamanho", arquivo.name, f"acima de {limites['imagem']['tamanho_max_mb']} MB"))
    try:
        with Image.open(arquivo) as im:
            im.load()
            # MPO e JPS são recusados pela Meta e aparecem com outro formato no Pillow.
            if im.format != "JPEG":
                erros.append(Erro("imagem.formato", arquivo.name, f"formato {im.format}; use JPEG"))
            if im.mode != "RGB":
                erros.append(Erro("imagem.cor", arquivo.name, f"modo {im.mode}; use RGB"))
            perfil_icc = im.info.get("icc_profile")
            if perfil_icc and b"sRGB" not in perfil_icc:
                erros.append(Erro("imagem.cor", arquivo.name, "perfil de cor diferente de sRGB"))
            if list(im.size) != list(esperado):
                erros.append(Erro("imagem.dimensao", arquivo.name, f"{im.size}; esperado {tuple(esperado)}"))
    except (UnidentifiedImageError, OSError) as e:
        erros.append(Erro("imagem.formato", arquivo.name, f"arquivo inválido: {type(e).__name__}"))
    return erros


def validar_pasta(pasta: Path, post: dict, limites: dict) -> list[Erro]:
    erros = []
    grupos = [("slide", len(post["slides"]), limites["imagem"]["feed"]), ("story", len(post.get("stories", [])), limites["imagem"]["story"])]
    for prefixo, total, dimensao in grupos:
        esperados = {f"{prefixo}_{i:02d}.jpg" for i in range(1, total + 1)}
        presentes = {p.name for p in pasta.glob(f"{prefixo}_*.jpg")}
        if esperados != presentes:
            erros.append(Erro("imagem.quantidade", prefixo, f"faltam {sorted(esperados - presentes)}; sobram {sorted(presentes - esperados)}"))
        for nome in sorted(esperados & presentes):
            erros += _checar(pasta / nome, dimensao, limites)
    return erros


def main(argv=None) -> int:
    pastas = [Path(a) for a in (argv if argv is not None else sys.argv[1:])]
    limites = comum.limites()
    falhou = False
    for pasta in pastas:
        erros = validar_pasta(pasta, comum.ler_json(pasta / "post.json"), limites)
        print(("REPROVADO " if erros else "OK ") + str(pasta))
        for e in erros:
            print(f"  {e}")
        falhou = falhou or bool(erros)
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
