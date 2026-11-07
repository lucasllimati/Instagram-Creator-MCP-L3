"""Gera gráficos em SVG diretamente dos dados, sem números digitados por IA."""
from __future__ import annotations

import datetime as dt
import math
from html import escape

import comum

PASSOS = (0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 50)


def recorte(pontos: list[dict], inicio: str, fim: str, degrau: bool = False) -> list[dict]:
    saida = [p for p in pontos if inicio <= p["data"] <= fim]
    if degrau and (not saida or saida[0]["data"] != inicio):
        vigente = comum.valor_em(pontos, inicio)
        if vigente is not None:
            saida.insert(0, {"data": inicio, "valor": vigente})
    return saida


def formatar(valor: float, unidade: str = "%") -> str:
    return f"{valor:.2f}".replace(".", ",") + unidade


def _rotulo_eixo(valor: float, unidade: str) -> str:
    return f"{round(valor, 2):g}".replace(".", ",") + unidade


def marcas_eixo(minimo: float, maximo: float, max_marcas: int = 6) -> list[float]:
    """Valores redondos que cobrem o intervalo."""
    if minimo == maximo:
        minimo, maximo = minimo - 0.5, maximo + 0.5
    for passo in PASSOS:
        inicio = math.floor(minimo / passo)
        fim = math.ceil(maximo / passo)
        if fim - inicio + 1 <= max_marcas:
            return [round(i * passo, 2) for i in range(inicio, fim + 1)]
    raise ValueError("intervalo grande demais para o eixo")


def lado_rotulo(pontos: list[dict]) -> str:
    """Coloca o rótulo final no lado oposto ao de onde a linha chega."""
    ultimo = pontos[-1]["valor"]
    for p in reversed(pontos[:-1]):
        if p["valor"] != ultimo:
            return "abaixo" if ultimo < p["valor"] else "acima"
    return "acima"


def vertices(pontos: list[dict], degrau: bool, x, y) -> list[tuple]:
    saida = []
    anterior = None
    for p in pontos:
        px, py = x(p["data"]), y(p["valor"])
        if degrau and anterior is not None and p["valor"] != anterior:
            saida.append((px, y(anterior)))
        saida.append((px, py))
        anterior = p["valor"]
    return saida


def svg_serie(pontos: list[dict], cores: dict, degrau: bool, largura: int = 920, altura: int = 720, unidade: str = "%") -> str:
    if not pontos:
        raise ValueError("série sem pontos")
    ordinais = [comum.data_iso(p["data"]).toordinal() for p in pontos]
    x0, x1 = min(ordinais), max(ordinais)
    marcas = marcas_eixo(min(p["valor"] for p in pontos), max(p["valor"] for p in pontos))
    v0, v1 = marcas[0], marcas[-1]
    esq, dir_, topo, base = 100, 24, 30, 64
    area_l, area_a = largura - esq - dir_, altura - topo - base

    def x(data):
        o = comum.data_iso(data).toordinal()
        return round(esq + (o - x0) / max(x1 - x0, 1) * area_l, 1)

    def y(valor):
        return round(topo + (v1 - valor) / (v1 - v0) * area_a, 1)

    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" viewBox="0 0 {largura} {altura}" '
        f'font-family="Inter, sans-serif" fill="{escape(cores["texto"])}">'
    ]
    for valor in marcas:
        py = y(valor)
        partes.append(f'<line x1="{esq}" x2="{largura - dir_}" y1="{py}" y2="{py}" stroke="{escape(cores["grade"])}" stroke-width="2"/>')
        partes.append(f'<text x="{esq - 14}" y="{py + 11}" text-anchor="end" font-size="30">{escape(_rotulo_eixo(valor, unidade))}</text>')

    inicio_ano = dt.date.fromordinal(x0).year
    fim_ano = dt.date.fromordinal(x1).year
    passo = max(1, (fim_ano - inicio_ano + 1) // 5)
    for ano in range(inicio_ano + 1, fim_ano + 1, passo):
        px = x(f"{ano}-01-01")
        partes.append(f'<line x1="{px}" x2="{px}" y1="{altura - base}" y2="{altura - base + 12}" stroke="{escape(cores["texto"])}" stroke-width="2"/>')
        partes.append(f'<text x="{px}" y="{altura - 12}" text-anchor="middle" font-size="30">{ano}</text>')

    linha = " ".join(f"{a},{b}" for a, b in vertices(pontos, degrau, x, y))
    partes.append(f'<polyline points="{linha}" fill="none" stroke="{escape(cores["linha"])}" stroke-width="9" stroke-linejoin="round" stroke-linecap="round"/>')

    ux, uy = x(pontos[-1]["data"]), y(pontos[-1]["valor"])
    partes.append(f'<circle cx="{ux}" cy="{uy}" r="15" fill="{escape(cores["destaque"])}"/>')
    abaixo = lado_rotulo(pontos) == "abaixo" and uy + 84 <= altura - base
    rotulo_y = uy + 84 if abaixo else max(uy - 34, 62)
    partes.append(
        f'<text x="{largura - dir_}" y="{rotulo_y}" text-anchor="end" font-size="64" font-weight="800" '
        f'font-family="Montserrat, sans-serif">{escape(formatar(pontos[-1]["valor"], unidade))}</text>'
    )
    partes.append("</svg>")
    return "".join(partes)
