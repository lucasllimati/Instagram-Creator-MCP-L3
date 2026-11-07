"""Busca os insights dos posts recentes e grava em relatorios/dados/AAAA-WW.json.

Roda no GitHub Actions, que tem os tokens. A Meta avisa que os dados podem
demorar até 48 horas e que a resposta pode vir vazia.
"""
from __future__ import annotations

import datetime as dt
import os
import sys
from pathlib import Path

import requests

import comum

METRICAS = "reach,saved,shares,comments,likes"
JANELA_DIAS = 14


def coletar_post(media_id: str, token: str, api: dict) -> dict:
    r = requests.get(
        f"{api['base']}/{api['versao']}/{media_id}/insights",
        params={"metric": METRICAS},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}")
    saida = {}
    for item in r.json().get("data", []):
        if item.get("values"):
            saida[item["name"]] = item["values"][0].get("value")
        elif item.get("total_value"):
            saida[item["name"]] = item["total_value"].get("value")
    return saida


def taxa(metricas: dict) -> float | None:
    """Métrica principal: (salvamentos + compartilhamentos) / alcance."""
    alcance = metricas.get("reach")
    if not alcance:
        return None
    return round((metricas.get("saved", 0) + metricas.get("shares", 0)) / alcance, 4)


def executar(tokens: dict, raiz: Path, hoje: dt.date) -> tuple[Path, int]:
    api = comum.limites(raiz)["api"]
    corte = (hoje - dt.timedelta(days=JANELA_DIAS)).isoformat()
    posts, falhas = [], 0
    for l in comum.ler_publicacoes(raiz):
        if l.get("status") != "publicado" or l["data"] < corte or l.get("media_id") in ("", "desconhecido", None):
            continue
        token = tokens.get(l["perfil"])
        base = {"id": l["id"], "perfil": l["perfil"], "pilar": l["pilar"], "data": l["data"]}
        try:
            if not token:
                raise RuntimeError("sem token")
            metricas = coletar_post(l["media_id"], token, api)
            posts.append({**base, **metricas, "taxa_salva_compartilha": taxa(metricas)})
        except (requests.RequestException, RuntimeError, ValueError) as e:
            falhas += 1
            print(f"AVISO {l['id']}: insights indisponíveis ({e})")
            posts.append({**base, "indisponivel": True})
    ano, semana, _ = hoje.isocalendar()
    caminho = raiz / "relatorios" / "dados" / f"{ano}-{semana:02d}.json"
    comum.gravar_json(caminho, {"coletado_em": hoje.isoformat(), "posts": posts})
    return caminho, falhas


def main() -> int:
    tokens = {p: os.environ.get(f"IG_TOKEN_{p}", "") for p in comum.PERFIS}
    caminho, falhas = executar(tokens, comum.RAIZ, comum.hoje_sp())
    print(f"{caminho.name}: {falhas} post(s) sem dados")
    return 0


if __name__ == "__main__":
    sys.exit(main())
