"""Plano do dia para o comando /hoje, calculado sem IA.

Uso: python scripts/hoje.py [FIN] [MKT] [--data AAAA-MM-DD]

Para cada perfil, devolve em JSON: pilar e formato do dia, se o dia está na
rampa, se já existe post, se a vaga é de evento, temas já usados e as melhores
notícias do radar. Assim os agentes começam com o contexto pronto.

Valores de "acao": criar, confirmar_fora_da_rampa, usar_evento, ja_existe, ja_entregue.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import comum
import pautar
import rampa

NOTICIAS = 3


def _radar(raiz: Path, data: dt.date, perfil: str) -> list[dict]:
    for dias in range(0, 3):
        arquivo = comum.ler_json(raiz / "pesquisa" / "radar" / f"{(data - dt.timedelta(days=dias)).isoformat()}.json")
        if arquivo is not None:
            itens = sorted(arquivo.get(perfil, []), key=lambda i: -i.get("pontos", 0))[:NOTICIAS]
            return [{k: i[k] for k in ("id", "titulo", "fonte", "data")} for i in itens]
    return []


def _situacao(raiz: Path, data: dt.date, perfil: str) -> tuple[str | None, str | None]:
    """Status do post existente e se já foi entregue ou publicado."""
    for evento in (True, False):
        pasta = comum.pasta_post(raiz, data, perfil, evento)
        post = comum.ler_json(pasta / "post.json")
        if post:
            estado = comum.ler_json(pasta / "estado.json", {})
            entregue = estado.get("estado") == "publicado" or estado.get("telegram", {}).get("estado") == "enviado"
            return post.get("status"), "sim" if entregue else None
    return None, None


def plano(data: dt.date, perfis, raiz: Path, cfg_rampa: dict, grade: dict, eventos: list[dict]) -> list[dict]:
    regra = rampa.regra(data, cfg_rampa)
    na_rampa = data.weekday() in regra["dias"]
    dias = comum.limites(raiz)["conteudo"]["repeticao_dias"]
    temas = pautar.temas_recentes(comum.ler_publicacoes(raiz), [p for _, p in comum.posts_da_fila(raiz)], data, dias)
    copom_ontem = next(
        (e for e in eventos if e["tipo"] == "copom" and comum.data_iso(e["data"]) == data - dt.timedelta(days=1)), None
    )
    ano, semana, _ = data.isocalendar()
    saida = []
    for perfil in perfis:
        pilar = grade["dias"][data.weekday()]
        cfg_pilar = grade["pilares"][pilar]
        status, entregue = _situacao(raiz, data, perfil)
        item = {
            "perfil": perfil,
            "data": data.isoformat(),
            "semana": f"{ano}-{semana:02d}",
            "pilar": pilar,
            "formato": cfg_pilar["formato"],
            "slides_min": cfg_pilar["min"],
            "slides_max": cfg_pilar["max"],
            "na_rampa": na_rampa,
            "stories": bool(regra["stories"]),
            "status_atual": status,
            "temas_usados": [t["tema_slug"] for t in temas.get(perfil, [])],
            "radar": _radar(raiz, data, perfil),
        }
        if entregue:
            item["acao"] = "ja_entregue"
        elif status:
            item["acao"] = "ja_existe"
        elif perfil == "FIN" and copom_ontem:
            item["acao"] = "usar_evento"
            item["reuniao_copom"] = comum.data_iso(copom_ontem["data"]).isoformat()
        elif not na_rampa:
            item["acao"] = "confirmar_fora_da_rampa"
        else:
            item["acao"] = "criar"
        saida.append(item)
    return saida


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("perfis", nargs="*", help="FIN, MKT ou os dois (padrão)")
    ap.add_argument("--data", type=dt.date.fromisoformat)
    args = ap.parse_args(argv)
    invalidos = [p for p in args.perfis if p not in comum.PERFIS]
    if invalidos:
        ap.error(f"perfil inválido: {', '.join(invalidos)}")
    perfis = args.perfis or list(comum.PERFIS)
    eventos = comum.carregar_yaml("config/calendario_economico.yaml").get("eventos") or []
    resultado = plano(args.data or comum.hoje_sp(), perfis, comum.RAIZ, rampa.carregar(), comum.grade(), eventos)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
