# -*- coding: utf-8 -*-
"""As receitas do FORGE.

Por que elas sao escritas aqui, e nao copiadas de um livro
----------------------------------------------------------
A ideia veio de tres PDFs de receitas. Um deles carrega, em todas as 308 paginas, a marca
"Licenciado para <nome> - <CPF> - Protegido por Eduzz.com", e os termos dele dizem que e
ilegal copiar ou distribuir o livro "ou parte dele". O FORGE e um produto vendido: publicar
aquele conteudo aqui seria exatamente o que aquele texto proibe. Os outros dois nao trazem
termos, mas direito autoral nao precisa de aviso para existir.

Entao estas receitas sao do FORGE. E isso acabou sendo melhor de produto, e nao so mais
seguro:

CADA INGREDIENTE APONTA PARA O CATALOGO. `food_id` e o mesmo id que o motor usa no plano.
Por isso a caloria e o macro de cada receita sao CALCULADOS, nunca digitados — nao existe
como a receita dizer 260 kcal e o prato ter 400. E, mais importante, o FORGE consegue
responder a unica pergunta que interessa a quem esta seguindo um plano: "isto cabe no meu
lanche da tarde?".

`extras` sao os itens que nao movem macro (canela, adocante, sal, alho, cafe). Eles existem
porque a receita precisa deles para ser comida de verdade, e ficariam absurdos se tivessem
de virar gramas no catalogo.

`refeicao_livre` marca o que serve de doce ou de recompensa. Nao e uma lista de escapadas:
sao receitas feitas com os MESMOS alimentos do plano, entao a pessoa mata a vontade sem sair
da conta do dia. Foi o pedido do treinador — "as melhores receitas sem fugir muito do plano,
tipo sobremesa, como se fosse uma refeicao livre".
"""
from typing import Any, Dict, List, Optional

from nutrition_engine import FOOD_INDEX, tolerancia_de_caloria

# As classes, na ordem em que o dia acontece. O rotulo e o que aparece na tela; a chave e a
# mesma nocao de refeicao que `_infer_meal_type` usa, para a receita poder ser encaixada no
# plano sem tradutor no meio.
CLASSES = [
    ("cafe_da_manha", "Café da manhã", "breakfast"),
    ("lanche_da_manha", "Lanche da manhã", "morning_snack"),
    ("pre_treino", "Pré-treino", "pre_workout"),
    ("pos_treino", "Pós-treino", "post_workout"),
    ("almoco_jantar", "Almoço e jantar", "lunch"),
    ("lanche", "Lanche da tarde", "snack"),
    ("sobremesa", "Sobremesa", "snack"),
]

CLASSE_PARA_REFEICAO = {chave: tipo for chave, _, tipo in CLASSES}
ROTULO_DA_CLASSE = {chave: rotulo for chave, rotulo, _ in CLASSES}


