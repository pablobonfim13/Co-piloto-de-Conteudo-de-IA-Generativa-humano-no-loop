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
# Use 35s se o faturamento NÃO estiver ativo. Use 2s se o faturamento ESTIVER ativo.
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

def pesquisar_fontes_api(tema_pesquisa: str, num_results: int = 6) -> Optional[List[Dict[str, str]]]:
    """Pesquisa no Google usando a API oficial."""
    print(f"\n[PESQUISA] Buscando {num_results} fontes para: '{tema_pesquisa}'...")
    try:
        service = build("customsearch", "v1", developerKey=API_KEY)
        res = service.cse().list(q=tema_pesquisa, cx=SEARCH_ENGINE_ID, num=num_results, hl='pt-BR').execute()

        if 'items' not in res:
            print("[AVISO] Nenhuma fonte encontrada.")
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
    contexto_formatado = "--- FONTES DE PESQUISA PARA ESTA SEÇÃO ---\n"
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
#           MOTOR DE GERAÇÃO COM AUTO-RETRY E TRADUÇÃO
# ==============================================================================

def criar_prompt_mestre(prompt_especifico: str, persona: str = "analista") -> str:
    """Anexa uma instrução de sistema rigorosa ao prompt da seção."""
    if persona == "analista":
        instrucao_sistema = "ATENÇÃO: Sua identidade é de um pesquisador sênior e analista crítico. Sua missão é gerar APENAS o conteúdo para a seção solicitada, seguindo estas regras ESTRITAS:\n1.  **NÃO GERE TÍTULOS:** Comece sua resposta DIRETAMENTE com o primeiro parágrafo do texto.\n2.  **BASE ESTRITA NAS FONTES:** Baseie TODAS as suas afirmações EXCLUSIVAMENTE nas \"FONTES DE PESQUISA\" e no \"CONTEXTO JÁ ESCRITO\".\n3.  **PROFUNDIDADE E SÍNTESE:** Sintetize as informações das fontes para construir um argumento coeso e aprofundado.\n4.  **PROIBIDO INVENTAR:** NÃO invente informações, dados ou exemplos que não estejam nas fontes.\n5.  **SEM SAUDAÇÕES:** NÃO use frases como \"Com certeza\", \"Aqui está\", etc."
    elif persona == "editor":
        instrucao_sistema = "ATENÇÃO: Você é um Editor Sênior. Revise o documento fornecido e ofereça sugestões CRÍTICAS e ACIONÁVEIS. Para cada sugestão, forneça três itens em um formato claro: 1. **Título Sugerido:** (Um título H2 conciso), 2. **Termo de Pesquisa:** (Uma string de pesquisa otimizada para Google), 3. **Justificativa:** (Uma breve análise da lacuna). Responda DIRETAMENTE com 2 a 3 sugestões."
    elif persona == "referencias":
        return f"Você é um assistente de formatação bibliográfica. Organize a lista de fontes brutas a seguir em uma seção de 'Referências' limpa e profissional. Formate cada item com o título e o link de forma clara. Agrupe em ordem alfabética pelo título.\n\nFONTES BRUTAS:\n{prompt_especifico}"
    elif persona == "tradutor_en":
        return f"Translate the following text to English, preserving the original Markdown formatting. Respond only with the translated text.\n\n---\n\n{prompt_especifico}"
    elif persona == "tradutor_es":
        return f"Traduce el siguiente texto al español, conservando el formato Markdown original. Responde únicamente con el texto traducido.\n\n---\n\n{prompt_especifico}"
    return f"{instrucao_sistema}\n--- INSTRUÇÃO ESPECÍFICA ---\n{prompt_especifico}"


def chamar_api_gemini(prompt: str, persona: str = "analista") -> str:
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


