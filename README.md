# 🚀 Co-piloto de Conteúdo Simbiótico (v21.0)

[![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Pablo_Bonfim-blue?style=for-the-badge&logo=linkedin)](https://www.linkedin.com/in/seu-perfil-aqui/)

Uma plataforma interativa em Python para a co-criação de documentos analíticos, aplicando frameworks acadêmicos de **Human-in-the-Loop (HITL)** para fundir a velocidade da IA com o julgamento crítico humano.

---

### Visão Geral do Projeto

Este projeto nasceu da necessidade de superar a geração de conteúdo genérico por IA. Em vez de uma ferramenta "aperta-botão", o Co-piloto de Conteúdo é um **estúdio de criação interativo** que posiciona o usuário como **Editor-Chefe** e a IA como um **assistente de pesquisa e redação**. O resultado é um workflow simbiótico que produz whitepapers, e-books e análises de mercado com uma profundidade e coerência que a automação pura não consegue alcançar.

![GIF do Projeto em Ação](link_para_seu_gif_aqui.gif)
*(Sugestão: Grave um GIF do seu terminal rodando o script para mostrar o processo interativo!)*

---

### Principais Funcionalidades

🧠 **Workflow Human-in-the-Loop (HITL):** O script pausa estrategicamente após a geração de cada "Parte" do documento, salvando uma versão parcial e permitindo a intervenção e curadoria do editor humano.

🤖 **Auto-Crítica da IA (Revisão Aumentada):** Uma função inovadora onde a própria IA analisa o conteúdo que gerou e apresenta um relatório crítico com:
  * **Sugestões de Aprofundamento:** Propostas de novas seções, com Título, Termo de Pesquisa e Justificativa.
  * **Questionário Crítico:** Perguntas direcionadas ao editor humano para focar a revisão em pontos como coesão e força do argumento.

🔍 **Pesquisa em Tempo Real:** Utiliza a **API do Google Search** para coletar múltiplas fontes externas para cada seção, garantindo que o conteúdo seja atual e fundamentado em dados.

✍️ **Geração com Persona e Alinhamento (RLHF):** Emprega a **API do Google Gemini (2.5 Pro)** com personas programáveis ("Analista Sênior", "Editor") e um ciclo de **RLHF simplificado**, onde o usuário pode escolher entre múltiplas variações de texto para seções críticas, alinhando o resultado à sua preferência.

🌐 **Finalização Multilíngue:** Após a aprovação final do conteúdo em português, a ferramenta orquestra a tradução automática e opcional para Inglês e Espanhol.

🛡️ **Resiliência e Segurança:** Implementa um sistema de auto-retry com backoff exponencial para lidar com erros de API (HTTP 429) e utiliza arquivos `.env` para proteger as chaves de API.

---

### Tecnologias Utilizadas

* **Linguagem:** Python
* **APIs Principais:**
    * Google Gemini Pro API
    * Google Custom Search API
* **Bibliotecas Chave:**
    * `google-generativeai`
    * `google-api-python-client`
    * `pypandoc` (para conversão .md -> .docx)
    * `python-dotenv` (para gestão de variáveis de ambiente)
    * `re` (para parsing de erros da API)
* **Dependência Externa:** Pandoc

---

### Instalação e Configuração

1.  **Clone o repositório:**
    ```bash
    git clone [https://github.com/pablobonfim13/Co-piloto-de-Conte-do-de-IA-Generativa-humano-no-loop.git](https://github.com/pablobonfim13/Co-piloto-de-Conte-do-de-IA-Generativa-humano-no-loop.git)
    cd Co-piloto-de-Conte-do-de-IA-Generativa-humano-no-loop
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv venv
    source venv/bin/activate  # No Windows: venv\Scripts\activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Instale o Pandoc:** Esta ferramenta é necessária para a conversão de Markdown para DOCX. Siga as instruções de instalação em [pandoc.org](https://pandoc.org/installing.html).

5.  **Configure as variáveis de ambiente:**
    * Crie um arquivo chamado `.env` na raiz do projeto.
    * Copie o conteúdo do arquivo `.env.example` e preencha com suas chaves:
        ```
        GEMINI_API_KEY="SUA_CHAVE_API_AQUI"
        SEARCH_ENGINE_ID="SEU_ID_DE_BUSCA_AQUI"
        ```

---

### Como Usar

Para iniciar o processo de criação de um novo documento, basta rodar o script principal e seguir as instruções interativas no console:

```bash
python main.py
