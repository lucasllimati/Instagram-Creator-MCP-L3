import datetime as dt
import json
import shutil
import subprocess

import pytest
import responses

import coletar_insights as ci
import comum
import evento
import renovar_token as rt
import status as st
import validar

HOJE = dt.date(2026, 12, 9)
SELIC = {
    "serie": 432, "nome": "Selic", "fonte": "Banco Central, SGS série 432", "coletado_em": "2026-12-09", "degrau": True,
    "pontos": [{"data": "2024-01-01", "valor": 11.75}, {"data": "2026-09-17", "valor": 13.75}, {"data": "2026-12-10", "valor": 13.5}],
}


@pytest.fixture
def raiz(tmp_path):
    shutil.copytree(comum.RAIZ / "config", tmp_path / "config")
    comum.gravar_json(tmp_path / "dados" / "sgs_432.json", SELIC)
    return tmp_path


def test_esqueleto_copom_traz_numeros_da_serie(raiz):
    pasta = evento.preparar_copom(HOJE, raiz, HOJE)
    post = comum.ler_json(pasta / "post.json")
    assert post["id"] == "FIN-2026-12-10-evento"
    assert post["status"] == "roteiro"
    assert post["prioridade"] == "evento"
    assert "cortou" in post["slides"][0]["titulo"]
    assert "13,50%" in post["slides"][0]["titulo"]
    assert "13,75%" in post["slides"][1]["texto"]
    assert any(s["tipo"] == "grafico" for s in post["slides"])
    assert post["valido_ate"] == "2026-12-11"
    assert post["fontes"][0]["primaria"] is True
    assert comum.ler_json(pasta / "fatos.json")["direcao"] == "cortou"


def test_esqueleto_copom_passa_na_validacao_de_roteiro(raiz):
    pasta = evento.preparar_copom(HOJE, raiz, HOJE)
    ctx = validar.carregar_contexto(raiz, HOJE)
    ctx.fila = []
    assert [str(e) for e in validar.validar_post(comum.ler_json(pasta / "post.json"), ctx)] == []


def test_sem_mudanca_nao_afirma_manutencao_sem_confirmar(raiz):
    selic = dict(SELIC, pontos=[{"data": "2026-09-17", "valor": 13.75}, {"data": "2026-12-10", "valor": 13.75}])
    comum.gravar_json(raiz / "dados" / "sgs_432.json", selic)
    pasta = evento.preparar_copom(HOJE, raiz, HOJE)
    post = comum.ler_json(pasta / "post.json")
    assert comum.ler_json(pasta / "fatos.json")["confirmar_no_comunicado"] is True
    assert post["status"] == "revisar_humano"
    assert "manteve" not in post["slides"][0]["titulo"].lower()


def test_nao_sobrescreve_post_existente(raiz):
    pasta = evento.preparar_copom(HOJE, raiz, HOJE)
    (pasta / "post.json").write_text('{"editado": true}', encoding="utf-8")
    with pytest.raises(FileExistsError):
        evento.preparar_copom(HOJE, raiz, HOJE)


def test_noticia_cria_esqueleto_a_partir_do_radar(raiz):
    comum.gravar_json(raiz / "pesquisa" / "radar" / "2026-12-08.json", {"MKT": [{"id": "abc", "titulo": "Instagram muda", "fonte": "Meta Newsroom", "link": "https://x.test/1", "data": "2026-12-08"}], "FIN": []})
    pasta = evento.preparar_noticia("abc", raiz, HOJE, dt.date(2026, 12, 9))
    post = comum.ler_json(pasta / "post.json")
    assert post["id"] == "MKT-2026-12-09-evento"
    assert post["pilar"] == "atualidade"
    assert post["fontes"][0]["veiculo"] == "Meta Newsroom"
    assert post["valido_ate"] == "2026-12-11"


def test_noticia_inexistente_gera_erro(raiz):
    with pytest.raises(LookupError):
        evento.preparar_noticia("zzz", raiz, HOJE, HOJE)


@responses.activate
def test_insights_calcula_taxa_de_salvamento_e_compartilhamento(tmp_path):
    responses.get(
        "https://graph.instagram.com/v27.0/77/insights",
        json={"data": [{"name": "reach", "values": [{"value": 200}]}, {"name": "saved", "values": [{"value": 6}]}, {"name": "shares", "values": [{"value": 4}]}]},
    )
    r = ci.coletar_post("77", "TOK", {"base": "https://graph.instagram.com", "versao": "v27.0"})
    assert r["reach"] == 200
    assert ci.taxa(r) == 0.05


def test_taxa_sem_alcance_e_nula():
    assert ci.taxa({"saved": 1, "shares": 1}) is None


