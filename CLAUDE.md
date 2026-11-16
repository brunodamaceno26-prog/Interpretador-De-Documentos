# Interpretador de Contratos — contexto para o Claude Code

Projeto de portfólio (não comercial) do Bruno. Lê contratos em PDF, divide em
cláusulas, busca termos, responde perguntas citando cláusulas e gera recortes
visuais dos trechos.

## Decisões já tomadas
- **Linguagem:** Python 3.10+. Código, nomes e mensagens em português.
- **PDF:** PyMuPDF (`import pymupdf`, nunca `import fitz`). Licença do projeto: AGPL-3.0.
- **Recorte:** só o recorte visual do original (`show_pdf_page` com `clip`), empilhado em A4.
  Cláusulas que atravessam páginas viram vários trechos em sequência.
- **IA:** API do Claude (SDK `anthropic`), com **Citations** no modo *custom content*:
  cada cláusula vai como um bloco do documento; o `start_block_index` da citação
  mapeia direto para a cláusula, que já tem coordenadas para o recorte.
  Chave via variável de ambiente `ANTHROPIC_API_KEY` — nunca no código.
  Modelo padrão `claude-sonnet-5-5`, trocável pela variável `CONTRATOS_MODELO`.
- **OCR:** fase futura. Por enquanto, PDFs sem texto digital retornam erro amigável.

## Estrutura
```
src/contratos/
├── ingestao/leitor.py       # Linha(pagina, texto, bbox, negrito); junta pedaços na mesma altura
├── estrutura/clausulas.py   # Clausula, Contrato, estruturar(), buscar()
├── exportacao/recorte.py    # recortar() — Clausula ou Dispositivo; titulos=, destaques= (marca-texto via bake)
├── exportacao/galeria.py    # agrupar_resultados() por dispositivo, gerar_imagens(), zip_de_imagens()
├── ia/perguntas.py          # Conversa, montar_documento(), interpretar_resposta()
├── app.py                   # interface Streamlit (abas: Cláusulas, Buscar, Recortar, Perguntar)
├── iniciar_app.py           # comando contratos-app (Streamlit headless + abre o navegador)
└── cli.py                   # listar | ver | buscar | recortar | perguntar
tests/                       # pytest; contrato fictício em conftest.py; IA testada com cliente
                             # falso e com o SDK real + HTTP simulado (sem gastar créditos)
```

## Uso no Windows
`Instalar.bat` (uma vez) e `Abrir Interpretador.bat`. O Bruno prefere interface gráfica a terminal.

## Regras
- Rodar `pytest` depois de qualquer mudança; todo recurso novo ganha teste.
- Testes usam apenas contratos fictícios gerados no próprio teste.
- **Nunca versionar contratos reais** (têm CPF/CNPJ/endereço). `*.pdf` está no .gitignore;
  exemplos públicos só em `exemplos/` e só fictícios. Prints em `docs/` só com o contrato fictício.

## Detalhes que já deram problema
- Títulos inseridos no PDF usam fonte base14: não tem travessão "–"; use "·".
- Marca-texto precisa de `doc.bake()` senão some no `show_pdf_page`.
- `sem_acento()` troca "º" por "o": remova º/ª/§ antes de comparar rótulos.

## Roteiro
1. [x] Leitura + divisão em cláusulas + busca por palavra + recorte visual
2. [x] Subdivisão: parágrafos (§), incisos (I, II) e alíneas (a, b) dentro das cláusulas
3. [x] Comando `perguntar`: API do Claude com citations → resposta + cláusulas citadas
       + opção `--recortar` para gerar o PDF das cláusulas citadas
4. [ ] Busca semântica (embeddings) além da palavra-chave
5. [x] Interface Streamlit (+ galeria de recortes na aba Buscar) (upload, lista de cláusulas, chat, botão de recorte)
6. [ ] OCR para PDFs escaneados
7. [~] README com prints (falta GIF) de demonstração e contrato fictício em `exemplos/`
