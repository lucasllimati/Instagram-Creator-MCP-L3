"""Cria o esqueleto de um post de evento, com números vindos direto da série oficial.

Uso:
  python scripts/evento.py copom --reuniao 2026-12-09
  python scripts/evento.py noticia <id-do-radar> --data 2026-12-10

Os campos [preencher] são do Roteirista. O validador reprova o post se algum
deles chegar à etapa de publicação.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import comum
import dados_economicos as de
import grafico

PREENCHER = "[preencher]"
VERBOS = {"cortou": "reduziu", "subiu": "aumentou"}


def _preparar_pasta(raiz: Path, data, perfil: str) -> Path:
    pasta = comum.pasta_post(raiz, data, perfil, evento=True)
    if (pasta / "post.json").exists():
        raise FileExistsError(f"{pasta / 'post.json'} já existe")
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def preparar_copom(reuniao: dt.date, raiz: Path = comum.RAIZ, hoje: dt.date | None = None) -> Path:
    hoje = hoje or comum.hoje_sp()
    serie = comum.ler_json(raiz / "dados" / "sgs_432.json")
    if serie is None:
        raise de.ErroDados("dados/sgs_432.json não encontrado; rode scripts/dados_economicos.py")
    fatos = de.fatos_copom(serie["pontos"], reuniao)
    data = reuniao + dt.timedelta(days=1)
    atual, anterior = grafico.formatar(fatos["atual"]), grafico.formatar(fatos["anterior"])
    dia_br = data.strftime("%d/%m/%Y")

    if fatos["direcao"] in VERBOS:
        capa = f"Copom {fatos['direcao']} a Selic: {atual}"
        texto = (
            f"O Copom, comitê do Banco Central, {VERBOS[fatos['direcao']]} a meta da Selic "
            f"de {anterior} para {atual} ao ano. A taxa nova vale desde {dia_br}."
        )
        status = "roteiro"
    else:
        # A série não prova manutenção. Exige conferir o comunicado antes de afirmar.
        capa = f"Decisão do Copom: Selic em {atual}"
        texto = f"A série do Banco Central mostra a meta da Selic em {atual} em {dia_br}. {PREENCHER} confirmar no comunicado."
        status = "revisar_humano"

    inicio = f"{reuniao.year - 2}-01-01"
    post = {
        "id": f"FIN-{data.isoformat()}-evento",
        "perfil": "FIN",
        "data": data.isoformat(),
        "pilar": "evento",
        "formato": "carrossel",
        "prioridade": "evento",
        "titulo": capa,
        "tema_slug": f"copom-{reuniao.strftime('%Y-%m')}",
        "status": status,
        "valido_ate": (data + dt.timedelta(days=1)).isoformat(),
        "slides": [
            {"n": 1, "tipo": "capa", "titulo": capa, "texto": "O que mudou e o que isso muda para você"},
            {"n": 2, "tipo": "conteudo", "titulo": "O que aconteceu", "texto": texto},
            {"n": 3, "tipo": "grafico", "titulo": f"A Selic desde {reuniao.year - 2}", "serie": 432},
            {"n": 4, "tipo": "conteudo", "titulo": "Por que importa", "texto": PREENCHER},
            {"n": 5, "tipo": "conteudo", "titulo": "Onde o efeito aparece", "itens": [f"Crédito: {PREENCHER}", f"Renda fixa: {PREENCHER}", f"Poupança: {PREENCHER}"]},
            {"n": 6, "tipo": "conteudo", "titulo": "O que observar", "texto": PREENCHER},
            {"n": 7, "tipo": "cta", "titulo": "Resumo", "texto": PREENCHER, "cta": "Salve para consultar depois"},
        ],
        "stories": [{"tipo": "chamada", "texto": "Decisão do Copom: veja o que muda no post de hoje"}],
        "fontes": [
            {
                "descricao": "Meta da Selic, série SGS 432",
                "url": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados?formato=json",
                "data": serie["coletado_em"],
                "veiculo": "Banco Central",
                "primaria": True,
            }
        ],
        "dados_ref": {
            "serie": 432,
            "inicio": inicio,
            "fim": data.isoformat(),
            "coletado_em": serie["coletado_em"],
            "valores_declarados": [
                {"data": reuniao.isoformat(), "valor": fatos["anterior"]},
                {"data": data.isoformat(), "valor": fatos["atual"]},
            ],
        },
    }
    pasta = _preparar_pasta(raiz, data, "FIN")
    comum.gravar_json(pasta / "fatos.json", fatos)
    comum.gravar_json(pasta / "post.json", post)
    return pasta


def _buscar_no_radar(ident: str, raiz: Path) -> tuple[str, dict]:
    for arquivo in sorted((raiz / "pesquisa" / "radar").glob("*.json"), reverse=True):
        dados = comum.ler_json(arquivo, {})
        for perfil in comum.PERFIS:
            for item in dados.get(perfil, []):
                if item["id"] == ident:
                    return perfil, item
    raise LookupError(f"item {ident} não encontrado no radar")


def preparar_noticia(ident: str, raiz: Path = comum.RAIZ, hoje: dt.date | None = None, data: dt.date | None = None) -> Path:
    hoje = hoje or comum.hoje_sp()
    data = data or hoje
    perfil, item = _buscar_no_radar(ident, raiz)
    post = {
        "id": f"{perfil}-{data.isoformat()}-evento",
        "perfil": perfil,
        "data": data.isoformat(),
        "pilar": "atualidade",
        "formato": "carrossel",
        "prioridade": "evento",
        "titulo": PREENCHER,
        "tema_slug": f"noticia-{ident}",
        "status": "roteiro",
        "valido_ate": (data + dt.timedelta(days=2)).isoformat(),
        "slides": [
            {"n": 1, "tipo": "capa", "titulo": PREENCHER},
            {"n": 2, "tipo": "conteudo", "titulo": "O que aconteceu", "texto": PREENCHER},
            {"n": 3, "tipo": "conteudo", "titulo": "Por que importa", "texto": PREENCHER},
            {"n": 4, "tipo": "conteudo", "titulo": "O que fazer", "texto": PREENCHER},
            {"n": 5, "tipo": "cta", "titulo": "Resumo", "texto": PREENCHER, "cta": "Salve para consultar depois"},
        ],
        "stories": [{"tipo": "chamada", "texto": PREENCHER}],
        "fontes": [{"descricao": PREENCHER, "url": item["link"], "data": item["data"], "veiculo": item["fonte"]}],
    }
    pasta = _preparar_pasta(raiz, data, perfil)
    comum.gravar_json(pasta / "post.json", post)
    return pasta


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="tipo", required=True)
    c = sub.add_parser("copom")
    c.add_argument("--reuniao", type=dt.date.fromisoformat, default=comum.hoje_sp())
    n = sub.add_parser("noticia")
    n.add_argument("ident")
    n.add_argument("--data", type=dt.date.fromisoformat)
    args = ap.parse_args(argv)
    try:
        pasta = preparar_copom(args.reuniao) if args.tipo == "copom" else preparar_noticia(args.ident, data=args.data)
    except (de.ErroDados, LookupError, FileExistsError) as e:
        print(f"ERRO: {e}")
        return 1
    print(pasta)
    fatos = comum.ler_json(pasta / "fatos.json")
    if fatos and fatos["confirmar_no_comunicado"]:
        print("ATENÇÃO: a série não mostra mudança. Confirme a decisão no comunicado oficial antes de afirmar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
