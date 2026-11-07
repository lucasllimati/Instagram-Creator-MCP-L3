import copy
import datetime as dt
import json
import re
import shutil

import pytest
import responses
from PIL import Image

import comum
import publicar

BASE = "https://graph.instagram.com/v27.0"
HOJE = dt.date(2026, 11, 9)
TOKEN = "TOKEN-SECRETO-123"
SEM_STORIES = {"inicio": "2026-11-09", "semanas": {1: {"dias": [0, 2, 4], "stories": False}}}
COM_STORIES = {"inicio": "2026-11-09", "semanas": {1: {"dias": [0, 2, 4], "stories": True}}}


class FakeGit:
    def __init__(self, api_calls=None, falhar=False):
        self.commits = []
        self.falhar = falhar

    def commit_push(self, caminhos, mensagem):
        if self.falhar:
            raise publicar.ErroEstado("push recusado")
        self.commits.append((mensagem, len(responses.calls)))


class FakeMidia:
    def __init__(self):
        self.enviados = []

    def enviar(self, arquivos, prefixo):
        self.enviados.extend(arquivos)
        return [f"https://cdn.test/{prefixo}/{a.name}" for a in arquivos]


class FakeNotificador:
    def __init__(self):
        self.issues = []

    def abrir(self, titulo, corpo):
        self.issues.append((titulo, corpo))


def instalar(raiz, post, evento=False):
    pasta = comum.pasta_post(raiz, post["data"], post["perfil"], evento)
    pasta.mkdir(parents=True, exist_ok=True)
    comum.gravar_json(pasta / "post.json", post)
    for s in post["slides"]:
        Image.new("RGB", (1080, 1350)).save(pasta / f"slide_{s['n']:02d}.jpg", "JPEG")
    for i, _ in enumerate(post.get("stories", []), 1):
        Image.new("RGB", (1080, 1920)).save(pasta / f"story_{i:02d}.jpg", "JPEG")
    return pasta


@pytest.fixture
def raiz(tmp_path):
    shutil.copytree(comum.RAIZ / "config", tmp_path / "config")
    return tmp_path


@pytest.fixture
def post_hoje(post):
    return post


def novo(raiz, cfg=SEM_STORIES, hoje=HOJE, git=None, ativa=True, dry_run=False, perfil="FIN"):
    return publicar.Publicador(
        perfil=perfil,
        raiz=raiz,
        hoje=hoje,
        token=TOKEN,
        ig_id="111",
        midia=FakeMidia(),
        git=git or FakeGit(),
        notificador=FakeNotificador(),
        cfg_rampa=cfg,
        ativa=ativa,
        dry_run=dry_run,
        dormir=lambda s: None,
    )


class ApiFeliz:
    def __init__(self, status="FINISHED", usado=1):
        self.proximo = 1000
        self.status = status
        responses.add_callback(responses.POST, f"{BASE}/111/media", callback=self._criar)
        responses.add(responses.GET, f"{BASE}/111/content_publishing_limit", json={"data": [{"quota_usage": usado, "config": {"quota_total": 50, "quota_duration": 86400}}]})
        responses.add_callback(responses.POST, f"{BASE}/111/media_publish", callback=self._publicar)
        responses.add_callback(responses.GET, re.compile(rf"{re.escape(BASE)}/\d+(\?.*)?$"), callback=self._consultar)
        self.criados = []

    def _criar(self, req):
        self.proximo += 1
        self.criados.append(dict(item.split("=", 1) for item in req.body.split("&")))
        return (200, {}, json.dumps({"id": str(self.proximo)}))

    def _publicar(self, req):
        return (200, {}, json.dumps({"id": "9" + req.body.split("=")[1]}))

    def _consultar(self, req):
        ident = req.url.split("?")[0].rsplit("/", 1)[1]
        if "permalink" in req.url:
            return (200, {}, json.dumps({"id": ident, "permalink": f"https://instagram.com/p/{ident}"}))
        return (200, {}, json.dumps({"status_code": self.status}))


def chamadas(trecho, metodo="POST"):
    return [c for c in responses.calls if trecho in c.request.url and c.request.method == metodo]


def estado(raiz, post, evento=False):
    return comum.ler_json(comum.pasta_post(raiz, post["data"], post["perfil"], evento) / "estado.json", {})


