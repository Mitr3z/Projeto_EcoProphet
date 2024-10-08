from flask import render_template, request, jsonify, send_file
from config import app, collection
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
import plotly.express as px
import json
import plotly
import io
import csv
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
import time
import base64

# Dados fictícios com resíduos gerados por 5 meses
data = {
    'Mes': ['Jan', 'Fev', 'Mar', 'Abr', 'Mai'],
    'Organico': [50, 60, 55, 65, 70],
    'Reciclavel': [30, 35, 32, 34, 36],
    'Outros': [20, 25, 22, 21, 24],
    'Evento_Especial': [0, 0, 1, 0, 0],
    'Residuos_Gerados': [100, 120, 109, 120, 130]
}

# Convertendo os dados em DataFrame
df = pd.DataFrame(data)

# Variável para contar os meses previstos (controle)
mes_contador = 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/prever', methods=['POST'])
def prever():
    global mes_contador, df

    # Recebendo dados do formulário
    meses_selecionados = request.json['mesesSelecionados']
    organico = float(request.json['organico'])
    reciclavel = float(request.json['reciclavel'])
    outros = float(request.json['outros'])
    evento_especial = int(request.json['eventoEspecial'])

    if not meses_selecionados:
        return jsonify({'error': 'Selecione pelo menos um mês para treinar o modelo.'}), 400

    # Treinando o modelo com os meses selecionados
    df_treino = df.iloc[meses_selecionados]
    X_treino = df_treino[['Organico', 'Reciclavel', 'Outros', 'Evento_Especial']]
    y_treino = df_treino['Residuos_Gerados']

    # Criando o modelo de regressão linear
    model = LinearRegression()
    model.fit(X_treino, y_treino)

    # Prevendo resíduos para o próximo mês com base nas entradas do usuário
    dados_mes_a_prever = {
        'Organico': [organico],
        'Reciclavel': [reciclavel],
        'Outros': [outros],
        'Evento_Especial': [evento_especial]
    }
    df_mes_prever = pd.DataFrame(dados_mes_a_prever)
    residuos_previstos = model.predict(df_mes_prever)[0]

    # Aplicando o aumento de 50% no valor previsto se houver evento especial
    if evento_especial == 1:
        residuos_previstos *= 1.5

    # Criando nome dinâmico para o novo mês
    mes_contador += 1
    nome_novo_mes = f'Previsto {mes_contador}'

    # Adicionando o novo mês aos dados existentes
    df.loc[len(df)] = [nome_novo_mes, organico, reciclavel, outros, evento_especial, residuos_previstos]

    # Gráfico 1: Linha sinuosa
    fig_linha = px.line(df, x='Mes', y='Residuos_Gerados',
                        title='Resíduos Gerados por Mês',
                        labels={'Mes': 'Mês', 'Residuos_Gerados': 'Resíduos (Kg)'},
                        line_shape='spline', markers=True)

    # Gráfico 2: Gráfico de pizza
    residuos_por_tipo = {
        'Tipo': ['Orgânico', 'Reciclável', 'Outros'],
        'Quantidade': [organico, reciclavel, outros]
    }
    df_tipo = pd.DataFrame(residuos_por_tipo)
    fig_pizza = px.pie(df_tipo, names='Tipo', values='Quantidade',
                    title=f'Distribuição de Resíduos por Tipo ({nome_novo_mes})')

    # Convertendo gráficos para JSON
    linha_json = json.dumps(fig_linha, cls=plotly.utils.PlotlyJSONEncoder)
    pizza_json = json.dumps(fig_pizza, cls=plotly.utils.PlotlyJSONEncoder)

    # Salvando a previsão no MongoDB
    previsao_doc = {
        'mes': nome_novo_mes,
        'organico': organico,
        'reciclavel': reciclavel,
        'outros': outros,
        'evento_especial': evento_especial,
        'residuos_previstos': residuos_previstos,
        'data_previsao': datetime.now()
    }
    resultado = collection.insert_one(previsao_doc)

    return jsonify({
        'previsao': f"Previsão de resíduos para {nome_novo_mes}: {residuos_previstos:.2f} Kg",
        'graficoLinha': linha_json,
        'graficoPizza': pizza_json,
        'id_previsao': str(resultado.inserted_id)
    })

@app.route('/previsoes', methods=['GET'])
def obter_previsoes():
    previsoes = list(collection.find())
    for previsao in previsoes:
        previsao['_id'] = str(previsao['_id'])  # Converte ObjectId para string
    return jsonify(previsoes)

@app.route('/exportar_csv', methods=['POST'])
def exportar_csv():
    previsoes = list(collection.find())
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Mês', 'Resíduos Gerados', 'Orgânico', 'Reciclável', 'Outros', 'Evento Especial'])
    for previsao in previsoes:
        writer.writerow([
            previsao['mes'],
            previsao['residuos_previstos'],
            previsao['organico'],
            previsao['reciclavel'],
            previsao['outros'],
            previsao['evento_especial']
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='residuos.csv'
    )

@app.route('/exportar_pdf', methods=['POST'])
def exportar_pdf():
    try:
        app.logger.info("Iniciando exportação de PDF")
        previsoes = list(collection.find())
        app.logger.info(f"Dados recuperados: {previsoes}")

        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # Título
        p.setFont("Helvetica-Bold", 16)
        p.drawString(inch, height - inch, "Relatório de Resíduos Gerados")

        # Dados
        p.setFont("Helvetica", 12)
        y = height - 2*inch
        for previsao in previsoes:
            p.drawString(inch, y, f"{previsao['mes']}: {previsao['residuos_previstos']:.2f} Kg")
            y -= 20

        app.logger.info("Finalizando PDF")
        p.showPage()
        p.save()

        buffer.seek(0)
        app.logger.info("PDF gerado com sucesso")
        time.sleep(1)  # Adiciona um atraso de 1 segundo
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name='relatorio_residuos.pdf'
        )
    except Exception as e:
        app.logger.error(f"Erro ao gerar PDF: {str(e)}")
        return jsonify({"error": str(e)}), 500

if (__name__) == '__main__':
    app.run(debug=True)