def revisar_conteudo_gerado(contexto_atual: str) -> str:
    """Usa a IA para revisar o próprio conteúdo e sugerir melhorias acionáveis."""
    print("\n[REVISÃO DA IA] Analisando o conteúdo gerado para sugestões...")
    prompt = f"Revise o documento a seguir, que está em andamento. Siga rigorosamente as instruções da sua persona de Editor Sênior.\n\nDOCUMENTO A SER REVISADO:\n{contexto_atual[-10000:]}"
    return chamar_api_gemini(prompt, persona="editor")


def gerar_secao_ad_hoc(titulo_secao: str, termo_pesquisa: str, contexto_atual: str, num_parte: int,
                       num_secao: int) -> str:
    """Gera uma nova seção de forma independente (ad-hoc) por solicitação do usuário."""
    print(f"\n--- Gerando Seção Ad-Hoc: {titulo_secao} ---")
    fontes = pesquisar_fontes_api(termo_pesquisa)
    fontes_fmt = formatar_fontes_para_prompt(fontes) if fontes else "Nenhuma fonte externa encontrada."
    prompt = f"Elabore uma seção aprofundada sobre o tema '{titulo_secao}'. Analise criticamente o tema, sintetize as fontes e conecte-o ao contexto maior do documento.\n\n{fontes_fmt}\nCONTEXTO JÁ ESCRITO:\n{contexto_atual[-8000:]}"
    texto_gerado = chamar_api_gemini(prompt, persona="analista")
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
#           ORQUESTRADOR PRINCIPAL (MODO INTERATIVO)
# ==============================================================================