@responses.activate
def test_publica_carrossel_e_registra_historico(raiz, post):
    api = ApiFeliz()
    instalar(raiz, post)
    pub = novo(raiz)
    assert pub.executar() == 0
    filhos = api.criados[:-1]
    pai = api.criados[-1]
    assert len(filhos) == 6
    assert all(f["is_carousel_item"] == "true" for f in filhos)
    assert "alt_text" in filhos[0]
    assert pai["media_type"] == "CAROUSEL"
    assert "caption" in pai
    assert len(chamadas("media_publish")) == 1
    e = estado(raiz, post)
    assert e["estado"] == "publicado"
    assert e["permalink"].startswith("https://instagram.com/p/")
    linhas = comum.ler_publicacoes(raiz)
    assert linhas[0]["id"] == post["id"]
    assert linhas[0]["status"] == "publicado"


@responses.activate
def test_legenda_enviada_inclui_hashtags(raiz, post):
    assert "#l3investir" in publicar.legenda_final(post)


@responses.activate
def test_post_unico_usa_um_container(raiz, post):
    api = ApiFeliz()
    post.update(pilar="erro", formato="post_unico")
    post["slides"] = [{"n": 1, "tipo": "frase", "titulo": "Poupar pouco já ajuda"}]
    post["alt_text"] = ["Frase", "Story"]
    post["hipotetico"] = False
    instalar(raiz, post)
    assert novo(raiz).executar() == 0
    assert len(api.criados) == 1
    assert "is_carousel_item" not in api.criados[0]
    assert "alt_text" in api.criados[0]


@responses.activate
def test_token_vai_no_cabecalho_e_nao_na_url(raiz, post):
    ApiFeliz()
    instalar(raiz, post)
    novo(raiz).executar()
    for c in responses.calls:
        assert TOKEN not in c.request.url
        assert c.request.headers["Authorization"] == f"Bearer {TOKEN}"


@responses.activate
def test_estado_e_salvo_antes_de_publicar(raiz, post):
    ApiFeliz()
    instalar(raiz, post)
    git = FakeGit()
    novo(raiz, git=git).executar()
    indice_publicar = next(i for i, c in enumerate(responses.calls) if "media_publish" in c.request.url)
    assert git.commits[0][1] <= indice_publicar


@responses.activate
def test_falha_ao_salvar_estado_impede_publicacao(raiz, post):
    ApiFeliz()
    instalar(raiz, post)
    pub = novo(raiz, git=FakeGit(falhar=True))
    assert pub.executar() == 1
    assert chamadas("media_publish") == []
    assert pub.notificador.issues


@responses.activate
def test_reexecucao_depois_de_publicado_nao_duplica(raiz, post):
    ApiFeliz()
    instalar(raiz, post)
    novo(raiz).executar()
    novo(raiz).executar()
    assert len(chamadas("media_publish")) == 1
    assert len(comum.ler_publicacoes(raiz)) == 1


def com_container(raiz, post):
    pasta = instalar(raiz, post)
    comum.gravar_json(pasta / "estado.json", {"estado": "container_criado", "container": "5555", "filhos": []})
    return pasta


@responses.activate
def test_queda_entre_container_e_publicacao_retoma_sem_recriar(raiz, post):
    api = ApiFeliz(status="FINISHED")
    com_container(raiz, post)
    assert novo(raiz).executar() == 0
    assert api.criados == []
    assert "creation_id=5555" in chamadas("media_publish")[0].request.body
    assert estado(raiz, post)["estado"] == "publicado"


@responses.activate
def test_container_ja_publicado_reconcilia_sem_publicar_de_novo(raiz, post):
    ApiFeliz(status="PUBLISHED")
    responses.add(responses.GET, f"{BASE}/111/media", json={"data": [{"id": "777", "permalink": "https://instagram.com/p/777", "caption": publicar.legenda_final(post)}]})
    com_container(raiz, post)
    assert novo(raiz).executar() == 0
    assert chamadas("media_publish") == []
    assert estado(raiz, post)["media_id"] == "777"


