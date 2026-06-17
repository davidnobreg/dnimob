from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone
from .models import Contrato, Parcela


class ContratoForm(forms.ModelForm):
    class Meta:
        model = Contrato
        exclude = ['criado_em', 'atualizado_em']
        widgets = {
            'imovel':       forms.Select(attrs={'class': 'form-select'}),
            'inquilino':    forms.Select(attrs={'class': 'form-select'}),
            'responsavel':  forms.Select(attrs={'class': 'form-select'}),
            'status':       forms.Select(attrs={'class': 'form-select'}),
            'indice_reajuste': forms.Select(attrs={'class': 'form-select'}),
            'tipo_garantia':   forms.Select(attrs={'class': 'form-select'}),
            'data_inicio':     forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}, format='%Y-%m-%d'),
            'data_fim':        forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}, format='%Y-%m-%d'),
            'data_assinatura': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}, format='%Y-%m-%d'),
            'clausulas_adicionais': forms.Textarea(attrs={'class': 'form-input', 'rows': 5}),
            'observacoes':    forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        text_fields = [
            'numero', 'valor_aluguel', 'valor_condominio', 'valor_iptu',
            'dia_vencimento', 'percentual_fixo', 'periodicidade_reajuste',
            'valor_caucao', 'multa_rescisao',
        ]
        for f in text_fields:
            if f in self.fields:
                self.fields[f].widget.attrs.setdefault('class', 'form-input')

        # input type="date" exige formato ISO — sem isso o valor salvo não aparece pré-preenchido
        for campo in ['data_inicio', 'data_fim', 'data_assinatura']:
            self.fields[campo].input_formats = ['%Y-%m-%d']
            if self.instance.pk:
                valor = getattr(self.instance, campo)
                if valor:
                    self.initial[campo] = valor.strftime('%Y-%m-%d')

        # Filtrar apenas imóveis disponíveis (ou o atual se estiver editando,
        # mesmo que o status dele não seja disponivel/alugado)
        from apps.imoveis.models import Imovel
        if self.instance.pk:
            self.fields['imovel'].queryset = Imovel.objects.filter(
                Q(status__in=['disponivel', 'alugado']) | Q(pk=self.instance.imovel_id)
            ).distinct()
        else:
            self.fields['imovel'].queryset = Imovel.objects.filter(status='disponivel')

        # Dados para auto-fill de valores ao selecionar imóvel
        self.imoveis_data = {
            str(i.pk): {
                'valor': str(i.valor_aluguel or ''),
                'condominio': str(i.valor_condominio or '0.00'),
                'iptu': str(i.valor_iptu or '0.00'),
            }
            for i in self.fields['imovel'].queryset.only('pk', 'valor_aluguel', 'valor_condominio', 'valor_iptu')
        }
        self.fields['imovel'].widget.attrs['onchange'] = '_preencherImovel(this.value)'

    def clean(self):
        from dateutil.relativedelta import relativedelta
        cleaned = super().clean()
        inicio = cleaned.get('data_inicio')
        fim = cleaned.get('data_fim')
        dia = cleaned.get('dia_vencimento')

        if inicio and fim and fim <= inicio:
            self.add_error('data_fim', 'A data de fim deve ser posterior ao início.')

        if dia and not (1 <= dia <= 28):
            self.add_error('dia_vencimento', 'Use um dia entre 1 e 28 para evitar problemas em fevereiro.')

        if inicio and fim and dia and not self.errors:
            primeiro_venc = inicio.replace(day=dia)
            if primeiro_venc < inicio:
                primeiro_venc += relativedelta(months=1)
            if primeiro_venc > fim:
                self.add_error(
                    'dia_vencimento',
                    f'Com dia {dia} e as datas informadas, o primeiro vencimento seria '
                    f'{primeiro_venc.strftime("%d/%m/%Y")} — após o fim do contrato. '
                    f'Nenhuma parcela seria gerada. Ajuste o fim do contrato ou o dia de vencimento.'
                )

        return cleaned

    def clean_numero(self):
        numero = self.cleaned_data['numero'].strip().upper()
        qs = Contrato.objects.filter(numero=numero)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe um contrato com este número.')
        return numero


class FiltroContratoForm(forms.Form):
    q      = forms.CharField(required=False, widget=forms.TextInput(attrs={
        'placeholder': 'Número, inquilino, imóvel...',
        'class': 'form-input',
    }))
    status = forms.ChoiceField(required=False,
                               choices=[('', 'Todos')] + Contrato.STATUS_CHOICES,
                               widget=forms.Select(attrs={'class': 'form-select'}))
    vencendo = forms.BooleanField(required=False, label='Vencendo em 30 dias',
                                  widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}))


class ParcelaPagamentoForm(forms.ModelForm):
    class Meta:
        model = Parcela
        fields = ['data_pagamento', 'valor', 'valor_multa', 'valor_desconto', 'observacao']
        widgets = {
            'data_pagamento': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'valor':          forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'valor_multa':    forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'valor_desconto': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'observacao':     forms.TextInput(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.initial.get('data_pagamento'):
            self.fields['data_pagamento'].initial = timezone.now().date()

        # Multa de 2% (Lei do Inquilinato, art. 4º) só se a parcela estiver atrasada.
        # Base de cálculo é o total antes de multa/desconto — não usar valor_total.
        parcela = self.instance
        if parcela.pk and parcela.status in ('pendente', 'atrasado') \
           and parcela.data_vencimento < timezone.now().date() \
           and not self.initial.get('valor_multa'):
            base_calculo = parcela.valor + parcela.valor_condominio + parcela.valor_iptu
            multa_calculada = (base_calculo * Decimal('0.02')).quantize(Decimal('0.01'))
            self.fields['valor_multa'].initial = multa_calculada
