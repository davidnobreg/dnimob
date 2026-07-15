// Extensão FontAttrs — adiciona família e tamanho de fonte à mark
// "textStyle" (já usada por Color/Highlight) sem redeclarar a mark inteira.
// null = não define (renderHTML omite o style, mesmo idioma do indent-attrs.js).
(function () {
	if (!window.TipTapBundle) {
		console.error('TipTapBundle ausente — gere o bundle (documentos/frontend/README.md).')
		return
	}
	const { Extension } = window.TipTapBundle

	const FontAttrs = Extension.create({
		name: 'fontAttrs',
		addGlobalAttributes() {
			return [{
				types: ['textStyle'],
				attributes: {
					fontFamily: {
						default: null,
						parseHTML: el => el.style.fontFamily || null,
						renderHTML: attrs => attrs.fontFamily ? { style: `font-family: ${attrs.fontFamily}` } : {},
					},
					fontSize: {
						default: null,
						parseHTML: el => el.style.fontSize || null,
						renderHTML: attrs => attrs.fontSize ? { style: `font-size: ${attrs.fontSize}` } : {},
					},
				},
			}]
		},
	})

	window.FontAttrsExtension = FontAttrs
})()