@responses.activate
def test_container_publicado_sem_midia_encontrada_nao_republica(raiz, post):
    ApiFeliz(status="PUBLISHED")
    responses.add(responses.GET, f"{BASE}/111/media", json={"data": []})
    com_container(raiz, post)
    pub = novo(raiz)
    pub.executar()
    assert chamadas("media_publish") == []
    assert estado(raiz, post)["estado"] == "publicado"
    assert pub.notificador.issues


@pytest.mark.parametrize("status", ["EXPIRED", "ERROR"])
@responses.activate
def test_container_com_falha_nao_recria_sozinho(raiz, post, status):
    api = ApiFeliz(status=status)
    com_container(raiz, post)
    pub = novo(raiz)
    assert pub.executar() == 1
    assert api.criados == []
    assert chamadas("media_publish") == []
    assert estado(raiz, post)["estado"] == "falhou"
    assert pub.notificador.issues


@responses.activate
def test_status_em_progresso_consulta_no_maximo_5_vezes(raiz, post):
    ApiFeliz(status="IN_PROGRESS")
    com_container(raiz, post)
    esperas = []
    pub = novo(raiz)
    pub.dormir = esperas.append
    assert pub.executar() == 1
    assert chamadas("media_publish") == []
    assert esperas == [60] * 5
    assert estado(raiz, post)["estado"] == "container_criado"


@responses.activate
def test_erro_5xx_tenta_novamente_e_conclui(raiz, post):
    ApiFeliz()
    responses.replace(responses.POST, f"{BASE}/111/media_publish", status=500)
    responses.add(responses.POST, f"{BASE}/111/media_publish", json={"id": "888"})
    instalar(raiz, post)
    assert novo(raiz).executar() == 0
    assert len(chamadas("media_publish")) == 2
    assert estado(raiz, post)["media_id"] == "888"


@responses.activate
def test_antes_de_repetir_publicacao_consulta_container(raiz, post):
    # Timeout pode significar que publicou. Consultar evita a duplicata.
    api = ApiFeliz()
    responses.replace(responses.POST, f"{BASE}/111/media_publish", status=503)
    responses.add(responses.GET, f"{BASE}/111/media", json={"data": [{"id": "777", "permalink": "https://x", "caption": publicar.legenda_final(post)}]})
    instalar(raiz, post)
    pub = novo(raiz)

    def apos_falha(_):
        api.status = "PUBLISHED"

    pub.dormir = apos_falha
    assert pub.executar() == 0
    assert len(chamadas("media_publish")) == 1
    assert estado(raiz, post)["media_id"] == "777"


def erro_meta(code, subcode=None, mensagem="falhou"):
    corpo = {"error": {"message": mensagem, "code": code}}
    if subcode:
        corpo["error"]["error_subcode"] = subcode
    return corpo


@pytest.mark.parametrize(
    "code,subcode",
    [(190, None), (10, None), (200, None), (4, 2207051), (25, 2207050), (368, None)],
)
@responses.activate
def test_token_invalido_ou_bloqueio_para_a_conta_sem_nova_tentativa(raiz, post, code, subcode):
    ApiFeliz()
    responses.replace(responses.POST, f"{BASE}/111/media", json=erro_meta(code, subcode), status=400)
    instalar(raiz, post)
    pub = novo(raiz)
    assert pub.executar() == 1
    assert len(chamadas("/111/media")) == 1
    assert chamadas("media_publish") == []
    assert pub.notificador.issues
    assert "FIN" in comum.ler_json(raiz / "historico" / "contas_pausadas.json")


@responses.activate
def test_conta_pausada_nao_faz_nenhuma_chamada(raiz, post):
    instalar(raiz, post)
    comum.gravar_json(raiz / "historico" / "contas_pausadas.json", {"FIN": {"motivo": "x", "data": "2026-11-08"}})
    assert novo(raiz).executar() == 0
    assert len(responses.calls) == 0


@responses.activate
def test_pausa_de_uma_conta_nao_afeta_a_outra(raiz, post_mkt):
    ApiFeliz()
    instalar(raiz, post_mkt)
    comum.gravar_json(raiz / "historico" / "contas_pausadas.json", {"FIN": {"motivo": "x", "data": "2026-11-08"}})
    assert novo(raiz, perfil="MKT").executar() == 0
    assert estado(raiz, post_mkt)["estado"] == "publicado"


