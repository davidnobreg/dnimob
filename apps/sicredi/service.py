"""
apps/sicredi/service.py
Camada de negócio da integração Sicredi.

Orquestra o SicrediClient (client.py) e o processamento de webhook.
Não fala HTTP direto — isso é responsabilidade do client.
"""
import io
import logging
import secrets
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import connection
from django.utils import timezone
from django_tenants.utils import schema_context

from .client import SicrediClient, SicrediAuthError, SicrediAPIError

logger = logging.getLogger('apps.sicredi')

# Movimentos de webhook que representam pagamento
MOVIMENTOS_LIQUIDACAO = {
	'LIQUIDACAO_PIX',
	'LIQUIDACAO_REDE',
	'LIQUIDACAO_COMPE_H5',
	'LIQUIDACAO_COMPE_H6',
	'LIQUIDACAO_COMPE_H8',
	'LIQUIDACAO_CARTORIO',
}
MOVIMENTO_ESTORNO = 'ESTORNO_LIQUIDACAO_REDE'


class WebhookAuthError(Exception):
	"""
	Webhook rejeitado por falha de autenticação: em produção (DEBUG=False),
	webhook_secret não configurado para o tenant, ou secret da URL não bate
	com o do tenant. A view responde 401 nesse caso, em vez do 200 padrão
	do Sicredi.
	"""


# ── Config do tenant ──────────────────────────────────────────────────────────

def get_config_tenant():
	"""
	Retorna a ConfigSicredi ativa do tenant atual (ou None).
	ConfigSicredi vive no schema public; filtramos pelo schema_name corrente.
	"""
	from apps.tenants.models import ConfigSicredi
	return ConfigSicredi.objects.filter(
		schema_name=connection.schema_name, ativo=True
	).first()


# ── Teste de credenciais ──────────────────────────────────────────────────────

def testar_credenciais_sicredi(config) -> tuple[bool, str]:
	"""Tenta autenticar no Sicredi. Retorna (sucesso, mensagem)."""
	try:
		client = SicrediClient(config, schema_name=connection.schema_name)
		client.autenticar()
		return True, 'Credenciais válidas! Conexão com o Sicredi estabelecida.'
	except SicrediAuthError as e:
		return False, str(e)
	except Exception as e:  # noqa: BLE001 — defensivo, nunca derruba a view
		logger.exception('Erro inesperado ao testar credenciais Sicredi')
		return False, f'Erro inesperado ao testar conexão: {e}'


# ── Geração / cancelamento de boleto ──────────────────────────────────────────

def gerar_boleto_parcela(parcela):
	"""
	Gera o boleto da parcela no Sicredi. Usa a ConfigSicredi do tenant atual.
	Em falha, registra o erro no Boleto (status='erro') e relança.
	"""
	from apps.sicredi.models import Boleto

	config = get_config_tenant()
	if not config:
		raise SicrediAPIError('Integração Sicredi não configurada ou inativa para esta imobiliária.')

	client = SicrediClient(config, schema_name=connection.schema_name)
	try:
		return client.criar_boleto(parcela)
	except (SicrediAuthError, SicrediAPIError) as e:
		# Marca o boleto como erro para a UI exibir o botão de reemissão
		Boleto.objects.update_or_create(
			parcela=parcela,
			defaults={
				'nosso_numero': getattr(parcela.boleto, 'nosso_numero', '') if hasattr(parcela, 'boleto') else f'ERRO-{parcela.pk}',
				'status': 'erro',
				'erro_mensagem': str(e),
			},
		)
		raise


