"""Renova os tokens longos do Instagram e atualiza o GitHub Secrets.

Roda no GitHub Actions, a cada mês, para ter folga antes do fim dos 60 dias.
A Meta exige que o token tenha pelo menos 24 horas e ainda esteja válido.
"""
from __future__ import annotations

import os
import subprocess
import sys

import requests

import comum

URL = "https://graph.instagram.com/refresh_access_token"


def renovar(nome_segredo: str, token: str, pat: str, executar=subprocess.run) -> bool:
    try:
        r = requests.get(URL, params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=60)
    except requests.RequestException as e:
        print(f"{nome_segredo}: falha de rede ({type(e).__name__})")
        return False
    if r.status_code != 200:
        # O corpo e a URL não são exibidos, pois podem conter o token.
        print(f"{nome_segredo}: renovação recusada (HTTP {r.status_code})")
        return False
    novo = r.json().get("access_token")
    if not novo:
        print(f"{nome_segredo}: resposta sem token")
        return False
    if os.environ.get("GITHUB_ACTIONS") == "true":
        print(f"::add-mask::{novo}")
    resultado = executar(
        ["gh", "secret", "set", nome_segredo],
        input=novo,
        text=True,
        capture_output=True,
        env={**os.environ, "GH_TOKEN": pat},
    )
    if resultado.returncode != 0:
        print(f"{nome_segredo}: não foi possível gravar o segredo")
        return False
    print(f"{nome_segredo}: renovado; validade de {r.json().get('expires_in', '?')} segundos")
    return True


def main() -> int:
    pat = os.environ.get("SECRETS_PAT", "")
    if not pat:
        print("Falta o segredo SECRETS_PAT.")
        return 1
    ok = True
    for perfil in comum.PERFIS:
        nome = f"IG_TOKEN_{perfil}"
        token = os.environ.get(nome, "")
        if not token:
            print(f"{nome}: não configurado")
            ok = False
            continue
        ok = renovar(nome, token, pat) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