@responses.activate
def test_cota_em_50_por_cento_para_sem_publicar(raiz, post):
    api = ApiFeliz(usado=25)
    instalar(raiz, post)
    pub = novo(raiz)
    assert pub.executar() == 1
    assert api.criados == []
    assert pub.midia.enviados == []
    assert pub.notificador.issues


@responses.activate
def test_limite_da_api_para_sem_nova_tentativa(raiz, post):
    ApiFeliz()
    responses.replace(responses.POST, f"{BASE}/111/media", json=erro_meta(9, 2207042), status=400)
    instalar(raiz, post)
    pub = novo(raiz)
    assert pub.executar() == 1
    assert len(chamadas("/111/media")) == 1
    assert not (raiz / "historico" / "contas_pausadas.json").exists()


@responses.activate
def test_pausa_global_nao_publica(raiz, post):
    instalar(raiz, post)
    assert novo(raiz, ativa=False).executar() == 0
    assert len(responses.calls) == 0


@responses.activate
def test_post_de_ontem_vira_atrasado_e_nao_e_publicado(raiz, post):
    api = ApiFeliz()
    instalar(raiz, post)
    pub = novo(raiz, hoje=HOJE + dt.timedelta(days=1))
    assert pub.executar() == 0
    assert api.criados == []
    assert estado(raiz, post)["estado"] == "atrasado"
    assert pub.notificador.issues


@responses.activate
def test_dia_perdido_nao_gera_dois_posts(raiz, post):
    ApiFeliz()
    instalar(raiz, post)
    hoje = copy.deepcopy(post)
    hoje.update(id="FIN-2026-11-10", data="2026-11-10", tema_slug="outro-tema", legenda=post["legenda"] + " Dois.")
    hoje["hashtags"][0] = "#poupanca"
    instalar(raiz, hoje)
    assert novo(raiz, hoje=dt.date(2026, 11, 10)).executar() == 0
    assert len(chamadas("media_publish")) == 1
    assert estado(raiz, post)["estado"] == "atrasado"
    assert estado(raiz, hoje)["estado"] == "publicado"


@responses.activate
def test_container_de_ontem_que_foi_publicado_e_reconciliado(raiz, post):
    ApiFeliz(status="PUBLISHED")
    responses.add(responses.GET, f"{BASE}/111/media", json={"data": [{"id": "777", "permalink": "https://x", "caption": publicar.legenda_final(post)}]})
    com_container(raiz, post)
    novo(raiz, hoje=HOJE + dt.timedelta(days=1)).executar()
    assert estado(raiz, post)["estado"] == "publicado"


@responses.activate
def test_disparo_manual_com_data_republica_post_atrasado(raiz, post):
    ApiFeliz()
    pasta = instalar(raiz, post)
    comum.gravar_json(pasta / "estado.json", {"estado": "atrasado"})
    assert novo(raiz, hoje=HOJE + dt.timedelta(days=1)).executar(data_forcada=HOJE) == 0
    assert estado(raiz, post)["estado"] == "publicado"


@responses.activate
def test_status_diferente_de_pronto_nao_publica(raiz, post):
    api = ApiFeliz()
    post["status"] = "revisar_humano"
    instalar(raiz, post)
    pub = novo(raiz)
    assert pub.executar() == 1
    assert api.criados == []
    assert pub.notificador.issues


@responses.activate
def test_post_invalido_nao_publica(raiz, post):
    api = ApiFeliz()
    post["slides"][1]["texto"] = "Fique rico com isto"
    instalar(raiz, post)
    pub = novo(raiz)
    assert pub.executar() == 1
    assert api.criados == []
    assert estado(raiz, post)["estado"] == "falhou"
    assert "promessa" in pub.notificador.issues[0][1]


@responses.activate
def test_imagem_invalida_nao_publica(raiz, post):
    api = ApiFeliz()
    pasta = instalar(raiz, post)
    (pasta / "slide_01.jpg").unlink()
    assert novo(raiz).executar() == 1
    assert api.criados == []


