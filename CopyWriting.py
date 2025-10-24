import google.generativeai as genai
import os
import dotenv
import pypandoc
from pathlib import Path
from typing import List, Dict, Optional
from googleapiclient.discovery import build
from google.api_core import exceptions
import time
import re

# --- Constantes de Configuração ---
MODEL_NAME = 'models/gemini-2.5-pro'
# Ajuste conforme seu status de faturamento (2s se pago, 35s se free tier)
RATE_LIMIT_PAUSE = 2

# --- Configuração da API ---
dotenv.load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH_ENGINE_ID")

if not API_KEY or not SEARCH_ENGINE_ID:
    print("Erro: Chave de API ou ID do Mecanismo de Pesquisa não encontrada no arquivo .env")
    exit()

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(MODEL_NAME)


# ==============================================================================
#           FUNÇÕES DE APOIO (Inalteradas)
# ==============================================================================
def pesquisar_fontes_api(tema_pesquisa: str, num_results: int = 4) -> Optional[List[Dict[str, str]]]:
    """Pesquisa no Google usando a API oficial."""
    print(f"\n[PESQUISA] Buscando {num_results} fontes/contexto para: '{tema_pesquisa}'...")
    try:
        service = build("customsearch", "v1", developerKey=API_KEY)
        res = service.cse().list(q=tema_pesquisa, cx=SEARCH_ENGINE_ID, num=num_results, hl='pt-BR').execute()

        if 'items' not in res:
            print("[AVISO] Nenhuma fonte externa encontrada.")
            return None
        resultados = [{"titulo": i.get('title'), "url": i.get('link'), "snippet": i.get('snippet')} for i in
                      res.get('items', [])]
        print(f"   -> {len(resultados)} fontes encontradas.")
        return resultados
    except Exception as e:
        print(f"[ERRO] Falha na busca via API. Detalhe: {e}")
        time.sleep(2)
        return None


def formatar_fontes_para_prompt(fontes: List[Dict[str, str]]) -> str:
    contexto_formatado = "--- CONTEXTO EXTERNO (Pesquisa) ---\n"
    if not fontes:
        return "Nenhum contexto externo encontrado.\n"
    for i, fonte in enumerate(fontes, 1):
        contexto_formatado += f"Fonte {i}: {fonte['titulo']}\nSnippet: {fonte['snippet']}\nURL: {fonte['url']}\n\n"
    return contexto_formatado


def salvar_documento(nome_arquivo_base: str, tema: str, conteudo: str) -> None:
    """Salva o conteúdo em .md e .docx."""
    nome_base = "".join(c for c in tema if c.isalnum() or c in " _-").rstrip().replace(' ', '_').lower()
    caminho_md = Path(f"{nome_arquivo_base}_{nome_base}.md")
    caminho_docx = caminho_md.with_suffix(".docx")
    try:
        caminho_md.write_text(conteudo, encoding="utf-8")
        print(f"\n✅ Documento Markdown salvo em: {caminho_md}")
    except IOError as e:
        print(f"❌ ERRO ao salvar o arquivo .md: {e}")
        return
    print(f"🔄 Convertendo para DOCX...")
    try:
        pypandoc.convert_file(str(caminho_md), 'docx', outputfile=str(caminho_docx))
        print(f"📄 Arquivo DOCX salvo em: {caminho_docx}")
    except Exception as e:
        print(f"❌ ERRO AO CONVERTER PARA DOCX: {e}\n   (Verifique se o Pandoc está instalado)")


# ==============================================================================
#           MOTOR DE GERAÇÃO (Persona Copywriter) E REVISÃO
# ==============================================================================

