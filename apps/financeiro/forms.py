from django import forms
from django.utils import timezone
from .models import Lancamento


class LancamentoForm(forms.ModelForm):
    class Meta:
        model = Lancamento
        fields = ['tipo', 'categoria', 'status', 'descricao', 'valor',
                  'data', 'data_prevista', 'contrato', 'observacao']
        widgets = {
            'tipo':          forms.Select(attrs={'class': 'form-select'}),
            'categoria':     forms.Select(attrs={'class': 'form-select'}),
            'status':        forms.Select(attrs={'class': 'form-select'}),
            'contrato':      forms.Select(attrs={'class': 'form-select'}),
            'descricao':     forms.TextInput(attrs={'class': 'form-input'}),
            'valor':         forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'data':          forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'data_prevista': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'observacao':    forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('data'):
            self.fields['data'].initial = timezone.now().date()
        self.fields['contrato'].required = False
        self.fields['data_prevista'].required = False


class FiltroLancamentoForm(forms.Form):
    q         = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Descrição...', 'class': 'form-input',
    }))
    tipo      = forms.ChoiceField(required=False,
                                  choices=[('', 'Receitas e Despesas')] + Lancamento.TIPO_CHOICES,
                                  widget=forms.Select(attrs={'class': 'form-select'}))
    categoria = forms.ChoiceField(required=False,
                                  choices=[('', 'Todas as categorias')] + Lancamento.CATEGORIA_CHOICES,
                                  widget=forms.Select(attrs={'class': 'form-select'}))
    status    = forms.ChoiceField(required=False,
                                  choices=[('', 'Todos')] + Lancamento.STATUS_CHOICES,
                                  widget=forms.Select(attrs={'class': 'form-select'}))
    data_ini  = forms.DateField(required=False, widget=forms.DateInput(attrs={
        'class': 'form-input', 'type': 'date',
    }))
    data_fim  = forms.DateField(required=False, widget=forms.DateInput(attrs={
        'class': 'form-input', 'type': 'date',
    }))
