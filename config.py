from flask import Flask
from pymongo import MongoClient
from flask_cors import CORS

# Iniciando a aplicação Flask
app = Flask(__name__)
CORS(app)

# Configuração do MongoDB
client = MongoClient('mongodb://localhost:27017/')  # Ajuste a URL conforme necessário
db = client['residuos_db']  # Nome do banco de dados
collection = db['previsoes']  # Nome da coleção