def gerar_boletos_lote(contrato) -> dict:
	"""
	Gera boleto pra toda parcela pendente/atrasada do contrato que ainda não
	tem boleto (ou cujo boleto está 'erro'/'cancelado'). Uma falha isolada
	não interrompe o lote — cada parcela é tentada independente.

	Retorna {'gerados': int, 'falhas': [(parcela, mensagem), ...]}.
	"""
	parcelas = contrato.parcelas.filter(status__in=['pendente', 'atrasado']).order_by('numero')

	gerados = 0
	falhas = []
	for parcela in parcelas:
		boleto = getattr(parcela, 'boleto', None)
		if boleto and boleto.status not in ('erro', 'cancelado'):
			continue
		try:
			gerar_boleto_parcela(parcela)
			gerados += 1
		except (SicrediAuthError, SicrediAPIError) as e:
			falhas.append((parcela, str(e)))
			if isinstance(e, SicrediAuthError):
				# credencial inválida não vai se resolver na próxima parcela — para o lote
				break

	logger.info('Sicredi lote de boletos schema=%s contrato=%s gerados=%s falhas=%s',
	            connection.schema_name, contrato.pk, gerados, len(falhas))
	return {'gerados': gerados, 'falhas': falhas}


def cancelar_boleto(boleto) -> tuple[bool, str]:
	"""Baixa (cancela) o boleto no Sicredi. Retorna (sucesso, mensagem)."""
	config = get_config_tenant()
	if not config:
		raise SicrediAPIError('Integração Sicredi não configurada ou inativa para esta imobiliária.')

	client = SicrediClient(config, schema_name=connection.schema_name)
	return client.baixar_boleto(boleto)


def imprimir_boleto(boleto) -> bytes:
	"""Busca o PDF de impressão do boleto no Sicredi. Retorna os bytes do PDF."""
	if not boleto.linha_digitavel:
		raise SicrediAPIError('Boleto sem linha digitável — não é possível imprimir.')

	config = get_config_tenant()
	if not config:
		raise SicrediAPIError('Integração Sicredi não configurada ou inativa para esta imobiliária.')

	client = SicrediClient(config, schema_name=connection.schema_name)
	return client.imprimir_boleto(boleto.linha_digitavel)


def imprimir_carne_contrato(contrato) -> bytes:
	"""
	Gera um carnê compacto (3 boletos por folha A4) a partir dos dados
	locais de cada Boleto — diferente de `imprimir_boleto`, que busca o
	PDF oficial (folha cheia) direto na Sicredi. Aqui o código de barras
	é desenhado localmente (Interleaved 2 of 5) a partir do
	`codigo_barras` de 44 dígitos que a Sicredi devolveu na emissão, sem
	nova chamada à API. Ordena por número da parcela; ignora parcelas
	sem boleto ou sem linha digitável (boleto cancelado/erro).
	"""
	from reportlab.lib.pagesizes import A4
	from reportlab.pdfgen import canvas
	from apps.contratos.models import Parcela
	from apps.tenants.models import Tenant

	config = get_config_tenant()
	if not config:
		raise SicrediAPIError('Integração Sicredi não configurada ou inativa para esta imobiliária.')

	tenant = Tenant.objects.get(schema_name=connection.schema_name)

	parcelas = list(
		Parcela.objects.filter(contrato=contrato, boleto__isnull=False)
			.select_related('boleto').order_by('numero')
	)
	itens = [p for p in parcelas if p.boleto.linha_digitavel]
	if not itens:
		raise SicrediAPIError('Este contrato não possui boletos emitidos para gerar o carnê.')

	total_parcelas = contrato.parcelas.count()

	buffer = io.BytesIO()
	c = canvas.Canvas(buffer, pagesize=A4)
	largura, altura = A4
	altura_slip = altura / 3

	for i, parcela in enumerate(itens):
		pos = i % 3
		if i > 0 and pos == 0:
			c.showPage()
		y0 = altura - altura_slip * (pos + 1)
		_desenhar_slip_carne(c, parcela, parcela.boleto, config, contrato, total_parcelas, tenant, y0, largura, altura_slip)

	c.save()
	buffer.seek(0)
	return buffer.read()


