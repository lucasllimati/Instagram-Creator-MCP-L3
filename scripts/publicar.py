"""Publica o post do dia de um perfil pela API oficial do Instagram.

Uso:
  python scripts/publicar.py FIN --dry-run                # simula, em qualquer máquina
  python scripts/publicar.py FIN                          # real, só no GitHub Actions
  python scripts/publicar.py FIN --janela evento          # tentativa da tarde: só evento
  python scripts/publicar.py FIN --data 2026-11-09        # republica um dia, em disparo manual

Garantias principais:
  - nunca publica duas vezes: o container é salvo antes de publicar e, em caso de
    dúvida, o status é consultado antes de qualquer nova tentativa;
  - erro de autorização ou bloqueio pausa a conta, sem novas tentativas;
  - post atrasado não é publicado sozinho.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

import comum
import rampa
import validar
import validar_imagem

ESTADOS_FINAIS = {"publicado", "falhou", "atrasado", "adiado", "vencido"}
CODIGOS_BLOQUEIO = {190, 102, 10, 25, 368}
SUBCODIGOS_BLOQUEIO = {2207050, 2207051}
CODIGOS_LIMITE = {4, 9, 17, 32, 613}
CODIGOS_TEMPORARIOS = {1, 2}


class ErroPublicacao(Exception):
    pass


class ErroTemporario(ErroPublicacao):
    pass


class ErroCota(ErroPublicacao):
    pass


class ErroBloqueio(ErroPublicacao):
    pass


class ErroConteudo(ErroPublicacao):
    pass


class ErroEstado(ErroPublicacao):
    pass


def legenda_final(post: dict) -> str:
    return post["legenda"] + "\n\n" + " ".join(post["hashtags"])


def classificar(status: int, corpo: dict) -> ErroPublicacao:
    erro = corpo.get("error", {}) if isinstance(corpo, dict) else {}
    code = erro.get("code")
    sub = erro.get("error_subcode")
    resumo = f"HTTP {status}, código {code}, subcódigo {sub}: {erro.get('message', '')}"
    if sub in SUBCODIGOS_BLOQUEIO or code in CODIGOS_BLOQUEIO or (isinstance(code, int) and 200 <= code <= 299):
        return ErroBloqueio(resumo)
    if code in CODIGOS_LIMITE:
        return ErroCota(resumo)
    if status >= 500 or erro.get("is_transient") or code in CODIGOS_TEMPORARIOS:
        return ErroTemporario(resumo)
    return ErroConteudo(resumo)


class ClienteGraph:
    def __init__(self, cfg_api: dict, ig_id: str, token: str):
        self.base = f"{cfg_api['base']}/{cfg_api['versao']}"
        self.ig_id = ig_id
        self.cabecalhos = {"Authorization": f"Bearer {token}"}

    def _req(self, metodo: str, caminho: str, **kw) -> dict:
        try:
            r = requests.request(metodo, f"{self.base}/{caminho}", headers=self.cabecalhos, timeout=60, **kw)
        except requests.RequestException as e:
            raise ErroTemporario(type(e).__name__) from e
        try:
            corpo = r.json()
        except ValueError:
            corpo = {}
        if r.status_code >= 400 or (isinstance(corpo, dict) and "error" in corpo):
            raise classificar(r.status_code, corpo)
        return corpo

    def criar_container(self, **campos) -> str:
        return self._req("POST", f"{self.ig_id}/media", data=campos)["id"]

    def status(self, container: str) -> str:
        return self._req("GET", container, params={"fields": "status_code"})["status_code"]

    def publicar(self, container: str) -> str:
        return self._req("POST", f"{self.ig_id}/media_publish", data={"creation_id": container})["id"]

    def permalink(self, media_id: str) -> str:
        return self._req("GET", media_id, params={"fields": "permalink"}).get("permalink", "")

    def cota(self) -> tuple[int, int]:
        item = self._req("GET", f"{self.ig_id}/content_publishing_limit", params={"fields": "quota_usage,config"})["data"][0]
        return item.get("quota_usage", 0), item.get("config", {}).get("quota_total", 50)

    def recentes(self) -> list[dict]:
        return self._req("GET", f"{self.ig_id}/media", params={"fields": "id,permalink,caption,timestamp", "limit": 10}).get("data", [])


class Midia:
    """Envia imagens ao repositório público no momento de publicar."""

    def __init__(self, cfg: dict, token: str, dormir=time.sleep):
        self.cfg = cfg
        self.token = token
        self.dormir = dormir

    def _url_api(self, caminho: str) -> str:
        return f"https://api.github.com/repos/{self.cfg['owner']}/{self.cfg['repo']}/contents/{caminho}"

    def _url_publica(self, caminho: str) -> str:
        return f"https://raw.githubusercontent.com/{self.cfg['owner']}/{self.cfg['repo']}/{self.cfg['branch']}/{caminho}"

    def _enviar_um(self, arquivo: Path, caminho: str) -> None:
        h = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}
        try:
            atual = requests.get(self._url_api(caminho), headers=h, params={"ref": self.cfg["branch"]}, timeout=30)
            corpo = {
                "message": f"Mídia {caminho}",
                "branch": self.cfg["branch"],
                "content": base64.b64encode(arquivo.read_bytes()).decode(),
            }
            if atual.status_code == 200:
                corpo["sha"] = atual.json()["sha"]
            r = requests.put(self._url_api(caminho), headers=h, json=corpo, timeout=60)
        except requests.RequestException as e:
            raise ErroTemporario(f"envio de mídia: {type(e).__name__}") from e
        if r.status_code >= 500:
            raise ErroTemporario(f"envio de mídia: HTTP {r.status_code}")
        if r.status_code >= 400:
            raise ErroConteudo(f"envio de mídia recusado: HTTP {r.status_code}")

    def _verificar(self, url: str) -> None:
        for tentativa in range(5):
            try:
                r = requests.head(url, timeout=30, allow_redirects=True)
                if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image/jpeg"):
                    return
            except requests.RequestException:
                pass
            if tentativa < 4:
                self.dormir(5)
        raise ErroConteudo(f"URL pública indisponível ou não é JPEG: {url}")

    def enviar(self, arquivos: list[Path], prefixo: str) -> list[str]:
        urls = []
        for arquivo in arquivos:
            caminho = f"{prefixo}/{arquivo.name}"
            self._enviar_um(arquivo, caminho)
            urls.append(self._url_publica(caminho))
        for url in urls:
            self._verificar(url)
        return urls


class Git:
    def __init__(self, raiz: Path):
        self.raiz = raiz

    def _rodar(self, *args) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=self.raiz, capture_output=True, text=True)

    def commit_push(self, caminhos: list[Path], mensagem: str) -> None:
        self._rodar("add", "--", *[str(c) for c in caminhos])
        if self._rodar("diff", "--cached", "--quiet").returncode == 0:
            return
        if self._rodar("commit", "-m", mensagem).returncode != 0:
            raise ErroEstado("não foi possível criar o commit de estado")
        for _ in range(3):
            if self._rodar("pull", "--rebase", "--autostash").returncode == 0 and self._rodar("push").returncode == 0:
                return
            time.sleep(5)
        raise ErroEstado("não foi possível enviar o estado ao repositório")


class Notificador:
    def abrir(self, titulo: str, corpo: str) -> None:
        try:
            existentes = subprocess.run(
                ["gh", "issue", "list", "--state", "open", "--search", f'"{titulo}" in:title', "--json", "title", "--jq", ".[].title"],
                capture_output=True, text=True, timeout=60,
            )
            if titulo in existentes.stdout.splitlines():
                return
            r = subprocess.run(["gh", "issue", "create", "--title", titulo, "--body", corpo], capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                print("AVISO: não foi possível abrir a issue")
        except (OSError, subprocess.TimeoutExpired):
            print("AVISO: não foi possível abrir a issue")


class Publicador:
    def __init__(self, perfil, raiz, hoje, token, ig_id, midia, git, notificador, cfg_rampa, ativa=True, dry_run=False, dormir=time.sleep, segredos=()):
        self.perfil = perfil
        self.raiz = Path(raiz)
        self.hoje = hoje
        self.token = token
        self.midia = midia
        self.git = git
        self.notificador = notificador
        self.cfg_rampa = cfg_rampa
        self.ativa = ativa
        self.dry_run = dry_run
        self.dormir = dormir
        self.limites = comum.limites(self.raiz)
        self.pub = self.limites["publicacao"]
        self.graph = ClienteGraph(self.limites["api"], ig_id, token)
        self.segredos = [s for s in (token, *segredos) if s]

    # --- saída sempre mascarada ---
    def _mascarar(self, texto) -> str:
        texto = str(texto)
        for s in self.segredos:
            texto = texto.replace(s, "***")
        return texto

    def _log(self, texto) -> None:
        print(self._mascarar(f"[{self.perfil}] {texto}"))

    def _issue(self, titulo: str, corpo) -> None:
        self._log(f"ALERTA {titulo}: {corpo}")
        if not self.dry_run:
            self.notificador.abrir(self._mascarar(f"[{self.perfil}] {titulo}"), self._mascarar(corpo))

    # --- estado ---
    def _ler_estado(self, pasta: Path) -> dict:
        return comum.ler_json(pasta / "estado.json", {})

    def _salvar(self, pasta: Path, estado: dict, mensagem: str, extras=()) -> None:
        if self.dry_run:
            return
        limpo = {k: (self._mascarar(v) if isinstance(v, str) else v) for k, v in estado.items()}
        comum.gravar_json(pasta / "estado.json", limpo)
        self.git.commit_push([pasta / "estado.json", *extras], mensagem)

    def _encerrar_post(self, pasta: Path, estado: dict, novo: str, motivo: str = "") -> None:
        estado.update(estado=novo)
        if motivo:
            estado["erro"] = self._mascarar(motivo)
        self._salvar(pasta, estado, f"Estado {pasta.parent.name}/{pasta.name}: {novo}")

    # --- pausa por conta ---
    def _pausas_caminho(self) -> Path:
        return self.raiz / "historico" / "contas_pausadas.json"

    def _conta_pausada(self) -> bool:
        return self.perfil in comum.ler_json(self._pausas_caminho(), {})

    def _pausar_conta(self, erro: Exception) -> None:
        caminho = self._pausas_caminho()
        pausas = comum.ler_json(caminho, {})
        pausas[self.perfil] = {"motivo": self._mascarar(erro), "data": self.hoje.isoformat()}
        comum.gravar_json(caminho, pausas)
        try:
            self.git.commit_push([caminho], f"Pausa publicação de {self.perfil}")
        except ErroEstado as e:
            self._log(e)
        self._issue(
            "Conta pausada: autorização ou bloqueio",
            f"{erro}\n\nA publicação desta conta está parada, sem novas tentativas. "
            "Depois de resolver, remova a entrada de historico/contas_pausadas.json. Veja docs/operacao.md.",
        )

    # --- apoio à API ---
    def _tentar(self, funcao, *args, **kw):
        for i in range(self.pub["tentativas"]):
            try:
                return funcao(*args, **kw)
            except ErroTemporario:
                if i == self.pub["tentativas"] - 1:
                    raise
                self.dormir(self.pub["espera_base_s"] * 2**i)

    def _checar_cota(self) -> None:
        usado, total = self._tentar(self.graph.cota)
        if usado >= total * self.pub["cota_parada_fracao"]:
            raise ErroCota(f"cota em {usado} de {total}; parada em {self.pub['cota_parada_fracao']:.0%}")

    def _aguardar(self, container: str) -> str:
        """Devolve FINISHED ou PUBLISHED; levanta erro nos demais casos."""
        for _ in range(self.pub["status_tentativas"]):
            status = self._tentar(self.graph.status, container)
            if status in ("FINISHED", "PUBLISHED"):
                return status
            if status in ("EXPIRED", "ERROR"):
                raise ErroConteudo(f"container {container} com status {status}")
            self.dormir(self.pub["status_intervalo_s"])
        raise ErroTemporario(f"container {container} ainda em processamento")

    def _publicar_container(self, container: str) -> str | None:
        """Devolve o media_id ou None se o container já constar como publicado."""
        for i in range(self.pub["tentativas"]):
            try:
                return self.graph.publicar(container)
            except ErroTemporario:
                # A resposta pode ter se perdido depois de publicar: confere antes de repetir.
                self.dormir(self.pub["espera_base_s"] * 2**i)
                if self._tentar(self.graph.status, container) == "PUBLISHED":
                    return None
                if i == self.pub["tentativas"] - 1:
                    raise

    def _localizar_publicado(self, post: dict) -> dict | None:
        legenda = legenda_final(post)
        return next((m for m in self._tentar(self.graph.recentes) if m.get("caption") == legenda), None)

    # --- post ---
    def _concluir(self, pasta: Path, post: dict, estado: dict, media_id: str, permalink: str) -> None:
        agora = dt.datetime.now(comum.TZ).isoformat(timespec="seconds")
        estado.update(estado="publicado", media_id=media_id, permalink=permalink, publicado_em=agora)
        estado.pop("erro", None)
        csv_caminho = self.raiz / "historico" / "publicacoes.csv"
        if post["id"] not in {l["id"] for l in comum.ler_publicacoes(self.raiz)}:
            comum.acrescentar_publicacao(
                {**{k: post[k] for k in ("id", "data", "perfil", "pilar", "tema_slug", "titulo")},
                 "media_id": media_id, "permalink": permalink, "publicado_em": agora, "status": "publicado"},
                self.raiz,
            )
        self._log(f"publicado {post['id']}: {permalink or media_id}")
        self._salvar(pasta, estado, f"Publica {post['id']}", [csv_caminho])

    def _reconciliar(self, pasta: Path, post: dict, estado: dict) -> None:
        achado = self._localizar_publicado(post)
        if achado:
            self._concluir(pasta, post, estado, achado["id"], achado.get("permalink", ""))
        else:
            self._concluir(pasta, post, estado, "desconhecido", "")
            self._issue(f"Conferir publicação de {post['id']}", "O container consta como publicado, mas a mídia não foi localizada.")

    def _finalizar_container(self, pasta: Path, post: dict, estado: dict) -> None:
        container = estado["container"]
        if self._aguardar(container) == "PUBLISHED":
            self._reconciliar(pasta, post, estado)
            return
        media_id = self._publicar_container(container)
        if media_id is None:
            self._reconciliar(pasta, post, estado)
            return
        self._concluir(pasta, post, estado, media_id, self._tentar(self.graph.permalink, media_id))

    def _prefixo(self, post: dict, pasta: Path) -> str:
        return f"{post['data'].replace('-', '/')}/{pasta.name}"

    def _criar_containers(self, pasta: Path, post: dict, estado: dict) -> None:
        self._checar_cota()
        arquivos = [pasta / f"slide_{s['n']:02d}.jpg" for s in post["slides"]]
        urls = self._tentar(self.midia.enviar, arquivos, self._prefixo(post, pasta))
        alts = post["alt_text"]
        legenda = legenda_final(post)
        if post["formato"] == "carrossel":
            filhos = [
                self._tentar(self.graph.criar_container, image_url=u, is_carousel_item="true", alt_text=alts[i])
                for i, u in enumerate(urls)
            ]
            container = self._tentar(self.graph.criar_container, media_type="CAROUSEL", children=",".join(filhos), caption=legenda)
        else:
            filhos = []
            container = self._tentar(self.graph.criar_container, image_url=urls[0], caption=legenda, alt_text=alts[0])
        estado.update(estado="container_criado", container=container, filhos=filhos)
        # Só publica depois de o estado estar salvo: é o que impede duplicata após uma queda.
        self._salvar(pasta, estado, f"Container de {post['id']}")

    def _erros_validacao(self, pasta: Path, post: dict) -> list:
        ctx = validar.carregar_contexto(self.raiz, self.hoje)
        return validar.validar_post(post, ctx) + validar_imagem.validar_pasta(pasta, post, self.limites)

    def _publicar_post(self, pasta: Path, post: dict, forcada: bool) -> int:
        estado = self._ler_estado(pasta)
        atual = estado.get("estado", "pendente")
        if atual == "publicado":
            return self._publicar_stories(pasta, post, estado)
        if atual in ESTADOS_FINAIS:
            if not forcada:
                self._log(f"{post['id']} está como {atual}; nada a fazer")
                return 0
            estado, atual = {}, "pendente"
        if post.get("valido_ate") and post["valido_ate"] < self.hoje.isoformat():
            self._encerrar_post(pasta, estado, "vencido", f"validade terminou em {post['valido_ate']}")
            self._issue(f"Post vencido: {post['id']}", f"valido_ate = {post['valido_ate']}. Nada foi publicado.")
            return 1
        if post.get("status") != "pronto":
            self._issue(f"Post não está pronto: {post['id']}", f"status = {post.get('status')}. Nada foi publicado.")
            return 1
        erros = self._erros_validacao(pasta, post)
        if erros:
            corpo = "\n".join(f"- {e}" for e in erros)
            self._encerrar_post(pasta, estado, "falhou", "reprovado na validação")
            self._issue(f"Post reprovado na validação: {post['id']}", corpo)
            return 1
        if self.dry_run:
            return self._simular(post)

        try:
            if atual != "container_criado":
                self._criar_containers(pasta, post, estado)
            self._finalizar_container(pasta, post, estado)
        except ErroConteudo as e:
            self._encerrar_post(pasta, estado, "falhou", str(e))
            self._issue(f"Falha ao publicar {post['id']}", e)
            return 1
        return self._publicar_stories(pasta, post, estado)

    def _simular(self, post: dict) -> int:
        self._log(f"SIMULAÇÃO: {post['id']} passou nas validações; {len(post['slides'])} imagens ({post['formato']})")
        if self.token:
            try:
                usado, total = self.graph.cota()
                self._log(f"SIMULAÇÃO: cota {usado} de {total}")
            except ErroPublicacao as e:
                self._log(f"SIMULAÇÃO: não foi possível ler a cota: {e}")
        return 0

    # --- stories ---
    def _publicar_stories(self, pasta: Path, post: dict, estado: dict) -> int:
        if not rampa.stories_ativos(comum.data_iso(post["data"]), self.cfg_rampa) or not post.get("stories"):
            return 0
        itens = estado.setdefault("stories", [{"estado": "pendente"} for _ in post["stories"]])
        codigo = 0
        for i, item in enumerate(itens, 1):
            if item["estado"] in ("publicado", "falhou"):
                continue
            try:
                if item["estado"] != "container_criado":
                    url = self._tentar(self.midia.enviar, [pasta / f"story_{i:02d}.jpg"], self._prefixo(post, pasta))[0]
                    item.update(estado="container_criado", container=self._tentar(self.graph.criar_container, image_url=url, media_type="STORIES"))
                    self._salvar(pasta, estado, f"Container do story {i} de {post['id']}")
                if self._aguardar(item["container"]) != "PUBLISHED":
                    item["media_id"] = self._publicar_container(item["container"]) or "desconhecido"
                item["estado"] = "publicado"
                self._salvar(pasta, estado, f"Story {i} de {post['id']}")
            except (ErroConteudo, ErroTemporario) as e:
                codigo = 1
                item.update(estado="falhou", erro=self._mascarar(e))
                self._salvar(pasta, estado, f"Falha no story {i} de {post['id']}")
                self._issue(f"Falha no story {i} de {post['id']}", e)
        return codigo

    # --- seleção ---
    def _carregar(self, data, evento: bool):
        pasta = comum.pasta_post(self.raiz, data, self.perfil, evento)
        post = comum.ler_json(pasta / "post.json")
        return (pasta, post) if post else (None, None)

    def _tratar_atrasados(self, excluir: dt.date) -> None:
        for dias in range(1, self.pub["dias_verificar_atraso"] + 1):
            data = self.hoje - dt.timedelta(days=dias)
            if data == excluir:
                continue
            for evento in (False, True):
                pasta, post = self._carregar(data, evento)
                if not post or post.get("status") != "pronto":
                    continue
                estado = self._ler_estado(pasta)
                atual = estado.get("estado", "pendente")
                if atual == "container_criado":
                    try:
                        if self._tentar(self.graph.status, estado["container"]) == "PUBLISHED":
                            self._reconciliar(pasta, post, estado)
                            continue
                    except ErroConteudo:
                        pass
                elif atual != "pendente":
                    continue
                self._log(f"{post['id']} ficou sem publicar e não será publicado automaticamente")
                self._encerrar_post(pasta, estado, "atrasado")
                self._issue(
                    f"Post atrasado: {post['id']}",
                    f"Não foi publicado em {post['data']}. Para publicar, dispare o workflow manualmente com data {post['data']}.",
                )

    def _executar_dia(self, data: dt.date, janela: str, forcada: bool) -> int:
        pasta_n, post_n = self._carregar(data, False)
        pasta_e, post_e = self._carregar(data, True)
        est_n = self._ler_estado(pasta_n).get("estado", "pendente") if post_n else None
        est_e = self._ler_estado(pasta_e).get("estado", "pendente") if post_e else None
        evento_aberto = post_e and (est_e not in ESTADOS_FINAIS or forcada)

        if est_e == "publicado":
            return self._publicar_post(pasta_e, post_e, False)
        if est_n == "publicado":
            if evento_aberto:
                # Teto de 1 post por dia: o evento não entra depois do post fixo.
                self._encerrar_post(pasta_e, self._ler_estado(pasta_e), "atrasado")
                self._issue(f"Evento sem vaga: {post_e['id']}", f"O post fixo de {data} já foi publicado. Escolha outra data.")
            return self._publicar_post(pasta_n, post_n, False) if janela == "normal" else 0
        if evento_aberto:
            if post_n and est_n == "pendente":
                self._log(f"evento tem prioridade; {post_n['id']} foi adiado")
                self._encerrar_post(pasta_n, self._ler_estado(pasta_n), "adiado")
            return self._publicar_post(pasta_e, post_e, forcada)
        if post_n and janela == "normal":
            return self._publicar_post(pasta_n, post_n, forcada)
        self._log(f"nada a publicar em {data} (janela {janela})")
        return 0

    def executar(self, janela: str = "normal", data_forcada: dt.date | None = None) -> int:
        if not self.ativa and not self.dry_run:
            self._log("PUBLICACAO_ATIVA não é true; nada foi feito")
            return 0
        if self._conta_pausada():
            self._log("conta pausada em historico/contas_pausadas.json; nada foi feito")
            return 0
        data = data_forcada or self.hoje
        try:
            if not self.dry_run:
                self._tratar_atrasados(excluir=data)
            return self._executar_dia(data, janela, bool(data_forcada))
        except ErroBloqueio as e:
            self._pausar_conta(e)
        except ErroCota as e:
            self._issue("Cota de publicação", e)
        except ErroEstado as e:
            self._issue("Falha ao salvar o estado; publicação interrompida", e)
        except ErroPublicacao as e:
            self._issue("Falha temporária na publicação", e)
        except Exception as e:  # falha inesperada também precisa virar alerta, sem vazar segredo
            self._issue("Erro inesperado na publicação", f"{type(e).__name__}: {e}")
        return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("perfil", choices=comum.PERFIS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--janela", choices=["normal", "evento"], default="normal")
    ap.add_argument("--data", type=dt.date.fromisoformat)
    args = ap.parse_args(argv)

    if not args.dry_run and os.environ.get("GITHUB_ACTIONS") != "true":
        print("Publicação real só roda no GitHub Actions. Aqui, use --dry-run.")
        return 2

    if not args.dry_run and os.environ.get("PUBLICACAO_ATIVA") != "true":
        # Modo desligado não é erro: o workflow agendado termina verde sem pedir segredos.
        print(f"[{args.perfil}] PUBLICACAO_ATIVA não é true; nada foi feito")
        return 0

    token = os.environ.get(f"IG_TOKEN_{args.perfil}", "")
    ig_id = os.environ.get(f"IG_USER_ID_{args.perfil}", "")
    token_midia = os.environ.get("MEDIA_REPO_TOKEN", "")
    if not args.dry_run and not (token and ig_id and token_midia):
        print(f"Faltam segredos: IG_TOKEN_{args.perfil}, IG_USER_ID_{args.perfil} ou MEDIA_REPO_TOKEN.")
        return 2

    limites = comum.limites()
    return Publicador(
        perfil=args.perfil,
        raiz=comum.RAIZ,
        hoje=comum.hoje_sp(),
        token=token,
        ig_id=ig_id,
        midia=Midia(limites["midia"], token_midia),
        git=Git(comum.RAIZ),
        notificador=Notificador(),
        cfg_rampa=rampa.carregar(),
        ativa=os.environ.get("PUBLICACAO_ATIVA") == "true",
        dry_run=args.dry_run,
        segredos=(token_midia,),
    ).executar(args.janela, args.data)


if __name__ == "__main__":
    sys.exit(main())
