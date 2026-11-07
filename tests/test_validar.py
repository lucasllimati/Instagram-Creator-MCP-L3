import json

import pytest

import validar


def test_imagens_so_sao_checadas_em_posts_renderizados(post):
    assert validar.exige_imagens({**post, "status": "pronto"})
    assert validar.exige_imagens({**post, "status": "renderizado"})
    assert not validar.exige_imagens({**post, "status": "roteiro"})
    assert not validar.exige_imagens({**post, "status": "revisar_humano"})


def test_narracao_valida_passa(post, ctx):
    post["narracao"] = [f"Fala curta do slide {i}." for i in range(1, 7)]
    assert validar.validar_post(post, ctx) == []


def test_narracao_deve_ter_uma_fala_por_slide(post, ctx):
    post["narracao"] = ["Só uma fala."]
    assert "narracao.quantidade" in regras(post, ctx)


def test_fala_longa_demais_reprova(post, ctx):
    post["narracao"] = ["Fala."] * 6
    post["narracao"][2] = " ".join(["palavra"] * 31)
    assert "narracao.tamanho" in regras(post, ctx)


def test_narracao_passa_pelas_mesmas_regras_de_texto(post, ctx):
    post["narracao"] = ["Fala."] * 6
    post["narracao"][1] = "Com isso você vai ficar rico."
    assert "promessa" in regras(post, ctx)


def test_todos_ignora_post_ja_entregue_pelo_telegram(tmp_path):
    pasta = tmp_path / "fila" / "2026-11-07" / "FIN"
    pasta.mkdir(parents=True)
    (pasta / "estado.json").write_text('{"telegram": {"estado": "enviado"}}', encoding="utf-8")
    assert validar._publicado(pasta / "post.json")


def regras(post, ctx):
    return {e.regra for e in validar.validar_post(post, ctx)}


def test_post_fin_valido_passa(post, ctx):
    assert validar.validar_post(post, ctx) == []


def test_post_mkt_valido_passa(post_mkt, ctx):
    assert validar.validar_post(post_mkt, ctx) == []


def test_schema_reprova_campo_desconhecido(post, ctx):
    post["campo_errado"] = 1
    assert "schema" in regras(post, ctx)


def test_id_deve_bater_com_perfil_e_data(post, ctx):
    post["data"] = "2026-11-10"
    assert "estrutura.id" in regras(post, ctx)


def test_formato_deve_bater_com_pilar(post, ctx):
    post["formato"] = "post_unico"
    assert "estrutura.formato" in regras(post, ctx)


def test_carrossel_abaixo_da_faixa_do_pilar(post, ctx):
    del post["slides"][2:4]
    for i, s in enumerate(post["slides"], 1):
        s["n"] = i
    assert "estrutura.quantidade" in regras(post, ctx)


def test_numeracao_de_slides_sequencial(post, ctx):
    post["slides"][1]["n"] = 9
    assert "estrutura.numeracao" in regras(post, ctx)


def test_ultimo_slide_do_carrossel_exige_cta(post, ctx):
    del post["slides"][-1]["cta"]
    assert "texto.cta" in regras(post, ctx)


def test_gancho_com_11_palavras_reprova(post, ctx):
    post["slides"][0]["titulo"] = "um dois tres quatro cinco seis sete oito nove dez onze"
    assert "texto.gancho" in regras(post, ctx)


def test_gancho_com_10_palavras_passa(post, ctx):
    post["slides"][0]["titulo"] = "um dois tres quatro cinco seis sete oito nove dez"
    assert "texto.gancho" not in regras(post, ctx)


def test_titulo_com_9_palavras_reprova(post, ctx):
    post["slides"][1]["titulo"] = "um dois tres quatro cinco seis sete oito nove"
    assert "texto.titulo" in regras(post, ctx)


def test_slide_com_36_palavras_reprova(post, ctx):
    post["slides"][1]["texto"] = " ".join(["palavra"] * 36)
    assert "texto.slide" in regras(post, ctx)


def test_itens_contam_no_limite_do_slide(post, ctx):
    post["slides"][1]["texto"] = " ".join(["a"] * 30)
    post["slides"][1]["itens"] = [" ".join(["b"] * 6)]
    assert "texto.slide" in regras(post, ctx)


def test_legenda_longa_reprova(post, ctx):
    post["legenda"] = post["legenda"] + "x" * 2200
    assert "legenda.tamanho" in regras(post, ctx)


def test_legenda_com_hashtags_acima_do_limite_reprova(post, ctx):
    # A Meta recebe legenda e hashtags juntas.
    post["legenda"] = post["legenda"] + "\n" + "x" * (2200 - len(post["legenda"]) - 1)
    assert len(post["legenda"]) == 2200
    assert "legenda.tamanho" in regras(post, ctx)


