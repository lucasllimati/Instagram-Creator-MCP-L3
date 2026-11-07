import datetime as dt

import comum
import pautar
import rampa

CFG = {"inicio": "2026-11-09", "semanas": {1: {"dias": [0, 2, 4], "stories": False}, 2: {"dias": [0, 1, 2, 3, 4], "stories": False}, 3: {"dias": [0, 1, 2, 3, 4, 5, 6], "stories": True}}}
GRADE = comum.grade()


def test_sem_inicio_definido_vale_semana_1():
    assert rampa.indice_semana(dt.date(2027, 5, 1), {**CFG, "inicio": None}) == 1


def test_antes_do_inicio_vale_semana_1():
    assert rampa.indice_semana(dt.date(2026, 11, 1), CFG) == 1


def test_semana_conta_a_partir_da_segunda_do_inicio():
    assert rampa.indice_semana(dt.date(2026, 11, 15), CFG) == 1
    assert rampa.indice_semana(dt.date(2026, 11, 16), CFG) == 2


def test_depois_da_ultima_semana_configurada_mantem_a_ultima():
    assert rampa.regra(dt.date(2027, 6, 1), CFG)["stories"] is True


def test_stories_so_a_partir_da_semana_3():
    assert rampa.stories_ativos(dt.date(2026, 11, 20), CFG) is False
    assert rampa.stories_ativos(dt.date(2026, 11, 23), CFG) is True


def test_semana_1_gera_3_posts_por_perfil_seg_qua_sex():
    linhas = pautar.gerar_pauta("2026-46", CFG, GRADE, [])
    fin = [l for l in linhas if l["perfil"] == "FIN"]
    assert [l["data"] for l in fin] == ["2026-11-09", "2026-11-11", "2026-11-13"]
    assert [l["pilar"] for l in fin] == ["conceito", "exemplo", "checklist"]
    assert len(linhas) == 6


def test_semana_3_gera_7_posts_com_formato_do_pilar():
    linhas = pautar.gerar_pauta("2026-48", CFG, GRADE, [])
    fin = [l for l in linhas if l["perfil"] == "FIN"]
    assert len(fin) == 7
    assert fin[1]["formato"] == "post_unico"


def test_dia_seguinte_ao_copom_reserva_vaga_em_fin_e_nao_em_mkt():
    eventos = [{"tipo": "copom", "data": dt.date(2026, 12, 9)}]
    linhas = pautar.gerar_pauta("2026-50", CFG, GRADE, eventos)
    quinta_fin = next(l for l in linhas if l["perfil"] == "FIN" and l["data"] == "2026-12-10")
    quinta_mkt = next(l for l in linhas if l["perfil"] == "MKT" and l["data"] == "2026-12-10")
    assert quinta_fin["status"] == "reservado_evento"
    assert quinta_fin["pilar"] == "evento"
    assert quinta_mkt["status"] == "pauta"


def test_evento_em_dia_fora_da_rampa_mantem_o_total_da_semana():
    eventos = [{"tipo": "copom", "data": dt.date(2026, 11, 11)}]  # dia seguinte: quinta
    linhas = pautar.gerar_pauta("2026-46", CFG, GRADE, eventos)
    fin = [l for l in linhas if l["perfil"] == "FIN"]
    assert len(fin) == 3
    assert "2026-11-12" in [l["data"] for l in fin]


def preencher(linhas):
    for i, l in enumerate(linhas):
        if l["status"] != "reservado_evento":
            l["tema"] = f"Tema {i}"
            l["tema_slug"] = f"tema-{i}"
    return linhas


def test_checar_aceita_pauta_preenchida():
    assert pautar.checar_calendario(preencher(pautar.gerar_pauta("2026-46", CFG, GRADE, [])), {}, GRADE) == []


def test_checar_reprova_tema_vazio():
    linhas = pautar.gerar_pauta("2026-46", CFG, GRADE, [])
    assert any("tema vazio" in e for e in pautar.checar_calendario(linhas, {}, GRADE))


def test_checar_reprova_tema_repetido_em_60_dias():
    linhas = preencher(pautar.gerar_pauta("2026-46", CFG, GRADE, []))
    temas = {"FIN": [{"tema_slug": "tema-0", "data": "2026-10-01"}]}
    assert any("repetido" in e for e in pautar.checar_calendario(linhas, temas, GRADE))


def test_checar_reprova_tema_duplicado_na_semana():
    linhas = preencher(pautar.gerar_pauta("2026-46", CFG, GRADE, []))
    linhas[1]["tema_slug"] = linhas[0]["tema_slug"]
    assert any("repetido" in e for e in pautar.checar_calendario(linhas, {}, GRADE))


def test_checar_reprova_pilar_fora_da_grade():
    linhas = preencher(pautar.gerar_pauta("2026-46", CFG, GRADE, []))
    linhas[0]["pilar"] = "livro"
    assert any("grade" in e for e in pautar.checar_calendario(linhas, {}, GRADE))


def test_atualidade_pode_substituir_ate_dois_temas_por_perfil():
    linhas = preencher(pautar.gerar_pauta("2026-48", CFG, GRADE, []))
    fin = [l for l in linhas if l["perfil"] == "FIN"]
    for l in fin[:2]:
        l.update(pilar="atualidade", formato="carrossel")
    assert pautar.checar_calendario(linhas, {}, GRADE) == []
    fin[2].update(pilar="atualidade", formato="carrossel")
    assert any("atualidades" in e for e in pautar.checar_calendario(linhas, {}, GRADE))


def test_temas_recentes_filtra_por_janela_e_publicado():
    pub = [
        {"perfil": "FIN", "tema_slug": "a", "data": "2026-10-01", "status": "publicado"},
        {"perfil": "FIN", "tema_slug": "b", "data": "2026-01-01", "status": "publicado"},
        {"perfil": "MKT", "tema_slug": "c", "data": "2026-10-01", "status": "falhou"},
    ]
    r = pautar.temas_recentes(pub, [{"perfil": "MKT", "tema_slug": "d", "data": "2026-11-20"}], dt.date(2026, 11, 7), 60)
    assert [t["tema_slug"] for t in r["FIN"]] == ["a"]
    assert [t["tema_slug"] for t in r["MKT"]] == ["d"]
