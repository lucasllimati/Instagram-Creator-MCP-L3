import copy
import datetime as dt
from pathlib import Path

import pytest

import comum
import validar


def _post_base():
    return {
        "id": "FIN-2026-11-09",
        "perfil": "FIN",
        "data": "2026-11-09",
        "pilar": "conceito",
        "formato": "carrossel",
        "titulo": "Juros compostos em 1 minuto",
        "tema_slug": "juros-compostos",
        "status": "pronto",
        "hipotetico": True,
        "slides": [
            {"n": 1, "tipo": "capa", "titulo": "Seu dinheiro pode render sobre o rendimento", "texto": "Entenda em 6 slides"},
            {"n": 2, "tipo": "conteudo", "titulo": "Juros simples", "texto": "O rendimento incide só sobre o valor inicial."},
            {"n": 3, "tipo": "conteudo", "titulo": "Juros compostos", "texto": "O rendimento entra na conta e também passa a render."},
            {"n": 4, "tipo": "conteudo", "titulo": "Um exemplo", "texto": "Supondo 1% ao mês, R$ 1.000 viram R$ 1.127 em um ano."},
            {"n": 5, "tipo": "conteudo", "titulo": "O que pesa", "texto": "Tempo pesa mais que o valor do primeiro aporte."},
            {"n": 6, "tipo": "cta", "titulo": "Resumo", "texto": "Tempo faz os juros trabalharem.", "cta": "Salve para rever depois"},
        ],
        "stories": [{"tipo": "chamada", "texto": "Post novo sobre juros compostos"}],
        "legenda": (
            "Juros compostos: entenda por que o tempo importa tanto.\n\n"
            "Exemplo com taxa hipotética.\n\nSalve este post.\n\n"
            "Conteúdo educativo, não é recomendação de investimento."
        ),
        "hashtags": ["#educacaofinanceira", "#financaspessoais", "#juroscompostos", "#investimentos", "#l3investir"],
        "alt_text": [f"Slide {i}" for i in range(1, 8)],
        "fontes": [],
    }


def _post_mkt():
    p = _post_base()
    p.update(
        id="MKT-2026-11-09",
        perfil="MKT",
        titulo="Funil de vendas",
        tema_slug="funil-de-vendas",
        hipotetico=False,
        legenda="Funil de vendas para pequeno negócio.\n\nDá para fazer hoje.\n\nSalve este post.",
        hashtags=["#marketingdigital", "#pequenosnegocios", "#funildevendas", "#vendas", "#l3mktdigital"],
    )
    p["slides"][3] = {"n": 4, "tipo": "conteudo", "titulo": "Um exemplo", "texto": "Uma padaria atrai no bairro e vende no balcão."}
    return p


@pytest.fixture
def post():
    return copy.deepcopy(_post_base())


@pytest.fixture
def post_mkt():
    return copy.deepcopy(_post_mkt())


@pytest.fixture
def ctx(tmp_path):
    (tmp_path / "dados").mkdir()
    return validar.Contexto(
        limites=comum.limites(),
        grade=comum.grade(),
        termos=comum.carregar_yaml("config/termos_proibidos.yaml"),
        hoje=dt.date(2026, 11, 7),
        publicacoes=[],
        fila=[],
        dados_dir=Path(tmp_path / "dados"),
    )
