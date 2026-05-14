-- Script de inicialização do PostgreSQL
-- Cria databases adicionais necessários

-- Database para o n8n
CREATE DATABASE n8n;
GRANT ALL PRIVILEGES ON DATABASE n8n TO postgres;

-- Extensão UUID para o banco principal
\c atendimento
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- Para busca de texto