def evento(post):
    ev = copy.deepcopy(post)
    ev.update(
        id="FIN-2026-11-09-evento",
        pilar="evento",
        prioridade="evento",
        tema_slug="copom-teste",
        valido_ate="2026-11-10",
        legenda=post["legenda"] + "\n\nFonte: Banco Central.",
        hipotetico=False,
        fontes=[{"descricao": "Comunicado", "url": "https://bcb.gov.br", "data": "2026-11-08", "veiculo": "Banco Central", "primaria": True}],
    )
    ev["hashtags"][0] = "#selic"
    ev["slides"][1]["texto"] = "Banco Central em 08/11/2026."
    return ev


@responses.activate
def test_evento_tem_prioridade_e_adia_o_post_fixo(raiz, post):
    ApiFeliz()
    instalar(raiz, post)
    ev = evento(post)
    instalar(raiz, ev, evento=True)
    assert novo(raiz).executar() == 0
    assert len(chamadas("media_publish")) == 1
    assert estado(raiz, ev, evento=True)["estado"] == "publicado"
    assert estado(raiz, post)["estado"] == "adiado"


@responses.activate
def test_janela_da_tarde_nao_publica_post_fixo(raiz, post):
    api = ApiFeliz()
    instalar(raiz, post)
    assert novo(raiz).executar(janela="evento") == 0
    assert api.criados == []
    assert estado(raiz, post) == {}


@responses.activate
def test_janela_da_tarde_publica_evento_aprovado_depois_da_manha(raiz, post):
    ApiFeliz()
    ev = evento(post)
    instalar(raiz, ev, evento=True)
    assert novo(raiz).executar(janela="evento") == 0
    assert estado(raiz, ev, evento=True)["estado"] == "publicado"


@responses.activate
def test_evento_respeita_o_teto_diario(raiz, post):
    ApiFeliz()
    pasta = instalar(raiz, post)
    comum.gravar_json(pasta / "estado.json", {"estado": "publicado", "media_id": "1"})
    ev = evento(post)
    instalar(raiz, ev, evento=True)
    pub = novo(raiz)
    assert pub.executar(janela="evento") == 0
    assert chamadas("media_publish") == []
    assert estado(raiz, ev, evento=True)["estado"] == "atrasado"
    assert pub.notificador.issues


@responses.activate
def test_post_vencido_nao_publica(raiz, post):
    api = ApiFeliz()
    ev = evento(post)
    ev["valido_ate"] = ev["data"]
    pasta = instalar(raiz, ev, evento=True)
    comum.gravar_json(pasta / "estado.json", {"estado": "atrasado"})
    pub = novo(raiz, hoje=HOJE + dt.timedelta(days=1))
    assert pub.executar(data_forcada=HOJE) == 1
    assert api.criados == []
    assert estado(raiz, ev, evento=True)["estado"] == "vencido"


@responses.activate
def test_stories_desligados_na_rampa_nao_publicam(raiz, post):
    api = ApiFeliz()
    instalar(raiz, post)
    novo(raiz, cfg=SEM_STORIES).executar()
    assert all(c.get("media_type") != "STORIES" for c in api.criados)


@responses.activate
def test_stories_ligados_publicam_depois_do_post(raiz, post):
    api = ApiFeliz()
    instalar(raiz, post)
    assert novo(raiz, cfg=COM_STORIES).executar() == 0
    assert api.criados[-1]["media_type"] == "STORIES"
    assert "alt_text" not in api.criados[-1]
    assert len(chamadas("media_publish")) == 2
    assert estado(raiz, post)["stories"][0]["estado"] == "publicado"


@responses.activate
def test_falha_em_story_nao_desfaz_o_post(raiz, post):
    ApiFeliz()
    instalar(raiz, post)
    pub = novo(raiz, cfg=COM_STORIES)
    original = pub.graph.criar_container

    def cria(**campos):
        if campos.get("media_type") == "STORIES":
            raise publicar.ErroConteudo("mídia recusada")
        return original(**campos)

    pub.graph.criar_container = cria
    assert pub.executar() == 1
    assert estado(raiz, post)["estado"] == "publicado"
    assert estado(raiz, post)["stories"][0]["estado"] == "falhou"
    assert pub.notificador.issues


@responses.activate
def test_reexecucao_nao_duplica_stories(raiz, post):
    ApiFeliz()
    instalar(raiz, post)
    novo(raiz, cfg=COM_STORIES).executar()
    novo(raiz, cfg=COM_STORIES).executar()
    assert len(chamadas("media_publish")) == 2


