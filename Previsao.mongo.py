import pymongo
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
import numpy as np
#Previsao com MongoDb e com a API de atualização do horário 

# Conectar ao banco de dados MongoDB
client = pymongo.MongoClient("mongodb://localhost:27017/")
db = client["lixo"]
collection = db["historicos"]

# Coletar os dados históricos
cursor = collection.find()
data_historica = []
for doc in cursor:
    data_historica.append(doc)

# Preparar os dados
X = np.array([d['data'] for d in data_historica]).reshape(-1, 1)
y = np.array([d['quantidade'] for d in data_historica])

# Dividir os dados em treinamento e teste
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Criar e treinar o modelo de regressão linear
model = LinearRegression()
model.fit(X_train, y_train)

# Avaliar o desempenho do modelo
score = model.score(X_test, y_test)
print(f'Precisão do modelo: {score:.2f}')

# Criar uma função para fazer previsões futuras
def fazer_previsao(data_futura):
    futuro = np.array([[data_futura]])
    return model.predict(futuro)[0]

# Implementar a lógica de previsão no banco de dados MongoDB
def atualizar_previsao():
    # Obter os dados mais recentes do banco
    cursor = collection.find().sort("data", -1).limit(1)
    mais_recente = next(cursor)
    
    # Fazer a previsão para o próximo dia
    data_proxima = mais_recente['data'] + timedelta(days=1)
    previsao = fazer_previsao(data_proxima)
    
    # Atualizar o documento no banco de dados
    collection.update_one(
        {"_id": mais_recente["_id"]},
        {"$set": {
            "previsao_lixo": previsao,
            "data_previsao": data_proxima
        }}
    )

# Executar a atualização de previsão periodicamente (por exemplo, todos os dias)
import schedule
import time

def job():
    atualizar_previsao()

schedule.every().day.at("00:00").do(job)  # Executar às 0h00 da manhã

while True:
    schedule.run_pending()
    time.sleep(1)
  