def criar_prompt_mestre(prompt_especifico: str, persona: str = "copywriter") -> str:
    """Anexa uma instrução de sistema rigorosa ao prompt da seção."""
    if persona == "copywriter":
        instrucao_sistema = "ATENÇÃO: Sua identidade é de um Copywriter Sênior, especialista em escrita persuasiva e otimização para conversão (CRO). Sua missão é gerar APENAS o conteúdo textual para a seção do website solicitada, seguindo estas regras ESTRITAS:\n1.  **FOCO TOTAL NO CLIENTE:** Use as informações fornecidas sobre a marca, produto, público e diferenciais como base principal. O CONTEXTO DO CLIENTE é mais importante que as fontes externas.\n2.  **PERSUASÃO E CONVERSÃO:** Seu objetivo é engajar o leitor e levá-lo à ação. Use técnicas de copywriting (gatilhos mentais, AIDA, PAS), foque em benefícios e resultados para o cliente, não apenas características.\n3.  **STORYTELLING:** Quando apropriado (ex: seção \"Sobre Nós\"), incorpore elementos de storytelling para conectar emocionalmente com o leitor.\n4.  **CLAREZA E OBJETIVIDADE:** Use linguagem clara, direta e acessível ao público-alvo. Evite jargões desnecessários. Parágrafos curtos.\n5.  **TOM DE VOZ DA MARCA:** Adapte seu estilo de escrita ao tom de voz desejado (informado no contexto).\n6.  **NÃO GERE TÍTULOS DE SEÇÃO:** Comece a resposta DIRETAMENTE com o conteúdo (headline, parágrafo, etc.). O script principal cuidará da estrutura.\n7.  **SEM SAUDAÇÕES/METATEXTO:** Não use frases como \"Com certeza\", \"Aqui está a copy\", etc."
    elif persona == "editor_copy":
        instrucao_sistema = "ATENÇÃO: Você é um Editor de Copy Sênior, focado em conversão. Revise a copy fornecida e ofereça sugestões CRÍTICAS e ACIONÁVEIS para AUMENTAR A PERSUASÃO e a CLAREZA. Para cada sugestão, forneça:\n1.  **Ponto a Melhorar:** (Ex: Headline pouco impactante, CTA fraco, Foco excessivo em características)\n2.  **Sugestão Específica:** (Ex: Reescrever headline focando no principal benefício; Tornar o CTA mais específico e urgente; Reformular parágrafo para destacar resultados)\n3.  **Justificativa:** (Por que a mudança aumentaria a conversão)\n\nResponda DIRETAMENTE com 2 a 3 sugestões, seguindo o formato."
    elif persona == "tradutor_en":
        return f"Translate the following website copy text to English, preserving the original Markdown formatting (headings, bold text, bullet points). Maintain a persuasive and brand-aligned tone. Respond only with the translated text.\n\n---\n\n{prompt_especifico}"
    elif persona == "tradutor_es":
        return f"Traduce el siguiente texto de copywriting para sitio web al español, conservando el formato Markdown original (encabezados, negritas, viñetas). Mantén un tono persuasivo y alineado a la marca. Responde únicamente con el texto traducido.\n\n---\n\n{prompt_especifico}"

    return f"{instrucao_sistema}\n--- CONTEXTO DO CLIENTE E INSTRUÇÃO ESPECÍFICA ---\n{prompt_especifico}"


def chamar_api_gemini(prompt: str, persona: str = "copywriter") -> str:
    """Função central que chama a API do Gemini com resiliência (auto-retry)."""
    prompt_final = criar_prompt_mestre(prompt, persona)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt_final)
            print(f"   -> Resposta recebida. Aguardando {RATE_LIMIT_PAUSE} segundos...")
            time.sleep(RATE_LIMIT_PAUSE)
            return response.text.strip()
        except exceptions.ResourceExhausted as e:
            print(f"   [AVISO] Erro de cota (429) detectado. Tentativa {attempt + 1} de {max_retries}.")
            match = re.search(r'seconds: (\d+)', str(e))
            if match:
                wait_time = int(match.group(1)) + 1
                print(f"   -> A API sugeriu esperar {wait_time - 1}s. Tentando novamente em {wait_time}s...")
                time.sleep(wait_time)
            else:
                wait_time = (2 ** attempt) * 5
                print(f"   -> Tentando novamente em {wait_time}s...")
                time.sleep(wait_time)
        except Exception as e:
            print(f"   [ERRO NA GERAÇÃO] Detalhe: {e}")
            return f"\n\n[ERRO: {e}]\n\n"
    error_msg = "[ERRO CRÍTICO: Todas as tentativas de chamada à API falharam devido a erros de cota.]"
    print(error_msg)
    return error_msg


def revisar_conteudo_gerado(contexto_atual: str, info_cliente: Dict) -> str:
    """Usa a IA (editor_copy) para revisar a copy e sugerir melhorias de conversão."""
    print("\n[REVISÃO DA IA - FOCO EM COPY] Analisando a copy gerada...")
    prompt = f"Contexto do Cliente:\nMarca: {info_cliente['nome_marca']}\nPúblico: {info_cliente['publico_alvo']}\nProduto/Serviço: {info_cliente['produto_servico']}\nDiferenciais: {info_cliente['diferenciais']}\nTom de Voz: {info_cliente['tom_de_voz']}\n\nCOPY GERADA ATÉ AGORA (Últimos trechos):\n{contexto_atual[-6000:]}\n\nSiga rigorosamente as instruções da sua persona de Editor de Copy Sênior. Forneça sugestões para aumentar a persuasão e clareza."
    return chamar_api_gemini(prompt, persona="editor_copy")


