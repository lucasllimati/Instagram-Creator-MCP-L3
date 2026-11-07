"""Transforma post.json em imagens JPEG usando os templates HTML.

Uso: python scripts/renderizar.py fila/2026-11-09/FIN [...]
Também gera a folha de miniaturas previa.jpg em cada pasta.
"""
from __future__ import annotations

import io
import sys
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image

import comum
import folha_contato
import grafico

TEMPLATES = comum.RAIZ / "templates"
ROTULOS_PILAR = {
    "conceito": "Conceito",
    "erro": "Erro comum",
    "exemplo": "Passo a passo",
    "livro": "Ideia de livro",
    "checklist": "Checklist",
    "comparativo": "Comparativo",
    "reflexao": "Reflexão",
    "atualidade": "Atualidade",
    "evento": "O que aconteceu",
}
ROTULOS_STORY = {"chamada": "Post novo", "curiosidade": "Você sabia?", "salve": "Salve o post"}
ESCALAS = (1, 0.94, 0.88, 0.82, 0.76, 0.7)
JS_ESTOURO = """() => {
  const a = document.querySelector('.area');
  if (a.scrollHeight > a.clientHeight + 1 || a.scrollWidth > a.clientWidth + 1) return true;
  const r = a.getBoundingClientRect();
  return [...a.querySelectorAll('*')].some(e => {
    if (e.closest('svg') && e.tagName.toLowerCase() !== 'svg') return false;
    const q = e.getBoundingClientRect();
    return q.top < r.top - 1 || q.bottom > r.bottom + 1 || q.left < r.left - 1 || q.right > r.right + 1;
  });
}"""

_env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))


class ErroRender(Exception):
    pass


def _tamanho_titulo(tipo: str, titulo: str) -> int:
    n = len(titulo)
    if tipo in ("capa", "frase"):
        return 128 if n <= 28 else 112 if n <= 45 else 96 if n <= 70 else 80
    return 88 if n <= 30 else 76


def _base(marca: dict, largura: int, altura: int, topo: int, base: int, superficie: str) -> dict:
    return {
        "marca": marca,
        "cores": marca["cores"],
        "largura": largura,
        "altura": altura,
        "margem_topo": topo,
        "margem_base": base,
        "superficie": superficie,
        "fontes": {
            "inter": (TEMPLATES / "fontes" / "Inter.ttf").as_uri(),
            "montserrat": (TEMPLATES / "fontes" / "Montserrat.ttf").as_uri(),
        },
    }


def _dados_grafico(post: dict, slide: dict, marca: dict, dados_dir: Path) -> dict:
    arquivo = comum.ler_json(dados_dir / f"sgs_{slide.get('serie')}.json")
    ref = post.get("dados_ref")
    if arquivo is None or ref is None:
        raise ErroRender(f"slide {slide['n']}: dados ausentes para a série {slide.get('serie')}")
    pontos = grafico.recorte(arquivo["pontos"], ref["inicio"], ref["fim"], arquivo.get("degrau", False))
    if not pontos:
        raise ErroRender(f"slide {slide['n']}: período sem dados")
    c = marca["cores"]
    cores = {"linha": c["destaque_sobre_fundo"], "texto": c["corpo_sobre_fundo"], "grade": c["corpo_sobre_fundo"] + "33", "destaque": c["destaque"]}
    ano, mes, dia = arquivo["coletado_em"].split("-")
    return {
        "svg": grafico.svg_serie(pontos, cores, arquivo.get("degrau", False)),
        "fonte_dados": arquivo.get("fonte", f"Banco Central, SGS série {slide['serie']}"),
        "data_coleta": f"{dia}/{mes}/{ano}",
    }


