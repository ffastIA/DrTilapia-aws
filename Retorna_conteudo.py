import os
import argparse
from fnmatch import fnmatch

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
)

try:
    pdfmetrics.registerFont(TTFont("DejaVuSans", "DejaVuSans.ttf"))
    FONTE_PADRAO = "DejaVuSans"
except Exception:
    FONTE_PADRAO = "Helvetica"

EXTENSOES_PADRAO = (
    ".py", ".txt", ".md", ".json", ".xml",
    ".html", ".css", ".js", ".mjs", ".ts",
    ".tsx", ".yml"
)

DIRETORIOS_IGNORADOS_PADRAO = (
    ".git", "__pycache__", ".vscode", ".idea",
    "node_modules", "build", "dist"
)

ARQUIVOS_IGNORADOS_PADRAO = (
    "*.pyc", "*.log", "*.tmp", "*.bak",
    "*~", "*.swp", "*.DS_Store", "Thumbs.db", "*.pyo"
)

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="TituloRelatorio",
    fontSize=18,
    leading=22,
    spaceAfter=12,
    fontName=FONTE_PADRAO,
))
styles.add(ParagraphStyle(
    name="TituloDiretorio",
    fontSize=15,
    leading=18,
    spaceBefore=10,
    spaceAfter=8,
    fontName=FONTE_PADRAO,
))
styles.add(ParagraphStyle(
    name="TituloArquivo",
    fontSize=12,
    leading=14,
    spaceBefore=6,
    spaceAfter=4,
    fontName=FONTE_PADRAO,
))
styles.add(ParagraphStyle(
    name="TextoNormalFonte",
    parent=styles["Normal"],
    fontName=FONTE_PADRAO,
    leading=12,
))
styles.add(ParagraphStyle(
    name="TextoCodigo",
    fontName="Courier",
    fontSize=8,
    leading=9,
))
styles.add(ParagraphStyle(
    name="TituloSumario",
    fontSize=16,
    leading=20,
    spaceAfter=12,
    fontName=FONTE_PADRAO,
))


def arquivo_deve_ser_ignorado(nome_arquivo, padroes_ignorados):
    return any(fnmatch(nome_arquivo, padrao) for padrao in padroes_ignorados)


def criar_numero_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont(FONTE_PADRAO, 9)
    canvas.drawRightString(letter[0] - 0.5 * inch, 0.5 * inch, f"Página {doc.page}")
    canvas.restoreState()


def gerar_relatorio_pdf(
    diretorio_raiz,
    arquivo_saida,
    extensoes_filtro=None,
    diretorios_excluir_adicional=None,
    arquivos_excluir_adicional=None,
):
    if extensoes_filtro is None:
        extensoes_filtro = EXTENSOES_PADRAO
    else:
        extensoes_filtro = tuple(extensoes_filtro)

    if diretorios_excluir_adicional is None:
        diretorios_excluir_adicional = ()
    else:
        diretorios_excluir_adicional = tuple(diretorios_excluir_adicional)

    if arquivos_excluir_adicional is None:
        arquivos_excluir_adicional = ()
    else:
        arquivos_excluir_adicional = tuple(arquivos_excluir_adicional)

    diretorios_ignorados = tuple(set(DIRETORIOS_IGNORADOS_PADRAO + diretorios_excluir_adicional))
    arquivos_ignorados = tuple(set(ARQUIVOS_IGNORADOS_PADRAO + arquivos_excluir_adicional))

    estrutura = []
    total_arquivos = 0
    total_diretorios = 0

    for raiz, dirs, arquivos in os.walk(diretorio_raiz):
        dirs[:] = [
            d for d in dirs
            if not d.startswith(".") and d not in diretorios_ignorados
        ]

        arquivos_validos = []
        for nome_arquivo in sorted(arquivos):
            if not nome_arquivo.endswith(extensoes_filtro):
                continue
            if arquivo_deve_ser_ignorado(nome_arquivo, arquivos_ignorados):
                continue

            caminho_arquivo = os.path.join(raiz, nome_arquivo)
            try:
                with open(caminho_arquivo, "r", encoding="utf-8") as f:
                    conteudo = f.read()
            except UnicodeDecodeError:
                conteudo = "[Erro: arquivo binário ou encoding inválido - conteúdo omitido]"
            except Exception as e:
                conteudo = f"[Erro ao ler: {str(e)}]"

            arquivos_validos.append({
                "nome": nome_arquivo,
                "caminho": os.path.relpath(caminho_arquivo, diretorio_raiz),
                "conteudo": conteudo,
            })
            total_arquivos += 1

        if arquivos_validos:
            caminho_relativo = os.path.relpath(raiz, diretorio_raiz)
            estrutura.append({
                "diretorio": diretorio_raiz if caminho_relativo == "." else caminho_relativo,
                "arquivos": arquivos_validos,
            })
            total_diretorios += 1

    doc = SimpleDocTemplate(
        arquivo_saida,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=54,
        bottomMargin=54,
        title="Relatório de Diretório",
        author="Gerador de Relatório",
    )

    story = []

    story.append(Paragraph("Relatório de Conteúdo do Diretório", styles["TituloRelatorio"]))
    story.append(Paragraph(f"Diretório raiz: {os.path.abspath(diretorio_raiz)}", styles["TextoNormalFonte"]))
    story.append(Paragraph(f"Total de diretórios com conteúdo: {total_diretorios}", styles["TextoNormalFonte"]))
    story.append(Paragraph(f"Total de arquivos incluídos: {total_arquivos}", styles["TextoNormalFonte"]))
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("Sumário", styles["TituloSumario"]))

    tabela_sumario = [["Seção", "Arquivos"]]
    for secao in estrutura:
        tabela_sumario.append([secao["diretorio"], str(len(secao["arquivos"]))])

    tabela = Table(tabela_sumario, colWidths=[4.8 * inch, 1.2 * inch])
    tabela.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, -1), FONTE_PADRAO),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 11),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightyellow]),
    ]))
    story.append(tabela)
    story.append(PageBreak())

    for indice, secao in enumerate(estrutura, start=1):
        story.append(Paragraph(f"{indice}. Diretório: {secao['diretorio']}", styles["TituloDiretorio"]))
        story.append(Spacer(1, 0.08 * inch))

        for arquivo in secao["arquivos"]:
            story.append(Paragraph(f"Arquivo: {arquivo['caminho']}", styles["TituloArquivo"]))
            story.append(Preformatted(arquivo["conteudo"], styles["TextoCodigo"]))
            story.append(Spacer(1, 0.16 * inch))

        if indice < len(estrutura):
            story.append(PageBreak())

    doc.build(story, onFirstPage=criar_numero_pagina, onLaterPages=criar_numero_pagina)


if __name__ == "__main__":
    gerar_relatorio_pdf(
        diretorio_raiz=r"C:\Users\usuario\Python\DrTilapIA",
        arquivo_saida=r"C:\Users\usuario\Python\DrTilapIA\Codigo210526.pdf",
        extensoes_filtro=(
            ".py", ".txt", ".md", ".json", ".xml",
            ".html", ".css", ".js", ".mjs", ".ts",
            ".tsx", ".yml"
        ),
        diretorios_excluir_adicional=(
            ".git", "__pycache__", ".vscode", ".idea",
            "node_modules", "build", "dist",
        ),
        arquivos_excluir_adicional=()
    )

    print(r"Relatório PDF gerado com sucesso em: C:\Users\usuario\Python\DrTilapIA\Codigo.pdf")