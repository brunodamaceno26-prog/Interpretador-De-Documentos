"""Divisão do contrato em cláusulas e dispositivos, guardando onde cada um está no PDF."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

import pymupdf

from contratos.ingestao.leitor import Linha

ORDINAIS = {
    "primeira": 1, "segunda": 2, "terceira": 3, "quarta": 4, "quinta": 5,
    "sexta": 6, "setima": 7, "oitava": 8, "nona": 9, "decima": 10,
    "decima primeira": 11, "decima segunda": 12, "decima terceira": 13,
    "decima quarta": 14, "decima quinta": 15, "decima sexta": 16,
    "decima setima": 17, "decima oitava": 18, "decima nona": 19, "vigesima": 20,
}

# "Cláusula Primeira: Objeto", "CLÁUSULA 1ª - DO OBJETO", "Cláusula 2 – Prazo"
RE_CLAUSULA = re.compile(
    r"^cl[aá]usula\s+"
    r"(?P<num>\d+\s*[ªºa°]?|[a-zçéíú]+(?:\s+[a-zçéíú]+)?)"
    r"\s*(?:[:\-–—.]\s*(?P<titulo>.*))?$",
    re.IGNORECASE,
)

# Fim do corpo do contrato: data de assinatura, testemunhas ou linha de assinatura.
RE_FIM = re.compile(
    r"^(?:[\wÀ-ú .]+,\s*\d{1,2}\s+de\s+[a-zç]+\s+de\s+\d{4}\.?|testemunhas:?|_{5,}.*)$",
    re.IGNORECASE,
)

# Dispositivos dentro de uma cláusula
RE_PARAGRAFO = re.compile(r"^(?:§\s*(?P<num>\d+)\s*[º°o]?|(?P<unico>par[aá]grafo\s+[uú]nico))\s*[.:\-–]?\s*", re.IGNORECASE)
RE_INCISO = re.compile(r"^(?P<num>[IVXLC]+)\s*[.\-–)]\s+")
RE_ALINEA = re.compile(r"^(?P<num>[a-z])\s*[.)]\s+")


def sem_acento(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


def _numero(bruto: str) -> int | None:
    digitos = re.match(r"\d+", bruto)
    if digitos:
        return int(digitos.group())
    return ORDINAIS.get(sem_acento(bruto).strip())


@dataclass(frozen=True)
class Trecho:
    """Área retangular de uma página onde parte do texto aparece."""
    pagina: int
    area: pymupdf.Rect


def calcular_trechos(linhas: list[Linha], x0: float, x1: float, margem: float = 4.0) -> list[Trecho]:
    """Um retângulo por página, com largura fixa (x0..x1) para o recorte ficar alinhado."""
    resultado = []
    for pag in sorted({l.pagina for l in linhas}):
        ls = [l for l in linhas if l.pagina == pag]
        y0 = min(l.bbox.y0 for l in ls) - margem
        y1 = max(l.bbox.y1 for l in ls) + margem
        resultado.append(Trecho(pag, pymupdf.Rect(x0, y0, x1, y1)))
    return resultado


@dataclass
class Dispositivo:
    """Parte de uma cláusula: caput, parágrafo (§), inciso (I, II) ou alínea (a, b)."""
    tipo: str  # "caput" | "paragrafo" | "inciso" | "alinea"
    rotulo: str  # ex.: "§2º", "Parágrafo único", "II", "II, b"
    linhas: list[Linha] = field(default_factory=list)

    @property
    def texto(self) -> str:
        return "\n".join(l.texto for l in self.linhas)


@dataclass
class Clausula:
    numero: int | None  # None = preâmbulo
    titulo: str
    linhas: list[Linha] = field(default_factory=list)

    @property
    def texto(self) -> str:
        return "\n".join(l.texto for l in self.linhas)

    @property
    def paginas(self) -> list[int]:
        return sorted({l.pagina for l in self.linhas})

    def trechos(self, x0: float, x1: float, margem: float = 4.0) -> list[Trecho]:
        return calcular_trechos(self.linhas, x0, x1, margem)

    @property
    def rotulo(self) -> str:
        if self.numero is None:
            return "Preâmbulo"
        return f"Cláusula {self.numero}ª" + (f" – {self.titulo}" if self.titulo else "")

    @property
    def dispositivos(self) -> list[Dispositivo]:
        """Subdivide a cláusula. Alíneas herdam o inciso atual no rótulo ("II, b")."""
        corpo = self.linhas[1:] if self.numero is not None else self.linhas  # pula o título
        atual = Dispositivo("caput", "Caput")
        resultado = [atual]
        inciso = ""
        for linha in corpo:
            t = linha.texto
            if m := RE_PARAGRAFO.match(t):
                rotulo = "Parágrafo único" if m.group("unico") else f"§{m.group('num')}º"
                atual, inciso = Dispositivo("paragrafo", rotulo), ""
            elif m := RE_INCISO.match(t):
                inciso = m.group("num")
                atual = Dispositivo("inciso", inciso)
            elif m := RE_ALINEA.match(t):
                rotulo = f"{inciso}, {m.group('num')}" if inciso else m.group("num")
                atual = Dispositivo("alinea", rotulo)
            else:
                atual.linhas.append(linha)
                continue
            resultado.append(atual)
            atual.linhas.append(linha)
        return [d for d in resultado if d.linhas]

    def dispositivo(self, rotulo: str) -> Dispositivo:
        """Busca por rótulo, aceitando "§2", "2", "unico", "II", "II,b"."""
        def normalizar(texto: str) -> str:
            texto = re.sub(r"[§º°ª\s]", "", texto)  # antes do sem_acento, que troca º por "o"
            return sem_acento(texto).replace("paragrafounico", "unico")

        alvo = normalizar(rotulo)
        for d in self.dispositivos:
            if normalizar(d.rotulo) == alvo:
                return d
        raise KeyError(f"Dispositivo '{rotulo}' não encontrado na {self.rotulo}")


@dataclass
class Contrato:
    clausulas: list[Clausula]
    x0: float  # margem esquerda do texto
    x1: float  # margem direita do texto

    def clausula(self, numero: int) -> Clausula:
        for c in self.clausulas:
            if c.numero == numero:
                return c
        raise KeyError(f"Cláusula {numero} não encontrada")

    def buscar(self, termo: str) -> list[tuple[Clausula, Linha]]:
        """Busca simples por palavra, ignorando acentos e maiúsculas."""
        alvo = sem_acento(termo)
        return [
            (c, l) for c in self.clausulas for l in c.linhas if alvo in sem_acento(l.texto)
        ]


def estruturar(linhas: list[Linha]) -> Contrato:
    if not linhas:
        raise ValueError("Nenhum texto encontrado (PDF escaneado? Vai precisar de OCR).")

    atual = Clausula(numero=None, titulo="Preâmbulo")
    clausulas = [atual]
    for linha in linhas:
        m = RE_CLAUSULA.match(linha.texto)
        if m and _numero(m.group("num")) is not None:
            atual = Clausula(_numero(m.group("num")), (m.group("titulo") or "").strip())
            clausulas.append(atual)
        elif atual.numero is not None and RE_FIM.match(linha.texto):
            break  # chegou nas assinaturas
        atual.linhas.append(linha)  # a linha do título também entra no recorte

    clausulas = [c for c in clausulas if c.linhas]
    x0 = min(l.bbox.x0 for l in linhas) - 4
    x1 = max(l.bbox.x1 for l in linhas) + 4
    return Contrato(clausulas, x0, x1)
