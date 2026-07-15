// Extensão LineHeightAttrs — adiciona espaçamento entre linhas ao nó
// "paragraph" do StarterKit sem redeclarar o nó (evita "Duplicate extension
// names"). null = não define (renderHTML omite o style, cai no padrão do CSS
// de exibição/impressão — documento_a4.css, hoje 1.5).
(function () {
	if (!window.TipTapBundle) {
		console.error('TipTapBundle ausente — gere o bundle (documentos/frontend/README.md).')
		return
	}
	const { Extension } = window.TipTapBundle

	const LineHeightAttrs = Extension.create({
		name: 'lineHeightAttrs',
		addGlobalAttributes() {
			return [{
				types: ['paragraph'],
				attributes: {
					lineHeight: {
						default: null,
						parseHTML: el => el.style.lineHeight || null,
						renderHTML: attrs => attrs.lineHeight ? { style: `line-height: ${attrs.lineHeight}` } : {},
					},
				},
			}]
		},
	})

	window.LineHeightAttrsExtension = LineHeightAttrs
})()