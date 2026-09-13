from pathlib import Path

# Diretórios considerados "lixo" em projetos reais
IGNORAR_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "__pycache__",
    "node_modules",
    ".pytest_cache",
    "dist",
    "build",
    "venv",
    "env",
}

# Arquivos inúteis também podem ser ignorados aqui
IGNORAR_ARQUIVOS = {
    ".DS_Store",
    "Thumbs.db",
}


def gerar_arvore(diretorio, prefixo=""):
    caminho = Path(diretorio)

    # Lista somente itens relevantes
    itens = []
    for item in caminho.iterdir():

        # Ignorar ocultos (.qualquercoisa)
        if item.name.startswith(".") and item.name != ".gitignore":
            continue

        # Ignorar diretórios lixo
        if item.is_dir() and item.name in IGNORAR_DIRS:
            continue

        # Ignorar arquivos lixo
        if item.is_file() and item.name in IGNORAR_ARQUIVOS:
            continue

        itens.append(item)

    # Ordenação: pastas primeiro, depois arquivos
    itens.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

    total = len(itens)
    for index, item in enumerate(itens):
        ultimo = (index == total - 1)
        conector = "└── " if ultimo else "├── "

        print(prefixo + conector + item.name)

        if item.is_dir():
            novo_prefixo = prefixo + ("    " if ultimo else "│   ")
            gerar_arvore(item, novo_prefixo)


# --- Execução ---
print("📦 Estrutura do Projeto (clean):")
gerar_arvore(".")