def main():
    """Função principal que orquestra a criação interativa do documento."""
    print("--- 🚀 Gerador de Documentos v22.0 (Geração Estendida + Referências) 🚀 ---")
    print("Bem-vindo, Pablo!\n")

    tema_principal = input("Digite o tema principal do documento: ")
    if not tema_principal:
        print("Nenhum tema foi digitado. Encerrando.")
        return

    # --- ESTRUTURA UNIVERSAL E COMPLETA DE 5 CAPÍTULOS ---
    estrutura_documento = [
        {"titulo_parte": "Introdução e Fundamentos", "secoes": [
            {"titulo": "Introdução Abrangente", "pesquisa": f"o que é {tema_principal} guia completo",
             "prompt": lambda f,
                              c: f"Elabore uma Introdução aprofundada (3-4 parágrafos) para um manual sobre '{tema_principal}'. A introdução deve definir o conceito, apresentar a tese central, justificar a importância do tema e apresentar a estrutura do manual.\n\n{f}"},
            {"titulo": "Contexto Histórico e Evolução", "pesquisa": f"história e evolução de {tema_principal}",
             "prompt": lambda f,
                              c: f"Analise criticamente a evolução de '{tema_principal}', comparando abordagens tradicionais com as mais recentes inovações.\n\nCONTEXTO:\n{c}\n\n{f}"},
        ]},
        {"titulo_parte": "Análise dos Componentes Principais", "secoes": [
            {"titulo": "Conceitos e Mecanismos Chave",
             "pesquisa": f"principais conceitos e mecanismos de {tema_principal}", "prompt": lambda f,
                                                                                                    c: f"Analise criticamente os principais conceitos ou componentes de '{tema_principal}'. Explique o papel estratégico de cada um.\n\nCONTEXTO:\n{c}\n\n{f}"},
            {"titulo": "Tecnologias Habilitadoras", "pesquisa": f"tecnologias habilitadoras de {tema_principal}",
             "prompt": lambda f,
                              c: f"Descreva as principais tecnologias que sustentam '{tema_principal}' e como elas interagem.\n\nCONTEXTO:\n{c}\n\n{f}"},
        ]},
        {"titulo_parte": "Aplicações Práticas e Estudos de Caso", "secoes": [
            {"titulo": "Aplicações Setoriais", "pesquisa": f"aplicações práticas de {tema_principal}",
             "prompt": lambda f,
                              c: f"Explore diversas aplicações práticas de '{tema_principal}' em diferentes setores da indústria ou sociedade.\n\nCONTEXTO:\n{c}\n\n{f}"},
            {"titulo": "Estudo de Caso Aprofundado", "pesquisa": f"estudo de caso detalhado {tema_principal}",
             "prompt": lambda f,
                              c: f"Elabore uma análise de um estudo de caso sobre a aplicação de '{tema_principal}'. Descreva o desafio, a solução e analise criticamente os resultados.\n\nCONTEXTO:\n{c}\n\n{f}"},
        ]},
        {"titulo_parte": "Desafios, Ética e Implementação", "secoes": [
            {"titulo": "Desafios e Barreiras à Adoção", "pesquisa": f"desafios e barreiras de {tema_principal}",
             "prompt": lambda f,
                              c: f"Analise os principais desafios (técnicos, culturais, financeiros) para a implementação ou adoção de '{tema_principal}'.\n\nCONTEXTO:\n{c}\n\n{f}"},
            {"titulo": "Considerações Éticas e de Segurança", "pesquisa": f"ética e segurança em {tema_principal}",
             "prompt": lambda f,
                              c: f"Elabore uma análise crítica sobre os riscos (privacidade, viés, segurança) ao se trabalhar com '{tema_principal}' e ofereça recomendações para mitigá-los.\n\nCONTEXTO:\n{c}\n\n{f}"},
        ]},
        {"titulo_parte": "Conclusão e Visão de Futuro", "secoes": [
            {"titulo": "Análise de Tendências e Inovações Futuras",
             "pesquisa": f"tendências futuras e inovações de {tema_principal}", "prompt": lambda f,
                                                                                                 c: f"Elabore uma análise das tendências futuras para '{tema_principal}' nos próximos 5 a 10 anos.\n\nCONTEXTO:\n{c}\n\n{f}"},
            {"titulo": "Conclusão e Recomendações Finais",
             "pesquisa": f"conclusão e recomendações sobre {tema_principal}", "prompt": lambda f,
                                                                                               c: f"Elabore uma síntese de todo o documento, recapitulando os argumentos principais. Finalize com uma lista de recomendações acionáveis para diferentes públicos.\n\nCONTEXTO:\n{c}\n\n{f}"},
        ]}
    ]

    documento_pt = f"# {tema_principal}\n\n"
    contexto_cumulativo = ""
    collected_references = []  # NOVA LISTA PARA COLETAR REFERÊNCIAS
    seen_urls = set()  # NOVO SET PARA EVITAR URLS DUPLICADAS

    print(f"\nIniciando a construção interativa sobre: {tema_principal}")

    num_parte_atual = 0
    for parte in estrutura_documento:
        num_parte_atual += 1
        titulo_parte = parte['titulo_parte']
        print(f"\n\n--- INICIANDO PARTE {num_parte_atual}: {titulo_parte} ---")

        conteudo_parte_atual = f"# {num_parte_atual}. {titulo_parte}\n\n"

        num_secao_atual = 0
        for secao in parte['secoes']:
            num_secao_atual += 1
            print(f"    --- Gerando Seção {num_parte_atual}.{num_secao_atual}: {secao['titulo']} ---")

            fontes = pesquisar_fontes_api(secao["pesquisa"])

            # NOVO: Coleta de referências
            if fontes:
                for fonte in fontes:
                    if fonte['url'] and fonte['url'] not in seen_urls:
                        collected_references.append(fonte)
                        seen_urls.add(fonte['url'])

            fontes_fmt = formatar_fontes_para_prompt(fontes) if fontes else "Nenhuma fonte externa encontrada."
            prompt = secao["prompt"](fontes_fmt, contexto_cumulativo[-8000:])

            conteudo_parte_atual += f"## {num_parte_atual}.{num_secao_atual}. {secao['titulo']}\n\n"

            texto_gerado = chamar_api_gemini(prompt, persona="analista")
            conteudo_parte_atual += texto_gerado + "\n\n"
            contexto_cumulativo += texto_gerado + "\n\n"

        documento_pt += conteudo_parte_atual

        print(f"\n--- PARTE {num_parte_atual} CONCLUÍDA ---")
        salvar_documento("documento_parcial", tema_principal, documento_pt)
        print("Documento parcial salvo. Por favor, revise o arquivo .docx gerado.")

        sugestoes_ia = revisar_conteudo_gerado(conteudo_parte_atual)
        print("\n--- SUGESTÕES DA IA PARA APRIMORAMENTO DESTA PARTE ---")
        print(sugestoes_ia)
        print("--------------------------------------------------")

        while True:
            add_secao = input("Deseja COMPLEMENTAR esta Parte com uma nova seção? (s/n): ").lower().strip()
            if add_secao == 'n':
                break
            elif add_secao == 's':
                num_secao_atual += 1
                titulo_novo = input("Digite o título da nova seção: ")
                pesquisa_nova = input("Digite o termo de pesquisa para esta seção: ")
                novo_conteudo = gerar_secao_ad_hoc(titulo_novo, pesquisa_nova, contexto_cumulativo, num_parte_atual,
                                                   num_secao_atual)
                documento_pt += novo_conteudo
                contexto_cumulativo += novo_conteudo
                salvar_documento("documento_parcial", tema_principal, documento_pt)
                print("Seção adicional gerada e salva no documento parcial.")
            else:
                print("Resposta inválida. Digite 's' ou 'n'.")

    # --- NOVA ETAPA: GERAÇÃO DA SEÇÃO DE REFERÊNCIAS ---
    print("\n\n--- GERANDO SEÇÃO DE REFERÊNCIAS ---")
    if collected_references:
        fontes_brutas = ""
        for ref in collected_references:
            fontes_brutas += f"Título: {ref['titulo']}\nURL: {ref['url']}\n\n"

        secao_referencias = chamar_api_gemini(fontes_brutas, persona="referencias")
        documento_pt += f"# Referências\n\n{secao_referencias}\n\n"
    else:
        documento_pt += "# Referências\n\nNenhuma fonte externa foi utilizada na geração deste documento.\n\n"

    print("--- GERAÇÃO DE CONTEÚDO EM PORTUGUÊS CONCLUÍDA ---")

    # --- FLUXO DE TRADUÇÃO OPCIONAL E MÚLTIPLA ---
    quer_traduzir = ""
    while quer_traduzir not in ['s', 'n']:
        quer_traduzir = input("Todo o conteúdo está pronto. Deseja seguir para as traduções? (s/n): ").lower().strip()

    if quer_traduzir == 'n':
        print("Processo finalizado pelo usuário. Salvando documento final apenas em Português.")
        salvar_documento("documento_final", tema_principal, documento_pt)
        return

    documento_final = documento_pt

    traduzir_en = ""
    while traduzir_en not in ['s', 'n']:
        traduzir_en = input("Deseja traduzir o documento para o Inglês? (s/n): ").lower().strip()
    if traduzir_en == 's':
        documento_en = traduzir_texto_em_chunks(documento_pt, lang='en')
        documento_final += "\n\n---\n\n# English Translation\n\n" + documento_en

    traduzir_es = ""
    while traduzir_es not in ['s', 'n']:
        traduzir_es = input("Deseja traduzir o documento para o Espanhol? (s/n): ").lower().strip()
    if traduzir_es == 's':
        documento_es = traduzir_texto_em_chunks(documento_pt, lang='es')
        documento_final += "\n\n---\n\n# Traducción al Español\n\n" + documento_es

    salvar_documento("documento_final_multilingue", tema_principal, documento_final)
    print("\n--- PROCESSO TOTALMENTE CONCLUÍDO ---")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nEncerrado pelo usuário.")