def _formatar_linha_digitavel(bruta: str) -> str:
	"""Formata `AAAAA.AAAAA BBBBB.BBBBBB CCCCC.CCCCCC D EEEEEEEEEEEEEE` a partir
	de uma string só com dígitos (47), caso a Sicredi devolva sem pontuação.
	Se já vier formatada (ou em formato inesperado), devolve como veio."""
	digitos = ''.join(ch for ch in bruta if ch.isdigit())
	if ' ' in bruta or '.' in bruta or len(digitos) != 47:
		return bruta
	return (f'{digitos[0:5]}.{digitos[5:10]} {digitos[10:15]}.{digitos[15:21]} '
	        f'{digitos[21:26]}.{digitos[26:32]} {digitos[32:33]} {digitos[33:47]}')


def _desenhar_slip_carne(c, parcela, boleto, config, contrato, total_parcelas, tenant, y0, largura, altura_slip):
	"""
	Desenha um boleto no padrão FEBRABAN dentro da faixa [y0, y0+altura_slip]:
	Recibo do Pagador (coluna estreita à esquerda) + Ficha de Compensação
	(coluna larga à direita), separadas por linha pontilhada de corte.
	"""
	from reportlab.lib import colors
	from reportlab.lib.units import mm
	from reportlab.graphics.barcode.common import I2of5
	from reportlab.graphics.barcode.qr import QrCodeWidget
	from reportlab.graphics.shapes import Drawing
	from reportlab.graphics import renderPDF

	verde = colors.HexColor('#00833E')
	pagador = contrato.inquilino
	valor_fmt = f'{parcela.valor_total:,.2f}'.translate(str.maketrans(',.', '.,'))
	vencimento_fmt = parcela.data_vencimento.strftime('%d/%m/%Y')
	agencia_beneficiario = f'{config.cooperativa}.{config.posto}.{config.codigo_beneficiario}'
	beneficiario_doc = f'CNPJ: {tenant.cnpj}' if tenant.cnpj else (f'CPF: {tenant.cpf}' if tenant.cpf else '')
	beneficiario_endereco = ', '.join(p for p in [tenant.endereco, tenant.cidade and f'{tenant.cidade}/{tenant.estado}'] if p)
	linha_dig_fmt = _formatar_linha_digitavel(boleto.linha_digitavel)
	numero_documento = boleto.seu_numero or boleto.nosso_numero
	emitido = boleto.emitido_em.strftime('%d/%m/%Y') if boleto.emitido_em else ''

	def txt(x, y, valor, fonte='Helvetica', tam=6, cor=colors.black, direita=False, meio=False):
		c.setFillColor(cor)
		c.setFont(fonte, tam)
		if direita:
			c.drawRightString(x, y, valor)
		elif meio:
			c.drawCentredString(x, y, valor)
		else:
			c.drawString(x, y, valor)
		c.setFillColor(colors.black)

	def label_valor(x1, x2, ytopo, label, valor, tam_label=4.6, tam_valor=6.5, negrito=False, direita=False):
		txt(x1 + 1 * mm, ytopo - 2.4 * mm, label, tam=tam_label, cor=colors.grey)
		xv = x2 - 1 * mm if direita else x1 + 1 * mm
		txt(xv, ytopo - 5.6 * mm, valor, fonte='Helvetica-Bold' if negrito else 'Helvetica', tam=tam_valor, direita=direita)

	# ── moldura externa do slip ────────────────────────────────────────────
	pad = 2.5 * mm
	y_topo = y0 + altura_slip - pad
	y_base = y0 + pad
	x_esq = 3 * mm
	x_dir = largura - 3 * mm
	larg_recibo = 30 * mm
	x_corte = x_esq + larg_recibo
	x_ficha = x_corte + 3 * mm

	c.setLineWidth(0.6)
	c.rect(x_esq, y_base, x_dir - x_esq, y_topo - y_base, stroke=1, fill=0)

	# linha pontilhada vertical de corte entre recibo e ficha
	c.setDash(2, 2)
	c.setLineWidth(0.5)
	c.line(x_corte + 1.5 * mm, y_base, x_corte + 1.5 * mm, y_topo)
	c.setDash()

	# ═══════════════════════════ RECIBO DO PAGADOR (esquerda) ═══════════════
	c.setLineWidth(0.5)

	ry = y_topo
	txt(x_esq + 1 * mm, ry - 3.5 * mm, 'Sicredi', fonte='Helvetica-Bold', tam=8, cor=verde)
	ry -= 6 * mm
	c.line(x_esq, ry, x_corte, ry)

	meio_recibo = x_esq + larg_recibo * 0.5
	label_valor(x_esq, meio_recibo, ry, 'PARCELA', f'{parcela.numero:03d}/{total_parcelas:03d}')
	label_valor(meio_recibo, x_corte, ry, 'VENCIMENTO', vencimento_fmt, negrito=True)
	c.line(meio_recibo, ry - 6.5 * mm, meio_recibo, ry)
	ry -= 6.5 * mm
	c.line(x_esq, ry, x_corte, ry)

	label_valor(x_esq, x_corte, ry, 'AGÊNCIA/CÓDIGO BENEFICIÁRIO', agencia_beneficiario)
	ry -= 6.5 * mm
	c.line(x_esq, ry, x_corte, ry)

	txt(x_esq + 1 * mm, ry - 2.4 * mm, 'BENEFICIÁRIO', tam=4.6, cor=colors.grey)
	txt(x_esq + 1 * mm, ry - 5.4 * mm, (config.beneficiario or '-')[:34], tam=5.5)
	txt(x_esq + 1 * mm, ry - 8.4 * mm, beneficiario_endereco[:38], tam=4.6, cor=colors.grey)
	txt(x_esq + 1 * mm, ry - 11.0 * mm, beneficiario_doc, tam=4.6, cor=colors.grey)
	ry -= 13.5 * mm
	c.line(x_esq, ry, x_corte, ry)

	label_valor(x_esq, x_corte, ry, 'NOSSO NÚMERO', boleto.nosso_numero)
	ry -= 6.5 * mm
	c.line(x_esq, ry, x_corte, ry)

	txt(x_esq + 1 * mm, ry - 2.4 * mm, 'PAGADOR', tam=4.6, cor=colors.grey)
	txt(x_esq + 1 * mm, ry - 5.4 * mm, pagador.nome[:34], tam=5.5)
	ry -= 7 * mm
	c.line(x_esq, ry, x_corte, ry)

	label_valor(x_esq, x_corte, ry, 'CPF/CNPJ', pagador.documento_principal or '-')
	ry -= 6.5 * mm
	c.line(x_esq, ry, x_corte, ry)

	c.setLineWidth(0.4)
	c.line(x_esq, y_base + 5.5 * mm, x_corte, y_base + 5.5 * mm)
	txt(x_esq, y_base + 3.2 * mm, 'Recibo do Pagador', tam=4.8, fonte='Helvetica-Bold')
	txt(x_esq, y_base + 1.0 * mm, 'Autenticação no Verso', tam=4, cor=colors.grey)

	# ═══════════════════════════ FICHA DE COMPENSAÇÃO (direita) ═════════════
	fy = y_topo
	txt(x_ficha, fy - 3.8 * mm, 'Sicredi', fonte='Helvetica-Bold', tam=10, cor=verde)
	txt(x_ficha + 20 * mm, fy - 3.8 * mm, '748-X', fonte='Helvetica-Bold', tam=11)
	txt(x_dir - 1 * mm, fy - 3.8 * mm, linha_dig_fmt, fonte='Helvetica-Bold', tam=8.5, direita=True)
	fy -= 5.5 * mm
	c.setLineWidth(0.5)
	c.line(x_ficha, fy, x_dir, fy)
	fy -= 0.3 * mm

	fy_ficha_topo = fy

	label_valor(x_ficha, x_ficha + 110 * mm, fy, 'LOCAL DE PAGAMENTO',
	            'Pagável preferencialmente nas cooperativas de crédito do Sicredi', tam_valor=5.2)
	label_valor(x_ficha + 110 * mm, x_dir, fy, 'VENCIMENTO', vencimento_fmt, negrito=True, direita=True)
	c.line(x_ficha + 110 * mm, fy - 6.5 * mm, x_ficha + 110 * mm, fy)
	fy -= 6.5 * mm
	c.line(x_ficha, fy, x_dir, fy)

	txt(x_ficha + 1 * mm, fy - 2.4 * mm, 'BENEFICIÁRIO', tam=4.6, cor=colors.grey)
	txt(x_ficha + 1 * mm, fy - 5.2 * mm, f'{config.beneficiario or "-"} {beneficiario_doc}'[:70], tam=5.5)
	label_valor(x_ficha + 110 * mm, x_dir, fy, 'AGÊNCIA/CÓDIGO BENEFICIÁRIO', agencia_beneficiario, direita=True)
	c.line(x_ficha + 110 * mm, fy - 7.5 * mm, x_ficha + 110 * mm, fy)
	fy -= 7.5 * mm
	c.line(x_ficha, fy, x_dir, fy)

	# grid 1: seis colunas
	larg_ficha = x_dir - x_ficha
	cols1 = [0, 0.18, 0.34, 0.46, 0.56, 0.76, 1.0]
	campos1 = [
		('DATA DO DOCUMENTO', emitido),
		('Nº DO DOCUMENTO', numero_documento),
		('ESPÉCIE DOC.', 'DM'),
		('ACEITE', 'N'),
		('DATA DE PROCESSAMENTO', emitido),
		('NOSSO NÚMERO', boleto.nosso_numero),
	]
	for i, (label, valor) in enumerate(campos1):
		xa = x_ficha + larg_ficha * cols1[i]
		xb = x_ficha + larg_ficha * cols1[i + 1]
		if i > 0:
			c.line(xa, fy - 7 * mm, xa, fy)
		label_valor(xa, xb, fy, label, valor, tam_valor=5.6)
	fy -= 7 * mm
	c.line(x_ficha, fy, x_dir, fy)

	# grid 2: uso do banco / carteira / espécie / quantidade / valor / (=) valor do documento
	cols2 = [0, 0.18, 0.30, 0.42, 0.56, 0.76, 1.0]
	campos2 = [
		('USO DO BANCO', ''),
		('CARTEIRA', 'A'),
		('ESPÉCIE', 'R$'),
		('QUANTIDADE', ''),
		('(=) VALOR UNITÁRIO', ''),
		('(=) VALOR DO DOCUMENTO', f'{valor_fmt}'),
	]
	for i, (label, valor) in enumerate(campos2):
		xa = x_ficha + larg_ficha * cols2[i]
		xb = x_ficha + larg_ficha * cols2[i + 1]
		if i > 0:
			c.line(xa, fy - 7 * mm, xa, fy)
		label_valor(xa, xb, fy, label, valor, tam_valor=6.2, negrito=(i == 5))
	fy -= 7 * mm
	c.line(x_ficha, fy, x_dir, fy)

	# instruções + coluna de valores (desconto / mora / valor cobrado), cada
	# um em sua própria célula (linhas horizontais dividindo a coluna em 3)
	x_valores = x_dir - 42 * mm
	c.line(x_valores, fy - 15 * mm, x_valores, fy)
	txt(x_ficha + 1 * mm, fy - 2.6 * mm, 'INSTRUÇÕES (Texto de responsabilidade do beneficiário.)', tam=4.6, cor=colors.grey)
	for i, (label, valor) in enumerate([('(-) DESCONTO/ABATIMENTO', ''), ('(+) MORA/MULTA', ''), ('(=) VALOR COBRADO', '')]):
		yy = fy - 5 * mm - i * 5 * mm
		label_valor(x_valores, x_dir, yy, label, valor, tam_valor=6, direita=True)
		if i > 0:
			c.line(x_valores, yy + 5 * mm, x_dir, yy + 5 * mm)
	fy -= 15 * mm
	c.line(x_ficha, fy, x_dir, fy)

	# PIX copia e cola + QR code
	pix_area_top = fy
	fy -= 3 * mm
	txt(x_ficha + 1 * mm, fy, 'PIX Copia e Cola', fonte='Helvetica-Bold', tam=5)
	fy -= 3.2 * mm
	if boleto.qr_code:
		txt(x_ficha + 1 * mm, fy, boleto.qr_code[:95], fonte='Helvetica', tam=4.2)
		fy -= 3.2 * mm
		txt(x_ficha + 1 * mm, fy, boleto.qr_code[95:190], fonte='Helvetica', tam=4.2)

		lado_qr = 13 * mm
		qr = QrCodeWidget(boleto.qr_code)
		bounds = qr.getBounds()
		w_qr = bounds[2] - bounds[0]
		h_qr = bounds[3] - bounds[1]
		d = Drawing(lado_qr, lado_qr, transform=[lado_qr / w_qr, 0, 0, lado_qr / h_qr, 0, 0])
		d.add(qr)
		renderPDF.draw(d, c, x_dir - lado_qr, pix_area_top - lado_qr - 1 * mm)
	fy = pix_area_top - 15 * mm
	c.line(x_ficha, fy, x_dir, fy)

	# pagador + CPF/CNPJ do sacado / código de baixa
	endereco_pagador = ', '.join(p for p in [
		f'{pagador.logradouro}, {pagador.numero}' if pagador.logradouro else '',
		pagador.bairro, pagador.cidade and f'{pagador.cidade}/{pagador.estado}',
	] if p)
	txt(x_ficha + 1 * mm, fy - 2.6 * mm, 'PAGADOR', tam=4.6, cor=colors.grey)
	txt(x_ficha + 1 * mm, fy - 5.4 * mm, pagador.nome[:60], fonte='Helvetica-Bold', tam=6)
	txt(x_ficha + 1 * mm, fy - 8.2 * mm, endereco_pagador[:70], tam=5)
	label_valor(x_dir - 42 * mm, x_dir, fy, 'CPF/CNPJ DO SACADO', pagador.documento_principal or '-', direita=True)
	txt(x_dir - 1 * mm, fy - 8.2 * mm, 'Código de Baixa:', tam=4.6, cor=colors.grey, direita=True)
	fy -= 9.5 * mm
	c.line(x_ficha, fy, x_dir, fy)

	txt(x_ficha + 1 * mm, fy - 2.6 * mm, 'Beneficiário Final:', tam=4.6, cor=colors.grey)
	fy -= 4.5 * mm

	# moldura externa da ficha (fecha o "efeito tabela" das linhas internas)
	c.line(x_ficha, fy, x_ficha, fy_ficha_topo)
	c.line(x_dir, fy, x_dir, fy_ficha_topo)

	# código de barras — módulo no mínimo FEBRABAN (0.4233mm = 1.2pt), razão
	# 2,5:1 (padrão boleto bancário) e zona de silêncio automática
	# (quiet=1, 10x o módulo) — sem isso a leitora não reconhece o código.
	if boleto.codigo_barras:
		barcode = I2of5(boleto.codigo_barras, checksum=0, barWidth=1.2, barHeight=13 * mm, ratio=2.5, quiet=1)
		barcode.drawOn(c, x_ficha, fy - 13 * mm)
	fy -= 14.5 * mm

	txt(x_ficha, fy, 'Autenticação Mecânica', tam=4.4, cor=colors.grey)
	txt(x_dir, fy, 'Ficha de Compensação', tam=4.4, cor=colors.grey, direita=True)

	# ── linha de corte horizontal entre boletos empilhados ────────────────
	c.setDash(2, 2)
	c.setLineWidth(0.5)
	c.line(0, y0, largura, y0)
	c.setDash()


