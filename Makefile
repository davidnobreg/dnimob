.PHONY: help build up down logs shell migrate migrate-shared createsuperuser collectstatic create-tenant network

help:
	@echo ""
	@echo "  ImobCloud — comandos disponíveis"
	@echo ""
	@echo "  Configuração inicial:"
	@echo "    make network          Cria a rede Docker externa (1x apenas)"
	@echo "    make build            Build das imagens"
	@echo "    make up               Sobe web, celery, celery-beat, flower"
	@echo ""
	@echo "  Banco de dados:"
	@echo "    make migrate-shared   Migrations do schema public (1x no início)"
	@echo "    make migrate          Migrations em todos os tenants"
	@echo ""
	@echo "  Operação:"
	@echo "    make down             Para todos os serviços"
	@echo "    make logs             Logs em tempo real"
	@echo "    make shell            Django shell interativo"
	@echo "    make collectstatic    Coleta arquivos estáticos"
	@echo "    make create-tenant    Cria um tenant de teste"
	@echo ""

# Cria a rede externa compartilhada (rode uma vez por servidor)
network:
	docker network create imob_network 2>/dev/null || echo "Rede imob_network já existe."

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f web celery celery-beat

shell:
	docker-compose exec web python manage.py shell

migrate:
	docker-compose exec web python manage.py migrate_schemas

migrate-shared:
	docker-compose exec web python manage.py migrate_schemas --shared

createsuperuser:
	docker-compose exec web python manage.py createsuperuser

collectstatic:
	docker-compose exec web python manage.py collectstatic --noinput

create-tenant:
	docker-compose exec web python manage.py shell -c "\
from apps.tenants.services import criar_tenant; \
t, dominio, senha = criar_tenant('imob_teste', 'Imobiliária Teste', 'admin@teste.com'); \
print(f'\nTenant criado com sucesso!'); \
print(f'  Domínio : {dominio}'); \
print(f'  Usuário : admin'); \
print(f'  Senha   : {senha}\n')"

# Shell dentro de um schema específico
# uso: make tenant-shell schema=imob_alpha
tenant-shell:
	docker-compose exec web python manage.py tenant_command shell --schema=$(schema)

# Verifica se a rede externa existe e os containers externos são visíveis
check-network:
	@echo "=== Rede imob_network ===" && docker network inspect imob_network --format '{{range .Containers}}{{.Name}} {{end}}' 2>/dev/null || echo "Rede não encontrada — rode: make network"
