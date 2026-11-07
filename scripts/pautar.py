"""Monta o esqueleto da semana e confere o calendário preenchido.

Uso:
  python scripts/pautar.py gerar 2026-46     # cria calendario/semana-2026-46.csv
  python scripts/pautar.py checar 2026-46    # confere grade, rampa e repetição
  python scripts/pautar.py temas             # atualiza historico/temas-60d.json
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import sys
from pathlib import Path

import comum
import rampa

COLUNAS = ["data", "perfil", "pilar", "formato", "tema", "tema_slug", "angulo", "status"]


def segunda_da_semana(semana: str) -> dt.date:
    ano, numero = semana.split("-")
    return dt.date.fromisocalendar(int(ano), int(numero.lstrip("W")), 1)


def _vagas_evento(segunda: dt.date, eventos: list[dict]) -> set[dt.date]:
    """Dia seguinte a cada Copom dentro da semana."""
    fim = segunda + dt.timedelta(days=6)
    vagas = set()
    for e in eventos:
        if e["tipo"] == "copom":
            dia = comum.data_iso(e["data"]) + dt.timedelta(days=1)
            if segunda <= dia <= fim:
                vagas.add(dia)
    return vagas


def gerar_pauta(semana: str, cfg_rampa: dict, grade: dict, eventos: list[dict]) -> list[dict]:
    segunda = segunda_da_semana(semana)
    dias_base = list(rampa.regra(segunda, cfg_rampa)["dias"])
    vagas = _vagas_evento(segunda, eventos)
    linhas = []
    for perfil in comum.PERFIS:
        dias = list(dias_base)
        if perfil == "FIN":
            # Vaga de evento conta na rampa: entra no lugar do último dia livre.
            for vaga in sorted(vagas):
                if vaga.weekday() not in dias:
                    livres = [d for d in dias if segunda + dt.timedelta(days=d) not in vagas]
                    dias.remove(livres[-1])
                    dias.append(vaga.weekday())
        for d in sorted(dias):
            data = segunda + dt.timedelta(days=d)
            reservado = perfil == "FIN" and data in vagas
            pilar = "evento" if reservado else grade["dias"][d]
            linhas.append(
                {
                    "data": data.isoformat(),
                    "perfil": perfil,
                    "pilar": pilar,
                    "formato": grade["pilares"][pilar]["formato"],
                    "tema": "",
                    "tema_slug": "",
                    "angulo": "",
                    "status": "reservado_evento" if reservado else "pauta",
                }
            )
    return linhas


def checar_calendario(linhas: list[dict], temas: dict, grade: dict) -> list[str]:
    erros = []
    usados = {p: {t["tema_slug"] for t in temas.get(p, [])} for p in comum.PERFIS}
    atualidades = {p: 0 for p in comum.PERFIS}
    for l in linhas:
        rotulo = f"{l['data']} {l['perfil']}"
        if l["status"] == "reservado_evento":
            continue
        if not l["tema"].strip() or not l["tema_slug"].strip():
            erros.append(f"{rotulo}: tema vazio")
            continue
        if l["tema_slug"] in usados[l["perfil"]]:
            erros.append(f"{rotulo}: tema repetido ({l['tema_slug']})")
        usados[l["perfil"]].add(l["tema_slug"])
        if l["pilar"] == "atualidade":
            atualidades[l["perfil"]] += 1
        elif l["pilar"] != grade["dias"][comum.data_iso(l["data"]).weekday()]:
            erros.append(f"{rotulo}: pilar {l['pilar']} fora da grade")
        if l["formato"] != grade["pilares"][l["pilar"]]["formato"]:
            erros.append(f"{rotulo}: formato incompatível com o pilar")
    for perfil, total in atualidades.items():
        if total > grade["atualidades_max_por_semana"]:
            erros.append(f"{perfil}: {total} atualidades; máximo {grade['atualidades_max_por_semana']}")
    return erros


def temas_recentes(publicacoes: list[dict], fila: list[dict], hoje: dt.date, dias: int) -> dict:
    limite = (hoje - dt.timedelta(days=dias)).isoformat()
    saida = {p: [] for p in comum.PERFIS}
    vistos = set()
    fontes = [p for p in publicacoes if p.get("status") == "publicado"] + list(fila)
    for p in fontes:
        chave = (p.get("perfil"), p.get("tema_slug"), p.get("data"))
        if p.get("perfil") in saida and p.get("data", "") >= limite and chave not in vistos:
            vistos.add(chave)
            saida[p["perfil"]].append({"tema_slug": p["tema_slug"], "data": p["data"]})
    return saida


def _caminho(semana: str, raiz: Path) -> Path:
    return raiz / "calendario" / f"semana-{semana}.csv"


def main(argv=None, raiz: Path = comum.RAIZ) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("acao", choices=["gerar", "checar", "temas"])
    ap.add_argument("semana", nargs="?", help="AAAA-WW")
    args = ap.parse_args(argv)
    dias = comum.limites(raiz)["conteudo"]["repeticao_dias"]
    temas = temas_recentes(comum.ler_publicacoes(raiz), [p for _, p in comum.posts_da_fila(raiz)], comum.hoje_sp(), dias)

    if args.acao == "temas":
        comum.gravar_json(raiz / "historico" / "temas-60d.json", temas)
        print("historico/temas-60d.json atualizado")
        return 0
    if not args.semana:
        ap.error("informe a semana AAAA-WW")

    grade = comum.grade(raiz)
    caminho = _caminho(args.semana, raiz)
    if args.acao == "gerar":
        eventos = comum.carregar_yaml("config/calendario_economico.yaml", raiz).get("eventos") or []
        linhas = gerar_pauta(args.semana, comum.carregar_yaml("config/rampa.yaml", raiz), grade, eventos)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        if caminho.exists():
            print(f"{caminho.name} já existe; nada foi alterado")
            return 0
        with open(caminho, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=COLUNAS)
            w.writeheader()
            w.writerows(linhas)
        print(f"{caminho.name}: {len(linhas)} linhas")
        return 0

    with open(caminho, encoding="utf-8", newline="") as f:
        erros = checar_calendario(list(csv.DictReader(f)), temas, grade)
    for e in erros:
        print(e)
    print("OK" if not erros else f"{len(erros)} problema(s)")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