RECEITAS: List[Dict[str, Any]] = [
    # ── Café da manhã ────────────────────────────────────────────────────────────────
    {
        "id": "mingau-forge",
        "nome": "Mingau FORGE",
        "classe": "cafe_da_manha",
        "tempo_min": 5,
        "resumo": "O café da manhã do método, em cinco minutos e uma panela só.",
        "ingredientes": [
            {"food_id": "oats", "gramas": 60},
            {"food_id": "whey-protein", "gramas": 30},
            {"food_id": "banana", "gramas": 100},
            {"food_id": "peanut-butter", "gramas": 10},
        ],
        "extras": ["Canela a gosto", "Água ou leite desnatado para dar o ponto"],
        "preparo": [
            "Cozinhe a aveia com água ou leite em fogo baixo, mexendo, até engrossar.",
            "Tire do fogo e ESPERE amornar antes de juntar o whey — no calor ele talha e vira grumo.",
            "Misture o whey, junte a banana em rodelas e a pasta de amendoim por cima.",
        ],
        "por_que": "Aveia com whey é a base do café da manhã do método: carboidrato de "
                   "digestão lenta com proteína rápida, e a fruta fecha.",
        "tags": ["rapida", "uma_panela"],
    },
    {
        "id": "panqueca-de-aveia",
        "nome": "Panqueca de aveia e whey",
        "classe": "cafe_da_manha",
        "tempo_min": 10,
        "resumo": "Mesma conta do mingau, em formato de panqueca.",
        "ingredientes": [
            {"food_id": "oats", "gramas": 50},
            {"food_id": "egg-whites", "gramas": 120},
            {"food_id": "whey-protein", "gramas": 15},
            {"food_id": "banana", "gramas": 60},
        ],
        "extras": ["Canela", "Fermento em pó (1 pitada)", "Adoçante a gosto"],
        "preparo": [
            "Bata tudo no liquidificador até virar uma massa lisa.",
            "Frigideira antiaderente bem quente, fogo médio, sem óleo.",
            "Vire quando a superfície começar a fazer bolhas e as bordas soltarem.",
        ],
        "por_que": "Mesma combinação do mingau, para quem não come doce de colher de manhã.",
        "tags": ["rapida"],
    },
    {
        "id": "crepioca-proteica",
        "nome": "Crepioca proteica",
        "classe": "cafe_da_manha",
        "tempo_min": 8,
        "resumo": "Salgada, pronta numa frigideira, sem forno.",
        "ingredientes": [
            {"food_id": "tapioca", "gramas": 40},
            {"food_id": "eggs-whole", "gramas": 100},
            {"food_id": "cheese-cottage", "gramas": 40},
        ],
        "extras": ["Sal", "Orégano"],
        "preparo": [
            "Misture a goma de tapioca com os ovos batidos até ficar homogêneo.",
            "Despeje na frigideira quente e espalhe fino.",
            "Quando soltar do fundo, ponha o cottage de um lado e dobre.",
        ],
        "por_que": "Café salgado para quem enjoa de doce — a tapioca entrega o carboidrato "
                   "rápido sem pesar.",
        "tags": ["rapida", "salgada"],
    },
    {
        "id": "ovos-com-cuscuz",
        "nome": "Cuscuz com ovos",
        "classe": "cafe_da_manha",
        "tempo_min": 12,
        "resumo": "Café da manhã de obra: barato, sustenta e é rápido.",
        "ingredientes": [
            {"food_id": "corn-flour", "gramas": 80},
            {"food_id": "eggs-whole", "gramas": 100},
            {"food_id": "tomato", "gramas": 60},
            {"food_id": "olive-oil", "gramas": 5},
        ],
        "extras": ["Sal", "Cebolinha"],
        "preparo": [
            "Hidrate o cuscuz com água morna e sal, descanse 10 minutos e leve à cuscuzeira.",
            "Enquanto isso, mexa os ovos no azeite com o tomate picado.",
            "Sirva os ovos por cima do cuscuz.",
        ],
        "por_que": "O cuscuz tem menos da metade da densidade calórica da aveia — é volume "
                   "de comida por caloria, que é o que segura a fome.",
        "tags": ["barata", "salgada"],
    },

    # ── Lanche da manhã (prato salgado pequeno) ──────────────────────────────────────
    {
        "id": "frango-com-batata",
        "nome": "Frango com batata na air fryer",
        "classe": "lanche_da_manha",
        "tempo_min": 25,
        "resumo": "O lanche da manhã do método. Faz no domingo, come a semana.",
        "ingredientes": [
            {"food_id": "chicken-breast", "gramas": 150},
            {"food_id": "potato", "gramas": 250},
            {"food_id": "olive-oil", "gramas": 5},
        ],
        "extras": ["Sal", "Alho", "Páprica", "Pimenta-do-reino"],
        "preparo": [
            "Corte a batata em cubos, tempere com sal, alho e o azeite.",
            "Air fryer a 200 °C por 18 minutos, sacudindo na metade.",
            "Grelhe o frango temperado e junte. Guarde em potes: rende a semana inteira.",
        ],
        "por_que": "É a refeição que o método pede às nove da manhã — prato salgado pequeno, "
                   "e não shake.",
        "tags": ["marmita", "salgada"],
    },
    {
        "id": "pao-com-frango-desfiado",
        "nome": "Pão francês com frango desfiado",
        "classe": "lanche_da_manha",
        "tempo_min": 10,
        "resumo": "Come na mão, no caminho, sem esquentar nada.",
        "ingredientes": [
            {"food_id": "bread-white", "gramas": 50},
            {"food_id": "chicken-breast", "gramas": 120},
            {"food_id": "tomato", "gramas": 40},
        ],
        "extras": ["Sal", "Orégano", "Folhas de alface"],
        "preparo": [
            "Desfie o frango já cozido e tempere com sal e orégano.",
            "Abra o pão, recheie com o frango, o tomate em rodelas e a alface.",
        ],
        "por_que": "Para quem está em ganho e precisa de caloria que não dá trabalho.",
        "tags": ["rapida", "salgada", "ganho"],
    },
    {
        "id": "omelete-de-legumes",
        "nome": "Omelete de legumes",
        "classe": "lanche_da_manha",
        "tempo_min": 10,
        "resumo": "Quando o carboidrato do dia já foi gasto.",
        "ingredientes": [
            {"food_id": "eggs-whole", "gramas": 150},
            {"food_id": "zucchini", "gramas": 80},
            {"food_id": "spinach", "gramas": 40},
            {"food_id": "olive-oil", "gramas": 5},
        ],
        "extras": ["Sal", "Pimenta", "Cebola"],
        "preparo": [
            "Refogue a abobrinha e o espinafre no azeite até soltar a água.",
            "Junte os ovos batidos, abaixe o fogo e tampe até firmar em cima.",
        ],
        "por_que": "Sem amido nenhum: cabe em dia de corte agressivo sem estourar o "
                   "carboidrato.",
        "tags": ["sem_amido", "salgada", "corte"],
    },

    # ── Pré-treino ──────────────────────────────────────────────────────────────────
    {
        "id": "pre-treino-farinha-de-arroz",
        "nome": "Mingau rápido de farinha de arroz",
        "classe": "pre_treino",
        "tempo_min": 4,
        "resumo": "Carboidrato rápido e proteína, sem peso no estômago.",
        "ingredientes": [
            {"food_id": "rice-flour", "gramas": 50},
            {"food_id": "whey-protein", "gramas": 25},
            {"food_id": "banana", "gramas": 80},
        ],
        "extras": ["Canela", "Água"],
        "preparo": [
            "Dissolva a farinha de arroz em água fria e leve ao fogo mexendo até engrossar.",
            "Fora do fogo e já morno, misture o whey.",
            "Coma 40 a 60 minutos antes de treinar.",
        ],
        "por_que": "A farinha de arroz é o carboidrato do método para antes do treino: "
                   "sobe rápido e não fica pesando.",
        "tags": ["rapida", "pre"],
    },
    {
        "id": "tapioca-com-pasta-de-amendoim",
        "nome": "Tapioca com pasta de amendoim e banana",
        "classe": "pre_treino",
        "tempo_min": 6,
        "resumo": "Para treino mais tarde, quando precisa segurar mais tempo.",
        "ingredientes": [
            {"food_id": "tapioca", "gramas": 50},
            {"food_id": "peanut-butter", "gramas": 15},
            {"food_id": "banana", "gramas": 80},
        ],
        "extras": ["Canela"],
        "preparo": [
            "Espalhe a goma na frigideira quente até formar o disco e soltar.",
            "Recheie com a pasta de amendoim e a banana em rodelas, dobre.",
        ],
        "por_que": "A gordura da pasta segura a digestão — serve quando o treino demora "
                   "mais de uma hora para começar.",
        "tags": ["pre"],
    },

    # ── Pós-treino ──────────────────────────────────────────────────────────────────
    {
        "id": "pos-treino-classico",
        "nome": "Whey com farinha de arroz",
        "classe": "pos_treino",
        "tempo_min": 2,
        "resumo": "Dois ingredientes, bate e bebe.",
        "ingredientes": [
            {"food_id": "whey-protein", "gramas": 35},
            {"food_id": "rice-flour", "gramas": 50},
            {"food_id": "watermelon", "gramas": 200},
        ],
        "extras": ["Água gelada", "Gelo"],
        "preparo": [
            "Bata tudo no liquidificador com água gelada.",
            "Beba logo depois do treino.",
        ],
        "por_que": "O pós-treino do método: proteína rápida com carboidrato rápido, sem "
                   "gordura para não atrasar a digestão.",
        "tags": ["rapida", "pos"],
    },
    {
        "id": "frango-com-arroz",
        "nome": "Frango com arroz branco",
        "classe": "pos_treino",
        "tempo_min": 20,
        "resumo": "Quem treina cedo almoça depois de treinar — e isso é o pós-treino.",
        "ingredientes": [
            {"food_id": "chicken-breast", "gramas": 150},
            {"food_id": "rice-white", "gramas": 200},
            {"food_id": "green-beans", "gramas": 100},
        ],
        "extras": ["Sal", "Alho", "Limão"],
        "preparo": [
            "Tempere o frango com alho, sal e limão e grelhe em fogo alto.",
            "Sirva com o arroz e a vagem no vapor.",
        ],
        "por_que": "Prato de verdade no lugar do shake, para quem treina perto do almoço.",
        "tags": ["marmita", "pos"],
    },

    # ── Almoço e jantar ─────────────────────────────────────────────────────────────
    {
        "id": "prato-completo",
        "nome": "Frango com arroz, feijão e salada",
        "classe": "almoco_jantar",
        "tempo_min": 25,
        "resumo": "O prato brasileiro, na conta certa.",
        "ingredientes": [
            {"food_id": "chicken-breast", "gramas": 150},
            {"food_id": "rice-white", "gramas": 180},
            {"food_id": "beans-carioca", "gramas": 100},
            {"food_id": "lettuce", "gramas": 60},
            {"food_id": "olive-oil", "gramas": 8},
        ],
        "extras": ["Sal", "Alho", "Vinagre"],
        "preparo": [
            "Grelhe o frango temperado com alho e sal.",
            "Monte o prato com o arroz, o feijão e a salada temperada com azeite e vinagre.",
        ],
        "por_que": "Arroz com feijão é proteína completa e sai barato — não existe motivo "
                   "para trocar isso por comida de dieta.",
        "tags": ["barata", "classica"],
    },
    {
        "id": "patinho-com-batata-doce",
        "nome": "Patinho com batata doce e brócolis",
        "classe": "almoco_jantar",
        "tempo_min": 30,
        "resumo": "Carne vermelha sem estourar a gordura do dia.",
        "ingredientes": [
            {"food_id": "beef-grill", "gramas": 150},
            {"food_id": "sweet-potato", "gramas": 250},
            {"food_id": "broccoli", "gramas": 150},
            {"food_id": "olive-oil", "gramas": 5},
        ],
        "extras": ["Sal", "Alho", "Alecrim"],
        "preparo": [
            "Cozinhe a batata doce com casca até ficar macia no garfo.",
            "Grelhe o patinho em fogo alto, 3 minutos de cada lado, e descanse antes de cortar.",
            "Brócolis no vapor, azeite e sal por cima na hora de servir.",
        ],
        "por_que": "Patinho é o corte magro: dá a carne vermelha sem a gordura do acém.",
        "tags": ["classica"],
    },
    {
        "id": "escondidinho-de-carne",
        "nome": "Escondidinho de carne com purê de batata doce",
        "classe": "almoco_jantar",
        "tempo_min": 40,
        "resumo": "Comida de domingo que cabe no plano.",
        "ingredientes": [
            {"food_id": "beef-ground", "gramas": 150},
            {"food_id": "sweet-potato", "gramas": 250},
            {"food_id": "tomato", "gramas": 80},
            {"food_id": "cheese-cottage", "gramas": 40},
        ],
        "extras": ["Sal", "Cebola", "Alho", "Cheiro-verde"],
        "preparo": [
            "Cozinhe a batata doce e amasse ainda quente até virar purê.",
            "Refogue a carne moída com cebola, alho e tomate até secar a água.",
            "Monte em camadas — carne embaixo, purê em cima, cottage por cima — e leve ao "
            "forno a 200 °C por 15 minutos.",
        ],
        "por_que": "O cottage entra no lugar do queijo gratinado e segura a gordura.",
        "tags": ["forno", "classica"],
    },
    {
        "id": "estrogonofe-leve",
        "nome": "Estrogonofe leve de frango",
        "classe": "almoco_jantar",
        "tempo_min": 25,
        "resumo": "Sem creme de leite, sem perder o gosto.",
        "ingredientes": [
            {"food_id": "chicken-breast", "gramas": 150},
            {"food_id": "yogurt-natural", "gramas": 120},
            {"food_id": "tomato", "gramas": 80},
            {"food_id": "rice-white", "gramas": 180},
        ],
        "extras": ["Sal", "Cebola", "Alho", "Mostarda", "Páprica"],
        "preparo": [
            "Doure o frango em cubos com cebola e alho.",
            "Junte o tomate e a mostarda, deixe apurar.",
            "Desligue o fogo e SÓ ENTÃO misture o iogurte — no fogo ele talha.",
        ],
        "por_que": "Troca o creme de leite por iogurte natural: mesma textura, uma fração "
                   "da gordura.",
        "tags": ["classica"],
    },
    {
        "id": "carne-com-abobrinha",
        "nome": "Carne moída com abobrinha",
        "classe": "almoco_jantar",
        "tempo_min": 20,
        "resumo": "Sem amido nenhum, para dia de corte.",
        "ingredientes": [
            {"food_id": "beef-ground", "gramas": 150},
            {"food_id": "zucchini", "gramas": 250},
            {"food_id": "tomato", "gramas": 80},
        ],
        "extras": ["Sal", "Cebola", "Alho", "Orégano"],
        "preparo": [
            "Refogue a carne com cebola e alho até secar.",
            "Junte a abobrinha em cubos e o tomate, tampe e deixe cozinhar no próprio vapor.",
        ],
        "por_que": "A abobrinha faz o volume que o arroz faria, com quase nenhuma caloria.",
        "tags": ["sem_amido", "corte", "rapida"],
    },
    {
        "id": "berinjela-recheada",
        "nome": "Berinjela recheada com carne",
        "classe": "almoco_jantar",
        "tempo_min": 45,
        "resumo": "Jantar que enche o prato e não enche a conta.",
        "ingredientes": [
            {"food_id": "eggplant", "gramas": 250},
            {"food_id": "beef-ground", "gramas": 140},
            {"food_id": "tomato", "gramas": 80},
            {"food_id": "cheese-mozzarella", "gramas": 30},
        ],
        "extras": ["Sal", "Cebola", "Alho", "Manjericão"],
        "preparo": [
            "Corte as berinjelas ao meio e retire o miolo, deixando as cascas inteiras.",
            "Refogue a carne com o miolo picado, a cebola, o alho e o tomate.",
            "Recheie, cubra com a mussarela e leve ao forno a 200 °C por 20 minutos.",
        ],
        "por_que": "Sem amido e com volume — jantar de quem está cortando e não quer "
                   "comer salada.",
        "tags": ["sem_amido", "forno", "corte"],
    },
    {
        "id": "salada-completa-de-atum",
        "nome": "Salada completa de atum com grão-de-bico",
        "classe": "almoco_jantar",
        "tempo_min": 10,
        "resumo": "Almoço sem fogão, pronto em dez minutos.",
        "ingredientes": [
            {"food_id": "tuna-can", "gramas": 120},
            {"food_id": "chickpeas", "gramas": 130},
            {"food_id": "tomato", "gramas": 80},
            {"food_id": "lettuce", "gramas": 60},
            {"food_id": "olive-oil", "gramas": 8},
        ],
        "extras": ["Sal", "Limão", "Cebola roxa"],
        "preparo": [
            "Escorra bem o atum e o grão-de-bico.",
            "Misture tudo, tempere com azeite, limão e sal na hora de comer.",
        ],
        "por_que": "O grão-de-bico dá o carboidrato e a fibra que faltariam numa salada só "
                   "de folhas.",
        "tags": ["sem_fogao", "rapida"],
    },
    {
        "id": "sopa-de-legumes-com-frango",
        "nome": "Sopa de legumes com frango",
        "classe": "almoco_jantar",
        "tempo_min": 35,
        "resumo": "Jantar leve de noite fria, e rende panela.",
        "ingredientes": [
            {"food_id": "chicken-breast", "gramas": 150},
            {"food_id": "pumpkin", "gramas": 200},
            {"food_id": "carrot", "gramas": 100},
            {"food_id": "green-beans", "gramas": 80},
        ],
        "extras": ["Sal", "Alho", "Cebola", "Louro", "Cheiro-verde"],
        "preparo": [
            "Refogue alho e cebola, junte o frango em cubos e sele.",
            "Acrescente os legumes e água até cobrir; cozinhe 25 minutos.",
            "Amasse parte da abóbora no próprio caldo para engrossar sem farinha.",
        ],
        "por_que": "A abóbora engrossa o caldo sozinha — não precisa de farinha nem de "
                   "creme.",
        "tags": ["panela", "corte"],
    },
    {
        "id": "macarrao-com-carne",
        "nome": "Macarrão com carne moída",
        "classe": "almoco_jantar",
        "tempo_min": 25,
        "resumo": "Para dia de treino pesado, quando o carboidrato é alto.",
        "ingredientes": [
            {"food_id": "pasta", "gramas": 200},
            {"food_id": "beef-ground", "gramas": 140},
            {"food_id": "tomato", "gramas": 120},
        ],
        "extras": ["Sal", "Alho", "Cebola", "Manjericão", "Orégano"],
        "preparo": [
            "Faça o molho refogando a carne com alho, cebola e tomate até apurar.",
            "Cozinhe o macarrão al dente e misture ao molho ainda na panela.",
        ],
        "por_que": "Dia de perna e de carboidrato alto pede massa — não é escapada, é o "
                   "plano.",
        "tags": ["ganho", "classica"],
    },

    # ── Lanche da tarde ─────────────────────────────────────────────────────────────
    {
        "id": "shake-whey-aveia",
        "nome": "Shake de whey com aveia",
        "classe": "lanche",
        "tempo_min": 3,
        "resumo": "O lanche da tarde do método.",
        "ingredientes": [
            {"food_id": "whey-protein", "gramas": 30},
            {"food_id": "oats", "gramas": 40},
            {"food_id": "milk-skim", "gramas": 200},
            {"food_id": "banana", "gramas": 80},
        ],
        "extras": ["Canela", "Gelo"],
        "preparo": ["Bata tudo no liquidificador com gelo."],
        "por_que": "Aveia com whey segura até o jantar; a fruta tira a vontade de doce.",
        "tags": ["rapida"],
    },
    {
        "id": "vitamina-de-morango",
        "nome": "Vitamina de morango",
        "classe": "lanche",
        "tempo_min": 3,
        "resumo": "Volume alto, caloria baixa — para quem está cortando.",
        "ingredientes": [
            {"food_id": "whey-protein", "gramas": 30},
            {"food_id": "strawberry", "gramas": 200},
            {"food_id": "milk-skim", "gramas": 200},
        ],
        "extras": ["Gelo", "Adoçante"],
        "preparo": ["Bata tudo com bastante gelo — quanto mais gelado, mais encorpa."],
        "por_que": "200 g de morango enchem o copo por pouquíssima caloria: é saciedade "
                   "quase de graça.",
        "tags": ["rapida", "corte"],
    },
    {
        "id": "iogurte-com-granola",
        "nome": "Iogurte grego com granola e mamão",
        "classe": "lanche",
        "tempo_min": 2,
        "resumo": "Sem liquidificador e sem louça.",
        "ingredientes": [
            {"food_id": "yogurt-greek", "gramas": 170},
            {"food_id": "granola", "gramas": 30},
            {"food_id": "papaya", "gramas": 120},
        ],
        "extras": ["Canela"],
        "preparo": ["Monte em camadas no pote: iogurte, mamão, granola por cima na hora."],
        "por_que": "A granola entra em 30 g de propósito — ela é o item mais calórico do "
                   "pote e some rápido se for no olho.",
        "tags": ["sem_fogao", "rapida"],
    },
    {
        "id": "ovos-cozidos-com-fruta",
        "nome": "Ovos cozidos com fruta",
        "classe": "lanche",
        "tempo_min": 12,
        "resumo": "Quando o whey acabou.",
        "ingredientes": [
            {"food_id": "eggs-whole", "gramas": 100},
            {"food_id": "egg-whites", "gramas": 100},
            {"food_id": "apple", "gramas": 150},
        ],
        "extras": ["Sal", "Pimenta-do-reino"],
        "preparo": [
            "Ovos na água fervente por 9 minutos e depois direto na água gelada — "
            "descascam sozinhos.",
            "Coma com a maçã.",
        ],
        "por_que": "Ovo é a proteína mais barata do catálogo, e o método aceita ovo no "
                   "lanche.",
        "tags": ["barata"],
    },

    # ── Sobremesa e refeição livre ──────────────────────────────────────────────────
    {
        "id": "mousse-de-morango",
        "nome": "Mousse de morango",
        "classe": "sobremesa",
        "refeicao_livre": True,
        "tempo_min": 5,
        "resumo": "Sobremesa de verdade, feita com o que já está no seu plano.",
        "ingredientes": [
            {"food_id": "yogurt-greek", "gramas": 150},
            {"food_id": "whey-protein", "gramas": 20},
            {"food_id": "strawberry", "gramas": 150},
        ],
        "extras": ["Adoçante", "Gelo"],
        "preparo": [
            "Bata o morango com o iogurte e o whey até ficar aerado.",
            "Leve ao congelador por 30 minutos antes de servir.",
        ],
        "por_que": "Mata a vontade de doce sem nada fora do plano — os três ingredientes "
                   "já estão no seu banco de alimentos.",
        "tags": ["doce", "sem_fogao"],
    },
    {
        "id": "sorvete-de-banana",
        "nome": "Sorvete de banana com pasta de amendoim",
        "classe": "sobremesa",
        "refeicao_livre": True,
        "tempo_min": 5,
        "resumo": "Dois ingredientes. Parece sorvete de máquina.",
        "ingredientes": [
            {"food_id": "banana", "gramas": 200},
            {"food_id": "peanut-butter", "gramas": 15},
        ],
        "extras": ["Canela"],
        "preparo": [
            "Congele a banana em rodelas por pelo menos 4 horas.",
            "Bata no processador — ela vira creme sozinha, sem leite e sem açúcar.",
            "Misture a pasta de amendoim no fim.",
        ],
        "por_que": "A banana congelada faz a textura de sorvete sem nenhum ingrediente a "
                   "mais. É o doce mais barato que existe.",
        "tags": ["doce", "barata", "sem_fogao"],
    },
    {
        "id": "bolinha-energetica",
        "nome": "Bolinhas de aveia com pasta de amendoim",
        "classe": "sobremesa",
        "refeicao_livre": True,
        "tempo_min": 10,
        "rendimento": 4,
        "resumo": "Faz uma vez, come a semana. Guarde na geladeira.",
        "ingredientes": [
            {"food_id": "oats", "gramas": 80},
            {"food_id": "peanut-butter", "gramas": 30},
            {"food_id": "whey-protein", "gramas": 30},
            {"food_id": "banana", "gramas": 100},
        ],
        "extras": ["Canela", "Adoçante"],
        "preparo": [
            "Amasse a banana e misture tudo até dar liga.",
            "Enrole bolinhas e leve à geladeira por 1 hora para firmarem.",
        ],
        "por_que": "É o doce que cabe na bolsa. Divida em porções ANTES de guardar — "
                   "comer do pote é como a receita sai do plano.",
        "tags": ["doce", "marmita"],
    },
    {
        "id": "maca-assada",
        "nome": "Maçã assada com canela",
        "classe": "sobremesa",
        "refeicao_livre": True,
        "tempo_min": 20,
        "resumo": "Sobremesa quente por menos de 150 kcal.",
        "ingredientes": [
            {"food_id": "apple", "gramas": 180},
            {"food_id": "peanut-butter", "gramas": 10},
        ],
        "extras": ["Canela em pau", "Adoçante", "Cravo"],
        "preparo": [
            "Tire o miolo da maçã sem furar o fundo.",
            "Recheie com a pasta de amendoim e a canela.",
            "Forno a 180 °C por 20 minutos, até a maçã ceder ao garfo.",
        ],
        "por_que": "A canela e o forno fazem o doce aparecer sem açúcar nenhum.",
        "tags": ["doce", "forno", "corte"],
    },
    {
        "id": "creme-de-mamao",
        "nome": "Creme de mamão com whey",
        "classe": "sobremesa",
        "refeicao_livre": True,
        "tempo_min": 3,
        "resumo": "Três minutos, uma fruta e um scoop.",
        "ingredientes": [
            {"food_id": "papaya", "gramas": 250},
            {"food_id": "whey-protein", "gramas": 25},
        ],
        "extras": ["Gelo", "Raspas de limão"],
        "preparo": ["Bata o mamão gelado com o whey e gelo até virar creme."],
        "por_que": "Sobremesa que é quase só fruta — cabe até em dia de corte agressivo.",
        "tags": ["doce", "rapida", "corte"],
    },
]


