"""Leitura do PDF: extrai as linhas de texto com página e coordenadas."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pymupdf

# Linhas cuja altura (y) difere menos que isso são consideradas a mesma linha.
# Resolve textos justificados que o PDF quebra palavra por palavra.
TOLERANCIA_Y = 2.0


@dataclass(frozen=True)
class Linha:
    pagina: int  # 0-indexada, igual ao PyMuPDF
    texto: str
    bbox: pymupdf.Rect
    negrito: bool = False


def _juntar_mesma_altura(linhas: list[Linha]) -> list[Linha]:
    """Une pedaços que estão na mesma altura da página em uma única linha."""
    linhas = sorted(linhas, key=lambda l: (l.pagina, round(l.bbox.y0), l.bbox.x0))
    resultado: list[Linha] = []
    for linha in linhas:
        anterior = resultado[-1] if resultado else None
        if (
            anterior
            and anterior.pagina == linha.pagina
            and abs(anterior.bbox.y0 - linha.bbox.y0) < TOLERANCIA_Y
        ):
            resultado[-1] = Linha(
                pagina=linha.pagina,
                texto=f"{anterior.texto.rstrip()} {linha.texto.lstrip()}",
                bbox=anterior.bbox | linha.bbox,
                negrito=anterior.negrito and linha.negrito,
            )
        else:
            resultado.append(linha)
    return resultado


def extrair_linhas(caminho: str | Path) -> list[Linha]:
    """Retorna todas as linhas não vazias do PDF, em ordem de leitura."""
    linhas: list[Linha] = []
    with pymupdf.open(caminho) as doc:
        for pagina in doc:
            dados = pagina.get_text("dict", sort=True)
            for bloco in dados["blocks"]:
                for l in bloco.get("lines", []):
                    spans = [s for s in l["spans"] if s["text"].strip()]
                    if not spans:
                        continue
                    texto = "".join(s["text"] for s in l["spans"]).strip()
                    negrito = all("Bold" in s["font"] for s in spans)
                    linhas.append(
                        Linha(pagina.number, texto, pymupdf.Rect(l["bbox"]), negrito)
                    )
    return _juntar_mesma_altura(linhas)


def tem_texto(caminho: str | Path, minimo_caracteres: int = 50) -> bool:
    """Indica se o PDF tem texto digital (se não tiver, vai precisar de OCR)."""
    with pymupdf.open(caminho) as doc:
        return sum(len(p.get_text().strip()) for p in doc) >= minimo_caracteres
