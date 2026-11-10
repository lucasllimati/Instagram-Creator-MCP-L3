"""Entrega o post do dia em um canal do Telegram, pronto para postar à mão.

Uso:
  python scripts/entregar_telegram.py FIN --dry-run
  python scripts/entregar_telegram.py FIN                       # no GitHub Actions
  python scripts/entregar_telegram.py FIN --confirmar-local     # da sua máquina, com as variáveis definidas
  python scripts/entregar_telegram.py FIN --janela evento
  python scripts/entregar_telegram.py FIN --data 2026-11-09

Ordem das mensagens: cabeçalho, imagens (como arquivo, sem compressão), vídeo
Reels, legenda pronta para copiar, apoio (alt text e dicas) e stories.
Só entrega o que está aprovado em `main`, com status `pronto`, e nunca repete.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import requests

import comum
import publicar
import rampa
import validar
import validar_imagem
import video

LIMITE_TEXTO = 4096
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _mmss(segundos: float) -> str:
    s = int(round(segundos))
    return f"{s // 60}:{s % 60:02d}"


class ErroTelegram(Exception):
    pass


class Telegram:
    def __init__(self, token: str, chat_id: str, dormir=time.sleep):
        self.token = token
        self.chat_id = chat_id
        self.dormir = dormir

    def _mascarar(self, texto) -> str:
        return str(texto).replace(self.token, "***") if self.token else str(texto)

    def _chamar(self, metodo: str, **kw) -> dict:
        url = f"https://api.telegram.org/bot{self.token}/{metodo}"
        for tentativa in range(3):
            try:
                r = requests.post(url, timeout=120, **kw)
            except requests.RequestException as e:
                if tentativa == 2:
                    raise ErroTelegram(self._mascarar(f"{metodo}: falha de rede ({type(e).__name__})")) from None
                self.dormir(5)
                continue
            try:
                corpo = r.json()
            except ValueError:
                corpo = {}
            if r.status_code == 429 and tentativa < 2:
                self.dormir(corpo.get("parameters", {}).get("retry_after", 5))
                continue
            if r.status_code >= 500 and tentativa < 2:
                self.dormir(5)
                continue
            if r.status_code >= 400 or not corpo.get("ok", False):
                raise ErroTelegram(self._mascarar(f"{metodo}: HTTP {r.status_code}: {corpo.get('description', '')}"))
            return corpo
        raise ErroTelegram(f"{metodo}: sem resposta válida")

    def enviar_texto(self, texto: str) -> None:
        pedacos, atual = [], ""
        for linha in texto.split("\n"):
            while len(linha) > LIMITE_TEXTO:
                if atual:
                    pedacos.append(atual)
                    atual = ""
                pedacos.append(linha[:LIMITE_TEXTO])
                linha = linha[LIMITE_TEXTO:]
            candidato = f"{atual}\n{linha}" if atual else linha
            if len(candidato) > LIMITE_TEXTO:
                pedacos.append(atual)
                atual = linha
            else:
                atual = candidato
        if atual:
            pedacos.append(atual)
        for p in pedacos:
            self._chamar("sendMessage", json={"chat_id": self.chat_id, "text": p, "disable_web_page_preview": True})

    def enviar_documentos(self, arquivos: list[Path]) -> None:
        """Como arquivo, o Telegram não comprime a imagem."""
        for inicio in range(0, len(arquivos), 10):
            grupo = arquivos[inicio : inicio + 10]
            if len(grupo) == 1:
                with open(grupo[0], "rb") as f:
                    self._chamar("sendDocument", data={"chat_id": self.chat_id}, files={"document": (grupo[0].name, f, "image/jpeg")})
                continue
            abertos = {f"f{i}": open(a, "rb") for i, a in enumerate(grupo)}
            try:
                media = [{"type": "document", "media": f"attach://f{i}"} for i in range(len(grupo))]
                self._chamar(
                    "sendMediaGroup",
                    data={"chat_id": self.chat_id, "media": json.dumps(media)},
                    files={k: (grupo[int(k[1:])].name, v, "image/jpeg") for k, v in abertos.items()},
                )
            finally:
                for f in abertos.values():
                    f.close()

    def enviar_video(self, arquivo: Path, legenda: str = "") -> None:
        with open(arquivo, "rb") as f:
            self._chamar(
                "sendVideo",
                data={"chat_id": self.chat_id, "caption": legenda, "supports_streaming": "true", "width": 1080, "height": 1920},
                files={"video": (arquivo.name, f, "video/mp4")},
            )


class SemGit:
    """Fora do Actions: grava o estado no disco, sem commit nem push."""

    def commit_push(self, caminhos, mensagem) -> None:
        print(f"(estado salvo localmente: {mensagem})")


class Entregador:
    def __init__(self, perfil, raiz, hoje, telegram, git, notificador, cfg_rampa, ativa=True, dry_run=False, gerar_video=video.gerar_reel, segredos=(), agora=None, respeitar_horario=False):
        self.agora = agora
        self.respeitar_horario = respeitar_horario
        self.perfil = perfil
        self.raiz = Path(raiz)
        self.hoje = hoje
        self.telegram = telegram
        self.git = git
        self.notificador = notificador
        self.cfg_rampa = cfg_rampa
        self.ativa = ativa
        self.dry_run = dry_run
        self.gerar_video = gerar_video
        self.limites = comum.limites(self.raiz)
        self.cfg = self.limites.get("telegram", {})
        self.marca = comum.marca(perfil)
        self.segredos = [s for s in (telegram.token, *segredos) if s]

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

    # --- estado, guardado em estado.json na chave "telegram" ---
    def _ler(self, pasta: Path) -> dict:
        return comum.ler_json(pasta / "estado.json", {})

    def _situacao(self, pasta: Path) -> str:
        return self._ler(pasta).get("telegram", {}).get("estado", "pendente")

    def _gravar(self, pasta: Path, tg: dict, commit: str | None = None, extras=()) -> None:
        if self.dry_run:
            return
        estado = self._ler(pasta)
        estado["telegram"] = tg
        comum.gravar_json(pasta / "estado.json", estado)
        if commit:
            self.git.commit_push([pasta / "estado.json", *extras], commit)

    def _marcar(self, pasta: Path, novo: str, motivo: str = "") -> None:
        tg = self._ler(pasta).get("telegram", {})
        tg["estado"] = novo
        if motivo:
            tg["motivo"] = motivo
        self._gravar(pasta, tg, f"Telegram {pasta.parent.name}/{pasta.name}: {novo}")

    # --- mensagens ---
    def _cabecalho(self, post: dict) -> str:
        data = comum.data_iso(post["data"])
        tipo = "Carrossel" if post["formato"] == "carrossel" else "Post único"
        hora = self.cfg.get("horarios", {}).get(self.perfil, "")
        linhas = [
            f"📌 {self.marca['arroba']} · {DIAS[data.weekday()]} {data.strftime('%d/%m')} · {tipo} ({len(post['slides'])} imagens)",
            f"Tema: {post['titulo']}",
        ]
        if hora:
            linhas.append(f"Horário sugerido: {hora}")
        linhas += ["", "A seguir: imagens, vídeo para Reels, legenda para copiar e dicas de postagem."]
        return "\n".join(linhas)

    def _apoio(self, post: dict) -> str:
        n = len(post["slides"])
        linhas = ["Texto alternativo de cada imagem", "(no app: Configurações avançadas > Acessibilidade > Escrever texto alternativo)", ""]
        linhas += [f"{i}. {t}" for i, t in enumerate(post["alt_text"][:n], 1)]
        linhas += ["", "Dicas"]
        if video.deve_gerar(post, self.limites):
            linhas.append("- Reels: adicione um áudio da biblioteca do Instagram antes de publicar.")
        linhas.append("- Publique as imagens na ordem dos arquivos (slide_01, slide_02...).")
        if post.get("enquete_manual"):
            linhas.append(f"- Enquete sugerida para o story: {post['enquete_manual']}")
        return "\n".join(linhas)

    def _texto_stories(self, post: dict) -> str:
        linhas = ["Stories do dia, na ordem"]
        linhas += [f"Story {i}: {s['texto']}" for i, s in enumerate(post["stories"], 1)]
        if post.get("enquete_manual"):
            linhas.append(f"Enquete sugerida: {post['enquete_manual']}")
        return "\n".join(linhas)

    def _roteiro(self, post: dict) -> str:
        tempos = video.duracoes(post, self.cfg.get("segundos_por_slide", 3.5))
        total = sum(tempos)
        linhas = [
            f"Roteiro para gravar a narração (cerca de {round(total)} s)",
            "Grave por cima do vídeo, na ferramenta de voz do Instagram ou do CapCut. Cada slide fica na tela o tempo da fala.",
            "",
        ]
        inicio = 0.0
        for i, (fala, t) in enumerate(zip(post["narracao"], tempos), 1):
            fim = inicio + t
            linhas.append(f"{_mmss(inicio)}–{_mmss(fim)} · Slide {i}: {fala}")
            inicio = fim
        return "\n".join(linhas)

    def _partes(self, post: dict) -> list[str]:
        partes = ["cabecalho", "imagens"]
        if video.deve_gerar(post, self.limites):
            partes.append("video")
            if post.get("narracao"):
                partes.append("roteiro")
        partes += ["legenda", "apoio"]
        if post.get("stories") and rampa.stories_ativos(comum.data_iso(post["data"]), self.cfg_rampa):
            partes.append("stories")
        return partes

    def _enviar_parte(self, parte: str, pasta: Path, post: dict) -> None:
        if parte == "cabecalho":
            self.telegram.enviar_texto(self._cabecalho(post))
        elif parte == "imagens":
            self.telegram.enviar_documentos([pasta / f"slide_{s['n']:02d}.jpg" for s in post["slides"]])
        elif parte == "video":
            with tempfile.TemporaryDirectory() as tmp:
                tempos = video.duracoes(post, self.cfg.get("segundos_por_slide", 3.5))
                arquivo = self.gerar_video(pasta, self.marca["cores"]["principal"], Path(tmp) / f"{post['id']}.mp4", tempos)
                self.telegram.enviar_video(arquivo, "Vídeo para Reels (sem áudio)")
        elif parte == "roteiro":
            self.telegram.enviar_texto(self._roteiro(post))
        elif parte == "legenda":
            self.telegram.enviar_texto(publicar.legenda_final(post))
        elif parte == "apoio":
            self.telegram.enviar_texto(self._apoio(post))
        elif parte == "stories":
            self.telegram.enviar_documentos([pasta / f"story_{i:02d}.jpg" for i in range(1, len(post["stories"]) + 1)])
            self.telegram.enviar_texto(self._texto_stories(post))

    def _entregar(self, pasta: Path, post: dict, forcada: bool) -> int:
        situacao = self._situacao(pasta)
        if situacao == "enviado":
            return 0
        if situacao in ("adiado", "vencido", "atrasado") and not forcada:
            self._log(f"{post['id']} está como {situacao}; nada a fazer")
            return 0
        if post.get("valido_ate") and post["valido_ate"] < self.hoje.isoformat():
            self._marcar(pasta, "vencido")
            self._issue(f"Post vencido: {post['id']}", f"valido_ate = {post['valido_ate']}. Nada foi enviado.")
            return 1
        if post.get("status") != "pronto":
            self._issue(f"Post não está pronto: {post['id']}", f"status = {post.get('status')}. Nada foi enviado.")
            return 1
        ctx = validar.carregar_contexto(self.raiz, self.hoje)
        erros = validar.validar_post(post, ctx) + validar_imagem.validar_pasta(pasta, post, self.limites)
        if erros:
            self._issue(f"Post reprovado na validação: {post['id']}", "\n".join(f"- {e}" for e in erros))
            return 1

        partes = self._partes(post)
        if self.dry_run:
            self._log(f"SIMULAÇÃO: {post['id']} passou nas validações; enviaria {', '.join(partes)}")
            return 0

        tg = self._ler(pasta).get("telegram", {})
        feitas = tg.setdefault("partes", [])
        tg["estado"] = "enviando"
        try:
            for parte in partes:
                if parte in feitas:
                    continue
                self._enviar_parte(parte, pasta, post)
                feitas.append(parte)
                self._gravar(pasta, tg)  # salva a cada parte para retomar sem repetir
        except (ErroTelegram, RuntimeError, OSError) as e:
            self._gravar(pasta, tg, f"Telegram parcial de {post['id']}")
            self._issue(f"Falha ao enviar {post['id']} ao Telegram", f"{e}\n\nPartes já enviadas: {', '.join(feitas) or 'nenhuma'}. A próxima execução continua de onde parou.")
            return 1

        tg.update(estado="enviado", enviado_em=dt.datetime.now(comum.TZ).isoformat(timespec="seconds"))
        if post["id"] not in {l["id"] for l in comum.ler_publicacoes(self.raiz)}:
            comum.acrescentar_publicacao(
                {**{k: post[k] for k in ("id", "data", "perfil", "pilar", "tema_slug", "titulo")}, "publicado_em": tg["enviado_em"], "status": "entregue"},
                self.raiz,
            )
        self._gravar(pasta, tg, f"Telegram: entrega de {post['id']}", [self.raiz / "historico" / "publicacoes.csv"])
        self._log(f"entregue {post['id']}")
        return 0

    def _carregar(self, data, evento: bool):
        pasta = comum.pasta_post(self.raiz, data, self.perfil, evento)
        post = comum.ler_json(pasta / "post.json")
        return (pasta, post) if post else (None, None)

    def _dia(self, data: dt.date, janela: str, forcada: bool) -> int:
        pasta_n, post_n = self._carregar(data, False)
        pasta_e, post_e = self._carregar(data, True)
        sit_n = self._situacao(pasta_n) if post_n else None
        sit_e = self._situacao(pasta_e) if post_e else None
        evento_aberto = post_e and (sit_e not in ("enviado", "adiado", "vencido", "atrasado") or forcada)

        if sit_e == "enviado":
            return 0
        if sit_n == "enviado":
            if evento_aberto:
                self._marcar(pasta_e, "atrasado")
                self._issue(f"Evento sem vaga: {post_e['id']}", f"O post fixo de {data} já foi entregue. Escolha outra data.")
            return 0
        if evento_aberto:
            if post_n and sit_n == "pendente":
                self._marcar(pasta_n, "adiado")
            return self._entregar(pasta_e, post_e, forcada)
        if post_n and janela == "normal":
            return self._entregar(pasta_n, post_n, forcada)
        self._log(f"nada a entregar em {data} (janela {janela})")
        return 0

    def _passou_horario(self) -> bool:
        horario = self.cfg.get("horarios", {}).get(self.perfil)
        if not horario:
            return True
        hora, minuto = map(int, horario.split(":"))
        agora = self.agora or dt.datetime.now(comum.TZ)
        return agora.time() >= dt.time(hora, minuto)

    def _tratar_perdidos(self, excluir: dt.date) -> None:
        """Post de dia anterior que não saiu vira atrasado: nunca dois posts no mesmo dia."""
        for dias in range(1, 4):
            data = self.hoje - dt.timedelta(days=dias)
            if data == excluir:
                continue
            for evento in (False, True):
                pasta, post = self._carregar(data, evento)
                if not post or post.get("status") != "pronto" or self._situacao(pasta) not in ("pendente", "enviando"):
                    continue
                self._marcar(pasta, "atrasado")
                self._issue(
                    f"Post atrasado: {post['id']}",
                    f"Não foi entregue em {post['data']}, provavelmente por atraso do agendamento do GitHub. "
                    f"Para enviar mesmo assim, rode Actions > Entregar no Telegram com perfil {self.perfil} e data {post['data']}.",
                )

    def executar(self, janela: str = "normal", data_forcada: dt.date | None = None) -> int:
        if not self.ativa and not self.dry_run:
            self._log("ENTREGA_TELEGRAM não é true; nada foi feito")
            return 0
        if self.perfil in comum.ler_json(self.raiz / "historico" / "contas_pausadas.json", {}):
            self._log("conta pausada em historico/contas_pausadas.json; nada foi feito")
            return 0
        try:
            data = data_forcada or self.hoje
            if not self.dry_run:
                self._tratar_perdidos(excluir=data)
            if self.respeitar_horario and not data_forcada and not self._passou_horario():
                self._log(f"ainda não é o horário de {self.perfil} ({self.cfg['horarios'][self.perfil]})")
                return 0
            return self._dia(data, janela, bool(data_forcada))
        except publicar.ErroEstado as e:
            self._issue("Falha ao salvar o estado da entrega", e)
        except Exception as e:  # qualquer falha vira alerta, sem vazar segredo
            self._issue("Erro inesperado na entrega pelo Telegram", f"{type(e).__name__}: {e}")
        return 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("perfil", choices=comum.PERFIS)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--confirmar-local", action="store_true", help="permite o envio real fora do GitHub Actions")
    ap.add_argument("--janela", choices=["normal", "evento"], default="normal")
    ap.add_argument("--data", type=dt.date.fromisoformat)
    ap.add_argument("--respeitar-horario", action="store_true", help="só entrega depois do horário do perfil (execuções agendadas)")
    args = ap.parse_args(argv)

    no_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    if not args.dry_run and not no_actions and not args.confirmar_local:
        print("Envio real fora do GitHub Actions exige --confirmar-local. Para testar, use --dry-run.")
        return 2
    ativa = os.environ.get("ENTREGA_TELEGRAM") == "true" or args.confirmar_local
    if not args.dry_run and not ativa:
        # Modo desligado não é erro: o workflow agendado termina verde.
        print(f"[{args.perfil}] ENTREGA_TELEGRAM não é true; nada foi feito")
        return 0
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not args.dry_run and not (token and chat):
        print("Faltam as variáveis TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID.")
        return 2
    return Entregador(
        respeitar_horario=args.respeitar_horario,
        perfil=args.perfil,
        raiz=comum.RAIZ,
        hoje=comum.hoje_sp(),
        telegram=Telegram(token, chat),
        git=publicar.Git(comum.RAIZ) if no_actions else SemGit(),
        notificador=publicar.Notificador() if no_actions else SemNotificador(),
        cfg_rampa=rampa.carregar(),
        ativa=ativa,
        dry_run=args.dry_run,
    ).executar(args.janela, args.data)


class SemNotificador:
    def abrir(self, titulo, corpo) -> None:
        print(f"ALERTA: {titulo}\n{corpo}")


if __name__ == "__main__":
    sys.exit(main())
