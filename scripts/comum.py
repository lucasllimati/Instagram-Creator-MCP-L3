"""Utilitários compartilhados: caminhos, configuração, datas e leitura da fila."""
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

RAIZ = Path(__file__).resolve().parents[1]
PERFIS = ("FIN", "MKT")
TZ = ZoneInfo("America/Sao_Paulo")
COLUNAS_PUBLICACOES = ["id", "data", "perfil", "pilar", "tema_slug", "titulo", "media_id", "permalink", "publicado_em", "status"]


def carregar_yaml(relativo: str, raiz: Path = RAIZ) -> dict:
    with open(raiz / relativo, encoding="utf-8") as f:
        return yaml.safe_load(f)


def limites(raiz: Path = RAIZ) -> dict:
    return carregar_yaml("config/limites.yaml", raiz)


def grade(raiz: Path = RAIZ) -> dict:
    return carregar_yaml("config/grade.yaml", raiz)


def marca(perfil: str, raiz: Path = RAIZ) -> dict:
    return carregar_yaml(f"marcas/{perfil.lower()}.yaml", raiz)


def hoje_sp() -> dt.date:
    return dt.datetime.now(TZ).date()


def data_iso(valor) -> dt.date:
    return valor if isinstance(valor, dt.date) else dt.date.fromisoformat(str(valor))


def ler_json(caminho: Path, padrao=None):
    if not caminho.exists():
        return padrao
    return json.loads(caminho.read_text(encoding="utf-8"))


def gravar_json(caminho: Path, dados) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def pasta_post(raiz: Path, data, perfil: str, evento: bool = False) -> Path:
    return raiz / "fila" / str(data) / (f"{perfil}-evento" if evento else perfil)


def posts_da_fila(raiz: Path = RAIZ) -> list[tuple[Path, dict]]:
    """Todos os post.json da fila, em ordem de caminho."""
    return [(p, ler_json(p)) for p in sorted((raiz / "fila").glob("*/*/post.json"))]


def ler_publicacoes(raiz: Path = RAIZ) -> list[dict]:
    caminho = raiz / "historico" / "publicacoes.csv"
    if not caminho.exists():
        return []
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def acrescentar_publicacao(linha: dict, raiz: Path = RAIZ) -> None:
    caminho = raiz / "historico" / "publicacoes.csv"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    novo = not caminho.exists() or caminho.stat().st_size == 0
    with open(caminho, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS_PUBLICACOES)
        if novo:
            w.writeheader()
        w.writerow({k: linha.get(k, "") for k in COLUNAS_PUBLICACOES})


def valor_em(pontos: list[dict], data) -> float | None:
    """Valor vigente na data, em uma série ordenada de pontos {data, valor}."""
    alvo = data_iso(data)
    atual = None
    for p in pontos:
        if data_iso(p["data"]) > alvo:
            break
        atual = p["valor"]
    return atual
