"""
apps/documentos/services.py
Renderizacao de variaveis em modelos de documento + geracao de PDF (xhtml2pdf,
mesmo padrao usado em apps/contratos/views.py e apps/relatorios/views.py).
"""
import io
import re

from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.files.base import ContentFile
from django.template import Context, Template
from django.template.defaultfilters import floatformat
from django.template.engine import Engine
from django.utils import timezone
from django.utils.formats import date_format
from xhtml2pdf import pisa

# Só variáveis são permitidas no conteúdo do modelo — bloqueia tags de lógica
# ({% if %}, {% for %} etc), que abririam brecha pra template injection.
RE_TAG_PROIBIDA = re.compile(r'\{%')


def _engine_seguro():
    """Django template engine sem loaders — só renderiza a string recebida."""
    return Engine(
        dirs=[],
        loaders=[],
        libraries={},
        builtins=['django.template.defaultfilters'],
    )


def _formatar_cpf(cpf):
    digitos = re.sub(r'\D', '', cpf or '')
    if len(digitos) != 11:
        return cpf or ''
    return f'{digitos[0:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:11]}'


def _endereco_completo_inquilino(inquilino):
    partes = [p for p in [
        inquilino.logradouro, inquilino.numero, inquilino.complemento,
        inquilino.bairro, inquilino.cidade, inquilino.estado,
    ] if p]
    return ', '.join(partes)


def _fmt_money(value):
    if value is None:
        return ''
    return f'R$ {intcomma(floatformat(value, 2))}'


def construir_contexto(contrato):
    """Monta o dicionário de variáveis a partir de um Contrato."""
    inquilino = contrato.inquilino
    imovel = contrato.imovel
    hoje = timezone.localdate()

    return {
        'inquilino': {
            'nome': inquilino.nome,
            'cpf_formatado': _formatar_cpf(inquilino.cpf),
            'rg': inquilino.rg,
            'nacionalidade': inquilino.nacionalidade,
            'estado_civil': inquilino.get_estado_civil_display(),
            'profissao': inquilino.profissao,
            'email': inquilino.email,
            'telefone': inquilino.telefone,
            'endereco_completo': _endereco_completo_inquilino(inquilino),
            'fiador_nome': inquilino.fiador_nome or 'DISPENSADO',
            'fiador_cpf': inquilino.fiador_cpf,
            'fiador_telefone': inquilino.fiador_telefone,
        },
        'imovel': {
            'endereco_completo': imovel.get_endereco_completo(),
            'tipo': imovel.get_tipo_display(),
            'proprietario_nome': imovel.proprietario_nome,
            'proprietario_cpf_cnpj': imovel.proprietario_cpf_cnpj,
            'proprietario_telefone': imovel.proprietario_telefone,
            'proprietario_email': imovel.proprietario_email,
        },
        'contrato': {
            'numero': contrato.numero,
            'data_inicio': date_format(contrato.data_inicio, 'd/m/Y'),
            'data_fim': date_format(contrato.data_fim, 'd/m/Y'),
            'valor_aluguel_formatado': _fmt_money(contrato.valor_aluguel),
            'valor_condominio_formatado': _fmt_money(contrato.valor_condominio),
            'valor_iptu_formatado': _fmt_money(contrato.valor_iptu),
            'dia_vencimento': str(contrato.dia_vencimento),
            'tipo_garantia': contrato.get_tipo_garantia_display(),
            'duracao_meses': str(contrato.duracao_meses),
            'indice_reajuste': contrato.get_indice_reajuste_display(),
            'multa_rescisao': str(contrato.multa_rescisao),
        },
        'data': {
            'data_atual': date_format(hoje, 'd/m/Y'),
            'data_atual_extenso': date_format(hoje, r'j \d\e F \d\e Y'),
        },
    }


def renderizar_modelo(conteudo_html, contrato):
    """
    Substitui as variáveis {{ slug }} do conteúdo pelos dados do contrato.
    Lança ValueError se o conteúdo tiver tags de lógica ({% %}).
    """
    if RE_TAG_PROIBIDA.search(conteudo_html):
        raise ValueError('O modelo contém tags de lógica não permitidas.')

    contexto = construir_contexto(contrato)
    template = Template(conteudo_html, engine=_engine_seguro())
    return template.render(Context(contexto))


def gerar_pdf(html_renderizado, titulo='documento'):
    """Recebe HTML já renderizado e retorna os bytes do PDF (xhtml2pdf)."""
    buffer = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html_renderizado), dest=buffer)
    buffer.seek(0)
    return buffer.read()


def salvar_documento_gerado(contrato, modelo, usuario):
    """
    Renderiza o modelo com dados do contrato, gera o PDF e salva o
    ContratoDocumentoGerado. Retorna a instância criada.
    """
    from .models import ContratoDocumentoGerado

    html = renderizar_modelo(modelo.conteudo_html, contrato)
    pdf_bytes = gerar_pdf(html, titulo=modelo.titulo)

    doc = ContratoDocumentoGerado(
        contrato=contrato,
        modelo=modelo,
        titulo=f'{modelo.titulo} — Contrato {contrato.numero}',
        conteudo_final_html=html,
        status='gerado',
        gerado_por=usuario,
    )
    if pdf_bytes:
        filename = f'contrato_{contrato.numero}_{modelo.tipo}.pdf'
        doc.arquivo_pdf.save(filename, ContentFile(pdf_bytes), save=False)
    doc.save()
    return doc


def criar_documentos_padrao():
    """
    Carrega as fixtures de variáveis e modelos padrão do app documentos
    no schema corrente. Deve ser chamada dentro de schema_context do tenant.
    Idempotente: pula cada fixture se já houver registro correspondente.
    """
    from django.core.management import call_command

    from .models import ModeloDocumento, VariavelDocumento

    if not VariavelDocumento.objects.exists():
        call_command('loaddata', 'variaveis_documento', app_label='documentos', verbosity=0)

    if not ModeloDocumento.objects.filter(padrao=True).exists():
        call_command('loaddata', 'modelos_padrao', app_label='documentos', verbosity=0)