@responses.activate
def test_dry_run_nao_altera_nada(raiz, post):
    ApiFeliz()
    pasta = instalar(raiz, post)
    pub = novo(raiz, dry_run=True)
    assert pub.executar() == 0
    assert [c for c in responses.calls if c.request.method == "POST"] == []
    assert pub.midia.enviados == []
    assert pub.git.commits == []
    assert not (pasta / "estado.json").exists()


@responses.activate
def test_dry_run_ignora_pausa_e_reprova_post_invalido(raiz, post):
    post["slides"][1]["texto"] = "Fique rico com isto"
    pasta = instalar(raiz, post)
    pub = novo(raiz, dry_run=True, ativa=False)
    assert pub.executar() == 1
    assert not (pasta / "estado.json").exists()


@responses.activate
def test_token_nunca_aparece_em_issue_nem_log(raiz, post, capsys):
    ApiFeliz()
    responses.replace(responses.POST, f"{BASE}/111/media", json=erro_meta(100, None, f"token {TOKEN} inválido"), status=400)
    instalar(raiz, post)
    pub = novo(raiz)
    pub.executar()
    assert pub.notificador.issues
    assert TOKEN not in json.dumps(pub.notificador.issues)
    assert TOKEN not in capsys.readouterr().out
    assert TOKEN not in (comum.pasta_post(raiz, post["data"], "FIN") / "estado.json").read_text(encoding="utf-8")


@responses.activate
def test_midia_envia_para_repo_publico_e_confere_url(tmp_path):
    arq = tmp_path / "slide_01.jpg"
    arq.write_bytes(b"abc")
    api = "https://api.github.com/repos/dono/l3-media/contents/2026/FIN/slide_01.jpg"
    responses.get(api, status=404)
    responses.put(api, json={"content": {}}, status=201)
    raw = "https://raw.githubusercontent.com/dono/l3-media/main/2026/FIN/slide_01.jpg"
    responses.head(raw, headers={"Content-Type": "image/jpeg"})
    m = publicar.Midia({"owner": "dono", "repo": "l3-media", "branch": "main"}, "MEDIATOKEN", dormir=lambda s: None)
    assert m.enviar([arq], "2026/FIN") == [raw]


@responses.activate
def test_midia_recusa_url_que_nao_devolve_jpeg(tmp_path):
    arq = tmp_path / "slide_01.jpg"
    arq.write_bytes(b"abc")
    api = "https://api.github.com/repos/dono/l3-media/contents/x/slide_01.jpg"
    responses.get(api, status=404)
    responses.put(api, json={}, status=201)
    responses.head("https://raw.githubusercontent.com/dono/l3-media/main/x/slide_01.jpg", status=404)
    m = publicar.Midia({"owner": "dono", "repo": "l3-media", "branch": "main"}, "T", dormir=lambda s: None)
    with pytest.raises(publicar.ErroConteudo):
        m.enviar([arq], "x")


@responses.activate
def test_midia_atualiza_arquivo_existente_com_sha(tmp_path):
    arq = tmp_path / "a.jpg"
    arq.write_bytes(b"abc")
    api = "https://api.github.com/repos/d/m/contents/x/a.jpg"
    responses.get(api, json={"sha": "ABC"})
    responses.put(api, json={})
    responses.head("https://raw.githubusercontent.com/d/m/main/x/a.jpg", headers={"Content-Type": "image/jpeg"})
    publicar.Midia({"owner": "d", "repo": "m", "branch": "main"}, "T", dormir=lambda s: None).enviar([arq], "x")
    assert json.loads(responses.calls[1].request.body)["sha"] == "ABC"


@responses.activate
def test_erro_inesperado_abre_issue_sem_vazar_token(raiz, post):
    ApiFeliz()
    instalar(raiz, post)
    pub = novo(raiz)

    def explode():
        raise RuntimeError(f"quebrou com {TOKEN}")

    pub.graph.cota = explode
    assert pub.executar() == 1
    assert pub.notificador.issues
    assert TOKEN not in json.dumps(pub.notificador.issues)
    assert chamadas("media_publish") == []


def test_publicacao_real_fora_do_actions_e_recusada(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert publicar.main(["FIN"]) == 2
    assert "GitHub Actions" in capsys.readouterr().out