def test_primeira_linha_longa_reprova(post, ctx):
    post["legenda"] = "x" * 126 + "\n" + post["legenda"]
    assert "legenda.primeira_linha" in regras(post, ctx)


def test_legenda_sem_cta_reprova(post_mkt, ctx):
    post_mkt["legenda"] = "Funil de vendas para pequeno negócio."
    assert "legenda.cta" in regras(post_mkt, ctx)


def test_legenda_igual_entre_contas_reprova(post, post_mkt, ctx):
    post_mkt["legenda"] = post["legenda"]
    ctx.fila.append(post)
    assert "legenda.duplicada" in regras(post_mkt, ctx)


def test_seis_hashtags_reprova_com_limite_padrao(post, ctx):
    post["hashtags"].append("#dinheiro")
    assert "hashtags.quantidade" in regras(post, ctx)


def test_hashtag_de_marca_obrigatoria(post, ctx):
    post["hashtags"][-1] = "#poupar"
    assert "hashtags.marca" in regras(post, ctx)


def test_hashtag_proibida_reprova(post, ctx):
    post["hashtags"][0] = "#instagood"
    assert "hashtags.proibida" in regras(post, ctx)


def test_hashtag_malformada_reprova(post, ctx):
    post["hashtags"][0] = "educacaofinanceira"
    assert "hashtags.formato" in regras(post, ctx)


def test_bloco_de_hashtags_igual_ao_post_anterior_reprova(post, ctx):
    anterior = json.loads(json.dumps(post))
    anterior.update(id="FIN-2026-11-08", data="2026-11-08", tema_slug="outro-tema", legenda="outra")
    ctx.fila.append(anterior)
    assert "hashtags.repetidas" in regras(post, ctx)


def test_bloco_igual_de_post_mais_antigo_passa(post, ctx):
    antigo = json.loads(json.dumps(post))
    antigo.update(id="FIN-2026-11-05", data="2026-11-05", tema_slug="tema-a", legenda="a")
    meio = json.loads(json.dumps(post))
    meio.update(id="FIN-2026-11-08", data="2026-11-08", tema_slug="tema-b", legenda="b")
    meio["hashtags"][0] = "#orcamento"
    ctx.fila.extend([antigo, meio])
    assert "hashtags.repetidas" not in regras(post, ctx)


def test_alt_text_deve_cobrir_slides_e_stories(post, ctx):
    post["alt_text"].pop()
    assert "acessibilidade.alt_text" in regras(post, ctx)


def test_stories_acima_do_teto_reprovam(post, ctx):
    post["stories"] = [{"tipo": "chamada", "texto": "x"}] * 5
    post["alt_text"] = ["a"] * 11
    assert "estrutura.stories" in regras(post, ctx)


def test_etapa_de_roteiro_nao_exige_legenda(post, ctx):
    post["status"] = "roteiro"
    del post["legenda"], post["hashtags"], post["alt_text"]
    assert validar.validar_post(post, ctx) == []


def test_campo_a_preencher_reprova_na_publicacao(post, ctx):
    post["slides"][1]["texto"] = "[preencher]"
    assert "texto.placeholder" in regras(post, ctx)


def test_campo_a_preencher_passa_no_roteiro(post, ctx):
    post["status"] = "roteiro"
    post["slides"][1]["texto"] = "[preencher]"
    assert "texto.placeholder" not in regras(post, ctx)


def test_status_pronto_exige_legenda(post, ctx):
    del post["legenda"]
    assert "legenda.ausente" in regras(post, ctx)


@pytest.mark.parametrize("frase", ["Fique rico em um ano", "Renda garantida todo mês", "10k seguidores em 7 dias"])
def test_promessa_de_resultado_reprova(post, ctx, frase):
    post["slides"][1]["texto"] = frase
    assert "promessa" in regras(post, ctx)


@pytest.mark.parametrize("texto", ["Compre PETR4 hoje", "VALE3 é uma ação", "Olhe o HGLG11"])
def test_fin_bloqueia_ticker(post, ctx, texto):
    post["slides"][1]["texto"] = texto
    assert "fin.ticker" in regras(post, ctx)


def test_fin_nao_confunde_sigla_com_ticker(post, ctx):
    post["slides"][1]["texto"] = "CDB, LCI e FGC são siglas."
    assert "fin.ticker" not in regras(post, ctx)


def test_fin_bloqueia_marca(post, ctx):
    post["slides"][1]["texto"] = "Abra conta no Nubank."
    assert "fin.marca" in regras(post, ctx)


