import datetime as dt

import pytest
import responses

import comum
import dados_economicos as de
import grafico

HOJE = dt.date(2026, 11, 7)
BRUTO = [
    {"data": "16/09/2026", "valor": "14.00"},
    {"data": "17/09/2026", "valor": "13.75"},
    {"data": "18/09/2026", "valor": "13.75"},
    {"data": "07/11/2026", "valor": "13.75"},
    {"data": "08/11/2026", "valor": "13.75"},
    {"data": "09/12/2026", "valor": "13.75"},
]


def test_descarta_datas_futuras():
    pontos = de.limpar(BRUTO, HOJE, degrau=False)
    assert pontos[-1]["data"] == "2026-11-07"
    assert all(p["data"] <= "2026-11-07" for p in pontos)


def test_serie_em_degrau_guarda_mudancas_e_o_ultimo_dia():
    pontos = de.limpar(BRUTO, HOJE, degrau=True)
    assert pontos == [
        {"data": "2026-09-16", "valor": 14.0},
        {"data": "2026-09-17", "valor": 13.75},
        {"data": "2026-11-07", "valor": 13.75},
    ]


def test_valor_em_devolve_o_vigente():
    pontos = de.limpar(BRUTO, HOJE, degrau=True)
    assert comum.valor_em(pontos, "2026-10-01") == 13.75
    assert comum.valor_em(pontos, "2026-09-16") == 14.0
    assert comum.valor_em(pontos, "2020-01-01") is None


@responses.activate
def test_baixar_consulta_a_janela_correta():
    responses.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados", json=BRUTO)
    r = de.baixar({"codigo": 432, "nome": "Selic", "degrau": True, "anos": 5}, HOJE)
    assert r["serie"] == 432
    assert r["coletado_em"] == "2026-11-07"
    url = responses.calls[0].request.url
    assert "dataInicial=07%2F11%2F2021" in url or "dataInicial=07/11/2021" in url


@responses.activate
def test_api_fora_do_ar_gera_erro_claro():
    responses.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados", status=503)
    with pytest.raises(de.ErroDados):
        de.baixar({"codigo": 432, "nome": "Selic", "degrau": True, "anos": 5}, HOJE)


@responses.activate
def test_resposta_vazia_gera_erro():
    responses.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados", json=[])
    with pytest.raises(de.ErroDados):
        de.baixar({"codigo": 432, "nome": "Selic", "degrau": True, "anos": 5}, HOJE)


@responses.activate
def test_falha_nao_sobrescreve_arquivo_existente(tmp_path):
    (tmp_path / "sgs_432.json").write_text('{"antigo": true}', encoding="utf-8")
    responses.get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados", status=500)
    falhas = de.atualizar([{"codigo": 432, "nome": "Selic", "degrau": True, "anos": 5}], HOJE, tmp_path)
    assert falhas == [432]
    assert "antigo" in (tmp_path / "sgs_432.json").read_text(encoding="utf-8")


def test_fatos_copom_identifica_corte():
    pontos = de.limpar(BRUTO, HOJE, degrau=True)
    f = de.fatos_copom(pontos, dt.date(2026, 9, 16))
    assert f["direcao"] == "cortou"
    assert (f["anterior"], f["atual"]) == (14.0, 13.75)
    assert f["confirmar_no_comunicado"] is False


def test_fatos_copom_sem_mudanca_exige_confirmacao():
    pontos = de.limpar(BRUTO, HOJE, degrau=True)
    f = de.fatos_copom(pontos, dt.date(2026, 11, 4))
    assert f["direcao"] == "sem_mudanca_na_serie"
    assert f["confirmar_no_comunicado"] is True


def test_fatos_copom_sem_dado_do_dia_seguinte_gera_erro():
    pontos = de.limpar(BRUTO, HOJE, degrau=True)
    with pytest.raises(de.ErroDados):
        de.fatos_copom(pontos, dt.date(2026, 11, 7))


