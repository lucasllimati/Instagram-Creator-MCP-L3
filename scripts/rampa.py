"""Subida gradual de volume definida em config/rampa.yaml."""
from __future__ import annotations

import datetime as dt

import comum


def carregar() -> dict:
    return comum.carregar_yaml("config/rampa.yaml")


def _segunda(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def indice_semana(data: dt.date, cfg: dict) -> int:
    if not cfg.get("inicio"):
        return 1
    inicio = _segunda(comum.data_iso(cfg["inicio"]))
    return max(1, (_segunda(data) - inicio).days // 7 + 1)


def regra(data: dt.date, cfg: dict) -> dict:
    semanas = {int(k): v for k, v in cfg["semanas"].items()}
    return semanas[min(indice_semana(data, cfg), max(semanas))]


def stories_ativos(data: dt.date, cfg: dict) -> bool:
    return bool(regra(data, cfg)["stories"])
