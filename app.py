from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import plotly.express as px
import plotly
import io
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

app = Flask(__name__)

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
def index():
    anos = sorted(df_residuos['Ano da geração'].unique())
    tipos_residuos = sorted(df_residuos['Tipo de Resíduo'].unique())
    return render_template('index.html', anos=anos, tipos_residuos=tipos_residuos)

@app.route('/dados-por-tipo', methods=['POST'])
def dados_por_tipo():
    tipo_residuo = request.json['tipo_residuo']
    df_tipo = df_residuos[(df_residuos['Tipo de Resíduo'] == tipo_residuo) & 
                        (df_residuos['Ano da geração'] >= 2012) & 
                        (df_residuos['Ano da geração'] <= 2023)]

    # Checar se o DataFrame não está vazio
    if df_tipo.empty:
        return jsonify({'erro': 'Nenhum dado disponível para o tipo de resíduo selecionado.'})

    # Remover ou substituir valores NaN, se necessário
    df_tipo['Quantidade Gerada'].fillna(0, inplace=True)

    # Converte a quantidade para float, tratando a vírgula como separador decimal
    df_tipo['Quantidade Gerada'] = df_tipo['Quantidade Gerada'].apply(lambda x: float(str(x).replace(',', '.')))

    # Transformar o 'Ano da geração' em string e ordenar
    df_tipo['Ano da geração'] = df_tipo['Ano da geração'].astype(str).sort_values()

    # Criação do gráfico de barras com barras sobrepostas
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
        barmode='overlay',
        xaxis=dict(categoryorder='category ascending')  # Garante a ordenação correta do eixo X
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

    return jsonify({
        'graficoBarra': json.dumps(fig_barra, cls=plotly.utils.PlotlyJSONEncoder),
        'graficoPizza': json.dumps(fig_pizza, cls=plotly.utils.PlotlyJSONEncoder)
    })

@app.route('/exportar_csv', methods=['POST'])
def exportar_csv():
    tipo_residuo = request.json['tipo_residuo']
    df_tipo = df_residuos[(df_residuos['Tipo de Resíduo'] == tipo_residuo) & 
                        (df_residuos['Ano da geração'] >= 2012) & 
                        (df_residuos['Ano da geração'] <= 2023)]
    df_tipo['Quantidade Gerada'] = df_tipo['Quantidade Gerada'].apply(lambda x: f"{x:.2f}".replace('.', ','))

    output = io.StringIO()
    df_tipo.to_csv(output, index=False, sep=';', encoding='utf-8')
    output.seek(0)
    
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'residuos_{tipo_residuo}.csv'
    )

@app.route('/exportar_pdf', methods=['POST'])
def exportar_pdf():
    tipo_residuo = request.json['tipo_residuo']
    df_tipo = df_residuos[(df_residuos['Tipo de Resíduo'] == tipo_residuo) & 
                        (df_residuos['Ano da geração'] >= 2012) & 
                        (df_residuos['Ano da geração'] <= 2023)]
    
    for _, row in df_tipo.iterrows():
        line = f"Ano: {row['Ano da geração']}, Quantidade: {row['Quantidade Gerada']:.2f}".replace('.', ',')

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    p.setFont("Helvetica-Bold", 16)
    p.drawString(72, height - 72, f"Relatório de Resíduos Gerados - {tipo_residuo}")

    p.setFont("Helvetica", 12)
    y = height - 144
    for _, row in df_tipo.iterrows():
        line = f"Ano: {row['Ano da geração']}, Quantidade: {row['Quantidade Gerada']}"
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
        download_name=f'relatorio_residuos_{tipo_residuo}.pdf'
    )

if __name__ == '__main__':
    app.run(debug=True)
