from django.db import migrations


def migrar_proprietarios(apps, schema_editor):
	Imovel = apps.get_model('imoveis', 'Imovel')
	Proprietario = apps.get_model('imoveis', 'Proprietario')

	for imovel in Imovel.objects.exclude(proprietario_nome=''):
		cpf_cnpj = ''.join(filter(str.isdigit, imovel.proprietario_cpf_cnpj or ''))

		tipo_pessoa = 'PJ' if len(cpf_cnpj) == 14 else 'PF'

		if cpf_cnpj:
			prop, _ = Proprietario.objects.get_or_create(
				cpf_cnpj=cpf_cnpj,
				defaults={
					'nome': imovel.proprietario_nome,
					'tipo_pessoa': tipo_pessoa,
					'telefone': imovel.proprietario_telefone or '',
					'email': imovel.proprietario_email or '',
				}
			)
		else:
			prop, _ = Proprietario.objects.get_or_create(
				nome=imovel.proprietario_nome,
				defaults={
					'tipo_pessoa': tipo_pessoa,
					'telefone': imovel.proprietario_telefone or '',
					'email': imovel.proprietario_email or '',
				}
			)

		imovel.proprietario = prop
		imovel.save(update_fields=['proprietario'])


def reverter(apps, schema_editor):
	pass  # irreversível intencionalmente


class Migration(migrations.Migration):

	dependencies = [
		('imoveis', '0004_add_proprietario_model_e_fk'),
	]

	operations = [
		migrations.RunPython(migrar_proprietarios, reverter),
	]
