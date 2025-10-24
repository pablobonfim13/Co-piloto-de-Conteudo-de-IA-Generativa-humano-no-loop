# verificar_modelos.py
import google.generativeai as genai

# COLOQUE A MESMA CHAVE DE API QUE VOCÊ ESTÁ USANDO NO OUTRO SCRIPT
SUA_API_KEY = "AIzaSyDn1Cvb9UP-5xEQs_Hn1K5UZBBQTad75EY"
genai.configure(api_key=SUA_API_KEY)

print("--- Modelos de IA que sua chave de API pode acessar ---")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)
print("----------------------------------------------------")