# Importando bibliotecas necessárias
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
import plotly.express as px
from flask import Flask, render_template, request, jsonify
import json
import plotly

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

# Iniciando a aplicação Flask
app = Flask(__name__)

# Variável para contar os meses previstos (controle)
mes_contador = 0

# Rota para a página principal
@app.route('/')
def index():
    return render_template('index.html')

# Rota para prever resíduos
@app.route('/prever', methods=['POST'])
def prever():
    global mes_contador

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

    # Criando nome dinâmico para o novo mês (ex: Mês Previsto 1, 2, 3...)
    mes_contador += 1
    nome_novo_mes = f'Previsto {mes_contador}'

    # Adicionando o novo mês aos dados existentes
    df.loc[len(df)] = [nome_novo_mes, organico, reciclavel, outros, evento_especial, residuos_previstos]

    # Gráfico 1: Linha sinuosa
    fig_linha = px.line(df, x='Mes', y='Residuos_Gerados',
                        title='Resíduos Gerados por Mês',
                        labels={'Mes': 'Mês', 'Residuos_Gerados': 'Resíduos (Kg)'},
                        line_shape='spline', markers=True)

    # Gráfico 2: Gráfico de pizza mostrando distribuição de tipos de resíduos no novo mês
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

    # Retornando os gráficos e o valor previsto
    return jsonify({
        'previsao': f"Previsão de resíduos para {nome_novo_mes}: {residuos_previstos:.2f} Kg",
        'graficoLinha': linha_json,
        'graficoPizza': pizza_json
    })

# Executa o app
if __name__ == '__main__':
    app.run(debug=True)