CORES = {"linha": "#3BB273", "texto": "#0F3D2E", "grade": "#D9D5CC", "destaque": "#E0B54A"}


def test_svg_mostra_o_ultimo_valor_em_formato_brasileiro():
    svg = grafico.svg_serie(de.limpar(BRUTO, HOJE, degrau=True), CORES, degrau=True)
    assert svg.startswith("<svg")
    assert "13,75%" in svg


def test_svg_em_degrau_gera_dois_vertices_por_mudanca():
    pontos = [{"data": "2026-01-01", "valor": 10.0}, {"data": "2026-02-01", "valor": 11.0}, {"data": "2026-03-01", "valor": 11.0}]
    assert grafico.vertices(pontos, degrau=True, x=lambda d: d, y=lambda v: v) == [
        ("2026-01-01", 10.0),
        ("2026-02-01", 10.0),
        ("2026-02-01", 11.0),
        ("2026-03-01", 11.0),
    ]


def test_eixo_usa_valores_redondos_em_formato_brasileiro():
    assert grafico.marcas_eixo(9.8, 15.7) == [8.0, 10.0, 12.0, 14.0, 16.0]
    pontos = [{"data": "2024-01-01", "valor": 10.5}, {"data": "2026-01-01", "valor": 15.0}]
    svg = grafico.svg_serie(pontos, CORES, degrau=True)
    assert ">10%<" in svg
    assert "15.7" not in svg


def test_eixo_com_decimais_usa_virgula():
    pontos = [{"data": "2026-01-01", "valor": 0.2}, {"data": "2026-06-01", "valor": 0.9}]
    assert ">0,5%<" in grafico.svg_serie(pontos, CORES, degrau=False)


def test_rotulo_final_nao_cobre_a_linha_em_queda():
    # A linha chega ao último ponto vindo de cima, então o rótulo fica abaixo do ponto.
    pontos = [{"data": "2024-01-01", "valor": 15.0}, {"data": "2026-01-01", "valor": 10.0}]
    assert grafico.lado_rotulo(pontos) == "abaixo"


def test_rotulo_final_nao_cobre_a_linha_em_alta():
    pontos = [{"data": "2024-01-01", "valor": 10.0}, {"data": "2026-01-01", "valor": 15.0}]
    assert grafico.lado_rotulo(pontos) == "acima"


def test_eixo_mostra_o_ano_inicial_quando_a_serie_comeca_em_janeiro():
    pontos = [{"data": "2025-01-01", "valor": 0.2}, {"data": "2026-09-01", "valor": 0.8}]
    svg = grafico.svg_serie(pontos, CORES, degrau=False)
    assert ">2025<" in svg and ">2026<" in svg


def test_eixo_nao_mostra_ano_anterior_ao_inicio_da_serie():
    pontos = [{"data": "2024-03-01", "valor": 0.2}, {"data": "2026-09-01", "valor": 0.8}]
    assert ">2024<" not in grafico.svg_serie(pontos, CORES, degrau=False)


def test_svg_com_um_ponto_nao_quebra():
    assert "<svg" in grafico.svg_serie([{"data": "2026-01-01", "valor": 10.0}], CORES, degrau=True)


def test_svg_sem_pontos_gera_erro():
    with pytest.raises(ValueError):
        grafico.svg_serie([], CORES, degrau=True)


def test_recorte_em_degrau_mantem_o_valor_vigente_no_inicio():
    pontos = [{"data": "2023-12-14", "valor": 11.75}, {"data": "2024-02-01", "valor": 11.25}]
    assert grafico.recorte(pontos, "2024-01-01", "2024-12-31", degrau=True) == [
        {"data": "2024-01-01", "valor": 11.75},
        {"data": "2024-02-01", "valor": 11.25},
    ]


def test_recorte_limita_o_periodo():
    pontos = de.limpar(BRUTO, HOJE, degrau=True)
    assert [p["data"] for p in grafico.recorte(pontos, "2026-09-17", "2026-10-01")] == ["2026-09-17"]