@responses.activate
def test_insights_erro_em_um_post_nao_derruba_a_coleta(tmp_path):
    (tmp_path / "config").mkdir()
    shutil.copy(comum.RAIZ / "config" / "limites.yaml", tmp_path / "config")
    comum.acrescentar_publicacao({"id": "FIN-2026-12-01", "data": "2026-12-01", "perfil": "FIN", "pilar": "conceito", "media_id": "77", "status": "publicado"}, tmp_path)
    comum.acrescentar_publicacao({"id": "FIN-2026-12-02", "data": "2026-12-02", "perfil": "FIN", "pilar": "erro", "media_id": "88", "status": "publicado"}, tmp_path)
    responses.get("https://graph.instagram.com/v27.0/77/insights", json={"data": [{"name": "reach", "values": [{"value": 100}]}]})
    responses.get("https://graph.instagram.com/v27.0/88/insights", json={"error": {"message": "x", "code": 100}}, status=400)
    caminho, falhas = ci.executar({"FIN": "TOK"}, tmp_path, HOJE)
    dados = comum.ler_json(caminho)
    assert len(dados["posts"]) == 2
    assert dados["posts"][1]["indisponivel"] is True
    assert falhas == 1


@responses.activate
def test_no_actions_o_novo_token_so_aparece_no_comando_de_mascara(monkeypatch, capsys):
    # O ::add-mask:: é o que faz o GitHub esconder o token nos logs seguintes.
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    responses.get("https://graph.instagram.com/refresh_access_token", json={"access_token": "NOVO", "expires_in": 5184000})
    rt.renovar("IG_TOKEN_FIN", "VELHO", "PAT", executar=lambda *a, **k: subprocess.CompletedProcess(a, 0))
    linhas = capsys.readouterr().out.splitlines()
    assert linhas[0] == "::add-mask::NOVO"
    assert not any("NOVO" in l or "VELHO" in l for l in linhas[1:])


@responses.activate
def test_renovacao_grava_novo_token_sem_exibir(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    responses.get("https://graph.instagram.com/refresh_access_token", json={"access_token": "NOVO", "expires_in": 5184000})
    gravados = []

    def fake(args, **kw):
        gravados.append((args, kw["input"]))
        return subprocess.CompletedProcess(args, 0)

    assert rt.renovar("IG_TOKEN_FIN", "VELHO", "PAT", executar=fake) is True
    assert gravados[0][1] == "NOVO"
    assert gravados[0][0][:3] == ["gh", "secret", "set"]
    saida = capsys.readouterr().out
    assert "NOVO" not in saida and "VELHO" not in saida


@responses.activate
def test_renovacao_recusada_nao_grava(capsys):
    responses.get("https://graph.instagram.com/refresh_access_token", json={"error": {"message": "token VELHO expirou"}}, status=400)
    chamou = []
    assert rt.renovar("IG_TOKEN_FIN", "VELHO", "PAT", executar=lambda *a, **k: chamou.append(1)) is False
    assert chamou == []
    assert "VELHO" not in capsys.readouterr().out


def post_status(post, status_="pronto"):
    return {**post, "status": status_}


def test_status_lista_a_fila(tmp_path, post, capsys):
    comum.gravar_json(tmp_path / "fila" / "2026-11-09" / "FIN" / "post.json", post)
    comum.gravar_json(tmp_path / "fila" / "2026-11-09" / "FIN" / "estado.json", {"estado": "falhou", "erro": "x"})
    st.mostrar(tmp_path)
    saida = capsys.readouterr().out
    assert "FIN-2026-11-09" in saida
    assert "falhou" in saida


def test_definir_status_recusa_valor_invalido(tmp_path, post):
    comum.gravar_json(tmp_path / "post.json", post)
    with pytest.raises(ValueError):
        st.definir(tmp_path, "aprovadissimo")


def test_definir_status_altera_o_campo(tmp_path, post):
    comum.gravar_json(tmp_path / "post.json", post)
    st.definir(tmp_path, "revisado")
    assert comum.ler_json(tmp_path / "post.json")["status"] == "revisado"


def test_registrar_execucao_acrescenta_linha(tmp_path):
    st.registrar(tmp_path, {"semana": "2026-46", "reprovacoes": 2})
    st.registrar(tmp_path, {"semana": "2026-46", "reprovacoes": 0})
    linhas = (tmp_path / "historico" / "execucoes.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 2
    assert json.loads(linhas[0])["reprovacoes"] == 2


def test_corpo_do_pr_tem_tabela_previas_e_alertas(tmp_path, post, post_mkt):
    a = comum.pasta_post(tmp_path, post["data"], "FIN")
    comum.gravar_json(a / "post.json", {**post, "enquete_manual": "Você já investe?"})
    comum.gravar_json(comum.pasta_post(tmp_path, post_mkt["data"], "MKT") / "post.json", {**post_mkt, "status": "revisar_humano"})
    corpo = st.corpo_pr(tmp_path, "2026-46", "semana/2026-46", "dono/repo")
    assert "| 2026-11-09 | FIN | conceito | carrossel |" in corpo
    assert "Seu dinheiro pode render" in corpo
    assert "fila/2026-11-09/FIN/previa.jpg?raw=1" in corpo
    assert "Precisa de olhar humano" in corpo
    assert "MKT-2026-11-09" in corpo
    assert "Você já investe?" in corpo
    assert "merge" in corpo.lower()
