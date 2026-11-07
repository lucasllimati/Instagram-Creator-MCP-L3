import datetime as dt
import shutil

import pytest

import comum
import hoje

CFG = {"inicio": "2026-11-09", "semanas": {1: {"dias": [0, 2, 4], "stories": False}, 3: {"dias": [0, 1, 2, 3, 4, 5, 6], "stories": True}}}
SEG = dt.date(2026, 11, 9)


@pytest.fixture
def raiz(tmp_path):
    shutil.copytree(comum.RAIZ / "config", tmp_path / "config")
    return tmp_path


def plano(raiz, data=SEG, perfis=("FIN", "MKT"), eventos=()):
    return {p["perfil"]: p for p in hoje.plano(data, perfis, raiz, CFG, comum.grade(), list(eventos))}


def test_traz_pilar_formato_e_faixa_de_slides_do_dia(raiz):
    p = plano(raiz)["FIN"]
    assert (p["pilar"], p["formato"], p["slides_min"], p["slides_max"]) == ("conceito", "carrossel", 6, 8)
    assert p["acao"] == "criar"


def test_dia_fora_da_rampa_pede_confirmacao(raiz):
    p = plano(raiz, data=dt.date(2026, 11, 10))["FIN"]
    assert p["na_rampa"] is False
    assert p["acao"] == "confirmar_fora_da_rampa"


def test_post_que_ja_existe_nao_e_refeito(raiz, post):
    post.update(id="FIN-2026-11-09", data="2026-11-09")
    comum.gravar_json(raiz / "fila" / "2026-11-09" / "FIN" / "post.json", post)
    p = plano(raiz)["FIN"]
    assert p["acao"] == "ja_existe"
    assert p["status_atual"] == "pronto"


def test_post_ja_entregue_aparece_como_entregue(raiz, post):
    post.update(id="FIN-2026-11-09", data="2026-11-09")
    pasta = raiz / "fila" / "2026-11-09" / "FIN"
    comum.gravar_json(pasta / "post.json", post)
    comum.gravar_json(pasta / "estado.json", {"telegram": {"estado": "enviado"}})
    assert plano(raiz)["FIN"]["acao"] == "ja_entregue"


def test_dia_seguinte_ao_copom_indica_o_fluxo_de_evento(raiz):
    p = plano(raiz, eventos=[{"tipo": "copom", "data": dt.date(2026, 11, 8)}])
    assert p["FIN"]["acao"] == "usar_evento"
    assert p["FIN"]["reuniao_copom"] == "2026-11-08"
    assert p["MKT"]["acao"] == "criar"


def test_traz_temas_ja_usados_do_perfil(raiz):
    comum.acrescentar_publicacao({"id": "FIN-2026-11-07", "data": "2026-11-07", "perfil": "FIN", "tema_slug": "poupanca-x", "status": "entregue"}, raiz)
    assert plano(raiz)["FIN"]["temas_usados"] == ["poupanca-x"]
    assert plano(raiz)["MKT"]["temas_usados"] == []


def test_traz_as_melhores_noticias_do_radar_do_perfil(raiz):
    comum.gravar_json(
        raiz / "pesquisa" / "radar" / "2026-11-09.json",
        {"FIN": [{"id": f"i{i}", "titulo": f"Notícia {i}", "fonte": "X", "link": "https://x", "data": "2026-11-09", "pontos": 9 - i} for i in range(5)], "MKT": []},
    )
    noticias = plano(raiz)["FIN"]["radar"]
    assert [n["id"] for n in noticias] == ["i0", "i1", "i2"]
    assert set(noticias[0]) == {"id", "titulo", "fonte", "data"}


@pytest.mark.parametrize("args,perfis", [(["--data", "2026-11-11"], ["FIN", "MKT"]), (["MKT", "--data", "2026-11-11"], ["MKT"])])
def test_linha_de_comando_aceita_perfis_opcionais(capsys, args, perfis):
    import json

    assert hoje.main(args) == 0
    assert [p["perfil"] for p in json.loads(capsys.readouterr().out)] == perfis


def test_linha_de_comando_recusa_perfil_invalido():
    with pytest.raises(SystemExit):
        hoje.main(["XYZ"])


def test_semana_iso_para_o_pr(raiz):
    assert plano(raiz)["FIN"]["semana"] == "2026-46"
