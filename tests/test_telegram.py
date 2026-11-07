import copy
import datetime as dt
import json
import shutil

import pytest
import responses
from PIL import Image

import comum
import entregar_telegram as et
import publicar
import validar

TOKEN = "123456:SEGREDO-DO-BOT"
API = f"https://api.telegram.org/bot{TOKEN}"
HOJE = dt.date(2026, 11, 9)
SEM_STORIES = {"inicio": "2026-11-09", "semanas": {1: {"dias": [0, 2, 4], "stories": False}}}
COM_STORIES = {"inicio": "2026-11-09", "semanas": {1: {"dias": [0, 2, 4], "stories": True}}}


class FakeGit:
    def __init__(self):
        self.commits = []

    def commit_push(self, caminhos, mensagem):
        self.commits.append(mensagem)


class FakeNotificador:
    def __init__(self):
        self.issues = []

    def abrir(self, titulo, corpo):
        self.issues.append((titulo, corpo))


def fake_video(pasta, cor, saida, segundos=3.5):
    saida.write_bytes(b"mp4")
    return saida


@pytest.fixture
def raiz(tmp_path):
    shutil.copytree(comum.RAIZ / "config", tmp_path / "config")
    return tmp_path


def instalar(raiz, post, evento=False):
    pasta = comum.pasta_post(raiz, post["data"], post["perfil"], evento)
    pasta.mkdir(parents=True, exist_ok=True)
    comum.gravar_json(pasta / "post.json", post)
    for s in post["slides"]:
        Image.new("RGB", (1080, 1350)).save(pasta / f"slide_{s['n']:02d}.jpg", "JPEG")
    for i, _ in enumerate(post.get("stories", []), 1):
        Image.new("RGB", (1080, 1920)).save(pasta / f"story_{i:02d}.jpg", "JPEG")
    return pasta


def novo(raiz, cfg=SEM_STORIES, hoje=HOJE, ativa=True, dry_run=False, perfil="FIN"):
    return et.Entregador(
        perfil=perfil,
        raiz=raiz,
        hoje=hoje,
        telegram=et.Telegram(TOKEN, "-100999", dormir=lambda s: None),
        git=FakeGit(),
        notificador=FakeNotificador(),
        cfg_rampa=cfg,
        ativa=ativa,
        dry_run=dry_run,
        gerar_video=fake_video,
    )


def ok_telegram():
    for metodo in ("sendMessage", "sendMediaGroup", "sendDocument", "sendVideo"):
        responses.add(responses.POST, f"{API}/{metodo}", json={"ok": True, "result": {}})


def metodos():
    return [c.request.url.rsplit("/", 1)[1] for c in responses.calls]


def textos():
    return [json.loads(c.request.body)["text"] for c in responses.calls if c.request.url.endswith("sendMessage")]


def estado_tg(raiz, post, evento=False):
    return comum.ler_json(comum.pasta_post(raiz, post["data"], post["perfil"], evento) / "estado.json", {}).get("telegram", {})


@responses.activate
def test_envia_cabecalho_album_video_legenda_e_apoio_em_ordem(raiz, post):
    ok_telegram()
    instalar(raiz, post)
    assert novo(raiz).executar() == 0
    assert metodos() == ["sendMessage", "sendMediaGroup", "sendVideo", "sendMessage", "sendMessage"]
    assert "@l3investir" in textos()[0]
    assert textos()[1] == publicar.legenda_final(post)  # mensagem só com a legenda, pronta para copiar
    assert "Slide 1" in textos()[2]  # alt text na mensagem de apoio
    assert estado_tg(raiz, post)["estado"] == "enviado"


@responses.activate
def test_roteiro_de_narracao_vem_depois_do_video_com_tempos(raiz, post):
    ok_telegram()
    post["narracao"] = ["Primeira fala da capa."] + [f"Fala do slide {i}." for i in range(2, 7)]
    instalar(raiz, post)
    assert novo(raiz).executar() == 0
    assert metodos() == ["sendMessage", "sendMediaGroup", "sendVideo", "sendMessage", "sendMessage", "sendMessage"]
    roteiro = textos()[1]
    assert "0:00" in roteiro
    assert "Slide 1: Primeira fala da capa." in roteiro
    assert textos()[2] == publicar.legenda_final(post)


@responses.activate
def test_album_vai_como_documento_para_nao_comprimir(raiz, post):
    ok_telegram()
    instalar(raiz, post)
    novo(raiz).executar()
    album = next(c for c in responses.calls if c.request.url.endswith("sendMediaGroup"))
    corpo = album.request.body.decode("latin-1") if isinstance(album.request.body, bytes) else album.request.body
    assert '"type": "document"' in corpo
    assert corpo.count("attach://") == 6


