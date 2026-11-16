"""Perguntas sobre o contrato usando a API do Claude com Citations.

Cada cláusula é enviada como um bloco de um documento "custom content".
Quando o Claude cita um trecho, a API devolve o índice do bloco — que é
exatamente a posição da cláusula na lista. Assim sabemos, sem adivinhar,
quais cláusulas sustentam a resposta (e podemos recortá-las do PDF).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from contratos.estrutura.clausulas import Clausula, Contrato

MODELO_PADRAO = os.environ.get("CONTRATOS_MODELO", "claude-sonnet-5-5")

INSTRUCOES = """Você é um assistente que lê contratos e responde dúvidas em português do Brasil.
Regras:
- Responda SOMENTE com base no contrato fornecido. Se a resposta não estiver nele, diga isso claramente.
- Seja direto e use linguagem simples; explique termos jurídicos quando aparecerem.
- Quando o contrato for ambíguo, aponte a ambiguidade em vez de escolher uma interpretação.
- Você não é advogado: para decisões importantes, sugira consultar um profissional."""


class ErroDeConfiguracao(RuntimeError):
    pass


@dataclass
class Citacao:
    clausula: Clausula
    trecho_citado: str


@dataclass
class Resposta:
    texto: str  # resposta com marcadores [1], [2]... onde há citação
    citacoes: list[Citacao] = field(default_factory=list)

    @property
    def clausulas_citadas(self) -> list[Clausula]:
        """Cláusulas citadas, sem repetição, na ordem em que aparecem no contrato."""
        vistas = {id(c.clausula): c.clausula for c in self.citacoes}
        return sorted(vistas.values(), key=lambda c: -1 if c.numero is None else c.numero)


def montar_documento(contrato: Contrato, titulo: str = "Contrato") -> dict[str, Any]:
    """Um bloco por cláusula; o índice do bloco == índice em contrato.clausulas."""
    return {
        "type": "document",
        "source": {
            "type": "content",
            "content": [
                {"type": "text", "text": f"{c.rotulo}\n{c.texto}"} for c in contrato.clausulas
            ],
        },
        "title": titulo,
        "citations": {"enabled": True},
        # Cacheia o contrato: perguntas seguidas sobre o mesmo PDF ficam mais baratas.
        "cache_control": {"type": "ephemeral"},
    }


def interpretar_resposta(blocos: list[Any], contrato: Contrato) -> Resposta:
    """Converte os blocos de texto da API em texto + lista de citações numeradas."""
    partes: list[str] = []
    citacoes: list[Citacao] = []
    for bloco in blocos:
        if getattr(bloco, "type", None) != "text":
            continue
        partes.append(bloco.text)
        marcadores = []
        for cit in getattr(bloco, "citations", None) or []:
            if getattr(cit, "type", None) != "content_block_location":
                continue
            # end_block_index é exclusivo
            for indice in range(cit.start_block_index, cit.end_block_index):
                if 0 <= indice < len(contrato.clausulas):
                    citacoes.append(Citacao(contrato.clausulas[indice], cit.cited_text))
                    marcadores.append(f"[{len(citacoes)}]")
        if marcadores:
            partes.append("".join(marcadores))
    return Resposta("".join(partes).strip(), citacoes)


def criar_cliente():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ErroDeConfiguracao(
            "Defina a variável de ambiente ANTHROPIC_API_KEY com sua chave da API "
            "(crie em https://platform.claude.com)."
        )
    import anthropic  # importado aqui para os outros comandos funcionarem sem o SDK

    return anthropic.Anthropic()


class Conversa:
    """Mantém o histórico para permitir perguntas de acompanhamento."""

    def __init__(self, contrato: Contrato, titulo: str = "Contrato", cliente=None,
                 modelo: str = MODELO_PADRAO):
        self.contrato = contrato
        self.cliente = cliente or criar_cliente()
        self.modelo = modelo
        self.documento = montar_documento(contrato, titulo)
        self.historico: list[dict[str, Any]] = []

    def perguntar(self, pergunta: str) -> Resposta:
        if not self.historico:
            # Na primeira pergunta o contrato vai junto; depois ele fica no histórico.
            conteudo: Any = [self.documento, {"type": "text", "text": pergunta}]
        else:
            conteudo = pergunta
        mensagens = self.historico + [{"role": "user", "content": conteudo}]

        resposta_api = self.cliente.messages.create(
            model=self.modelo,
            max_tokens=1500,
            system=INSTRUCOES,
            messages=mensagens,
        )
        conteudo_resposta = [
            b.model_dump(exclude_none=True) if hasattr(b, "model_dump") else b
            for b in resposta_api.content
        ]
        self.historico = mensagens + [{"role": "assistant", "content": conteudo_resposta}]
        return interpretar_resposta(resposta_api.content, self.contrato)
