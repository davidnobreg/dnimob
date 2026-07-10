from django.db import migrations

# Valores lidos do banco dev em 2026-07-10, antes desta migration:
#   basico        | 100.00 | imoveis=10  | contratos=10  | usuarios=2  | whatsapp=True  | sicredi=False | ativo=True | destaque=False
#   profissional  | 400.00 | imoveis=50  | contratos=50  | usuarios=10 | whatsapp=False | sicredi=False | ativo=True | destaque=True
#   enterprise    |   0.00 | imoveis=None| contratos=None| usuarios=None| whatsapp=True | sicredi=True  | ativo=True | destaque=True
#
# preco_mensal e ativo são fixados/corrigidos aqui (97/197/397, ativo=True).
# limites, tem_whatsapp, tem_sicredi e destaque são apenas congelados como
# estavam — não foram alterados nem "corrigidos".
PLANOS = [
    {
        'nome': 'basico',
        'preco_mensal': 97,
        'ativo': True,
        'limite_imoveis': 10,
        'limite_contratos': 10,
        'limite_usuarios': 2,
        'tem_whatsapp': True,
        'tem_sicredi': False,
        'destaque': False,
    },
    {
        'nome': 'profissional',
        'preco_mensal': 197,
        'ativo': True,
        'limite_imoveis': 50,
        'limite_contratos': 50,
        'limite_usuarios': 10,
        'tem_whatsapp': False,
        'tem_sicredi': False,
        'destaque': True,
    },
    {
        'nome': 'enterprise',
        'preco_mensal': 397,
        'ativo': True,
        'limite_imoveis': None,
        'limite_contratos': None,
        'limite_usuarios': None,
        'tem_whatsapp': True,
        'tem_sicredi': True,
        'destaque': True,
    },
]


def fixar_planos(apps, schema_editor):
    Plano = apps.get_model('tenants', 'Plano')
    for dados in PLANOS:
        nome = dados['nome']
        defaults = {chave: valor for chave, valor in dados.items() if chave != 'nome'}
        Plano.objects.update_or_create(nome=nome, defaults=defaults)


class Migration(migrations.Migration):
    """
    Não reversível de forma significativa: não há como recuperar os preços/
    status anteriores (100/400/0, todos já ativos) — reverter não desfaria
    nada de útil, então reverse_code é noop.
    """

    dependencies = [
        ('tenants', '0009_plano_destaque_tenant_aceite_termos_user_agent'),
    ]

    operations = [
        migrations.RunPython(fixar_planos, migrations.RunPython.noop),
    ]