@responses.activate
def test_album_com_mais_de_10_imagens_e_dividido(raiz, post):
    ok_telegram()
    arquivos = []
    for i in range(12):
        caminho = raiz / f"slide_{i:02d}.jpg"
        Image.new("RGB", (10, 10)).save(caminho, "JPEG")
        arquivos.append(caminho)
    et.Telegram(TOKEN, "-100999", dormir=lambda s: None).enviar_documentos(arquivos)
    assert metodos() == ["sendMediaGroup", "sendMediaGroup"]


@responses.activate
def test_imagem_unica_vai_como_documento(raiz, post):
    ok_telegram()
    caminho = raiz / "slide_01.jpg"
    Image.new("RGB", (10, 10)).save(caminho, "JPEG")
    et.Telegram(TOKEN, "-100999", dormir=lambda s: None).enviar_documentos([caminho])
    assert metodos() == ["sendDocument"]


@responses.activate
def test_texto_longo_e_dividido(raiz):
    ok_telegram()
    et.Telegram(TOKEN, "-100999", dormir=lambda s: None).enviar_texto("a" * 5000)
    assert metodos() == ["sendMessage", "sendMessage"]


@responses.activate
def test_post_unico_nao_tem_video(raiz, post):
    ok_telegram()
    post.update(pilar="erro", formato="post_unico", hipotetico=False)
    post["slides"] = [{"n": 1, "tipo": "frase", "titulo": "Poupar pouco já ajuda"}]
    post["alt_text"] = ["Frase", "Story"]
    instalar(raiz, post)
    assert novo(raiz).executar() == 0
    assert "sendVideo" not in metodos()
    assert "sendDocument" in metodos()


@responses.activate
def test_stories_seguem_a_rampa(raiz, post):
    ok_telegram()
    instalar(raiz, post)
    novo(raiz, cfg=SEM_STORIES).executar()
    sem = len(responses.calls)
    responses.calls.reset()
    outro = copy.deepcopy(post)
    outro.update(perfil="MKT", id="MKT-2026-11-09", legenda=post["legenda"] + " MKT", hashtags=["#a1", "#a2", "#a3", "#a4", "#l3mktdigital"])
    instalar(raiz, outro)
    novo(raiz, cfg=COM_STORIES, perfil="MKT").executar()
    assert len(responses.calls) == sem + 2  # imagens e textos dos stories
    assert any("Story 1" in t for t in textos())


@responses.activate
def test_reexecucao_nao_reenvia(raiz, post):
    ok_telegram()
    instalar(raiz, post)
    novo(raiz).executar()
    total = len(responses.calls)
    novo(raiz).executar()
    assert len(responses.calls) == total


@responses.activate
def test_falha_no_meio_retoma_so_o_que_faltou(raiz, post):
    ok_telegram()
    responses.replace(responses.POST, f"{API}/sendVideo", json={"ok": False, "description": "Bad Request"}, status=400)
    instalar(raiz, post)
    ent = novo(raiz)
    assert ent.executar() == 1
    assert ent.notificador.issues
    assert estado_tg(raiz, post)["partes"] == ["cabecalho", "imagens"]
    responses.calls.reset()
    responses.replace(responses.POST, f"{API}/sendVideo", json={"ok": True, "result": {}})
    assert novo(raiz).executar() == 0
    assert metodos() == ["sendVideo", "sendMessage", "sendMessage"]


@responses.activate
def test_limite_do_telegram_espera_o_tempo_pedido(raiz):
    responses.add(responses.POST, f"{API}/sendMessage", json={"ok": False, "parameters": {"retry_after": 7}}, status=429)
    responses.add(responses.POST, f"{API}/sendMessage", json={"ok": True, "result": {}})
    esperas = []
    et.Telegram(TOKEN, "-100999", dormir=esperas.append).enviar_texto("oi")
    assert esperas == [7]


@responses.activate
def test_token_invalido_nao_tenta_de_novo_e_nao_vaza(raiz, post, capsys):
    responses.add(responses.POST, f"{API}/sendMessage", json={"ok": False, "description": "Unauthorized"}, status=401)
    instalar(raiz, post)
    ent = novo(raiz)
    assert ent.executar() == 1
    assert len(responses.calls) == 1
    assert TOKEN not in json.dumps(ent.notificador.issues)
    assert TOKEN not in capsys.readouterr().out