# ── Reconciliação ativa (consulta de boletos liquidados) ──────────────────────

def reconciliar_liquidados_dia(dia, cpf_cnpj_beneficiario_final=None) -> dict:
	"""
	Reconciliação ativa: consulta a Sicredi pelos boletos liquidados no dia
	informado e corrige boletos que ficaram 'emitido' localmente porque o
	webhook falhou ou não chegou. Idempotente — boleto já 'pago' não é
	reprocessado.

	Reaproveita `_registrar_liquidacao` (mesma função usada pelo webhook) —
	não duplica a regra de negócio de marcar boleto+parcela como pagos.

	Retorna {'total', 'recuperados', 'nao_encontrados'}.
	"""
	from apps.sicredi.models import Boleto

	config = get_config_tenant()
	if not config:
		raise SicrediAPIError('Integração Sicredi não configurada ou inativa para esta imobiliária.')

	client = SicrediClient(config, schema_name=connection.schema_name)
	itens = client.consultar_liquidados_dia(dia, cpf_cnpj_beneficiario_final=cpf_cnpj_beneficiario_final)

	recuperados = 0
	nao_encontrados = 0

	for item in itens:
		nosso_numero = str(item.get('nossoNumero', '')).strip()
		if not nosso_numero:
			continue

		boleto = Boleto.objects.filter(nosso_numero=nosso_numero).first()
		if not boleto:
			nao_encontrados += 1
			logger.warning('Reconciliação Sicredi: boleto %s (dia=%s) não encontrado localmente', nosso_numero, dia)
			continue

		if boleto.status == 'pago':
			continue  # já consistente — webhook processou certo

		_registrar_liquidacao(nosso_numero, {
			'valorLiquidacao': item.get('valorLiquidado'),
			'dataPrevisaoPagamento': item.get('dataPagamento'),
		})
		recuperados += 1
		logger.warning('Reconciliação Sicredi: discrepância recuperada — boleto %s estava %s, webhook não processou',
		               nosso_numero, boleto.status)

	logger.info('Reconciliação Sicredi dia=%s: total=%s recuperados=%s nao_encontrados=%s',
	            dia, len(itens), recuperados, nao_encontrados)
	return {'total': len(itens), 'recuperados': recuperados, 'nao_encontrados': nao_encontrados}


