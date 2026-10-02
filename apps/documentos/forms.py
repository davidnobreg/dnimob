from django import forms
from django.core.exceptions import ValidationError

from .models import ModeloDocumento
from .services import analisar_docx
from .validators import ValidarDocx, validar_extensao_docx, validar_tamanho_modelo


class ModeloDocumentoUploadForm(forms.ModelForm):
	# Campo explícito: os validators rodam ANTES do clean_arquivo, que lê o zip
	arquivo = forms.FileField(
		label='Arquivo .docx',
		validators=[validar_extensao_docx, validar_tamanho_modelo, ValidarDocx()],
	)

	class Meta:
		model = ModeloDocumento
		fields = ['titulo', 'tipo', 'arquivo']

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.analise = None

	def clean_arquivo(self):
		arquivo = self.cleaned_data['arquivo']
		analise = analisar_docx(arquivo)
		if analise['erros']:
			raise ValidationError(analise['erros'])
		self.analise = analise
		return arquivo


class SubstituirArquivoModeloForm(ModeloDocumentoUploadForm):
	class Meta(ModeloDocumentoUploadForm.Meta):
		fields = ['arquivo']
