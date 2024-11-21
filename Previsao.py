import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt
import numpy as np

# Ler os dados do arquivo CSV (olhei essa funçao e achei válida pq a gente vai usar os dados secos no csv)
data = pd.read_csv('dados_lixo_historicos.csv') # Os dados vão estar aqui'C:\Users\filip\OneDrive\Documentos\Filipe\Projeto dashboard\relatorio-SSA.csv'

# Preparar os dados
X = data[['data']]  # Usaremos a coluna 'data' como variável independente
y = data['quantidade']  # Usaremos a coluna 'quantidade' como variável dependente

# Dividir os dados em treinamento e teste
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Criar e treinar o modelo de regressão linear (Aplicação de Caio para matéria dele)
model = LinearRegression()
model.fit(X_train, y_train)

# Avaliar o desempenho do modelo
score = model.score(X_test, y_test)
print(f'Precisão do modelo: {score:.2f}')

# Criar uma função para fazer previsões futuras
def fazer_previsao(data_futura):
    futuro = pd.DataFrame({'data': [data_futura]})
    return model.predict(futuro)[0]

# Plotar os resultados
plt.figure(figsize=(12,6))
plt.scatter(X['data'], y, label='Dados reais', alpha=0.5)
plt.plot(X['data'], model.predict(X), color='red', linewidth=3, label='Previsão')
plt.xlabel('Data')
plt.ylabel('Quantidade de Lixo')
plt.title('Previsão de Quantidade de Lixo')
plt.legend()
plt.show()

# Exemplo de uso da função de previsão
data_futura = pd.to_datetime('2024-12-31')
previsao = fazer_previsao(data_futura)
print(f'A previsão para {data_futura} é: {previsao:.2f}')