def gerar_secao_ad_hoc(titulo_secao: str, instrucao_especifica: str, contexto_atual: str, info_cliente: Dict,
                       num_parte: int, num_secao: int) -> str:
    """Gera uma nova seção de copy (ad-hoc) por solicitação do usuário."""
    print(f"\n--- Gerando Seção Ad-Hoc de Copy: {titulo_secao} ---")
    termo_pesquisa = f"concorrentes {info_cliente['nome_marca']} OU {info_cliente['produto_servico']}"
    fontes = pesquisar_fontes_api(termo_pesquisa, num_results=2)
    fontes_fmt = formatar_fontes_para_prompt(fontes) if fontes else "Nenhuma análise de concorrente encontrada."

    prompt = f"Contexto do Cliente:\nMarca: {info_cliente['nome_marca']}\nPúblico: {info_cliente['publico_alvo']}\nProduto/Serviço: {info_cliente['produto_servico']}\nDiferenciais: {info_cliente['diferenciais']}\nTom de Voz: {info_cliente['tom_de_voz']}\n\n{fontes_fmt}\n\nInstrução Específica para esta seção: {instrucao_especifica}\n\nCONTEXTO JÁ ESCRITO NO SITE:\n{contexto_atual[-8000:]}"
    texto_gerado = chamar_api_gemini(prompt, persona="copywriter")
    return f"## {num_parte}.{num_secao}. {titulo_secao}\n\n{texto_gerado}\n\n"


def traduzir_texto_em_chunks(texto_completo_pt: str, lang: str = 'en') -> str:
    """Divide o texto em blocos, traduz cada um e junta os resultados."""
    persona = f"tradutor_{lang}"
    lang_name = "Inglês" if lang == "en" else "Espanhol"
    print(f"\n\n--- INICIANDO PROCESSO DE TRADUÇÃO PARA {lang_name.upper()} ---")
    paragrafos = texto_completo_pt.split('\n')
    texto_traduzido_completo = ""
    chunk_atual = ""
    for i, p in enumerate(paragrafos):
        if len(chunk_atual) + len(p) + 1 > 4000:
            print(f"   [TRADUÇÃO] Traduzindo bloco de {len(chunk_atual)} caracteres para {lang_name}...")
            texto_traduzido_completo += chamar_api_gemini(chunk_atual, persona=persona) + "\n"
            chunk_atual = p
        else:
            chunk_atual += "\n" + p
        if i == len(paragrafos) - 1 and chunk_atual:
            print(f"   [TRADUÇÃO] Traduzindo bloco final de {len(chunk_atual)} caracteres para {lang_name}...")
            texto_traduzido_completo += chamar_api_gemini(chunk_atual, persona=persona) + "\n"
    print(f"--- TRADUÇÃO PARA {lang_name.upper()} CONCLUÍDA ---")
    return texto_traduzido_completo


# ==============================================================================
#           ORQUESTRADOR PRINCIPAL (MODO COPYWRITER INTERATIVO)
# ==============================================================================

