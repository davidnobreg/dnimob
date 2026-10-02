"""
apps/documentos/services.py
Renderizacao de variaveis em modelos de documento + geracao de PDF (xhtml2pdf,
mesmo padrao usado em apps/contratos/views.py e apps/relatorios/views.py).
"""
import io
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import tempfile
import zipfile
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from xml.etree import ElementTree as ET

from django.conf import settings
from django.core.files.base import ContentFile
from django.template import Context, Template
from django.template.engine import Engine
from django.utils import timezone
from django.utils.formats import date_format
from xhtml2pdf import pisa

logger = logging.getLogger(__name__)

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
    """R$ 1.234,50 — independente de locale (Decimal + quantize + troca manual)."""
    if value is None:
        return ''
    valor = Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    inteiro, centavos = f'{abs(valor):.2f}'.split('.')
    inteiro = f'{int(inteiro):,}'.replace(',', '.')
    sinal = '-' if valor < 0 else ''
    return f'R$ {sinal}{inteiro},{centavos}'


def _texto_fiador(inquilino):
    """Cláusula do fiador pré-montada; vazia sem fiador. Omite partes vazias sem deixar vírgula."""
    if not inquilino.fiador_nome:
        return ''
    partes = [f'FIADOR: {inquilino.fiador_nome}']
    if inquilino.fiador_cpf:
        partes.append(f'CPF {inquilino.fiador_cpf}')
    if inquilino.fiador_telefone:
        partes.append(f'telefone {inquilino.fiador_telefone}')
    return ', '.join(partes) + '.'


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
            'fiador_texto': _texto_fiador(inquilino),
        },
        'imovel': {
            'endereco_completo': imovel.get_endereco_completo(),
            'tipo': imovel.get_tipo_display(),
            'proprietario_nome': imovel.proprietario.nome if imovel.proprietario else '',
            'proprietario_cpf_cnpj': imovel.proprietario.cpf_cnpj if imovel.proprietario else '',
            'proprietario_telefone': imovel.proprietario.telefone if imovel.proprietario else '',
            'proprietario_email': imovel.proprietario.email if imovel.proprietario else '',
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


RE_VARIAVEL_DOCX = re.compile(r'\{\{\s*([\w\.]+)\s*\}\}')
_NS_W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def _paragrafos_docx(xml_bytes):
    """Texto de cada parágrafo, juntando todos os w:t (o Word fragmenta em runs).
    Rejeita DOCTYPE/ENTITY: o parser do stdlib não resolve entidades externas,
    mas bloqueamos de qualquer forma (XXE / billion laughs)."""
    if b'<!DOCTYPE' in xml_bytes or b'<!ENTITY' in xml_bytes:
        raise ValueError('XML com DOCTYPE/ENTITY não é permitido.')
    raiz = ET.fromstring(xml_bytes)
    return [
        ''.join(t.text or '' for t in p.iter(f'{_NS_W}t'))
        for p in raiz.iter(f'{_NS_W}p')
    ]


def _partes_texto_docx(zf):
    return [
        n for n in zf.namelist()
        if n == 'word/document.xml' or re.fullmatch(r'word/(header|footer)\d*\.xml', n)
    ]


def analisar_docx(arquivo):
    """
    Extrai variáveis {{ slug }} de um .docx (corpo, cabeçalhos e rodapés).
    Retorna {'variaveis': [...], 'desconhecidas': [...], 'erros': [...]}.
    `erros` (tags {% %}, {{ sem }} correspondente) deve bloquear o upload.
    """
    from .models import VariavelDocumento

    arquivo.seek(0)
    paragrafos = []
    erros = []
    with zipfile.ZipFile(arquivo) as zf:
        for nome in _partes_texto_docx(zf):
            try:
                paragrafos.extend(_paragrafos_docx(zf.read(nome)))
            except (ET.ParseError, ValueError):
                erros.append(f'Não foi possível ler o conteúdo de "{nome}".')
    arquivo.seek(0)

    variaveis = set()
    for texto in paragrafos:
        variaveis.update(RE_VARIAVEL_DOCX.findall(texto))
        if '{%' in texto or '%}' in texto:
            erros.append(
                f'Blocos {{% %}} não são permitidos (use apenas {{{{ variável }}}}): "{texto.strip()[:80]}"'
            )
        resto = RE_VARIAVEL_DOCX.sub('', texto)
        if '{{' in resto or '}}' in resto:
            erros.append(f'Variável com sintaxe quebrada (falta "{{{{" ou "}}}}"): "{texto.strip()[:80]}"')

    conhecidas = set(VariavelDocumento.objects.filter(ativo=True).values_list('slug', flat=True))
    return {
        'variaveis': sorted(variaveis),
        'desconhecidas': sorted(variaveis - conhecidas),
        'erros': list(dict.fromkeys(erros)),
    }


class ModeloDocxInvalido(ValueError):
    """Modelo .docx com conteúdo não permitido (ex.: tags de lógica)."""


class ConversaoDocxErro(Exception):
    """Falha ao gerar o PDF a partir do .docx. A mensagem é curta e segura para o usuário."""


def renderizar_docx(modelo, contexto):
    """Renderiza o .docx do modelo com o contexto (docxtpl em sandbox). Retorna bytes."""
    from docxtpl import DocxTemplate
    from jinja2.sandbox import SandboxedEnvironment

    with modelo.arquivo.storage.open(modelo.arquivo.name, 'rb') as f:
        conteudo = f.read()

    # Defesa em profundidade: o upload já bloqueia, mas arquivo antigo ou editado
    # fora do sistema não pode trazer lógica. Texto por parágrafo (junta os runs).
    with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
        for nome in _partes_texto_docx(zf):
            if any('{%' in t or '%}' in t for t in _paragrafos_docx(zf.read(nome))):
                raise ModeloDocxInvalido('O modelo contém tags de lógica não permitidas.')

    doc = DocxTemplate(io.BytesIO(conteudo))

    doc.render(contexto, jinja_env=SandboxedEnvironment(), autoescape=True)
    saida = io.BytesIO()
    doc.save(saida)
    return saida.getvalue()


def converter_docx_para_pdf(docx_bytes):
    """Converte .docx em PDF com LibreOffice headless. Isolada para ser mockada nos testes."""
    tmp = tempfile.mkdtemp(prefix='docx_')
    try:
        origem = Path(tmp) / 'documento.docx'
        origem.write_bytes(docx_bytes)
        perfil = (Path(tmp) / 'profile').as_uri()
        cmd = [
            settings.DOCUMENTO_SOFFICE_BIN, '--headless', '--norestore', '--nolockcheck',
            f'-env:UserInstallation={perfil}',
            '--convert-to', 'pdf', '--outdir', tmp, str(origem),
        ]
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
            )
        except OSError as exc:
            raise ConversaoDocxErro('Conversor de documentos indisponível.') from exc

        try:
            _, stderr = proc.communicate(timeout=settings.DOCUMENTO_SOFFICE_TIMEOUT)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, getattr(signal, 'SIGKILL', signal.SIGTERM))
            except (ProcessLookupError, PermissionError, AttributeError):
                proc.kill()
            proc.communicate()
            raise ConversaoDocxErro('Tempo esgotado na conversão do documento.')

        saida = Path(tmp) / 'documento.pdf'
        if proc.returncode != 0 or not saida.exists():
            logger.error(
                'soffice falhou (rc=%s): %s', proc.returncode,
                (stderr or b'').decode('utf-8', 'replace')[:2000],
            )
            raise ConversaoDocxErro('Falha ao converter o documento para PDF.')
        return saida.read_bytes()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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
        doc.arquivo_pdf.save('documento.pdf', ContentFile(pdf_bytes), save=False)
    doc.save()
    return doc