@responses.activate
def test_erro_de_rede_nao_vaza_token_da_url(raiz, post):
    import requests

    responses.add(responses.POST, f"{API}/sendMessage", body=requests.ConnectionError(f"falhou em {API}/sendMessage"))
    instalar(raiz, post)
    ent = novo(raiz)
    assert ent.executar() == 1
    assert TOKEN not in json.dumps(ent.notificador.issues)


@responses.activate
def test_entrega_desativada_nao_envia(raiz, post):
    instalar(raiz, post)
    assert novo(raiz, ativa=False).executar() == 0
    assert len(responses.calls) == 0


@responses.activate
def test_post_invalido_nao_envia(raiz, post):
    post["slides"][1]["texto"] = "Fique rico com isto"
    instalar(raiz, post)
    ent = novo(raiz)
    assert ent.executar() == 1
    assert len(responses.calls) == 0
    assert "promessa" in ent.notificador.issues[0][1]


@responses.activate
def test_post_que_nao_esta_pronto_nao_envia(raiz, post):
    post["status"] = "revisar_humano"
    instalar(raiz, post)
    assert novo(raiz).executar() == 1
    assert len(responses.calls) == 0


@responses.activate
def test_post_vencido_nao_envia(raiz, post):
    post.update(pilar="atualidade", valido_ate="2026-11-09", hipotetico=False,
                fontes=[{"descricao": "x", "url": "https://x", "data": "2026-11-08", "veiculo": "Banco Central", "primaria": True}])
    instalar(raiz, post)
    assert novo(raiz, hoje=dt.date(2026, 11, 10)).executar(data_forcada=HOJE) == 1
    assert len(responses.calls) == 0


@responses.activate
def test_evento_tem_prioridade_sobre_o_post_fixo(raiz, post):
    ok_telegram()
    instalar(raiz, post)
    ev = copy.deepcopy(post)
    ev.update(id="FIN-2026-11-09-evento", pilar="evento", prioridade="evento", tema_slug="copom-x", valido_ate="2026-11-10",
              legenda=post["legenda"] + "\n\nFonte: Banco Central.", hipotetico=False,
              fontes=[{"descricao": "c", "url": "https://bcb.gov.br", "data": "2026-11-08", "veiculo": "Banco Central", "primaria": True}])
    ev["hashtags"][0] = "#selic"
    ev["slides"][1]["texto"] = "Banco Central em 08/11/2026."
    instalar(raiz, ev, evento=True)
    assert novo(raiz).executar() == 0
    assert estado_tg(raiz, ev, evento=True)["estado"] == "enviado"
    assert estado_tg(raiz, post)["estado"] == "adiado"
    assert publicar.legenda_final(ev) in textos()


@responses.activate
def test_janela_da_tarde_ignora_post_fixo(raiz, post):
    instalar(raiz, post)
    assert novo(raiz).executar(janela="evento") == 0
    assert len(responses.calls) == 0


@responses.activate
def test_registra_no_historico_como_entregue(raiz, post):
    ok_telegram()
    instalar(raiz, post)
    novo(raiz).executar()
    linha = comum.ler_publicacoes(raiz)[0]
    assert (linha["id"], linha["status"]) == (post["id"], "entregue")


@responses.activate
def test_dry_run_nao_chama_o_telegram_nem_grava(raiz, post, capsys):
    pasta = instalar(raiz, post)
    ent = novo(raiz, dry_run=True)
    assert ent.executar() == 0
    assert len(responses.calls) == 0
    assert not (pasta / "estado.json").exists()
    assert ent.git.commits == []
    assert "SIMULAÇÃO" in capsys.readouterr().out


@responses.activate
def test_conta_pausada_por_bloqueio_nao_recebe_entrega(raiz, post):
    instalar(raiz, post)
    comum.gravar_json(raiz / "historico" / "contas_pausadas.json", {"FIN": {"motivo": "x", "data": "2026-11-08"}})
    assert novo(raiz).executar() == 0
    assert len(responses.calls) == 0


def test_tema_entregue_conta_para_repeticao(post, ctx):
    ctx.publicacoes.append({"perfil": "FIN", "tema_slug": "juros-compostos", "data": "2026-10-01", "status": "entregue", "id": "x"})
    assert "repeticao" in {e.regra for e in validar.validar_post(post, ctx)}


def test_envio_real_fora_do_actions_exige_confirmacao(monkeypatch, capsys):
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert et.main(["FIN"]) == 2
    assert "--confirmar-local" in capsys.readouterr().out
