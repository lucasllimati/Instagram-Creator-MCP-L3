"""Regras mensuráveis de conteúdo, sem IA.

Uso:
  python scripts/validar.py fila/2026-11-09/FIN/post.json [...]
  python scripts/validar.py --todos     # toda a fila ainda não publicada
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema

import comum

STATUS_SEM_LEGENDA = {"roteiro", "validado", "revisado", "revisar_humano"}
TICKER = re.compile(r"\b[A-Z]{4}(?:3|4|5|6|11)\b")
PERCENTUAL = re.compile(r"\d+(?:[.,]\d+)?\s?%")
TERMO_OFICIAL = re.compile(r"\b(?:Selic|IPCA|CDI|FGC|IR|Imposto de Renda)\b", re.I)
NUMERO = re.compile(r"\d")
INVESTIMENTO = re.compile(
    r"\b(?:invest\w*|renda fixa|tesouro|cdb|lci|lca|a[çc](?:ão|ões)|fundos?|selic|cdi|carteira|cripto\w*)\b", re.I
)
CTA_LEGENDA = re.compile(r"\b(?:salv\w+|coment\w+|compartilh\w+|envi\w+|marqu\w+|mand\w+)\b", re.I)
METRICA_MKT = re.compile(
    r"\d+(?:[.,]\d+)?\s?(?:%|x\b|vezes)[^.]*\b(?:alcance|engajamento|salvamentos?|seguidores|impress\w+|cliques|views)\b"
    r"|\b(?:alcance|engajamento|salvamentos?|seguidores|impress\w+|cliques|views)\b[^.]*\d+(?:[.,]\d+)?\s?(?:%|x\b|vezes)",
    re.I,
)
PLATAFORMA = re.compile(r"\b(?:Instagram|TikTok|Facebook|Google|YouTube|WhatsApp|LinkedIn)\b", re.I)
MUDANCA = re.compile(r"\b(?:algoritmo|recurso|atualiza\w+|mudou|novidade)\b", re.I)
ANO = re.compile(r"\b20\d{2}\b")
DATA_VISIVEL = re.compile(r"\b\d{1,2}/\d{1,2}(?:/\d{2,4})?\b|\b\d{1,2} de [a-zç]+\b", re.I)
CITACAO = re.compile(r"[“\"]([^”\"]+)[”\"]")
HASHTAG = re.compile(r"^#[a-z0-9_à-ÿ]+$")


@dataclass
class Erro:
    regra: str
    local: str
    mensagem: str

    def __str__(self) -> str:
        return f"[{self.regra}] {self.local}: {self.mensagem}"


@dataclass
class Contexto:
    limites: dict
    grade: dict
    termos: dict
    hoje: dt.date
    publicacoes: list = field(default_factory=list)
    fila: list = field(default_factory=list)
    dados_dir: Path = comum.RAIZ / "dados"


def carregar_contexto(raiz: Path = comum.RAIZ, hoje: dt.date | None = None) -> Contexto:
    return Contexto(
        limites=comum.limites(raiz),
        grade=comum.grade(raiz),
        termos=comum.carregar_yaml("config/termos_proibidos.yaml", raiz),
        hoje=hoje or comum.hoje_sp(),
        publicacoes=comum.ler_publicacoes(raiz),
        fila=[p for _, p in comum.posts_da_fila(raiz)],
        dados_dir=raiz / "dados",
    )


def _palavras(texto: str | None) -> int:
    return len((texto or "").split())


def _normaliza(texto: str) -> str:
    return " ".join(texto.lower().split())


def _campos_texto(post: dict) -> list[tuple[str, str]]:
    """Pares (local, texto) de tudo que aparece nas imagens e na legenda."""
    campos = []
    for s in post["slides"]:
        local = f"slide {s['n']}"
        campos.append((local, s["titulo"]))
        for chave in ("texto", "cta"):
            if s.get(chave):
                campos.append((local, s[chave]))
        campos.extend((local, item) for item in s.get("itens", []))
    campos.extend((f"story {i}", st["texto"]) for i, st in enumerate(post.get("stories", []), 1))
    campos.extend((f"narração do slide {i}", fala) for i, fala in enumerate(post.get("narracao", []), 1))
    if post.get("legenda"):
        campos.append(("legenda", post["legenda"]))
    return campos


def _buscar_termos(padroes: list[str], campos, regra: str) -> list[Erro]:
    if not padroes:
        return []
    rx = re.compile(r"\b(?:" + "|".join(padroes) + r")\b", re.I)
    erros = []
    for local, texto in campos:
        m = rx.search(texto)
        if m:
            erros.append(Erro(regra, local, f"termo não permitido: {m.group(0)!r}"))
    return erros


def _estrutura(post, ctx) -> list[Erro]:
    erros = []
    evento = post.get("prioridade") == "evento"
    esperado = f"{post['perfil']}-{post['data']}" + ("-evento" if evento else "")
    if post["id"] != esperado:
        erros.append(Erro("estrutura.id", "id", f"esperado {esperado}, recebido {post['id']}"))
    pilar = ctx.grade["pilares"][post["pilar"]]
    if post["formato"] != pilar["formato"]:
        erros.append(Erro("estrutura.formato", "formato", f"pilar {post['pilar']} usa {pilar['formato']}"))
    slides = post["slides"]
    maximo = min(pilar["max"], ctx.limites["conteudo"]["carrossel_max"])
    if not pilar["min"] <= len(slides) <= maximo:
        erros.append(Erro("estrutura.quantidade", "slides", f"{len(slides)} slides; faixa do pilar: {pilar['min']} a {maximo}"))
    if [s["n"] for s in slides] != list(range(1, len(slides) + 1)):
        erros.append(Erro("estrutura.numeracao", "slides", "a numeração deve ser 1, 2, 3..."))
    if len(post.get("stories", [])) > ctx.limites["conteudo"]["stories_max"]:
        erros.append(Erro("estrutura.stories", "stories", f"máximo de {ctx.limites['conteudo']['stories_max']} stories"))
    return erros


def _texto(post, ctx) -> list[Erro]:
    lim = ctx.limites["conteudo"]
    erros = []
    slides = post["slides"]
    if _palavras(slides[0]["titulo"]) > lim["gancho_palavras"]:
        erros.append(Erro("texto.gancho", "slide 1", f"gancho com mais de {lim['gancho_palavras']} palavras"))
    for s in slides:
        local = f"slide {s['n']}"
        if s is not slides[0] and _palavras(s["titulo"]) > lim["titulo_palavras"]:
            erros.append(Erro("texto.titulo", local, f"título com mais de {lim['titulo_palavras']} palavras"))
        total = _palavras(s.get("texto")) + sum(_palavras(i) for i in s.get("itens", []))
        if total > lim["slide_palavras"]:
            erros.append(Erro("texto.slide", local, f"{total} palavras; máximo {lim['slide_palavras']}"))
    if post["formato"] == "carrossel":
        ultimo = slides[-1]
        if ultimo["tipo"] != "cta" or not ultimo.get("cta"):
            erros.append(Erro("texto.cta", f"slide {ultimo['n']}", "o último slide precisa ser do tipo cta e ter CTA"))
    return erros


def _narracao(post, ctx) -> list[Erro]:
    falas = post.get("narracao")
    if not falas:
        return []
    erros = []
    if len(falas) != len(post["slides"]):
        erros.append(Erro("narracao.quantidade", "narracao", f"{len(falas)} falas; precisa de uma por slide ({len(post['slides'])})"))
    limite = ctx.limites["conteudo"]["narracao_palavras"]
    for i, fala in enumerate(falas, 1):
        if _palavras(fala) > limite:
            erros.append(Erro("narracao.tamanho", f"narração do slide {i}", f"{_palavras(fala)} palavras; máximo {limite}"))
    return erros


def _legenda(post, ctx) -> list[Erro]:
    lim = ctx.limites["conteudo"]
    legenda = post.get("legenda")
    if not legenda:
        return [Erro("legenda.ausente", "legenda", "campo obrigatório nesta etapa")]
    erros = []
    # A Meta recebe legenda e hashtags juntas, separadas por uma linha em branco.
    total = len(legenda) + 2 + len(" ".join(post.get("hashtags") or []))
    if total > lim["legenda_caracteres"]:
        erros.append(Erro("legenda.tamanho", "legenda", f"{total} caracteres com hashtags; máximo {lim['legenda_caracteres']}"))
    if len(legenda.split("\n")[0]) > lim["legenda_primeira_linha"]:
        erros.append(Erro("legenda.primeira_linha", "legenda", f"primeira linha acima de {lim['legenda_primeira_linha']} caracteres"))
    if not CTA_LEGENDA.search(legenda):
        erros.append(Erro("legenda.cta", "legenda", "sem CTA (salvar, comentar, compartilhar...)"))
    alvo = _normaliza(legenda)
    for outro in ctx.fila:
        if outro.get("id") != post["id"] and outro.get("legenda") and _normaliza(outro["legenda"]) == alvo:
            erros.append(Erro("legenda.duplicada", "legenda", f"igual à legenda de {outro['id']}"))
    return erros


def _hashtags(post, ctx) -> list[Erro]:
    lim = ctx.limites["conteudo"]
    tags = post.get("hashtags")
    if not tags:
        return [Erro("hashtags.quantidade", "hashtags", "campo obrigatório nesta etapa")]
    erros = []
    if not lim["hashtags_min"] <= len(tags) <= lim["hashtags_max"]:
        erros.append(Erro("hashtags.quantidade", "hashtags", f"{len(tags)} hashtags; faixa: {lim['hashtags_min']} a {lim['hashtags_max']}"))
    if comum.marca(post["perfil"])["hashtag_marca"] not in tags:
        erros.append(Erro("hashtags.marca", "hashtags", "falta a hashtag de marca"))
    proibidas = set(ctx.termos["hashtags_proibidas"])
    for t in tags:
        if not HASHTAG.match(t):
            erros.append(Erro("hashtags.formato", "hashtags", f"formato inválido: {t!r}"))
        elif t[1:] in proibidas:
            erros.append(Erro("hashtags.proibida", "hashtags", f"hashtag proibida: {t}"))
    anteriores = [p for p in ctx.fila if p.get("perfil") == post["perfil"] and p.get("data", "") < post["data"] and p.get("hashtags")]
    if anteriores and set(max(anteriores, key=lambda p: p["data"])["hashtags"]) == set(tags):
        erros.append(Erro("hashtags.repetidas", "hashtags", "bloco igual ao do post anterior"))
    return erros


def _acessibilidade(post) -> list[Erro]:
    imagens = len(post["slides"]) + len(post.get("stories", []))
    alts = post.get("alt_text") or []
    if len(alts) != imagens or not all(a.strip() for a in alts):
        return [Erro("acessibilidade.alt_text", "alt_text", f"{len(alts)} textos; {imagens} imagens")]
    return []


def _fin(post, ctx, campos, completo: bool) -> list[Erro]:
    erros = _buscar_termos(ctx.termos["fin_marcas"], campos, "fin.marca")
    erros += _buscar_termos(ctx.termos["fin_recomendacao"], campos, "fin.recomendacao")
    erros += _buscar_termos(ctx.termos["fin_urgencia"], campos, "fin.urgencia")
    for local, texto in campos:
        m = TICKER.search(texto)
        if m:
            erros.append(Erro("fin.ticker", local, f"ticker não permitido: {m.group(0)}"))
    if completo:
        aviso = comum.marca("FIN")["aviso_legal"]
        if any(INVESTIMENTO.search(t) for _, t in campos) and aviso not in (post.get("legenda") or ""):
            erros.append(Erro("fin.aviso_legal", "legenda", f"faltou o aviso: {aviso}"))
    tem_fonte = post.get("hipotetico") or post.get("dados_ref") or any(f.get("data") for f in post["fontes"])
    if not tem_fonte:
        for local, texto in campos:
            if PERCENTUAL.search(texto) or (TERMO_OFICIAL.search(texto) and NUMERO.search(texto)):
                erros.append(Erro("fin.fonte", local, "número oficial ou percentual exige fonte com data ou hipotetico=true"))
    return erros


def _mkt(post, campos) -> list[Erro]:
    erros = []
    for local, texto in campos:
        if METRICA_MKT.search(texto) and not post["fontes"]:
            erros.append(Erro("mkt.metrica", local, "métrica de alcance ou engajamento exige fonte"))
        if PLATAFORMA.search(texto) and MUDANCA.search(texto) and not ANO.search(texto):
            erros.append(Erro("mkt.ano", local, "plataforma e recurso citados exigem o ano"))
    return erros


def _livros(post, ctx, campos) -> list[Erro]:
    limite = ctx.limites["conteudo"]["citacao_palavras_limite"]
    erros = []
    if post["pilar"] == "livro" and not post.get("livro"):
        erros.append(Erro("livro.credito", "livro", "pilar livro exige título e autor"))
    citacoes = {_normaliza(m) for _, t in campos for m in CITACAO.findall(t)}
    if post.get("citacao"):
        citacoes.add(_normaliza(post["citacao"]["texto"]))
    if len(citacoes) > 1:
        erros.append(Erro("livro.citacoes", "post", f"{len(citacoes)} citações; máximo 1"))
    for c in citacoes:
        if _palavras(c) >= limite:
            erros.append(Erro("livro.citacao", "post", f"citação com {_palavras(c)} palavras; precisa ter menos de {limite}"))
    return erros


def _repeticao(post, ctx) -> list[Erro]:
    dias = ctx.limites["conteudo"]["repeticao_dias"]
    data = comum.data_iso(post["data"])
    candidatos = [p for p in ctx.publicacoes if p.get("status") in comum.STATUS_USADOS] + list(ctx.fila)
    for p in candidatos:
        if p.get("id") == post["id"] or p.get("perfil") != post["perfil"] or p.get("tema_slug") != post["tema_slug"]:
            continue
        if abs((data - comum.data_iso(p["data"])).days) <= dias:
            return [Erro("repeticao", "tema_slug", f"tema já usado em {p['data']} ({dias} dias)")]
    return []


def _atualidade(post, campos) -> list[Erro]:
    if post["pilar"] not in ("atualidade", "evento"):
        return []
    erros = []
    if not post.get("valido_ate") or post["valido_ate"] < post["data"]:
        erros.append(Erro("atualidade.valido_ate", "valido_ate", "obrigatório e não pode ser anterior à data do post"))
    fontes = post["fontes"]
    if len(fontes) < 2 and not any(f.get("primaria") for f in fontes):
        erros.append(Erro("atualidade.fontes", "fontes", "exige fonte primária ou duas fontes"))
    veiculos = [f["veiculo"] for f in fontes if f.get("veiculo")]
    texto_total = " ".join(t for _, t in campos).lower()
    if not any(v.lower() in texto_total for v in veiculos):
        erros.append(Erro("atualidade.veiculo", "fontes", "cite o nome do veículo nos slides ou na legenda"))
    slides = " ".join(t for local, t in campos if local.startswith("slide"))
    if not DATA_VISIVEL.search(slides) and not post.get("dados_ref"):
        erros.append(Erro("atualidade.data", "slides", "os slides precisam mostrar a data dos dados"))
    return erros


def _dados(post, ctx) -> list[Erro]:
    graficos = [s for s in post["slides"] if s["tipo"] == "grafico"]
    ref = post.get("dados_ref")
    if not graficos and not ref:
        return []
    if not ref:
        return [Erro("dados.ref", f"slide {graficos[0]['n']}", "slide de gráfico exige dados_ref")]
    erros = []
    if ref["fim"] > max(ctx.hoje.isoformat(), post["data"]):
        erros.append(Erro("dados.futuro", "dados_ref", f"período termina depois de hoje ({ref['fim']})"))
    arquivo = comum.ler_json(ctx.dados_dir / f"sgs_{ref['serie']}.json")
    if arquivo is None:
        return erros + [Erro("dados.arquivo", "dados_ref", f"dados/sgs_{ref['serie']}.json não encontrado")]
    for d in ref["valores_declarados"]:
        real = comum.valor_em(arquivo["pontos"], d["data"])
        if real is None or abs(real - d["valor"]) > 1e-6:
            erros.append(Erro("dados.divergencia", "dados_ref", f"{d['data']}: declarado {d['valor']}, série {real}"))
    return erros


def validar_post(post: dict, ctx: Contexto) -> list[Erro]:
    schema = comum.ler_json(comum.RAIZ / "schemas" / "post.schema.json")
    falhas = list(jsonschema.Draft202012Validator(schema).iter_errors(post))
    if falhas:
        return [Erro("schema", "/".join(map(str, f.path)) or "post", f.message) for f in falhas]

    completo = post["status"] not in STATUS_SEM_LEGENDA
    campos = _campos_texto(post)
    erros = _estrutura(post, ctx) + _texto(post, ctx) + _narracao(post, ctx)
    erros += _buscar_termos(ctx.termos["promessas"], campos, "promessa")
    erros += _livros(post, ctx, campos) + _repeticao(post, ctx) + _atualidade(post, campos) + _dados(post, ctx)
    erros += _fin(post, ctx, campos, completo) if post["perfil"] == "FIN" else _mkt(post, campos)
    if completo:
        erros += _legenda(post, ctx) + _hashtags(post, ctx) + _acessibilidade(post)
        erros += [Erro("texto.placeholder", local, "campo [preencher] não foi escrito") for local, t in campos if "[preencher]" in t]
    return erros


def exige_imagens(post: dict) -> bool:
    return post.get("status") in {"renderizado", "pronto"}


def _publicado(caminho: Path) -> bool:
    estado = comum.ler_json(caminho.parent / "estado.json", {})
    encerrados = {"publicado", "enviado", "adiado", "vencido", "atrasado"}
    # O publicador grava em "estado"; a entrega pelo Telegram, em "telegram.estado".
    return estado.get("estado") in encerrados or estado.get("telegram", {}).get("estado") in encerrados


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("arquivos", nargs="*", type=Path)
    ap.add_argument("--todos", action="store_true", help="valida toda a fila ainda não publicada")
    args = ap.parse_args(argv)
    ctx = carregar_contexto()
    arquivos = list(args.arquivos)
    if args.todos:
        arquivos += [p for p, _ in comum.posts_da_fila() if not _publicado(p)]
    falhou = False
    for caminho in arquivos:
        try:
            post = json.loads(Path(caminho).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"ERRO {caminho}: {e}")
            falhou = True
            continue
        erros = validar_post(post, ctx)
        if args.todos and not any(e.regra == "schema" for e in erros) and exige_imagens(post):
            import validar_imagem  # importado aqui porque ele usa a classe Erro deste módulo

            erros += validar_imagem.validar_pasta(Path(caminho).parent, post, ctx.limites)
        if erros:
            falhou = True
            print(f"REPROVADO {caminho}")
            for e in erros:
                print(f"  {e}")
        else:
            print(f"OK {caminho}")
    if not arquivos:
        print("Nenhum post para validar.")
    return 1 if falhou else 0


if __name__ == "__main__":
    sys.exit(main())