# ── Contas ───────────────────────────────────────────────────────────────────────────

def macros_da_receita(receita: Dict[str, Any]) -> Dict[str, float]:
    """Os macros da receita, CALCULADOS do catálogo.

    Nunca digitados. Uma receita que anuncia 260 kcal e entrega 400 destrói a confiança no
    plano inteiro, e e o defeito mais comum em livro de receita fitness.

    E sempre por PORCAO, e nao da panela. As bolinhas de aveia somam 681 kcal de massa e
    rendem quatro — mostrar 681 ao lado de uma sobremesa faria a pessoa achar que ela nao
    cabe no dia, ou pior, comer as quatro achando que era uma.
    """
    total = {"kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for item in receita.get("ingredientes", []):
        alimento = FOOD_INDEX.get(item["food_id"])
        if not alimento:
            continue
        fator = float(item["gramas"]) / max(1.0, float(alimento.get("grams") or 100))
        total["kcal"] += float(alimento.get("kcal") or 0) * fator
        total["protein_g"] += float(alimento.get("protein_g") or 0) * fator
        total["carbs_g"] += float(alimento.get("carbs_g") or 0) * fator
        total["fat_g"] += float(alimento.get("fat_g") or 0) * fator
    porcoes = max(1, int(receita.get("rendimento") or 1))
    return {k: round(v / porcoes) for k, v in total.items()}


def _ingredientes_legiveis(receita: Dict[str, Any]) -> List[Dict[str, Any]]:
    saida = []
    for item in receita.get("ingredientes", []):
        alimento = FOOD_INDEX.get(item["food_id"]) or {}
        saida.append({
            "food_id": item["food_id"],
            "nome": alimento.get("name", item["food_id"]),
            "gramas": item["gramas"],
        })
    return saida


def receita_completa(receita: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": receita["id"],
        "nome": receita["nome"],
        "classe": receita["classe"],
        "classe_rotulo": ROTULO_DA_CLASSE.get(receita["classe"], receita["classe"]),
        "resumo": receita.get("resumo", ""),
        "tempo_min": receita.get("tempo_min"),
        # Quantas porcoes a receita rende. A grama de cada ingrediente e a da RECEITA
        # INTEIRA, porque e assim que se cozinha — ninguem pesa um quarto de banana. Quem
        # divide e o rendimento, na hora de comer.
        "rendimento": int(receita.get("rendimento") or 1),
        "refeicao_livre": bool(receita.get("refeicao_livre")),
        "ingredientes": _ingredientes_legiveis(receita),
        "extras": receita.get("extras", []),
        "preparo": receita.get("preparo", []),
        "por_que": receita.get("por_que", ""),
        "tags": receita.get("tags", []),
        **macros_da_receita(receita),
    }


def listar(classe: Optional[str] = None,
           apenas_livres: bool = False) -> List[Dict[str, Any]]:
    """As receitas, opcionalmente de uma classe só."""
    saida = []
    for r in RECEITAS:
        if classe and r["classe"] != classe:
            continue
        if apenas_livres and not r.get("refeicao_livre"):
            continue
        saida.append(receita_completa(r))
    return saida


def por_id(receita_id: str) -> Optional[Dict[str, Any]]:
    r = next((x for x in RECEITAS if x["id"] == receita_id), None)
    return receita_completa(r) if r else None


def classes_com_contagem() -> List[Dict[str, Any]]:
    """As abas da tela, já sem as vazias."""
    saida = []
    for chave, rotulo, _tipo in CLASSES:
        quantas = sum(1 for r in RECEITAS if r["classe"] == chave)
        if quantas:
            saida.append({"chave": chave, "rotulo": rotulo, "quantas": quantas})
    return saida


def cabe_na_refeicao(receita_id: str, alvo_kcal: float) -> Optional[Dict[str, Any]]:
    """Esta receita cabe numa refeição com este alvo?

    É a pergunta que só o FORGE consegue responder, e a razão de as receitas viverem
    ligadas ao catálogo em vez de serem texto. A margem é a mesma do resto do produto —
    `tolerancia_de_caloria`, 5% com piso de 150 kcal —, então a resposta aqui nunca
    discorda da resposta que a tela do plano dá.

    So o EXCESSO reprova. Ficar abaixo do alvo nunca foi problema: uma sobremesa de 150 kcal
    cabe num lanche de 350 e ainda sobra espaco — dizer "nao cabe" ali seria transformar uma
    boa noticia em bloqueio. O que a tela precisa saber e quanto sobra, ou quanto passou.
    """
    r = por_id(receita_id)
    if not r:
        return None
    alvo = float(alvo_kcal or 0)
    margem = tolerancia_de_caloria(alvo)
    diferenca = r["kcal"] - alvo
    return {
        "receita": r["id"],
        "kcal": r["kcal"],
        "alvo": round(alvo),
        "diferenca": round(diferenca),
        "margem": round(margem),
        "cabe": diferenca <= margem,
        # Quanto ainda cabe depois dela, para a pessoa saber se precisa completar a
        # refeicao com mais alguma coisa.
        "sobra": round(max(0.0, alvo - r["kcal"])),
        "excedeu": round(max(0.0, diferenca - margem)),
    }
