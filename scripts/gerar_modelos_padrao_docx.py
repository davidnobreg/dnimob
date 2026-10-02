"""
scripts/gerar_modelos_padrao_docx.py

Gera os 3 modelos padrão em .docx (apps/documentos/modelos_padrao/) a partir do
texto dos HTML da fixture apps/documentos/fixtures/modelos_padrao.json.
Só o layout muda; o texto é o da fixture.

Uso (na raiz do projeto):
	python scripts/gerar_modelos_padrao_docx.py

Saída determinística: data/hora do core.xml fixas, para o .docx não mudar a
cada execução sem mudança de conteúdo.
"""
import json
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

RAIZ = Path(__file__).resolve().parent.parent
FIXTURE = RAIZ / 'apps' / 'documentos' / 'fixtures' / 'modelos_padrao.json'
SAIDA = RAIZ / 'apps' / 'documentos' / 'modelos_padrao'

# tipo da fixture -> nome do arquivo
ARQUIVOS = {
	'contrato': 'contrato_locacao_residencial.docx',
	'distrato': 'distrato_locacao.docx',
	'recibo': 'recibo_pagamento_aluguel.docx',
}

RE_VARIAVEL = re.compile(r'(\{\{\s*[\w\.]+\s*\}\})')
FONTE = 'Times New Roman'


class ParserHtml(HTMLParser):
	"""Converte o HTML simples da fixture em blocos:
	[{'tipo': 'h1'|'p', 'trechos': [(texto, negrito)] , '\n' = quebra de linha}]."""

	def __init__(self):
		super().__init__(convert_charrefs=True)
		self.blocos = []
		self._bloco = None
		self._negrito = 0

	def handle_starttag(self, tag, attrs):
		if tag in ('h1', 'p'):
			self._bloco = {'tipo': tag, 'trechos': []}
		elif tag == 'strong':
			self._negrito += 1
		elif tag == 'br' and self._bloco is not None:
			self._bloco['trechos'].append(('\n', False))

	def handle_endtag(self, tag):
		if tag in ('h1', 'p') and self._bloco is not None:
			self.blocos.append(self._bloco)
			self._bloco = None
		elif tag == 'strong':
			self._negrito -= 1

	def handle_data(self, data):
		if self._bloco is not None:
			self._bloco['trechos'].append((data, self._negrito > 0))


def configurar_documento(doc):
	secao = doc.sections[0]
	secao.page_width = Cm(21)
	secao.page_height = Cm(29.7)
	secao.left_margin = Cm(3)
	secao.top_margin = Cm(3)
	secao.right_margin = Cm(2)
	secao.bottom_margin = Cm(2)

	normal = doc.styles['Normal']
	normal.font.name = FONTE
	normal.font.size = Pt(12)
	rfonts = normal.element.get_or_add_rPr().get_or_add_rFonts()
	for atributo in ('w:ascii', 'w:hAnsi', 'w:eastAsia', 'w:cs'):
		rfonts.set(qn(atributo), FONTE)
	formato = normal.paragraph_format
	formato.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
	formato.space_before = Pt(0)
	formato.space_after = Pt(6)
	formato.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY


def adicionar_trecho(paragrafo, texto, negrito):
	"""Cada {{ variável }} vai inteira num único run; o texto ao redor em runs próprios."""
	for parte in RE_VARIAVEL.split(texto):
		if not parte:
			continue
		if parte == '\n':
			paragrafo.add_run().add_break()
			continue
		run = paragrafo.add_run(parte)
		run.bold = negrito or None


def montar_docx(html):
	parser = ParserHtml()
	parser.feed(html)

	doc = Document()
	configurar_documento(doc)
	for bloco in parser.blocos:
		paragrafo = doc.add_paragraph()
		if bloco['tipo'] == 'h1':
			paragrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
			paragrafo.paragraph_format.space_after = Pt(12)
		for texto, negrito in bloco['trechos']:
			adicionar_trecho(paragrafo, texto, negrito or bloco['tipo'] == 'h1')

	props = doc.core_properties
	props.author = 'DNImob'
	props.last_modified_by = 'DNImob'
	props.created = props.modified = datetime(2026, 7, 15, 9, 0, 0)
	return doc


def main():
	SAIDA.mkdir(parents=True, exist_ok=True)
	modelos = {m['fields']['tipo']: m['fields'] for m in json.loads(FIXTURE.read_text(encoding='utf-8'))}
	for tipo, nome in ARQUIVOS.items():
		doc = montar_docx(modelos[tipo]['conteudo_html'])
		destino = SAIDA / nome
		doc.save(destino)
		print(f'{destino.relative_to(RAIZ)}  ({destino.stat().st_size} bytes)')


if __name__ == '__main__':
	main()