# Modelos padrão em .docx entregues com a aplicação. Fonte única dos títulos:
# o sufixo distingue dos modelos HTML legados (que continuam nos tenants existentes).
SUFIXO_MODELO_DOCX = ' (DOCX)'
PASTA_MODELOS_PADRAO = Path(__file__).resolve().parent / 'modelos_padrao'
MODELOS_PADRAO_DOCX = {
    'contrato': {
        'titulo': f'Contrato de Locação Residencial{SUFIXO_MODELO_DOCX}',
        'arquivo': 'contrato_locacao_residencial.docx',
    },
    'distrato': {
        'titulo': f'Distrato de Locação{SUFIXO_MODELO_DOCX}',
        'arquivo': 'distrato_locacao.docx',
    },
    'recibo': {
        'titulo': f'Recibo de Pagamento de Aluguel{SUFIXO_MODELO_DOCX}',
        'arquivo': 'recibo_pagamento_aluguel.docx',
    },
}


def caminho_modelo_padrao_docx(tipo):
    """Caminho do .docx do pacote para `tipo`. Só aceita chaves de MODELOS_PADRAO_DOCX."""
    return PASTA_MODELOS_PADRAO / MODELOS_PADRAO_DOCX[tipo]['arquivo']


def criar_variaveis_padrao(dry_run=False):
    """Cria as variáveis da fixture que ainda não existem (por slug). Retorna quantas criou
    (com dry_run, quantas criaria). Não altera variáveis existentes (o tenant pode ter
    desativado/renomeado)."""
    from .models import VariavelDocumento

    fixture = Path(__file__).resolve().parent / 'fixtures' / 'variaveis_documento.json'
    criadas = 0
    for item in json.loads(fixture.read_text(encoding='utf-8')):
        campos = item['fields']
        if dry_run:
            criadas += not VariavelDocumento.objects.filter(slug=campos['slug']).exists()
            continue
        _, criada = VariavelDocumento.objects.get_or_create(
            slug=campos['slug'],
            defaults={k: campos[k] for k in ('label', 'categoria', 'ativo')},
        )
        criadas += criada
    return criadas


