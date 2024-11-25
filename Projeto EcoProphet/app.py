from flask import Flask, render_template, request, jsonify, redirect, url_for, session, send_file, flash
from pymongo import MongoClient
from flask_bcrypt import Bcrypt
import os
from bson import ObjectId
import pandas as pd
import plotly.express as px
import plotly
import io
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from sklearn.linear_model import LinearRegression
import numpy as np
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Chave secreta para sessões

client = MongoClient('mongodb://localhost:27017/')
db = client['ecoprophet_db']
users_collection = db['users']
analises_collection = db['analises']
previsoes_collection = db['previsoes']

bcrypt = Bcrypt(app)

# Caminho para o arquivo CSV
caminho_csv = r'C:\Users\filip\OneDrive\Documentos\Filipe\Projeto dashboard\relatorio-SSA.csv'

# Carregar o DataFrame do CSV
def carregar_dataframe(caminho):
    try:
        df = pd.read_csv(caminho, sep=';', encoding='utf-8', on_bad_lines='skip', decimal=',', thousands='.')
        return df
    except Exception as e:
        print(f"Erro ao carregar o arquivo CSV: {e}")
        return pd.DataFrame()

# Carrega o DataFrame
df_residuos = carregar_dataframe(caminho_csv)

# Verificação se as colunas necessárias existem
necessarias = ['Ano da geração', 'Tipo de Resíduo', 'Quantidade Gerada']
for col in necessarias:
    if col not in df_residuos.columns:
        print(f"A coluna '{col}' não foi encontrada no DataFrame.")

@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        existing_user = users_collection.find_one({'username': username})
        if existing_user:
            return "Usuário já existe"
        
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        users_collection.insert_one({'username': username, 'password': hashed_password})
        
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = users_collection.find_one({'username': username})
        if user and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = str(user['_id'])
            return redirect(url_for('dashboard'))
        else:
            flash('Senha ou usuário incorretos. Por favor, tente novamente.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = users_collection.find_one({'_id': ObjectId(session['user_id'])})
    return render_template('dashboard.html', username=user['username'])

@app.route('/analise')
def analise():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    anos = sorted(df_residuos['Ano da geração'].unique())
    tipos_residuos = sorted(df_residuos['Tipo de Resíduo'].unique())
    return render_template('analise.html', anos=anos, tipos_residuos=tipos_residuos)

@app.route('/previsao')
def previsao():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    tipos_residuos = sorted(df_residuos['Tipo de Resíduo'].unique())
    return render_template('previsao.html', tipos_residuos=tipos_residuos)

@app.route('/dados-por-tipo', methods=['POST'])
def dados_por_tipo():
    tipo_residuo = request.json['tipo_residuo']
    user_id = session.get('user_id')
    
    df_tipo = df_residuos[(df_residuos['Tipo de Resíduo'] == tipo_residuo) & 
                        (df_residuos['Ano da geração'] >= 2012) & 
                        (df_residuos['Ano da geração'] <= 2023)]

    if df_tipo.empty:
        return jsonify({'erro': 'Nenhum dado disponível para o tipo de resíduo selecionado.'})

    # Agrupar por ano e somar as quantidades
    df_tipo = df_tipo.groupby('Ano da geração')['Quantidade Gerada'].sum().reset_index()

    # Remover ou substituir valores NaN, se necessário
    df_tipo['Quantidade Gerada'].fillna(0, inplace=True)

    # Converte a quantidade para float, tratando a vírgula como separador decimal
    df_tipo['Quantidade Gerada'] = df_tipo['Quantidade Gerada'].apply(lambda x: float(str(x).replace(',', '.')))

    # Transformar o 'Ano da geração' em string e ordenar
    df_tipo['Ano da geração'] = df_tipo['Ano da geração'].astype(str)
    df_tipo = df_tipo.sort_values('Ano da geração')

    # Criação do gráfico de barras
    fig_barra = px.bar(
        df_tipo, 
        x='Ano da geração', 
        y='Quantidade Gerada',
        title=f'Resíduos por Ano para {tipo_residuo}',
        labels={'Quantidade Gerada': 'Quantidade (kg)', 'Ano da geração': 'Ano'},
        text='Quantidade Gerada'
    )
    
    # Configurações do layout
    fig_barra.update_layout(
        margin=dict(t=50, b=50, l=50, r=50),
        xaxis_title='Ano',
        yaxis_title='Quantidade (kg)',
        yaxis=dict(type='linear'),
        xaxis=dict(categoryorder='category ascending')
    )
    
    fig_barra.update_traces(
        texttemplate='%{text:.2f}', 
        textposition='outside',
        textfont=dict(size=10)
    )

    # Gráfico de Pizza
    fig_pizza = px.pie(
        df_tipo,
        values='Quantidade Gerada', 
        names='Ano da geração',
        title=f'Proporção de Quantidade por Ano para {tipo_residuo}'
    )
    
    fig_pizza.update_traces(textinfo='percent+label')
    fig_pizza.update_layout(margin=dict(t=50, b=50, l=50, r=50))

    # Salvar a análise no banco de dados
    analise = {
        'user_id': user_id,
        'tipo_residuo': tipo_residuo,
        'data_analise': datetime.now(),
        'dados': df_tipo.to_dict(orient='records')
    }
    analises_collection.insert_one(analise)

    return jsonify({
        'graficoBarra': json.dumps(fig_barra, cls=plotly.utils.PlotlyJSONEncoder),
        'graficoPizza': json.dumps(fig_pizza, cls=plotly.utils.PlotlyJSONEncoder)
    })

@app.route('/exportar_csv', methods=['POST'])
def exportar_csv():
    tipo_residuo = request.json['tipo_residuo']
    tipo_relatorio = request.json.get('tipo_relatorio', 'analise')  # 'analise' ou 'previsao'
    
    if tipo_relatorio == 'analise':
        df_tipo = df_residuos[(df_residuos['Tipo de Resíduo'] == tipo_residuo) & 
                            (df_residuos['Ano da geração'] >= 2012) & 
                            (df_residuos['Ano da geração'] <= 2023)]
    else:  # previsao
        # Recupere os dados de previsão do banco de dados
        previsao = previsoes_collection.find_one({'user_id': session.get('user_id'), 'tipo_residuo': tipo_residuo}, sort=[('data_previsao', -1)])
        if previsao:
            df_tipo = pd.DataFrame(previsao['dados'])
        else:
            return jsonify({'erro': 'Nenhuma previsão encontrada'})

    df_tipo['Quantidade Gerada'] = df_tipo['Quantidade Gerada'].apply(lambda x: f"{x:.2f}".replace('.', ','))

    output = io.StringIO()
    df_tipo.to_csv(output, index=False, sep=';', encoding='utf-8')
    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'{tipo_relatorio}_residuos_{tipo_residuo}.csv'
    )