def main():
    """Função principal que orquestra a criação interativa da copy do website."""
    print("--- 🚀 Gerador de Copy para Website v20.1 (Corrigido) 🚀 ---")
    print("Bem-vindo, Pablo!\n")

    print("--- Briefing do Cliente ---")
    info_cliente = {}
    info_cliente['nome_marca'] = input("Nome da Marca/Empresa: ")
    info_cliente['produto_servico'] = input("Descrição breve do Produto/Serviço principal: ")
    info_cliente['publico_alvo'] = input("Quem é o público-alvo? (Descreva em detalhes): ")
    info_cliente['diferenciais'] = input("Quais são os 2-3 principais diferenciais/benefícios únicos?: ")
    info_cliente['tom_de_voz'] = input(
        "Qual o tom de voz desejado? (Ex: Profissional, Amigável, Técnico, Inspirador): ")
    objetivo_principal = input("Qual o principal objetivo do site? (Ex: Gerar Leads, Vender Produto, Informar): ")
    print("---------------------------\n")

    # --- ESTRUTURA DO WEBSITE (COM A CORREÇÃO DE 'cli' PARA 'info_cliente') ---
    estrutura_website = [
        {"titulo_pagina": "Página Inicial (Home)", "secoes": [
            {"titulo": "Headline Principal",
             "pesquisa": f"headlines persuasivas para {info_cliente['produto_servico']}", "prompt": lambda f, c,
                                                                                                           cli: f"Crie 3 opções de Headlines (títulos principais) magnéticas e focadas em benefícios para a Home Page, considerando o objetivo de '{objetivo_principal}'.\n\n{f}"},
            {"titulo": "Sub-headline e Introdução",
             "pesquisa": f"introdução engajadora website {info_cliente['nome_marca']}", "prompt": lambda f, c,
                                                                                                         cli: f"Desenvolva uma sub-headline que complemente a headline principal e um parágrafo introdutório (2-3 linhas) que prenda a atenção do público '{cli['publico_alvo']}', apresentando o problema que '{cli['produto_servico']}' resolve.\n\n{f}"},
            {"titulo": "Seção de Benefícios Chave",
             "pesquisa": f"como apresentar benefícios {info_cliente['produto_servico']}", "prompt": lambda f, c,
                                                                                                           cli: f"Crie uma seção curta destacando os 2-3 principais benefícios de '{cli['produto_servico']}', focando nos resultados para o cliente '{cli['publico_alvo']}'. Use bullet points se apropriado.\n\n{f}"},
            {"titulo": "Chamada para Ação (CTA) Principal", "pesquisa": f"exemplos CTA eficaz {objetivo_principal}",
             "prompt": lambda f, c,
                              cli: f"Crie 2 opções de CTAs claros e diretos para a Home Page, alinhados com o objetivo de '{objetivo_principal}'.\n\n{f}"}
        ]},
        {"titulo_pagina": "Sobre Nós", "secoes": [
            {"titulo": "Nossa História / Missão",
             "pesquisa": f"storytelling para página sobre nós {info_cliente['nome_marca']}", "prompt": lambda f, c,
                                                                                                              cli: f"Desenvolva o texto para a seção 'Sobre Nós'. Conte a história da marca '{cli['nome_marca']}' ou sua missão de forma envolvente (storytelling), conectando com os valores do público '{cli['publico_alvo']}'. Use o tom de voz '{cli['tom_de_voz']}'.\n\n{f}"},
            {"titulo": "Diferenciais e Valores",
             "pesquisa": f"apresentar diferenciais empresa {info_cliente['nome_marca']}", "prompt": lambda f, c,
                                                                                                           cli: f"Crie um texto curto reforçando os diferenciais '{cli['diferenciais']}' e os valores da marca '{cli['nome_marca']}'.\n\n{f}"}
        ]},
        {"titulo_pagina": "Oferta do Produto/Serviço", "secoes": [
            {"titulo": "Headline da Oferta",
             "pesquisa": f"headline persuasiva oferta {info_cliente['produto_servico']}", "prompt": lambda f, c,
                                                                                                           cli: f"Crie 2 opções de headlines focadas na oferta principal de '{cli['produto_servico']}', destacando o maior benefício ou diferencial.\n\n{f}"},
            {"titulo": "Descrição Persuasiva", "pesquisa": f"copy de vendas para {info_cliente['produto_servico']}",
             "prompt": lambda f, c,
                              cli: f"Elabore a copy de vendas principal para '{cli['produto_servico']}'. Detalhe como ele funciona, mas foque nos **resultados e transformações** que ele entrega para '{cli['publico_alvo']}'. Use storytelling se aplicável e reforce os diferenciais '{cli['diferenciais']}'. O objetivo é a conversão ('{objetivo_principal}').\n\n{f}"},
            {"titulo": "Prova Social (Ex: Testemunhos)", "pesquisa": f"exemplos prova social website",
             "prompt": lambda f, c,
                              cli: f"Crie 2-3 modelos curtos de testemunhos fictícios (mas realistas) de clientes do público '{cli['publico_alvo']}' satisfeitos com '{cli['produto_servico']}'.\n\n{f}"},
            {"titulo": "CTA da Oferta", "pesquisa": f"CTA para página de vendas {objetivo_principal}",
             "prompt": lambda f, c,
                              cli: f"Crie 2 opções de CTAs fortes e claros para a página da oferta, incentivando a ação ('{objetivo_principal}').\n\n{f}"}
        ]},
    ]

    website_copy_pt = f"# Website Copy: {info_cliente['nome_marca']}\n\n"
    contexto_cumulativo = ""
    num_parte_atual = 0

    print(f"\nIniciando a criação da copy para: {info_cliente['nome_marca']}")

    for pagina in estrutura_website:
        num_parte_atual += 1
        titulo_pagina = pagina['titulo_pagina']
        print(f"\n\n--- INICIANDO PÁGINA {num_parte_atual}: {titulo_pagina} ---")
        conteudo_pagina_atual = f"# {num_parte_atual}. {titulo_pagina}\n\n"

        num_secao_atual = 0
        for secao in pagina['secoes']:
            num_secao_atual += 1
            print(f"    --- Gerando Seção {num_parte_atual}.{num_secao_atual}: {secao['titulo']} ---")

            termo_pesquisa_adaptado = secao["pesquisa"]
            fontes = pesquisar_fontes_api(termo_pesquisa_adaptado)
            fontes_fmt = formatar_fontes_para_prompt(
                fontes) if fontes else "Nenhuma fonte externa encontrada para referência."

            prompt_contextualizado = f"Contexto do Cliente:\nMarca: {info_cliente['nome_marca']}\nPúblico: {info_cliente['publico_alvo']}\nProduto/Serviço: {info_cliente['produto_servico']}\nDiferenciais: {info_cliente['diferenciais']}\nTom de Voz: {info_cliente['tom_de_voz']}\nObjetivo Principal do Site: {objetivo_principal}\n\n{fontes_fmt}\n\nInstrução Específica para esta seção ({secao['titulo']}):\n{secao['prompt'](fontes_fmt, contexto_cumulativo[-6000:], info_cliente)}\n\nCONTEXTO JÁ ESCRITO NO SITE:\n{contexto_cumulativo[-6000:]}"

            conteudo_pagina_atual += f"## {num_parte_atual}.{num_secao_atual}. {secao['titulo']}\n\n"

            texto_gerado = chamar_api_gemini(prompt_contextualizado, persona="copywriter")
            conteudo_pagina_atual += texto_gerado + "\n\n"
            contexto_cumulativo += texto_gerado + "\n\n"

        website_copy_pt += conteudo_pagina_atual

        print(f"\n--- PÁGINA '{titulo_pagina}' CONCLUÍDA ---")
        salvar_documento("website_copy_parcial", info_cliente['nome_marca'], website_copy_pt)
        print("Copy parcial salva. Por favor, revise o arquivo .docx gerado.")

        sugestoes_ia = revisar_conteudo_gerado(conteudo_pagina_atual, info_cliente)
        print("\n--- SUGESTÕES DA IA (FOCO EM COPY) PARA ESTA PÁGINA ---")
        print(sugestoes_ia)
        print("--------------------------------------------------")

        while True:
            add_secao = input(
                "Deseja COMPLEMENTAR esta Página com uma nova seção/bloco de copy? (s/n): ").lower().strip()
            if add_secao == 'n':
                break
            elif add_secao == 's':
                num_secao_atual += 1
                titulo_novo = input(
                    "Digite o título descritivo da nova seção (Ex: Bloco de Garantia, Seção de Bônus): ")
                instrucao_nova = input("Digite a instrução específica para a IA gerar esta copy: ")

                novo_conteudo = gerar_secao_ad_hoc(titulo_novo, instrucao_nova, contexto_cumulativo, info_cliente,
                                                   num_parte_atual, num_secao_atual)

                website_copy_pt += novo_conteudo
                contexto_cumulativo += novo_conteudo

                salvar_documento("website_copy_parcial", info_cliente['nome_marca'], website_copy_pt)
                print("Seção adicional de copy gerada e salva no documento parcial.")
            else:
                print("Resposta inválida. Digite 's' ou 'n'.")

    print("\n\n--- GERAÇÃO DA COPY EM PORTUGUÊS CONCLUÍDA ---")

    quer_traduzir = ""
    while quer_traduzir not in ['s', 'n']:
        quer_traduzir = input("A copy base está pronta. Deseja adicionar traduções? (s/n): ").lower().strip()

    documento_final = website_copy_pt
    nome_arquivo_final = "website_copy_final"

    if quer_traduzir == 's':
        nome_arquivo_final = "website_copy_final_multilingue"
        traduzir_en = ""
        while traduzir_en not in ['s', 'n']:
            traduzir_en = input("Deseja traduzir para o Inglês? (s/n): ").lower().strip()
        if traduzir_en == 's':
            documento_en = traduzir_texto_em_chunks(website_copy_pt, lang='en')
            documento_final += "\n\n---\n\n# English Website Copy\n\n" + documento_en

        traduzir_es = ""
        while traduzir_es not in ['s', 'n']:
            traduzir_es = input("Deseja traduzir para o Espanhol? (s/n): ").lower().strip()
        if traduzir_es == 's':
            documento_es = traduzir_texto_em_chunks(website_copy_pt, lang='es')
            documento_final += "\n\n---\n\n# Copy para Sitio Web en Español\n\n" + documento_es

    salvar_documento(nome_arquivo_final, info_cliente['nome_marca'], documento_final)
    print("\n--- PROCESSO TOTALMENTE CONCLUÍDO ---")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nEncerrado pelo usuário.")