def test_fin_bloqueia_recomendacao(post, ctx):
    post["slides"][1]["texto"] = "Este é o melhor investimento do ano."
    assert "fin.recomendacao" in regras(post, ctx)


def test_fin_bloqueia_urgencia(post, ctx):
    post["slides"][1]["texto"] = "Última chance para começar."
    assert "fin.urgencia" in regras(post, ctx)


def test_mkt_nao_aplica_regras_de_fin(post_mkt, ctx):
    post_mkt["slides"][1]["texto"] = "Nubank é um exemplo de marca forte."
    assert "fin.marca" not in regras(post_mkt, ctx)


def test_fin_investimento_exige_aviso_legal(post, ctx):
    post["legenda"] = "Investir começa pelo básico.\n\nSalve este post."
    assert "fin.aviso_legal" in regras(post, ctx)


def test_fin_percentual_exige_fonte_ou_hipotetico(post, ctx):
    post["hipotetico"] = False
    assert "fin.fonte" in regras(post, ctx)


def test_fin_termo_oficial_com_numero_exige_fonte(post, ctx):
    post["hipotetico"] = False
    post["slides"][3]["texto"] = "A Selic está em 13,75 ao ano."
    assert "fin.fonte" in regras(post, ctx)


def test_fin_termo_sem_numero_nao_exige_fonte(post, ctx):
    post["hipotetico"] = False
    post["slides"][3]["texto"] = "A Selic é a taxa básica de juros."
    assert "fin.fonte" not in regras(post, ctx)


def test_fin_fonte_com_data_libera_percentual(post, ctx):
    post["hipotetico"] = False
    post["fontes"] = [{"descricao": "BCB", "url": "https://bcb.gov.br", "data": "2026-11-01"}]
    assert "fin.fonte" not in regras(post, ctx)


def test_mkt_metrica_exige_fonte(post_mkt, ctx):
    post_mkt["slides"][1]["texto"] = "Carrossel tem 30% mais alcance."
    assert "mkt.metrica" in regras(post_mkt, ctx)


def test_mkt_plataforma_com_algoritmo_exige_ano(post_mkt, ctx):
    post_mkt["slides"][1]["texto"] = "O algoritmo do Instagram prioriza salvamentos."
    assert "mkt.ano" in regras(post_mkt, ctx)


def test_mkt_plataforma_com_ano_passa(post_mkt, ctx):
    post_mkt["slides"][1]["texto"] = "Em 2026, o algoritmo do Instagram muda sempre."
    assert "mkt.ano" not in regras(post_mkt, ctx)


def test_pilar_livro_exige_credito(post, ctx):
    post["pilar"] = "livro"
    assert "livro.credito" in regras(post, ctx)


def test_citacao_com_15_palavras_reprova(post, ctx):
    post["citacao"] = {"texto": " ".join(["a"] * 15), "autor": "X", "obra": "Y"}
    assert "livro.citacao" in regras(post, ctx)


def test_citacao_com_14_palavras_passa(post, ctx):
    post["citacao"] = {"texto": " ".join(["a"] * 14), "autor": "X", "obra": "Y"}
    assert "livro.citacao" not in regras(post, ctx)


def test_duas_citacoes_no_texto_reprovam(post, ctx):
    post["slides"][1]["texto"] = "“primeira frase” e “segunda frase”"
    assert "livro.citacoes" in regras(post, ctx)


def test_citacao_nao_declarada_longa_reprova(post, ctx):
    post["slides"][1]["texto"] = "“" + " ".join(["a"] * 16) + "”"
    assert "livro.citacao" in regras(post, ctx)


def test_tema_publicado_ha_59_dias_reprova(post, ctx):
    ctx.publicacoes.append({"perfil": "FIN", "tema_slug": "juros-compostos", "data": "2026-09-11", "status": "publicado", "id": "x"})
    assert "repeticao" in regras(post, ctx)


def test_tema_publicado_ha_61_dias_passa(post, ctx):
    ctx.publicacoes.append({"perfil": "FIN", "tema_slug": "juros-compostos", "data": "2026-09-09", "status": "publicado", "id": "x"})
    assert "repeticao" not in regras(post, ctx)


def test_mesmo_tema_em_outro_perfil_passa(post, ctx):
    ctx.publicacoes.append({"perfil": "MKT", "tema_slug": "juros-compostos", "data": "2026-11-01", "status": "publicado", "id": "x"})
    assert "repeticao" not in regras(post, ctx)


def test_tema_repetido_na_fila_reprova(post, ctx):
    outro = json.loads(json.dumps(post))
    outro.update(id="FIN-2026-11-11", data="2026-11-11")
    ctx.fila.append(outro)
    assert "repeticao" in regras(post, ctx)


