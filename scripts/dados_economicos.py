"""Baixa séries do SGS (Banco Central) e grava em dados/.

Uso: python scripts/dados_economicos.py [--ate AAAA-MM-DD]

`--ate` permite ler o dia seguinte na noite de uma decisão do Copom, quando a
taxa nova já consta como vigente amanhã. Por padrão, nada depois de hoje é gravado.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import requests

import comum

URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"


class ErroDados(Exception):
    pass


def _br_para_data(texto: str) -> dt.date:
    return dt.datetime.strptime(texto, "%d/%m/%Y").date()


def limpar(bruto: list[dict], limite: dt.date, degrau: bool) -> list[dict]:
    """Converte, ordena e descarta datas posteriores ao limite.

    A série 432 traz datas futuras (até a próxima reunião), por isso o corte.
    """
    pontos = sorted(
        ({"data": _br_para_data(x["data"]).isoformat(), "valor": float(x["valor"])} for x in bruto),
        key=lambda p: p["data"],
    )
    pontos = [p for p in pontos if p["data"] <= limite.isoformat()]
    if not degrau or not pontos:
        return pontos
    saida = [pontos[0]]
    for p in pontos[1:]:
        if p["valor"] != saida[-1]["valor"]:
            saida.append(p)
    if saida[-1]["data"] != pontos[-1]["data"]:
        saida.append(pontos[-1])
    return saida


def baixar(serie: dict, hoje: dt.date, limite: dt.date | None = None) -> dict:
    limite = limite or hoje
    inicio = hoje.replace(year=hoje.year - serie["anos"], day=min(hoje.day, 28))
    params = {"formato": "json", "dataInicial": inicio.strftime("%d/%m/%Y"), "dataFinal": limite.strftime("%d/%m/%Y")}
    try:
        r = requests.get(URL.format(codigo=serie["codigo"]), params=params, timeout=30)
        r.raise_for_status()
        bruto = r.json()
    except (requests.RequestException, ValueError) as e:
        raise ErroDados(f"série {serie['codigo']}: {type(e).__name__}") from e
    pontos = limpar(bruto, limite, serie["degrau"]) if bruto else []
    if not pontos:
        raise ErroDados(f"série {serie['codigo']}: resposta sem dados")
    return {
        "serie": serie["codigo"],
        "nome": serie["nome"],
        "fonte": f"Banco Central, SGS série {serie['codigo']}",
        "coletado_em": hoje.isoformat(),
        "degrau": serie["degrau"],
        "pontos": pontos,
    }


def atualizar(series: list[dict], hoje: dt.date, pasta: Path, limite: dt.date | None = None) -> list[int]:
    """Grava cada série; uma falha mantém o arquivo anterior intacto."""
    falhas = []
    for serie in series:
        try:
            comum.gravar_json(pasta / f"sgs_{serie['codigo']}.json", baixar(serie, hoje, limite))
        except ErroDados as e:
            print(f"FALHA {e}", file=sys.stderr)
            falhas.append(serie["codigo"])
    return falhas


def fatos_copom(pontos: list[dict], reuniao: dt.date) -> dict:
    """Compara a meta na reunião e no dia seguinte, quando a decisão passa a valer."""
    seguinte = reuniao + dt.timedelta(days=1)
    if not pontos or pontos[-1]["data"] < seguinte.isoformat():
        raise ErroDados(f"série ainda não cobre {seguinte.isoformat()}; rode com --ate {seguinte.isoformat()}")
    anterior = comum.valor_em(pontos, reuniao)
    atual = comum.valor_em(pontos, seguinte)
    if anterior is None or atual is None:
        raise ErroDados("série não cobre a data da reunião")
    direcao = "subiu" if atual > anterior else "cortou" if atual < anterior else "sem_mudanca_na_serie"
    return {
        "reuniao": reuniao.isoformat(),
        "vigente_em": seguinte.isoformat(),
        "anterior": anterior,
        "atual": atual,
        "variacao": round(atual - anterior, 2),
        "direcao": direcao,
        # A série não distingue manutenção de dado ainda não atualizado.
        "confirmar_no_comunicado": direcao == "sem_mudanca_na_serie",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ate", type=dt.date.fromisoformat)
    args = ap.parse_args(argv)
    series = comum.carregar_yaml("config/fontes.yaml")["series_sgs"]
    falhas = atualizar(series, comum.hoje_sp(), comum.RAIZ / "dados", args.ate)
    print("Falhas: " + ", ".join(map(str, falhas)) if falhas else f"{len(series)} séries atualizadas")
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
