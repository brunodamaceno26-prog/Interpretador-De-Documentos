"""Testes da camada de IA com um cliente falso (não chama a API de verdade)."""

from types import SimpleNamespace as NS

import pytest

from contratos.estrutura.clausulas import estruturar
from contratos.ia.perguntas import Conversa, ErroDeConfiguracao, criar_cliente, montar_documento
from contratos.ingestao.leitor import extrair_linhas


class ClienteFalso:
    """Imita client.messages.create e guarda o que foi enviado."""

    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.chamadas = []
        self.messages = self

    def create(self, **kwargs):
        self.chamadas.append(kwargs)
        return NS(content=self.respostas.pop(0))


def bloco(texto, *citacoes):
    return NS(type="text", text=texto, citations=list(citacoes) or None)


def citacao(inicio, fim, trecho):
    return NS(type="content_block_location", start_block_index=inicio,
              end_block_index=fim, cited_text=trecho)


@pytest.fixture
def contrato(contrato_pdf):
    return estruturar(extrair_linhas(contrato_pdf))


def test_documento_tem_um_bloco_por_clausula(contrato):
    doc = montar_documento(contrato)
    blocos = doc["source"]["content"]
    assert doc["citations"] == {"enabled": True}
    assert len(blocos) == len(contrato.clausulas)
    assert blocos[3]["text"].startswith("Cláusula 3ª")


def test_citacao_aponta_para_a_clausula_certa(contrato):
    cliente = ClienteFalso([[
        bloco("A multa é de "),
        bloco("10%", citacao(3, 4, "Qualquer parte pode rescindir com multa de 10%.")),
        bloco(", exceto nos primeiros 30 dias."),
    ]])
    resposta = Conversa(contrato, cliente=cliente).perguntar("Qual a multa?")

    assert resposta.texto == "A multa é de 10%[1], exceto nos primeiros 30 dias."
    assert [c.numero for c in resposta.clausulas_citadas] == [3]
    assert "10%" in resposta.citacoes[0].trecho_citado


def test_citacao_de_varios_blocos_e_sem_repeticao(contrato):
    cliente = ClienteFalso([[
        bloco("Resumo", citacao(1, 3, "...")),
        bloco(" e foro", citacao(4, 5, "...")),
        bloco(" de novo", citacao(1, 2, "...")),
    ]])
    resposta = Conversa(contrato, cliente=cliente).perguntar("Resuma")
    assert len(resposta.citacoes) == 4
    assert [c.numero for c in resposta.clausulas_citadas] == [1, 2, 4]


def test_contrato_so_vai_na_primeira_pergunta(contrato):
    cliente = ClienteFalso([[bloco("Primeira.")], [bloco("Segunda.")]])
    conversa = Conversa(contrato, cliente=cliente)
    conversa.perguntar("P1")
    conversa.perguntar("P2")

    primeira, segunda = cliente.chamadas
    assert primeira["messages"][0]["content"][0]["type"] == "document"
    assert len(segunda["messages"]) == 3  # pergunta 1, resposta 1, pergunta 2
    assert segunda["messages"][-1]["content"] == "P2"


def test_resposta_sem_citacao(contrato):
    cliente = ClienteFalso([[bloco("O contrato não fala sobre férias.")]])
    resposta = Conversa(contrato, cliente=cliente).perguntar("E as férias?")
    assert resposta.citacoes == []
    assert resposta.clausulas_citadas == []


def test_sem_chave_da_api_da_erro_amigavel(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ErroDeConfiguracao, match="ANTHROPIC_API_KEY"):
        criar_cliente()
