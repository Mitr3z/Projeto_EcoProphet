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
app.secret_key = os.urandom(24)

client = MongoClient('mongodb://localhost:27017/')
db = client['ecoprophet_db']
users_collection = db['users']
analises_collection = db['analises']
previsoes_collection = db['previsoes']

bcrypt = Bcrypt(app)

# É preciso alterar o caminho sempre para onde quer que o arquivo CSV esteja possa ser lido
caminho_csv = r'Projeto_EcoProphet\relatorio-SSA.csv'


def carregar_dataframe(caminho):
    try:
        df = pd.read_csv(caminho, sep=';', encoding='utf-8', on_bad_lines='skip', decimal=',', thousands='.')
        return df
    except Exception as e:
        print(f"Erro ao carregar o arquivo CSV: {e}")
        return pd.DataFrame()


df_residuos = carregar_dataframe(caminho_csv)


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


    df_tipo['Quantidade Gerada'].fillna(0, inplace=True)

    df_tipo['Quantidade Gerada'] = df_tipo['Quantidade Gerada'].apply(lambda x: float(str(x).replace(',', '.')))

    df_tipo['Ano da geração'] = df_tipo['Ano da geração'].astype(str)
    df_tipo = df_tipo.sort_values('Ano da geração')

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
    tipo_relatorio = request.json.get('tipo_relatorio', 'analise')
    
    if tipo_relatorio == 'analise':
        df_tipo = df_residuos[df_residuos['Tipo de Resíduo'] == tipo_residuo]
    else:
        previsao = previsoes_collection.find_one({'user_id': session.get('user_id'), 'tipo_residuo': tipo_residuo}, sort=[('data_previsao', -1)])
        if previsao:
            df_tipo = pd.DataFrame(previsao['dados'])
            # Não fazemos o merge aqui para previsões
        else:
            return jsonify({'erro': 'Nenhuma previsão encontrada'})

    # Ordenar o DataFrame por ano
    df_tipo = df_tipo.sort_values('Ano da geração')
    
    # Reordenar as colunas conforme especificado, mas apenas as que existem
    colunas_ordem = ['CNPJ do gerador', 'Razão Social do gerador', 'Estado', 'Município', 
                    'Código da Categoria', 'Categoria de Atividade', 'Código do Detalhe', 
                    'Detalhe', 'Ano da geração', 'Cód. Resíduo', 'Tipo de Resíduo', 
                    'Quantidade Gerada', 'Unidade', 'Classificação Resíduo', 'Situação Cadastral']
    
    colunas_existentes = [col for col in colunas_ordem if col in df_tipo.columns]
    df_tipo = df_tipo[colunas_existentes]
    
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
    tipo_relatorio = request.json.get('tipo_relatorio', 'analise')
    
    if tipo_relatorio == 'analise':
        df_tipo = df_residuos[df_residuos['Tipo de Resíduo'] == tipo_residuo]
    else:
        previsao = previsoes_collection.find_one({'user_id': session.get('user_id'), 'tipo_residuo': tipo_residuo}, sort=[('data_previsao', -1)])
        if previsao:
            df_tipo = pd.DataFrame(previsao['dados'])
        else:
            return jsonify({'erro': 'Nenhuma previsão encontrada'})

    # Ordenar o DataFrame por ano
    df_tipo = df_tipo.sort_values('Ano da geração')

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    p.setFont("Helvetica-Bold", 16)
    p.drawString(72, height - 72, f"Relatório de {tipo_relatorio.capitalize()} - {tipo_residuo}")

    p.setFont("Helvetica", 10)
    y = height - 100

    if tipo_relatorio == 'analise':
        for _, row in df_tipo.iterrows():
            p.setFont("Helvetica-Bold", 12)
            p.drawString(72, y, f"Ano: {row['Ano da geração']}")
            y -= 20
            p.setFont("Helvetica", 10)
            
            campos = [
                f"CNPJ: {row.get('CNPJ do gerador', 'N/A')}",
                f"Razão Social: {row.get('Razão Social do gerador', 'N/A')}",
                f"Estado: {row.get('Estado', 'N/A')}",
                f"Município: {row.get('Município', 'N/A')}",
                f"Categoria: {row.get('Categoria de Atividade', 'N/A')} (Código: {row.get('Código da Categoria', 'N/A')})",
                f"Detalhe: {row.get('Detalhe', 'N/A')} (Código: {row.get('Código do Detalhe', 'N/A')})",
                f"Cód. Resíduo: {row.get('Cód. Resíduo', 'N/A')}",
                f"Quantidade: {row['Quantidade Gerada']:.2f} {row.get('Unidade', 'kg')}".replace('.', ','),
                f"Classificação: {row.get('Classificação Resíduo', 'N/A')}",
                f"Situação Cadastral: {row.get('Situação Cadastral', 'N/A')}"
            ]
            
            for campo in campos:
                p.drawString(80, y, campo)
                y -= 15
                if y < 72:
                    p.showPage()
                    y = height - 72

            y -= 10  # Espaço extra entre registros
    else:  # Para relatório de previsão
        p.setFont("Helvetica-Bold", 12)
        p.drawString(72, y, "Ano | Quantidade Prevista (kg)")
        y -= 20
        p.setFont("Helvetica", 10)
        
        for _, row in df_tipo.iterrows():
            ano = row['Ano da geração']
            quantidade = f"{row['Quantidade Gerada']:.2f}".replace('.', ',')
            linha = f"{ano} | {quantidade} kg"
            p.drawString(80, y, linha)
            y -= 15
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

    df_tipo = df_tipo.groupby('Ano da geração')['Quantidade Gerada'].sum().reset_index()

    X = df_tipo['Ano da geração'].values.reshape(-1, 1)
    y = df_tipo['Quantidade Gerada'].values

    if len(X) < 2:
        return jsonify({'erro': 'Dados insuficientes para fazer a previsão. São necessários pelo menos dois anos de dados.'})

    model = LinearRegression()
    model.fit(X, y)

    ultimo_ano = int(X.max())
    anos_futuros = np.array(range(ultimo_ano + 1, ultimo_ano + anos_previsao + 1)).reshape(-1, 1)
    previsoes = model.predict(anos_futuros)

    todos_anos = np.concatenate([X.flatten(), anos_futuros.flatten()])
    todas_quantidades = np.concatenate([y, previsoes])

    df_previsao = pd.DataFrame({
        'Ano da geração': todos_anos,
        'Quantidade Gerada': todas_quantidades
    })

    fig = px.line(df_previsao, x='Ano da geração', y='Quantidade Gerada', 
                title=f'Previsão de Resíduos para {tipo_residuo}')
    fig.add_scatter(x=X.flatten(), y=y, mode='markers', name='Dados Reais')
    fig.add_scatter(x=anos_futuros.flatten(), y=previsoes, mode='markers', name='Previsões')

    # Ajuste no layout do gráfico para ser mais flexível
    fig.update_layout(
        autosize=True,
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

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
