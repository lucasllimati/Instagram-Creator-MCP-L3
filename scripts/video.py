"""Monta um vídeo vertical (9:16) para Reels com os slides do carrossel.

Uso: python scripts/video.py fila/2026-11-09/FIN [saida.mp4]

O vídeo sai sem áudio, para a música ser escolhida na biblioteca do Instagram.
Usa o ffmpeg embutido no pacote imageio-ffmpeg.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

import comum

LARGURA, ALTURA = 1080, 1920


def deve_gerar(post: dict, limites: dict) -> bool:
    return post["formato"] == "carrossel" and limites.get("telegram", {}).get("video", True)


def quadro(slide: Path, cor: str) -> Image.Image:
    fundo = Image.new("RGB", (LARGURA, ALTURA), cor)
    with Image.open(slide) as im:
        im = im.convert("RGB")
        im.thumbnail((LARGURA, ALTURA))
        fundo.paste(im, ((LARGURA - im.width) // 2, (ALTURA - im.height) // 2))
    return fundo


def lista_concat(quadros: list[Path], segundos: float) -> str:
    def linha(p: Path) -> str:
        return "file '" + p.as_posix().replace("'", "'\\''") + "'"

    partes = []
    for q in quadros:
        partes += [linha(q), f"duration {segundos}"]
    return "\n".join(partes) + "\n"


def _ffmpeg() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def gerar_reel(pasta: Path, cor: str, saida: Path, segundos: float = 3.5) -> Path:
    slides = sorted(Path(pasta).glob("slide_*.jpg"))
    if not slides:
        raise ValueError(f"nenhum slide em {pasta}")
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        quadros = []
        for i, s in enumerate(slides, 1):
            destino = tmp / f"q{i:02d}.png"
            quadro(s, cor).save(destino)
            quadros.append(destino)
        lista = tmp / "lista.txt"
        lista.write_text(lista_concat(quadros, segundos), encoding="utf-8")
        r = subprocess.run(
            [_ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lista),
             "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-movflags", "+faststart", "-an", str(saida)],
            capture_output=True, text=True,
        )
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg falhou: {r.stderr[-500:]}")
    return saida


def inspecionar(arquivo: Path) -> dict:
    r = subprocess.run([_ffmpeg(), "-i", str(arquivo)], capture_output=True, text=True)
    duracao = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", r.stderr)
    tamanho = re.search(r"Video:.*?, (\d{2,5})x(\d{2,5})", r.stderr)
    if not duracao or not tamanho:
        raise RuntimeError("não foi possível ler o vídeo")
    h, m, s = duracao.groups()
    return {"duracao": int(h) * 3600 + int(m) * 60 + float(s), "largura": int(tamanho.group(1)), "altura": int(tamanho.group(2))}


if __name__ == "__main__":
    pasta = Path(sys.argv[1])
    post = comum.ler_json(pasta / "post.json")
    saida = Path(sys.argv[2]) if len(sys.argv) > 2 else pasta / "reel.mp4"
    segundos = comum.limites().get("telegram", {}).get("segundos_por_slide", 3.5)
    print(gerar_reel(pasta, comum.marca(post["perfil"])["cores"]["principal"], saida, segundos))
