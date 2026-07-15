// Extensão IndentAttrs — adiciona recuo (esquerdo/direito/primeira linha) ao
// nó "paragraph" do StarterKit sem redeclarar o nó (evita "Duplicate
// extension names"). indentFirstLine negativo = recuo deslocado (hanging).
(function () {
	if (!window.TipTapBundle) {
		console.error('TipTapBundle ausente — gere o bundle (documentos/frontend/README.md).')
		return
	}
	const { Extension } = window.TipTapBundle

	const IndentAttrs = Extension.create({
		name: 'indentAttrs',
		addGlobalAttributes() {
			return [{
				types: ['paragraph'],
				attributes: {
					indentLeft: {
						default: 0,
						parseHTML: el => parseInt(el.style.marginLeft, 10) || 0,
						renderHTML: attrs => attrs.indentLeft ? { style: `margin-left: ${attrs.indentLeft}px` } : {},
					},
					indentRight: {
						default: 0,
						parseHTML: el => parseInt(el.style.marginRight, 10) || 0,
						renderHTML: attrs => attrs.indentRight ? { style: `margin-right: ${attrs.indentRight}px` } : {},
					},
					indentFirstLine: {
						default: 0,
						parseHTML: el => parseInt(el.style.textIndent, 10) || 0,
						renderHTML: attrs => attrs.indentFirstLine ? { style: `text-indent: ${attrs.indentFirstLine}px` } : {},
					},
				},
			}]
		},
	})

	window.IndentAttrsExtension = IndentAttrs
})()