def criar_modelos_padrao_docx(dry_run=False):
    """
    Garante os modelos .docx padrão no schema corrente. Idempotente por item:
    só cria o que não existe (padrao=True, com arquivo, mesmo título).
    Nunca altera nem remove modelos existentes.
    Cada modelo criado vira `predefinido` do seu tipo SOMENTE se o tenant ainda não tem
    predefinido ativo nesse tipo.
    Retorna {'criados': [títulos], 'existentes': [títulos], 'predefinidos': [títulos]};
    com dry_run não grava (predefinidos conta o que seria marcado).
    """
    from .models import ModeloDocumento

    resultado = {'criados': [], 'existentes': [], 'predefinidos': []}
    for tipo, dados in MODELOS_PADRAO_DOCX.items():
        existe = (
            ModeloDocumento.objects.filter(padrao=True, titulo=dados['titulo'])
            .exclude(arquivo='').exclude(arquivo__isnull=True).exists()
        )
        if existe:
            resultado['existentes'].append(dados['titulo'])
            continue
        predefinir = not ModeloDocumento.objects.filter(tipo=tipo, predefinido=True, ativo=True).exists()
        if not dry_run:
            modelo = ModeloDocumento(
                titulo=dados['titulo'], tipo=tipo, padrao=True, ativo=True, predefinido=predefinir,
            )
            modelo.arquivo.save(
                dados['arquivo'],
                ContentFile(caminho_modelo_padrao_docx(tipo).read_bytes()),
                save=False,
            )
            try:
                modelo.save()
            except Exception:
                modelo.arquivo.storage.delete(modelo.arquivo.name)
                raise
        resultado['criados'].append(dados['titulo'])
        if predefinir:
            resultado['predefinidos'].append(dados['titulo'])
    return resultado


def criar_documentos_padrao():
    """
    Entrega o catálogo de variáveis e os 3 modelos padrão (.docx) ao schema corrente.
    Deve ser chamada dentro de schema_context do tenant.
    Idempotente por peça (variáveis e cada modelo são checados separadamente).
    Retorna {'variaveis_criadas': int, 'modelos_criados': [...], 'modelos_existentes': [...]}.
    """
    variaveis_criadas = criar_variaveis_padrao()
    modelos = criar_modelos_padrao_docx()
    return {
        'variaveis_criadas': variaveis_criadas,
        'modelos_criados': modelos['criados'],
        'modelos_existentes': modelos['existentes'],
    }
