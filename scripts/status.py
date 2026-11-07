"""Consulta e atualiza a situação da fila.

Uso:
  python scripts/status.py fila
  python scripts/status.py definir fila/2026-11-09/FIN revisado
  python scripts/status.py registrar '{"semana": "2026-46", "reprovacoes": 2}'
  python scripts/status.py pr 2026-46 semana/2026-46 dono/repo
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import comum
import pautar

STATUS = {"roteiro", "validado", "revisado", "renderizado", "pronto", "revisar_humano"}


def _gancho(post: dict) -> str:
    return post["slides"][0]["titulo"].replace("|", "/")


def mostrar(raiz: Path = comum.RAIZ) -> None:
    posts = comum.posts_da_fila(raiz)
    if not posts:
        print("Fila vazia.")
    for caminho, post in posts:
        estado = comum.ler_json(caminho.parent / "estado.json", {})
        linha = f"{post['id']:<26} {post['pilar']:<12} status={post['status']:<15} publicação={estado.get('estado', 'pendente')}"
        if estado.get("erro"):
            linha += f"  erro: {estado['erro']}"
        print(linha)
    pausas = comum.ler_json(raiz / "historico" / "contas_pausadas.json", {})
    for perfil, info in pausas.items():
        print(f"CONTA PAUSADA {perfil}: {info['motivo']}")


def definir(pasta: Path, novo: str) -> None:
    if novo not in STATUS:
        raise ValueError(f"status inválido: {novo}")
    caminho = pasta / "post.json"
    post = comum.ler_json(caminho)
    post["status"] = novo
    comum.gravar_json(caminho, post)


def registrar(raiz: Path, dados: dict) -> None:
    caminho = raiz / "historico" / "execucoes.jsonl"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    linha = {"registrado_em": dt.datetime.now(comum.TZ).isoformat(timespec="seconds"), **dados}
    with open(caminho, "a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")


def corpo_pr(raiz: Path, semana: str, branch: str, repo: str) -> str:
    inicio = pautar.segunda_da_semana(semana)
    fim = inicio + dt.timedelta(days=6)
    posts = [(c, p) for c, p in comum.posts_da_fila(raiz) if inicio.isoformat() <= p["data"] <= fim.isoformat()]
    linhas = [
        f"## Semana {semana}",
        "",
        "**Fazer o merge aprova a publicação.** Para vetar um post, remova a pasta dele nesta branch.",
        "",
        "| Data | Perfil | Pilar | Formato | Gancho | Status | Prévia |",
        "|---|---|---|---|---|---|---|",
    ]
    humanos, enquetes, fontes = [], [], []
    for caminho, p in posts:
        relativo = caminho.parent.relative_to(raiz).as_posix()
        previa = f"[ver](https://github.com/{repo}/blob/{branch}/{relativo}/previa.jpg?raw=1)"
        linhas.append(f"| {p['data']} | {p['perfil']} | {p['pilar']} | {p['formato']} | {_gancho(p)} | {p['status']} | {previa} |")
        if p["status"] != "pronto":
            humanos.append(f"- `{p['id']}`: status `{p['status']}`")
        if p.get("enquete_manual"):
            enquetes.append(f"- `{p['id']}`: {p['enquete_manual']}")
        fontes.extend(f"- `{p['id']}`: {f['descricao']} ({f['url']}, {f['data']})" for f in p.get("fontes", []))
    if humanos:
        linhas += ["", "## Precisa de olhar humano", "", *humanos, "", "Esses posts não serão publicados até ficarem com status `pronto`."]
    if enquetes:
        linhas += ["", "## Enquetes opcionais (a API não publica enquete; postagem manual)", "", *enquetes]
    if fontes:
        linhas += ["", "## Fontes", "", *fontes]
    return "\n".join(linhas) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="acao", required=True)
    sub.add_parser("fila")
    d = sub.add_parser("definir")
    d.add_argument("pasta", type=Path)
    d.add_argument("status")
    r = sub.add_parser("registrar")
    r.add_argument("json")
    p = sub.add_parser("pr")
    p.add_argument("semana")
    p.add_argument("branch")
    p.add_argument("repo")
    args = ap.parse_args(argv)
    if args.acao == "fila":
        mostrar()
    elif args.acao == "definir":
        definir(args.pasta, args.status)
    elif args.acao == "registrar":
        registrar(comum.RAIZ, json.loads(args.json))
    else:
        print(corpo_pr(comum.RAIZ, args.semana, args.branch, args.repo))
    return 0


if __name__ == "__main__":
    sys.exit(main())