def post_atualidade(post):
    post.update(
        pilar="atualidade",
        valido_ate="2026-11-12",
        hipotetico=False,
        fontes=[{"descricao": "Ata", "url": "https://bcb.gov.br", "data": "2026-11-05", "veiculo": "Banco Central", "primaria": True}],
    )
    post["slides"][1]["texto"] = "Dados do Banco Central em 05/11/2026."
    post["legenda"] += "\n\nFonte: Banco Central."
    return post


def test_atualidade_valida_passa(post, ctx):
    assert validar.validar_post(post_atualidade(post), ctx) == []


def test_atualidade_exige_valido_ate(post, ctx):
    p = post_atualidade(post)
    del p["valido_ate"]
    assert "atualidade.valido_ate" in regras(p, ctx)


def test_valido_ate_anterior_a_data_reprova(post, ctx):
    p = post_atualidade(post)
    p["valido_ate"] = "2026-11-01"
    assert "atualidade.valido_ate" in regras(p, ctx)


def test_atualidade_com_uma_fonte_secundaria_reprova(post, ctx):
    p = post_atualidade(post)
    del p["fontes"][0]["primaria"]
    assert "atualidade.fontes" in regras(p, ctx)


def test_atualidade_com_duas_fontes_passa(post, ctx):
    p = post_atualidade(post)
    del p["fontes"][0]["primaria"]
    p["fontes"].append({"descricao": "B", "url": "https://b.com", "data": "2026-11-05", "veiculo": "B"})
    assert "atualidade.fontes" not in regras(p, ctx)


def test_atualidade_exige_veiculo_citado(post, ctx):
    p = post_atualidade(post)
    p["legenda"] = p["legenda"].replace("Fonte: Banco Central.", "")
    p["slides"][1]["texto"] = "Dados de 05/11/2026."
    assert "atualidade.veiculo" in regras(p, ctx)


def test_atualidade_exige_data_nos_slides(post, ctx):
    p = post_atualidade(post)
    p["slides"][1]["texto"] = "Dados do Banco Central."
    assert "atualidade.data" in regras(p, ctx)


def com_dados(post, ctx, valor=13.75):
    (ctx.dados_dir / "sgs_432.json").write_text(
        json.dumps(
            {
                "serie": 432,
                "nome": "Selic",
                "coletado_em": "2026-11-07",
                "pontos": [{"data": "2026-08-06", "valor": 14.0}, {"data": "2026-09-17", "valor": 13.75}, {"data": "2026-11-07", "valor": 13.75}],
            }
        ),
        encoding="utf-8",
    )
    post["slides"][2] = {"n": 3, "tipo": "grafico", "titulo": "Histórico", "serie": 432}
    post["dados_ref"] = {
        "serie": 432,
        "inicio": "2026-08-06",
        "fim": "2026-11-07",
        "coletado_em": "2026-11-07",
        "valores_declarados": [{"data": "2026-10-01", "valor": valor}],
    }
    return post


def test_grafico_com_dados_corretos_passa(post, ctx):
    assert validar.validar_post(com_dados(post, ctx), ctx) == []


def test_valor_divergente_dos_dados_reprova(post, ctx):
    assert "dados.divergencia" in regras(com_dados(post, ctx, valor=12.0), ctx)


def test_grafico_sem_dados_ref_reprova(post, ctx):
    com_dados(post, ctx)
    del post["dados_ref"]
    assert "dados.ref" in regras(post, ctx)


def test_arquivo_de_serie_ausente_reprova(post, ctx):
    com_dados(post, ctx)
    (ctx.dados_dir / "sgs_432.json").unlink()
    assert "dados.arquivo" in regras(post, ctx)


def test_dados_ref_com_fim_no_futuro_reprova(post, ctx):
    com_dados(post, ctx)
    post["dados_ref"]["fim"] = "2026-12-09"
    assert "dados.futuro" in regras(post, ctx)


def test_dados_ref_ate_a_data_do_post_passa(post, ctx):
    # Na noite do Copom, o dado vigente no dia seguinte já é o do post de amanhã.
    com_dados(post, ctx)
    post["dados_ref"]["fim"] = post["data"]
    assert "dados.futuro" not in regras(post, ctx)


def test_dados_ref_libera_fonte_fin(post, ctx):
    com_dados(post, ctx)
    post["hipotetico"] = False
    assert "fin.fonte" not in regras(post, ctx)


def test_evento_deve_ter_id_com_sufixo(post, ctx):
    post_atualidade(post)
    post["prioridade"] = "evento"
    assert "estrutura.id" in regras(post, ctx)
