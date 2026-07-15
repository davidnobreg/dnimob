// Bootstrap do editor de modelos de documento (DN Imob).
// Depende de: window.TipTapBundle (bundle vendorizado) e window.VariavelNode.
// Sem régua/paginação (fatia futura, se necessário) — só edição + preview A4 estático.
(function () {
	const elRoot = document.getElementById('editor-root')
	if (!elRoot) return
	if (!window.TipTapBundle) {
		elRoot.innerHTML = '<div class="text-sm text-red-600 p-4">Bundle TipTap não carregado.</div>'
		return
	}

	const T = window.TipTapBundle

	function getCookie(nome) {
		const valor = document.cookie
			.split('; ')
			.find(linha => linha.startsWith(nome + '='))
		return valor ? decodeURIComponent(valor.split('=')[1]) : ''
	}

	const csrf = getCookie('csrftoken')
	const saveUrl = elRoot.dataset.saveUrl
	const conteudoInicialEl = document.getElementById('conteudo-inicial')
	const conteudoInicial = conteudoInicialEl ? JSON.parse(conteudoInicialEl.textContent) : ''

	// Sanitiza HTML colado do Word: remove tags/atributos mso-* e margin/padding
	// inline por parágrafo que o Word injeta em todo <p>/<span>.
	function sanitizarHtmlColado(html) {
		const doWord = /mso-|urn:schemas-microsoft-com:office|w:WordDocument/i.test(html)
		const doc = new DOMParser().parseFromString(html, 'text/html')
		doc.querySelectorAll('style, script, meta, link').forEach(el => el.remove())
		doc.querySelectorAll('*').forEach(el => {
			if (el.tagName.includes(':')) {
				el.replaceWith(...el.childNodes)
				return
			}
			if (doWord) { el.removeAttribute('class') }
			const style = el.getAttribute('style')
			if (!style) { return }
			const mantido = style.split(';').map(s => s.trim()).filter(Boolean).filter(decl => {
				const prop = decl.split(':')[0].trim().toLowerCase()
				if (prop.startsWith('mso-')) { return false }
				if (prop.startsWith('page-break')) { return false }
				if (doWord && (prop.startsWith('margin') || prop.startsWith('padding'))) { return false }
				return true
			})
			if (mantido.length) { el.setAttribute('style', mantido.join('; ')) } else { el.removeAttribute('style') }
		})
		return doc.body.innerHTML
	}

	const extensoes = [
		// autolink: false — variáveis como {{ inquilino.email }} contêm texto no
		// formato palavra.palavra; o autolink converteria em <a>, quebrando a
		// sintaxe {{ }} e derrubando a renderização do documento.
		T.StarterKit.configure({ link: { openOnClick: false, autolink: false } }),
		T.TextAlign.configure({ types: ['heading', 'paragraph'] }),
		T.Table.configure({ resizable: true }),
		T.TableRow, T.TableHeader, T.TableCell,
		T.TextStyle,
		T.Color,
		T.Highlight.configure({ multicolor: true }),
		T.Subscript,
		T.Superscript,
		T.CharacterCount,
		window.VariavelNode,
	]
	if (window.IndentAttrsExtension) { extensoes.push(window.IndentAttrsExtension) }
	if (window.FontAttrsExtension) { extensoes.push(window.FontAttrsExtension) }
	if (window.LineHeightAttrsExtension) { extensoes.push(window.LineHeightAttrsExtension) }

	const elEditor = document.createElement('div')
	elRoot.appendChild(elEditor)

	const editor = new T.Editor({
		element: elEditor,
		editorProps: { transformPastedHTML: sanitizarHtmlColado },
		extensions: extensoes,
		content: conteudoInicial || '',
	})

	// ---- Autosave (debounce 30s, só se houve mudança) ----
	let sujo = false
	editor.on('update', () => { sujo = true })
	setInterval(() => {
		if (sujo) { sujo = false; salvar() }
	}, 30000)

	// ---- Contador de caracteres ----
	const contador = document.getElementById('contador-caracteres')
	function atualizarContador() {
		if (contador) { contador.textContent = `${editor.storage.characterCount.characters()} caracteres` }
	}
	editor.on('update', atualizarContador)
	atualizarContador()

	// ---- Grupo "tabela": só visível com cursor dentro de tabela ----
	const grupoTabela = document.getElementById('grupo-tabela')
	function atualizarGrupoTabela() {
		if (grupoTabela) { grupoTabela.style.display = editor.isActive('table') ? '' : 'none' }
	}
	editor.on('selectionUpdate', atualizarGrupoTabela)
	editor.on('transaction', atualizarGrupoTabela)
	atualizarGrupoTabela()

	// ---- Toolbar: botões com data-action ----
	document.querySelectorAll('[data-action]').forEach(btn => {
		btn.addEventListener('click', e => {
			e.preventDefault()
			const acao = btn.dataset.action
			const chain = editor.chain().focus()
			switch (acao) {
				case 'bold': chain.toggleBold().run(); break
				case 'italic': chain.toggleItalic().run(); break
				case 'underline': chain.toggleUnderline().run(); break
				case 'subscript': chain.toggleSubscript().run(); break
				case 'superscript': chain.toggleSuperscript().run(); break
				case 'h1': chain.toggleHeading({ level: 1 }).run(); break
				case 'h2': chain.toggleHeading({ level: 2 }).run(); break
				case 'p': chain.setParagraph().run(); break
				case 'left': chain.setTextAlign('left').run(); break
				case 'center': chain.setTextAlign('center').run(); break
				case 'justify': chain.setTextAlign('justify').run(); break
				case 'bullet': chain.toggleBulletList().run(); break
				case 'table': chain.insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(); break
				case 'hr': chain.setHorizontalRule().run(); break
				case 'link':
					if (editor.isActive('link')) {
						chain.unsetLink().run()
					} else {
						const url = window.prompt('URL do link:')
						if (url) { chain.setLink({ href: url }).run() }
					}
					break
				case 'undo': chain.undo().run(); break
				case 'redo': chain.redo().run(); break
				case 'clear': chain.unsetAllMarks().clearNodes().run(); break
				case 'color-clear': chain.unsetColor().run(); break
				case 'highlight-clear': chain.unsetHighlight().run(); break
				case 'font-family-clear': chain.setMark('textStyle', { fontFamily: null }).run(); break
				case 'font-size-clear': chain.setMark('textStyle', { fontSize: null }).run(); break
				case 'line-height-clear': chain.updateAttributes('paragraph', { lineHeight: null }).run(); break
				case 'col-before': chain.addColumnBefore().run(); break
				case 'col-after': chain.addColumnAfter().run(); break
				case 'col-del': chain.deleteColumn().run(); break
				case 'row-before': chain.addRowBefore().run(); break
				case 'row-after': chain.addRowAfter().run(); break
				case 'row-del': chain.deleteRow().run(); break
				case 'table-del': chain.deleteTable().run(); break
				default: break
			}
		})
	})

	document.querySelectorAll('[data-color]').forEach(sw => {
		sw.addEventListener('click', e => {
			e.preventDefault()
			editor.chain().focus().setColor(sw.dataset.color).run()
		})
	})

	document.querySelectorAll('[data-highlight]').forEach(sw => {
		sw.addEventListener('click', e => {
			e.preventDefault()
			editor.chain().focus().toggleHighlight({ color: sw.dataset.highlight }).run()
		})
	})

	document.querySelectorAll('[data-font-family]').forEach(btn => {
		btn.addEventListener('click', e => {
			e.preventDefault()
			editor.chain().focus().setMark('textStyle', { fontFamily: btn.dataset.fontFamily }).run()
		})
	})

	document.querySelectorAll('[data-font-size]').forEach(btn => {
		btn.addEventListener('click', e => {
			e.preventDefault()
			editor.chain().focus().setMark('textStyle', { fontSize: `${btn.dataset.fontSize}pt` }).run()
		})
	})

	document.querySelectorAll('[data-line-height]').forEach(btn => {
		btn.addEventListener('click', e => {
			e.preventDefault()
			editor.chain().focus().updateAttributes('paragraph', { lineHeight: btn.dataset.lineHeight }).run()
		})
	})

	// ---- Sidebar de variáveis: clique insere nó ----
	document.querySelectorAll('[data-var-slug]').forEach(item => {
		item.addEventListener('click', () => {
			const slug = item.dataset.varSlug
			editor.chain().focus().insertContent({ type: 'variavel', attrs: { slug } }).run()
		})
	})

	// ---- Busca de variáveis ----
	const busca = document.getElementById('busca-variavel')
	if (busca) {
		busca.addEventListener('input', () => {
			const termo = busca.value.toLowerCase()
			document.querySelectorAll('[data-var-slug]').forEach(item => {
				const txt = item.textContent.toLowerCase()
				item.style.display = txt.includes(termo) ? '' : 'none'
			})
		})
	}

	// ---- Salvar ----
	function salvar() {
		const status = document.getElementById('salvar-status')
		if (status) { status.textContent = 'salvando...' }
		fetch(saveUrl, {
			method: 'POST',
			headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
			body: JSON.stringify({ conteudo_html: editor.getHTML() }),
		})
			.then(r => r.json())
			.then(d => {
				if (d.ok) {
					if (status) { status.textContent = 'salvo' }
				} else {
					if (status) { status.textContent = 'erro' }
					alert(d.erro || 'Erro ao salvar.')
				}
			})
			.catch(() => { if (status) { status.textContent = 'falha de rede' } })
	}

	const btnSalvar = document.getElementById('btn-salvar')
	if (btnSalvar) { btnSalvar.addEventListener('click', salvar) }
})()