def html_slide(post: dict, slide: dict, marca: dict, dados_dir: Path) -> str:
    superficie = "principal" if slide["tipo"] in ("capa", "cta", "frase") else "fundo"
    ctx = _base(marca, 1080, 1350, 90, 140, superficie)
    ctx.update(
        slide=slide,
        rotulo_pilar=ROTULOS_PILAR[post["pilar"]],
        tamanho_titulo=_tamanho_titulo(slide["tipo"], slide["titulo"]),
        numeracao=f"{slide['n']}/{len(post['slides'])}" if post["formato"] == "carrossel" else "",
    )
    if slide["tipo"] == "grafico":
        ctx.update(_dados_grafico(post, slide, marca, dados_dir))
    return _env.get_template(f"{slide['tipo']}.html").render(**ctx)


def html_story(story: dict, marca: dict) -> str:
    ctx = _base(marca, 1080, 1920, 250, 250, "principal")
    ctx.update(story=story, rotulo_story=ROTULOS_STORY[story["tipo"]])
    return _env.get_template("story.html").render(**ctx)


def _capturar(pagina, html: str, tmp: Path, largura: int, altura: int, saida: Path, qualidade: int) -> bool:
    arquivo = tmp / "pagina.html"
    arquivo.write_text(html, encoding="utf-8")
    pagina.set_viewport_size({"width": largura, "height": altura})
    pagina.goto(arquivo.as_uri())
    pagina.evaluate("document.fonts.ready.then(() => true)")
    # Começa grande e reduz só o necessário, respeitando um mínimo legível.
    estourou = True
    for escala in ESCALAS:
        pagina.evaluate("e => document.documentElement.style.setProperty('--e', e)", str(escala))
        estourou = pagina.evaluate(JS_ESTOURO)
        if not estourou:
            break
    png = pagina.screenshot(type="png", clip={"x": 0, "y": 0, "width": largura, "height": altura})
    with Image.open(io.BytesIO(png)) as im:
        im.convert("RGB").save(saida, "JPEG", quality=qualidade, subsampling=0, optimize=True)
    return estourou


def renderizar_post(post: dict, saida: Path, dados_dir: Path = comum.RAIZ / "dados") -> list[Path]:
    from playwright.sync_api import sync_playwright

    marca = comum.marca(post["perfil"])
    limites = comum.limites()
    qualidade = limites["imagem"]["qualidade_jpeg"]
    saida.mkdir(parents=True, exist_ok=True)
    for antigo in list(saida.glob("slide_*.jpg")) + list(saida.glob("story_*.jpg")):
        antigo.unlink()

    trabalhos = [
        (f"slide {s['n']}", html_slide(post, s, marca, dados_dir), limites["imagem"]["feed"], saida / f"slide_{s['n']:02d}.jpg")
        for s in post["slides"]
    ]
    trabalhos += [
        (f"story {i}", html_story(st, marca), limites["imagem"]["story"], saida / f"story_{i:02d}.jpg")
        for i, st in enumerate(post.get("stories", []), 1)
    ]

    estouros = []
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        navegador = p.chromium.launch()
        pagina = navegador.new_page(device_scale_factor=1)
        pagina.route("http*://**", lambda rota: rota.abort())  # sem rede: só arquivos locais
        for rotulo, html, (largura, altura), destino in trabalhos:
            if _capturar(pagina, html, Path(tmp), largura, altura, destino, qualidade):
                estouros.append(rotulo)
        navegador.close()
    if estouros:
        raise ErroRender("texto fora da área segura em: " + ", ".join(estouros))
    return [t[3] for t in trabalhos]


def main(argv=None) -> int:
    pastas = [Path(a) for a in (argv if argv is not None else sys.argv[1:])]
    falhou = False
    for pasta in pastas:
        post = comum.ler_json(pasta / "post.json")
        try:
            arquivos = renderizar_post(post, pasta)
            folha_contato.gerar(pasta)
            print(f"OK {pasta}: {len(arquivos)} imagens")
        except ErroRender as e:
            falhou = True
            print(f"REPROVADO {pasta}: {e}")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