@app.route('/exportar_pdf', methods=['POST'])
def exportar_pdf():
    tipo_residuo = request.json['tipo_residuo']
    tipo_relatorio = request.json.get('tipo_relatorio', 'analise')  # 'analise' ou 'previsao'
    
    if tipo_relatorio == 'analise':
        df_tipo = df_residuos[(df_residuos['Tipo de Resíduo'] == tipo_residuo) & 
                            (df_residuos['Ano da geração'] >= 2012) & 
                            (df_residuos['Ano da geração'] <= 2023)]
    else:  # previsao
        # Recupere os dados de previsão do banco de dados
        previsao = previsoes_collection.find_one({'user_id': session.get('user_id'), 'tipo_residuo': tipo_residuo}, sort=[('data_previsao', -1)])
        if previsao:
            df_tipo = pd.DataFrame(previsao['dados'])
        else:
            return jsonify({'erro': 'Nenhuma previsão encontrada'})

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    p.setFont("Helvetica-Bold", 16)
    p.drawString(72, height - 72, f"Relatório de {tipo_relatorio.capitalize()} - {tipo_residuo}")

    p.setFont("Helvetica", 12)
    y = height - 144
    for _, row in df_tipo.iterrows():
        line = f"Ano: {row['Ano da geração']}, Quantidade: {row['Quantidade Gerada']:.2f}".replace('.', ',')
        p.drawString(72, y, line)
        y -= 12
        if y < 72:
            p.showPage()
            y = height - 72

    p.save()
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'{tipo_relatorio}_residuos_{tipo_residuo}.pdf'
    )

@app.route('/prever', methods=['POST'])
def prever():
    tipo_residuo = request.json['tipo_residuo']
    anos_previsao = int(request.json['anos_previsao'])
    user_id = session.get('user_id')

    df_tipo = df_residuos[(df_residuos['Tipo de Resíduo'] == tipo_residuo) & 
                        (df_residuos['Ano da geração'] >= 2012) & 
                        (df_residuos['Ano da geração'] <= 2023)]

    if df_tipo.empty:
        return jsonify({'erro': 'Dados insuficientes para fazer a previsão.'})

    # Agrupar por ano e somar as quantidades
    df_tipo = df_tipo.groupby('Ano da geração')['Quantidade Gerada'].sum().reset_index()

    # Preparar os dados para o modelo
    X = df_tipo['Ano da geração'].values.reshape(-1, 1)
    y = df_tipo['Quantidade Gerada'].values

    # Verificar se há dados suficientes para fazer a previsão
    if len(X) < 2:
        return jsonify({'erro': 'Dados insuficientes para fazer a previsão. São necessários pelo menos dois anos de dados.'})

    # Criar e treinar o modelo
    model = LinearRegression()
    model.fit(X, y)

    # Fazer previsões
    ultimo_ano = int(X.max())
    primeiro_ano = int(X.min())
    anos_futuros = np.array(range(ultimo_ano + 1, ultimo_ano + anos_previsao + 1)).reshape(-1, 1)
    previsoes = model.predict(anos_futuros)

    # Preparar dados para o gráfico
    todos_anos = np.concatenate([X.flatten(), anos_futuros.flatten()])
    todas_quantidades = np.concatenate([y, previsoes])

    df_previsao = pd.DataFrame({
        'Ano da geração': todos_anos,
        'Quantidade Gerada': todas_quantidades
    })

    # Criar gráfico de linha com dados reais e previsões
    fig = px.line(df_previsao, x='Ano da geração', y='Quantidade Gerada', 
                title=f'Previsão de Resíduos para {tipo_residuo}')
    fig.add_scatter(x=X.flatten(), y=y, mode='markers', name='Dados Reais')
    fig.add_scatter(x=anos_futuros.flatten(), y=previsoes, mode='markers', name='Previsões')

    # Salvar a previsão no banco de dados
    previsao = {
        'user_id': user_id,
        'tipo_residuo': tipo_residuo,
        'data_previsao': datetime.now(),
        'anos_previsao': anos_previsao,
        'dados': df_previsao.to_dict(orient='records')
    }
    previsoes_collection.insert_one(previsao)

    return jsonify({
        'grafico': json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder),
        'previsoes': [{'ano': int(ano), 'quantidade': float(qtd)} for ano, qtd in zip(anos_futuros.flatten(), previsoes)]
    })

if __name__ == '__main__':
    app.run(debug=True)