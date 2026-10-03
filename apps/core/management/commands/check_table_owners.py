"""
Verifica se alguma tabela do banco pertence a um owner diferente do usuário
de conexão configurado em DATABASES. Owner divergente faz ALTER TABLE
(rodado em migrations) falhar com "permission denied" — Postgres exige ser
owner (ou superuser) pra ALTER TABLE, GRANT normal não cobre isso.

Rodar antes de migrate_schemas no deploy, pra falhar cedo com mensagem clara
em vez do erro genérico do Postgres no meio da migration.
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Verifica se todas as tabelas pertencem ao usuário de conexão configurado.'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT schemaname, tablename, tableowner
                FROM pg_tables
                WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
                  AND tableowner != current_user
                ORDER BY schemaname, tablename
            """)
            divergentes = cursor.fetchall()

        if not divergentes:
            self.stdout.write(self.style.SUCCESS('OK: todas as tabelas pertencem ao usuário de conexão.'))
            return

        self.stderr.write(self.style.ERROR(
            f'{len(divergentes)} tabela(s) com owner diferente do usuário de conexão '
            '(migrations com ALTER TABLE vão falhar com permission denied):'
        ))
        for schema, tabela, owner in divergentes:
            self.stderr.write(f'  {schema}.{tabela} (owner atual: {owner})')

        raise CommandError(
            'Corrija o owner antes de migrar, ex.: '
            'ALTER TABLE <schema>.<tabela> OWNER TO <usuario_da_aplicacao>;'
        )
