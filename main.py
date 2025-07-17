from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
import json
import os
import threading
import time
from dotenv import load_dotenv

app = Flask(__name__)

load_dotenv()  # Carrega variáveis de ambiente do arquivo .env

# Credenciais Twilio (necessário para enviar múltiplas mensagens)
ACCOUNT_SID = os.getenv('ACCOUNT_SID')  # Corrigido
AUTH_TOKEN = os.getenv('AUTH_TOKEN')  # Corrigido
TWILIO_NUMBER = os.getenv('TWILIO_NUMBER')  # Corrigido

# Inicializa cliente Twilio
client = Client(ACCOUNT_SID, AUTH_TOKEN)

# Carrega perguntas do questionário (arquivo JSON externo)
with open('perguntas.json', encoding='utf-8') as f:
    perguntas = json.load(f)

# URL do áudio de saudação (deve estar hospedado com HTTPS)
AUDIO_URL = "https://www.example.com/saudacao.mp3"  # Altere para sua URL real

# Armazena conversas temporárias (use DB ou Redis em produção)
user_conversations = {}

# Função para enviar mensagem secundária após um pequeno delay
def enviar_mensagem_secundaria(para, audio_url, mensagem):
    time.sleep(1)  # Pequeno delay para garantir ordem das mensagens
    
    # Envia áudio
    client.messages.create(
        body="",
        media_url=[audio_url],
        to=para,
        from_=TWILIO_NUMBER
    )
    
    # Envia mensagem com pergunta sobre continuidade
    time.sleep(1)  # Pequeno delay entre mensagens
    client.messages.create(
        body=mensagem,
        to=para,
        from_=TWILIO_NUMBER
    )

@app.route("/")
def home():
    return """
    <h1>🤖 Bot Evelyn-Mon</h1>
    <p>Bot está rodando! ✅</p>
    <p>Webhook URL: <code>/bot</code></p>
    <p>Status: Aguardando mensagens do WhatsApp</p>
    """

@app.route("/bot", methods=['POST'])
def bot():
    sender = request.form.get('From', 'test_user')  # Ex: 'whatsapp:+5511999999999'
    body = request.form.get('Body', '').strip()

    resp = MessagingResponse()
    msg = resp.message()

    # Debug mais detalhado
    print(f"DEBUG RECEBIDO: Sender: {sender}, Body: '{body}'")

    # Inicializa conversa
    if sender not in user_conversations:
        user_conversations[sender] = {
            'etapa': 0,
            'respostas': [],
            'nome': '',
            'iniciado': False
        }
        print(f"DEBUG: Nova conversa iniciada para {sender}")

    conversa = user_conversations[sender]
    etapa = conversa['etapa']

    print(f"DEBUG: Estado atual: Etapa: {etapa}, Iniciado: {conversa['iniciado']}")

    if etapa == 0:
        if not conversa['iniciado']:
            # PRIMEIRA MENSAGEM - Removendo áudio temporariamente para debug
            mensagem_boas_vindas = f"👋 Olá! Seja bem-vindo(a) ao nosso atendimento!\n\n{perguntas[0]}"
            msg.body(mensagem_boas_vindas)
            # REMOVA OU COMENTE ESTA LINHA PARA TESTE:
            # msg.media(AUDIO_URL)
            conversa['iniciado'] = True
            print(f"DEBUG: Enviando primeira mensagem: {mensagem_boas_vindas}")
            print(f"{{pergunta: {perguntas[0]}; resposta: aguardando...}}")
        else:
            if body:
                conversa['nome'] = body
                conversa['respostas'].append(body)
                conversa['etapa'] = 1
                pergunta = perguntas[1].format(nome=conversa['nome'])
                msg.body(pergunta)
                print(f"{{pergunta: {perguntas[0]}; resposta: {body}}}")
                print(f"{{pergunta: {pergunta}; resposta: aguardando...}}")
            else:
                msg.body("Por favor, me diga seu nome 😊")
                print(f"{{pergunta: Por favor, me diga seu nome 😊; resposta: aguardando...}}")

    elif etapa == 1:
        conversa['respostas'].append(body)
        conversa['etapa'] = 2
        interesse = body.lower()

        if any(word in interesse for word in ['sim', 'quero', 'tenho', 'gostaria', 'yes', 'ok']):
            # Usando a thread para enviar mensagens múltiplas
            msg.body(perguntas[2])  # "Legal! Vou te encaminhar um áudio..."
            
            # Inicia thread para enviar as próximas mensagens
            threading.Thread(
                target=enviar_mensagem_secundaria,
                args=(sender, AUDIO_URL, perguntas[3])
            ).start()
            
            # Logs
            print(f"{{pergunta: {perguntas[1].format(nome=conversa['nome'])}; resposta: {body}}}")
            print(f"{{pergunta: {perguntas[2]}; resposta: enviando áudio...}}")
            print(f"{{pergunta: {perguntas[3]}; resposta: aguardando...}}")
        else:
            msg.body(perguntas[5])  # resposta negativa final
            print(f"{{pergunta: {perguntas[1].format(nome=conversa['nome'])}; resposta: {body}}}")
            print(f"{{pergunta: {perguntas[5]}; resposta: conversa encerrada}}")
            del user_conversations[sender]

    elif etapa == 2:
        conversa['respostas'].append(body)
        continuar = body.lower()

        if any(word in continuar for word in ['sim', 'quero', 'tenho', 'vamos', 'yes', 'ok']):
            resumo = f"""{perguntas[4]}

📋 Resumo da conversa:
👤 Nome: {conversa['nome']}
💊 Interesse inicial: {conversa['respostas'][1]}
📞 Quer continuar: {conversa['respostas'][2]}
✅ Status: Direcionado para questionário"""
            msg.body(resumo)
            print(f"{{pergunta: {perguntas[3]}; resposta: {body}}}")
            print(f"{{pergunta: {perguntas[4]}; resposta: questionário enviado}}")
        else:
            msg.body(perguntas[5])
            print(f"{{pergunta: {perguntas[3]}; resposta: {body}}}")
            print(f"{{pergunta: {perguntas[5]}; resposta: conversa encerrada}}")

        del user_conversations[sender]

    return str(resp)

@app.route("/debug")
def debug():
    return f"<h2>Debug - Conversas ativas:</h2><pre>{json.dumps(user_conversations, indent=2, ensure_ascii=False)}</pre>"

if __name__ == "__main__":
    app.run(debug=True, port=5000)