# ── Webhook ───────────────────────────────────────────────────────────────────

def processar_webhook(payload: dict, secret: str = ''):
	"""
	Processa um evento de movimentação recebido do Sicredi.

	Identifica o tenant pelo `beneficiario` (codigo_beneficiario em ConfigSicredi),
	entra no schema correto e atualiza o Boleto + a Parcela. Os signals já
	existentes (financeiro + whatsapp) cuidam de Lancamento e confirmação.

	`secret` vem do path da URL do webhook (não de header) — a Sicredi não
	envia nenhum header de autenticação nesta versão da API, então o segredo
	precisa estar embutido na própria URL cadastrada no portal deles.
	"""
	from apps.tenants.models import ConfigSicredi

	beneficiario = str(payload.get('beneficiario', '')).strip()
	nosso_numero = str(payload.get('nossoNumero', '')).strip()
	movimento = payload.get('movimento', '')

	logger.info('Webhook Sicredi: beneficiario=%s nossoNumero=%s movimento=%s',
	            beneficiario, nosso_numero, movimento)

	if not beneficiario or not nosso_numero:
		logger.warning('Webhook Sicredi: payload sem beneficiario/nossoNumero')
		return

	# ConfigSicredi vive no public — lookup direto pelo codigo_beneficiario
	config = ConfigSicredi.objects.filter(codigo_beneficiario=beneficiario).first()
	if not config or not config.schema_name:
		logger.warning('Webhook Sicredi: beneficiario %s sem config/schema mapeado', beneficiario)
		return

	# Em produção (settings.SICREDI_WEBHOOK_SECRET_REQUIRED=True, derivado de
	# DEBUG=False — ver config/settings/base.py), webhook_secret é obrigatório:
	# sem ele — ou com secret da URL não batendo — a requisição é REJEITADA
	# (WebhookAuthError, a view responde 401), não apenas descartada em silêncio.
	# Em dev/teste mantém o comportamento antigo: secret opcional, só valida
	# se o tenant tiver um configurado; sem secret, aceita normalmente.
	if settings.SICREDI_WEBHOOK_SECRET_REQUIRED:
		if not config.webhook_secret:
			logger.warning('Webhook Sicredi: producao sem webhook_secret configurado para beneficiario %s — requisição rejeitada',
			               beneficiario)
			raise WebhookAuthError('webhook_secret não configurado para este tenant em produção')
		if not secrets.compare_digest(secret, config.webhook_secret):
			logger.warning('Webhook Sicredi: secret da URL não confere para beneficiario %s — requisição rejeitada',
			               beneficiario)
			raise WebhookAuthError('secret inválido')
	elif config.webhook_secret and not secrets.compare_digest(secret, config.webhook_secret):
		logger.warning('Webhook Sicredi: secret da URL não confere para beneficiario %s — payload descartado',
		               beneficiario)
		return

	with schema_context(config.schema_name):
		if movimento in MOVIMENTOS_LIQUIDACAO:
			_registrar_liquidacao(nosso_numero, payload)
		elif movimento == MOVIMENTO_ESTORNO:
			_registrar_estorno(nosso_numero, payload)
		else:
			logger.info('Webhook Sicredi: movimento %s ignorado', movimento)


