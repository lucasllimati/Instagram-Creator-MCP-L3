import json

import pytest
from PIL import Image

import comum
import renderizar
import validar_imagem


def _lum(hexa):
    canais = [int(hexa[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in canais]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contraste(a, b):
    l1, l2 = sorted((_lum(a), _lum(b)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


@pytest.mark.parametrize("perfil", comum.PERFIS)
@pytest.mark.parametrize(
    "texto,fundo,minimo",
    [
        ("texto_sobre_principal", "principal", 4.5),
        ("texto_sobre_fundo", "fundo", 4.5),
        ("corpo_sobre_fundo", "fundo", 4.5),
        ("destaque_sobre_fundo", "fundo", 4.5),
        ("destaque_sobre_principal", "principal", 3.0),
        ("texto_sobre_destaque", "destaque", 4.5),
    ],
)
def test_cores_da_marca_tem_contraste_suficiente(perfil, texto, fundo, minimo):
    c = comum.marca(perfil)["cores"]
    assert contraste(c[texto], c[fundo]) >= minimo


def test_html_traz_numeracao_e_arroba(post):
    html = renderizar.html_slide(post, post["slides"][1], comum.marca("FIN"), comum.RAIZ / "dados")
    assert "2/6" in html
    assert "@l3investir" in html


def test_post_unico_nao_mostra_numeracao(post):
    post["slides"] = [{"n": 1, "tipo": "frase", "titulo": "Consistência vence perfeição"}]
    post["formato"] = "post_unico"
    assert "1/1" not in renderizar.html_slide(post, post["slides"][0], comum.marca("FIN"), comum.RAIZ / "dados")


def test_html_escapa_texto(post):
    post["slides"][1]["texto"] = "<script>alert(1)</script>"
    assert "<script>alert" not in renderizar.html_slide(post, post["slides"][1], comum.marca("FIN"), comum.RAIZ / "dados")


def test_grafico_sem_dados_gera_erro(post, tmp_path):
    post["slides"][2] = {"n": 3, "tipo": "grafico", "titulo": "Histórico", "serie": 432}
    with pytest.raises(renderizar.ErroRender):
        renderizar.html_slide(post, post["slides"][2], comum.marca("FIN"), tmp_path)


@pytest.mark.render
@pytest.mark.parametrize("fixture", ["post", "post_mkt"])
def test_renderiza_imagens_validas(request, fixture, tmp_path):
    p = request.getfixturevalue(fixture)
    renderizar.renderizar_post(p, tmp_path, comum.RAIZ / "dados")
    assert validar_imagem.validar_pasta(tmp_path, p, comum.limites()) == []
    with Image.open(tmp_path / "slide_01.jpg") as im:
        assert im.size == (1080, 1350)
    with Image.open(tmp_path / "story_01.jpg") as im:
        assert im.size == (1080, 1920)


@pytest.mark.render
@pytest.mark.parametrize("perfil_fixture", ["post", "post_mkt"])
def test_slide_no_limite_de_palavras_cabe_na_area(request, perfil_fixture, tmp_path):
    # Se o validador aprova, o template precisa comportar: limite e layout andam juntos.
    p = request.getfixturevalue(perfil_fixture)
    palavra = "planejamento"
    p["slides"][0]["titulo"] = " ".join([palavra] * 10)
    p["slides"][0]["texto"] = " ".join([palavra] * 12)
    p["slides"][1] = {"n": 2, "tipo": "conteudo", "titulo": " ".join([palavra] * 8), "texto": " ".join([palavra] * 15), "itens": [" ".join([palavra] * 5)] * 4}
    p["slides"][-1]["titulo"] = " ".join([palavra] * 8)
    p["slides"][-1]["texto"] = " ".join([palavra] * 25)
    p["stories"][0]["texto"] = " ".join([palavra] * 14)
    renderizar.renderizar_post(p, tmp_path, comum.RAIZ / "dados")


@pytest.mark.render
def test_grafico_com_titulo_e_texto_cabe_na_area(post, tmp_path):
    post["slides"][2] = {"n": 3, "tipo": "grafico", "titulo": "Selic desde dois mil e vinte e quatro", "serie": 432, "texto": "Meta da taxa básica definida pelo Copom em cada reunião do comitê no período"}
    post["dados_ref"] = {"serie": 432, "inicio": "2024-01-01", "fim": "2026-11-07", "coletado_em": "2026-11-07", "valores_declarados": []}
    renderizar.renderizar_post(post, tmp_path, comum.RAIZ / "dados")


@pytest.mark.render
def test_texto_que_estoura_a_area_reprova(post, tmp_path):
    post["slides"][1]["texto"] = " ".join(["desproporcional"] * 200)
    with pytest.raises(renderizar.ErroRender) as e:
        renderizar.renderizar_post(post, tmp_path, comum.RAIZ / "dados")
    assert "slide 2" in str(e.value)


@pytest.mark.render
def test_slide_de_grafico_renderiza(post, tmp_path):
    dados = tmp_path / "dados"
    dados.mkdir()
    (dados / "sgs_432.json").write_text(
        json.dumps({"serie": 432, "nome": "Selic", "fonte": "Banco Central, SGS série 432", "coletado_em": "2026-11-07", "degrau": True,
                    "pontos": [{"data": "2024-01-01", "valor": 11.75}, {"data": "2025-06-19", "valor": 15.0}, {"data": "2026-11-07", "valor": 13.75}]}),
        encoding="utf-8",
    )
    post["slides"][2] = {"n": 3, "tipo": "grafico", "titulo": "Histórico", "serie": 432, "texto": "Meta da Selic"}
    post["dados_ref"] = {"serie": 432, "inicio": "2024-01-01", "fim": "2026-11-07", "coletado_em": "2026-11-07", "valores_declarados": []}
    saida = tmp_path / "saida"
    renderizar.renderizar_post(post, saida, dados)
    assert (saida / "slide_03.jpg").exists()
    html = renderizar.html_slide(post, post["slides"][2], comum.marca("FIN"), dados)
    assert "13,75%" in html
    assert "Banco Central, SGS série 432" in html
    assert "07/11/2026" in html
