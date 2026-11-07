"""Os exemplos servem de modelo para os agentes, então precisam ser válidos."""
import datetime as dt

import pytest

import comum
import validar


@pytest.mark.parametrize("perfil", comum.PERFIS)
def test_exemplo_passa_nos_validadores(perfil):
    ctx = validar.carregar_contexto(hoje=dt.date(2026, 11, 7))
    ctx.fila, ctx.publicacoes = [], []
    post = comum.ler_json(comum.RAIZ / "exemplos" / perfil / "post.json")
    if post.get("dados_ref"):
        arquivo = comum.ler_json(ctx.dados_dir / f"sgs_{post['dados_ref']['serie']}.json")
        if arquivo is None:
            pytest.skip("dados ainda não baixados")
    assert [str(e) for e in validar.validar_post(post, ctx)] == []
