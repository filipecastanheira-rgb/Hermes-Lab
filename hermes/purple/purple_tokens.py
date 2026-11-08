"""Token management from the command line.

Tokens are stored as hashes, so the value exists only when it is created. Without
a command, adding a token for another person meant writing Python by hand - which
made "one token per person" unusable in practice.
"""


def criar(store, nome="token"):
    """Create a token and return (id, token). The token is shown once."""
    token = store.criar(nome)
    return store.dados["tokens"][-1]["id"], token


def listar(store):
    """Metadata of every configured token. Never includes a token or a hash."""
    return store.listar()


def revogar(store, token_id):
    return store.revogar(str(token_id))


def formatar_lista(tokens):
    if not tokens:
        return "No tokens configured."
    return "\n".join(f"{t['id']}  {t['nome']}  {t['criado_em']}" for t in tokens)


def utilizacao():
    return (
        "Usage:\n"
        "  python3 hermes_cli.py tokens criar <nome>\n"
        "  python3 hermes_cli.py tokens listar\n"
        "  python3 hermes_cli.py tokens revogar <id>"
    )