def _registrar_liquidacao(nosso_numero, payload):
	from apps.sicredi.models import Boleto

	try:
		boleto = Boleto.objects.select_related('parcela').get(nosso_numero=nosso_numero)
	except Boleto.DoesNotExist:
		logger.warning('Webhook Sicredi: boleto %s não encontrado', nosso_numero)
		return

	valor = _to_decimal(payload.get('valorLiquidacao'))
	data_pgto = _parse_data(payload.get('dataPrevisaoPagamento') or payload.get('dataEvento')) or timezone.now().date()

	boleto.status = 'pago'
	boleto.valor_pago = valor
	boleto.pago_em = data_pgto
	boleto.erro_mensagem = ''
	boleto.save(update_fields=['status', 'valor_pago', 'pago_em', 'erro_mensagem', 'atualizado_em'])

	parcela = boleto.parcela
	if parcela.status != 'pago':
		parcela.status = 'pago'
		parcela.data_pagamento = data_pgto
		parcela.save()  # dispara signals: Lancamento (financeiro) + WhatsApp confirmação
		logger.info('Webhook Sicredi: parcela %s marcada como paga', parcela.pk)


def _registrar_estorno(nosso_numero, payload):
	"""
	Estorno de LIQUIDACAO_REDE — só ocorre no mesmo dia do pagamento.
	A checagem de "mesmo dia" é regra específica do Sicredi (não existe no
	estorno manual pela tela), por isso fica aqui e não em
	`contratos.services.estornar_parcela` — essa função só reverte
	parcela/boleto e cancela o Lancamento, o pré-requisito é decidido por
	quem chama.
	"""
	from apps.sicredi.models import Boleto
	from apps.contratos.services import estornar_parcela

	try:
		boleto = Boleto.objects.select_related('parcela').get(nosso_numero=nosso_numero)
	except Boleto.DoesNotExist:
		logger.warning('Webhook Sicredi: estorno de boleto %s não encontrado', nosso_numero)
		return

	hoje = timezone.localdate()
	if boleto.pago_em and boleto.pago_em != hoje:
		logger.warning('Webhook Sicredi: estorno de %s fora do mesmo dia (pago_em=%s) — ignorado',
		               nosso_numero, boleto.pago_em)
		return

	estornar_parcela(boleto.parcela, motivo='webhook_sicredi')
	logger.info('Webhook Sicredi: estorno aplicado, parcela %s revertida', boleto.parcela_id)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _to_decimal(valor):
	try:
		return Decimal(str(valor)) if valor not in (None, '') else None
	except (InvalidOperation, ValueError):
		return None


def _parse_data(valor):
	"""
	Converte a data do payload Sicredi para date.
	Aceita lista [ano, mes, dia, ...] ou string 'YYYY-MM-DD'.
	"""
	if not valor:
		return None
	if isinstance(valor, (list, tuple)) and len(valor) >= 3:
		try:
			return datetime(int(valor[0]), int(valor[1]), int(valor[2])).date()
		except (ValueError, TypeError):
			return None
	if isinstance(valor, str):
		try:
			return datetime.fromisoformat(valor[:10]).date()
		except ValueError:
			return None
	return None