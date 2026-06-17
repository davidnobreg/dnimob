# Cole no shell: python manage.py tenant_command shell --schema=imob_alpha

from apps.tenants.models import TemplateWhatsApp

templates = [
    {
        'evento': 'boas_vindas',
        'mensagem': 'Olá {nome_inquilino}! 👋\n\nSeja bem-vindo(a)! Seu contrato de locação do imóvel em {endereco_imovel} foi registrado com sucesso.\n\nQualquer dúvida, estamos à disposição.',
        'variaveis_disponiveis': ['nome_inquilino', 'endereco_imovel', 'nome_imobiliaria'],
    },
    {
        'evento': 'boleto_gerado',
        'mensagem': 'Olá {nome_inquilino}!\n\nSeu boleto referente ao imóvel {endereco_imovel} já está disponível.\n\n💰 Valor: R$ {valor}\n📅 Vencimento: {data_vencimento}\n\nLinha digitável:\n{linha_digitavel}',
        'variaveis_disponiveis': ['nome_inquilino', 'endereco_imovel', 'valor', 'data_vencimento', 'linha_digitavel'],
    },
    {
        'evento': 'vence_amanha',
        'mensagem': 'Olá {nome_inquilino}! ⏰\n\nLembramos que seu boleto do imóvel {endereco_imovel} vence amanhã ({data_vencimento}).\n\n💰 Valor: R$ {valor}\n\nEvite multa e juros, pague em dia!',
        'variaveis_disponiveis': ['nome_inquilino', 'endereco_imovel', 'valor', 'data_vencimento'],
    },
    {
        'evento': 'vence_hoje',
        'mensagem': 'Olá {nome_inquilino}! 📌\n\nSeu boleto do imóvel {endereco_imovel} vence HOJE ({data_vencimento}).\n\n💰 Valor: R$ {valor}\n\nNão deixe para depois, evite encargos por atraso.',
        'variaveis_disponiveis': ['nome_inquilino', 'endereco_imovel', 'valor', 'data_vencimento'],
    },
    {
        'evento': 'atraso_3',
        'mensagem': 'Olá {nome_inquilino},\n\nIdentificamos que o boleto do imóvel {endereco_imovel}, vencido em {data_vencimento}, ainda não foi pago.\n\n💰 Valor atualizado: R$ {valor}\n\nRegularize o quanto antes para evitar maiores encargos.',
        'variaveis_disponiveis': ['nome_inquilino', 'endereco_imovel', 'valor', 'data_vencimento', 'dias_atraso'],
    },
    {
        'evento': 'atraso_7',
        'mensagem': 'Olá {nome_inquilino},\n\nSeu boleto do imóvel {endereco_imovel} está em atraso há {dias_atraso} dias (vencimento {data_vencimento}).\n\n💰 Valor atualizado com juros e multa: R$ {valor}\n\nEntre em contato conosco para regularizar a situação.',
        'variaveis_disponiveis': ['nome_inquilino', 'endereco_imovel', 'valor', 'data_vencimento', 'dias_atraso'],
    },
    {
        'evento': 'atraso_15',
        'mensagem': 'Olá {nome_inquilino},\n\nSeu boleto do imóvel {endereco_imovel} está em atraso há {dias_atraso} dias.\n\n⚠️ Valor atualizado: R$ {valor}\n\nÉ importante regularizar com urgência. Entre em contato com nossa equipe.',
        'variaveis_disponiveis': ['nome_inquilino', 'endereco_imovel', 'valor', 'data_vencimento', 'dias_atraso'],
    },
    {
        'evento': 'pagamento_confirmado',
        'mensagem': 'Olá {nome_inquilino}! ✅\n\nConfirmamos o recebimento do seu pagamento referente ao imóvel {endereco_imovel}.\n\n💰 Valor pago: R$ {valor}\n📅 Data: {data_pagamento}\n\nObrigado pela pontualidade!',
        'variaveis_disponiveis': ['nome_inquilino', 'endereco_imovel', 'valor', 'data_pagamento'],
    },
    {
        'evento': 'contrato_enviado',
        'mensagem': 'Olá {nome_inquilino}!\n\nSeu contrato de locação do imóvel {endereco_imovel} foi gerado e está disponível.\n\n📄 Acesse o documento em anexo ou pelo link enviado.\n\nQualquer dúvida, estamos à disposição.',
        'variaveis_disponiveis': ['nome_inquilino', 'endereco_imovel', 'link_documento'],
    },
    {
        'evento': 'contrato_60dias',
        'mensagem': 'Olá {nome_inquilino},\n\nSeu contrato de locação do imóvel {endereco_imovel} vence em 60 dias ({data_fim}).\n\nGostaria de renovar? Entre em contato com nossa equipe para conversarmos sobre a renovação.',
        'variaveis_disponiveis': ['nome_inquilino', 'endereco_imovel', 'data_fim'],
    },
    {
        'evento': 'contrato_30dias',
        'mensagem': 'Olá {nome_inquilino},\n\nSeu contrato de locação do imóvel {endereco_imovel} vence em 30 dias ({data_fim}).\n\n⚠️ É importante definir a renovação ou desocupação o quanto antes. Entre em contato conosco.',
        'variaveis_disponiveis': ['nome_inquilino', 'endereco_imovel', 'data_fim'],
    },
    {
        'evento': 'distrato_enviado',
        'mensagem': 'Olá {nome_inquilino},\n\nO distrato referente ao contrato do imóvel {endereco_imovel} foi gerado e está disponível.\n\n📄 Acesse o documento em anexo ou pelo link enviado.\n\nAgradecemos pela parceria.',
        'variaveis_disponiveis': ['nome_inquilino', 'endereco_imovel', 'link_documento'],
    },
    {
        'evento': 'recibo_pagamento',
        'mensagem': 'Olá {nome_inquilino}!\n\nSeu recibo de pagamento referente ao imóvel {endereco_imovel} está disponível.\n\n💰 Valor: R$ {valor}\n📅 Data: {data_pagamento}\n\n📄 Acesse o recibo em anexo.',
        'variaveis_disponiveis': ['nome_inquilino', 'endereco_imovel', 'valor', 'data_pagamento'],
    },
]

criados = 0
existentes = 0

for t in templates:
    obj, created = TemplateWhatsApp.objects.get_or_create(
        evento=t['evento'],
        defaults={
            'mensagem': t['mensagem'],
            'variaveis_disponiveis': t['variaveis_disponiveis'],
            'ativo': True,
        }
    )
    if created:
        criados += 1
        print(f'[OK] Criado: {obj.get_evento_display()}')
    else:
        existentes += 1
        print(f'[--] Ja existia: {obj.get_evento_display()}')

print(f'\n--- Total: {criados} criados, {existentes} já existiam ---')
print(f'Total no banco agora: {TemplateWhatsApp.objects.count()}')