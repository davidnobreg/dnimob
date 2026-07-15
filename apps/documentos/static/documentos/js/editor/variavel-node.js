// Extensão VariavelNode — nó atômico (não editável por dentro).
// Renderiza <span data-var="cliente.nome" class="doc-var">{{ cliente.nome }}</span>.
(function () {
	if (!window.TipTapBundle) {
		console.error('TipTapBundle ausente — gere o bundle (documentos/frontend/README.md).')
		return
	}
	const { Node, mergeAttributes } = window.TipTapBundle

	const VariavelNode = Node.create({
		name: 'variavel',
		group: 'inline',
		inline: true,
		atom: true,
		addAttributes() {
			return { slug: { default: '' } }
		},
		parseHTML() {
			return [{
				tag: 'span[data-var]',
				getAttrs: el => ({ slug: el.getAttribute('data-var') }),
			}]
		},
		renderHTML({ node }) {
			return ['span', mergeAttributes({
				'data-var': node.attrs.slug,
				'class': 'doc-var',
			}), `{{ ${node.attrs.slug} }}`]
		},
		renderText({ node }) {
			return `{{ ${node.attrs.slug} }}`
		},
	})

	window.VariavelNode = VariavelNode
})()
