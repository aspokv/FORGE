# -*- coding: utf-8 -*-
"""Ampliacao do catalogo de alimentos do diario.

Por que este arquivo existe: a busca do diario ja soma catalogo local e Open Food Facts, mas
o catalogo local tinha 107 itens. Quando o provedor mundial nao devolve nada — e para termo
em portugues isso acontece direto, "albumina" e o caso que o atleta reclamou — a pessoa fica
sem resultado e desiste de registrar. Alimento que nao entra no diario nao existe para o
motor, entao um catalogo curto e um buraco de dados, nao so um incomodo.

Nada aqui SUBSTITUI o que ja existia: todos os ids sao novos e prefixados, porque
`food_snapshot` resolve cada registro salvo pelo id. Renomear ou remover um id quebraria o
historico de quem ja registrou aquele alimento.

Valores por 100 g da parte comestivel, na faixa da TBCA/TACO, salvo onde a linha diz outra
porcao — suplemento e medido pela dose do rotulo, que e como a pessoa consome. Marca varia
por sabor e lote, entao o rotulo continua sendo a referencia final.
"""

# (id, nome, kcal, proteina_g, carboidrato_g, gordura_g, [apelidos])
# Os apelidos sao o que a pessoa realmente digita: sem acento, no diminutivo, no nome
# regional. "aipim", "macaxeira" e "mandioca" sao a mesma raiz em tres estados.

FRUTAS = [
    ("diary-fruit-banana-prata", "Banana prata", 98, 1.3, 26.0, 0.1, ["banana", "banana prata"]),
    ("diary-fruit-banana-nanica", "Banana nanica", 92, 1.4, 23.8, 0.1, ["banana nanica", "banana caturra"]),
    ("diary-fruit-banana-terra", "Banana-da-terra cozida", 128, 1.0, 33.0, 0.2, ["banana da terra", "banana cozida"]),
    ("diary-fruit-apple", "Maçã com casca", 56, 0.3, 15.2, 0.4, ["maca", "maçã", "maca com casca"]),
    ("diary-fruit-orange", "Laranja pera", 45, 1.0, 11.5, 0.1, ["laranja", "laranja pera"]),
    ("diary-fruit-tangerine", "Tangerina", 38, 0.8, 9.6, 0.1, ["mexerica", "bergamota", "poncã", "tangerina"]),
    ("diary-fruit-papaya", "Mamão formosa", 45, 0.8, 11.6, 0.1, ["mamao", "mamão", "papaia"]),
    ("diary-fruit-melon", "Melão", 29, 0.7, 7.5, 0.0, ["melao", "melão"]),
    ("diary-fruit-pineapple", "Abacaxi", 48, 0.9, 12.3, 0.1, ["abacaxi", "anana"]),
    ("diary-fruit-grape", "Uva itália", 53, 0.7, 13.6, 0.2, ["uva"]),
    ("diary-fruit-raisin", "Uva passa", 299, 3.1, 79.2, 0.5, ["passas", "uva passa"]),
    ("diary-fruit-kiwi", "Kiwi", 51, 1.3, 11.5, 0.6, ["kiwi"]),
    ("diary-fruit-pear", "Pera", 53, 0.6, 14.0, 0.1, ["pera"]),
    ("diary-fruit-guava", "Goiaba vermelha", 54, 1.1, 13.0, 0.4, ["goiaba"]),
    ("diary-fruit-persimmon", "Caqui", 71, 0.4, 19.3, 0.1, ["caqui"]),
    ("diary-fruit-plum", "Ameixa fresca", 53, 0.8, 13.9, 0.0, ["ameixa"]),
    ("diary-fruit-prune", "Ameixa seca", 240, 2.2, 63.9, 0.4, ["ameixa preta", "ameixa seca"]),
    ("diary-fruit-peach", "Pêssego", 36, 0.8, 9.3, 0.1, ["pessego", "pêssego"]),
    ("diary-fruit-nectarine", "Nectarina", 44, 1.1, 10.6, 0.3, ["nectarina"]),
    ("diary-fruit-passion", "Maracujá", 68, 2.0, 12.3, 2.1, ["maracuja", "maracujá"]),
    ("diary-fruit-lemon", "Limão", 32, 0.9, 11.1, 0.1, ["limao", "limão"]),
    ("diary-fruit-fig", "Figo", 41, 1.0, 10.2, 0.2, ["figo"]),
    ("diary-fruit-acerola", "Acerola", 33, 0.9, 8.0, 0.2, ["acerola"]),
    ("diary-fruit-jabuticaba", "Jabuticaba", 58, 0.6, 15.3, 0.1, ["jabuticaba"]),
    ("diary-fruit-blackberry", "Amora", 43, 1.4, 9.6, 0.5, ["amora"]),
    ("diary-fruit-blueberry", "Mirtilo", 57, 0.7, 14.5, 0.3, ["blueberry", "mirtilo"]),
    ("diary-fruit-raspberry", "Framboesa", 52, 1.2, 11.9, 0.7, ["framboesa"]),
    ("diary-fruit-starfruit", "Carambola", 31, 1.0, 6.7, 0.3, ["carambola"]),
    ("diary-fruit-soursop", "Graviola", 62, 0.8, 15.8, 0.2, ["graviola"]),
    ("diary-fruit-dragonfruit", "Pitaya", 50, 1.1, 11.0, 0.4, ["pitaya", "pitaia"]),
    ("diary-fruit-pomegranate", "Romã", 83, 1.7, 18.7, 1.2, ["roma", "romã"]),
    ("diary-fruit-cashew-fruit", "Caju (fruta)", 43, 1.0, 10.3, 0.3, ["caju", "fruta do caju"]),
    ("diary-fruit-cupuacu", "Cupuaçu (polpa)", 49, 1.0, 11.0, 0.6, ["cupuacu", "cupuaçu"]),
    ("diary-fruit-acai-pulp", "Açaí polpa pura, sem açúcar", 58, 0.8, 6.2, 3.9, ["acai puro", "polpa de acai"]),
    ("diary-fruit-coconut-fresh", "Coco fresco", 406, 3.7, 10.4, 42.0, ["coco", "coco ralado fresco"]),
    ("diary-fruit-date", "Tâmara seca", 282, 2.5, 75.0, 0.4, ["tamara", "tâmara"]),
]

VERDURAS_E_LEGUMES = [
    ("diary-veg-arugula", "Rúcula", 25, 2.6, 3.7, 0.7, ["rucula", "rúcula"]),
    ("diary-veg-watercress", "Agrião", 23, 2.3, 2.3, 0.2, ["agriao", "agrião"]),
    ("diary-veg-kale", "Couve manteiga crua", 27, 2.9, 4.3, 0.5, ["couve", "couve manteiga"]),
    ("diary-veg-kale-saute", "Couve refogada", 90, 2.7, 8.7, 5.5, ["couve refogada"]),
    ("diary-veg-spinach", "Espinafre cozido", 23, 2.7, 3.6, 0.3, ["espinafre"]),
    ("diary-veg-cauliflower", "Couve-flor cozida", 19, 1.2, 3.9, 0.2, ["couve flor"]),
    ("diary-veg-cabbage", "Repolho cru", 25, 1.3, 5.8, 0.1, ["repolho"]),
    ("diary-veg-beet", "Beterraba crua", 49, 1.9, 11.1, 0.1, ["beterraba"]),
    ("diary-veg-chayote", "Chuchu cozido", 17, 0.4, 4.1, 0.1, ["chuchu"]),
    ("diary-veg-okra", "Quiabo cozido", 30, 1.9, 6.4, 0.3, ["quiabo"]),
    ("diary-veg-cucumber", "Pepino", 10, 0.9, 2.0, 0.0, ["pepino"]),
    ("diary-veg-bellpepper", "Pimentão", 21, 1.1, 4.9, 0.2, ["pimentao", "pimentão"]),
    ("diary-veg-onion", "Cebola", 39, 1.7, 8.9, 0.1, ["cebola"]),
    ("diary-veg-garlic", "Alho", 113, 7.0, 23.9, 0.2, ["alho"]),
    ("diary-veg-corn", "Milho verde cozido", 98, 3.2, 20.0, 1.0, ["milho", "milho verde"]),
    ("diary-veg-peas", "Ervilha cozida", 88, 6.2, 14.8, 0.4, ["ervilha"]),
    ("diary-veg-palmheart", "Palmito em conserva", 24, 2.1, 4.4, 0.2, ["palmito"]),
    ("diary-veg-mushroom", "Champignon", 22, 3.1, 3.3, 0.3, ["champignon", "cogumelo"]),
    ("diary-veg-asparagus", "Aspargo cozido", 20, 2.2, 3.9, 0.1, ["aspargo"]),
    ("diary-veg-cassava-leaf", "Maxixe cozido", 16, 1.0, 3.5, 0.1, ["maxixe"]),
]

CARBOIDRATOS = [
    ("diary-carb-beans-white", "Feijão branco cozido", 91, 6.5, 16.0, 0.6, ["feijao branco"]),
    ("diary-carb-sweetpotato", "Batata-doce cozida", 77, 0.6, 18.4, 0.1, ["batata doce"]),
    ("diary-carb-yam", "Inhame cozido", 97, 2.1, 23.2, 0.1, ["inhame"]),
    ("diary-carb-taro", "Cará cozido", 100, 2.0, 23.9, 0.2, ["cara", "cará"]),
    ("diary-carb-tapioca", "Tapioca (goma hidratada)", 236, 0.0, 58.5, 0.0, ["tapioca", "goma de tapioca"]),
    ("diary-carb-couscous", "Cuscuz de milho cozido", 113, 2.4, 25.3, 0.6, ["cuscuz", "cuscuz nordestino"]),
    ("diary-carb-bread-whole", "Pão de forma integral", 253, 9.4, 49.9, 3.8, ["pao integral", "pão integral"]),
    ("diary-carb-bread-white", "Pão de forma branco", 265, 9.0, 49.0, 3.5, ["pao de forma", "pao branco"]),
    ("diary-carb-quinoa", "Quinoa cozida", 120, 4.4, 21.3, 1.9, ["quinoa"]),
    ("diary-carb-granola", "Granola", 471, 10.0, 62.0, 20.0, ["granola"]),
    ("diary-carb-polenta", "Polenta cozida", 103, 2.0, 22.0, 1.0, ["polenta", "angu"]),
    ("diary-carb-popcorn", "Pipoca sem óleo", 387, 12.0, 78.0, 4.5, ["pipoca"]),
    ("diary-carb-cornflakes", "Cereal matinal de milho", 375, 7.0, 84.0, 0.9, ["sucrilhos", "cereal matinal"]),
    ("diary-carb-rice-cake", "Biscoito de arroz", 387, 8.0, 81.0, 3.0, ["biscoito de arroz", "galete"]),
    ("diary-carb-manioc-flour", "Farinha de mandioca", 361, 1.6, 87.9, 0.3, ["farinha", "farinha de mandioca"]),
]

PROTEINAS = [
    ("diary-prot-egg-boiled", "Ovo de galinha cozido", 146, 13.3, 0.6, 9.5, ["ovo", "ovo cozido"]),
    ("diary-prot-egg-white", "Clara de ovo cozida", 52, 11.0, 0.7, 0.0, ["clara", "clara de ovo"]),
    ("diary-prot-egg-yolk", "Gema de ovo", 353, 15.9, 1.6, 30.9, ["gema"]),
    ("diary-prot-quail-egg", "Ovo de codorna", 158, 13.1, 0.4, 11.1, ["ovo de codorna", "codorna"]),
    ("diary-prot-tilapia", "Tilápia grelhada", 128, 26.2, 0.0, 1.7, ["tilapia", "tilápia", "peixe"]),
    ("diary-prot-tuna-water", "Atum em água, drenado", 116, 25.5, 0.0, 1.0, ["atum", "atum em agua"]),
    ("diary-prot-sardine", "Sardinha em óleo, drenada", 208, 24.6, 0.0, 11.5, ["sardinha"]),
    ("diary-prot-hake", "Merluza cozida", 122, 26.6, 0.0, 1.0, ["merluza", "pescada"]),
    ("diary-prot-shrimp", "Camarão cozido", 99, 24.0, 0.2, 0.3, ["camarao", "camarão"]),
    ("diary-prot-beef-patinho", "Patinho bovino grelhado", 219, 35.9, 0.0, 7.3, ["patinho"]),
    ("diary-prot-beef-ground-lean", "Carne moída magra refogada", 190, 30.0, 0.0, 7.0, ["carne moida", "carne moída"]),
    ("diary-prot-beef-alcatra", "Alcatra grelhada", 241, 32.0, 0.0, 11.8, ["alcatra"]),
    ("diary-prot-beef-coxao", "Coxão mole cozido", 219, 31.9, 0.0, 9.2, ["coxao mole", "coxão mole"]),
    ("diary-prot-beef-filet", "Filé mignon grelhado", 220, 32.8, 0.0, 8.8, ["file mignon", "filé mignon"]),
    ("diary-prot-beef-picanha", "Picanha assada", 267, 26.4, 0.0, 17.4, ["picanha"]),
    ("diary-prot-pork-loin", "Lombo suíno assado", 210, 35.7, 0.0, 6.4, ["lombo", "lombo suino"]),
    ("diary-prot-turkey-breast", "Peito de peru defumado", 95, 17.0, 2.0, 2.0, ["peito de peru", "peru"]),
    ("diary-prot-ham-lean", "Presunto magro", 110, 18.0, 1.5, 3.5, ["presunto"]),
    ("diary-prot-chicken-thigh", "Coxa de frango assada sem pele", 187, 27.5, 0.0, 7.8, ["coxa de frango", "coxa"]),
    ("diary-prot-chicken-drum", "Sobrecoxa assada sem pele", 215, 26.0, 0.0, 11.7, ["sobrecoxa"]),
    ("diary-prot-chicken-wing", "Asa de frango assada", 240, 27.0, 0.0, 14.0, ["asa de frango", "asinha"]),
    ("diary-prot-beef-liver", "Fígado bovino grelhado", 225, 29.0, 3.9, 9.0, ["figado", "fígado"]),
    ("diary-prot-tofu", "Tofu", 76, 8.1, 1.9, 4.8, ["tofu", "queijo de soja"]),
    ("diary-prot-soy-textured", "Proteína de soja texturizada seca", 336, 50.0, 30.0, 1.0, ["pts", "carne de soja", "proteina de soja"]),
    ("diary-prot-cod", "Bacalhau dessalgado cozido", 135, 29.0, 0.0, 1.5, ["bacalhau"]),
]

LATICINIOS = [
    ("diary-dairy-milk-powder", "Leite em pó integral", 497, 26.0, 38.0, 27.0, ["leite em po", "leite ninho"]),
    ("diary-dairy-yogurt-natural", "Iogurte natural integral", 61, 3.5, 4.7, 3.3, ["iogurte", "iogurte natural"]),
    ("diary-dairy-yogurt-skim", "Iogurte natural desnatado", 41, 4.1, 5.0, 0.2, ["iogurte desnatado"]),
    ("diary-dairy-cheese-minas", "Queijo minas frescal", 264, 17.4, 3.2, 20.2, ["queijo minas", "minas frescal"]),
    ("diary-dairy-cheese-mozzarella", "Queijo mussarela", 330, 25.0, 3.0, 25.0, ["mussarela", "muçarela", "queijo"]),
    ("diary-dairy-cheese-prato", "Queijo prato", 360, 25.0, 2.0, 28.0, ["queijo prato"]),
    ("diary-dairy-cheese-parmesan", "Queijo parmesão", 453, 35.6, 1.7, 33.5, ["parmesao", "parmesão"]),
    ("diary-dairy-ricotta", "Ricota", 140, 11.0, 3.0, 9.0, ["ricota"]),
    ("diary-dairy-requeijao", "Requeijão cremoso", 257, 9.0, 3.0, 23.0, ["requeijao", "requeijão"]),
    ("diary-dairy-cream", "Creme de leite", 195, 2.5, 4.0, 19.0, ["creme de leite", "nata"]),
    ("diary-dairy-butter", "Manteiga", 717, 0.9, 0.1, 81.1, ["manteiga"]),
]

GORDURAS_E_OLEAGINOSAS = [
    ("diary-fat-coconut-oil", "Óleo de coco", 862, 0.0, 0.0, 100.0, ["oleo de coco", "óleo de coco"]),
    ("diary-fat-soy-oil", "Óleo de soja", 884, 0.0, 0.0, 100.0, ["oleo", "óleo de soja"]),
    ("diary-nut-brazil", "Castanha-do-pará", 699, 14.5, 15.1, 63.5, ["castanha do para", "castanha do pará"]),
    ("diary-nut-cashew", "Castanha de caju", 570, 18.5, 29.1, 43.8, ["castanha de caju", "caju torrado"]),
    ("diary-nut-almond", "Amêndoa", 640, 21.6, 19.5, 47.3, ["amendoa", "amêndoa"]),
    ("diary-nut-walnut", "Nozes", 620, 14.0, 18.4, 59.4, ["noz", "nozes"]),
    ("diary-nut-pistachio", "Pistache", 560, 20.0, 28.0, 45.0, ["pistache"]),
    ("diary-nut-macadamia", "Macadâmia", 718, 7.9, 13.8, 75.8, ["macadamia", "macadâmia"]),
    ("diary-nut-peanut-butter", "Pasta de amendoim integral", 588, 25.0, 20.0, 50.0, ["pasta de amendoim", "peanut butter"]),
    ("diary-seed-chia", "Chia", 486, 16.5, 42.1, 30.7, ["chia"]),
    ("diary-seed-flax", "Linhaça", 495, 14.1, 43.3, 32.3, ["linhaca", "linhaça"]),
    ("diary-seed-sesame", "Gergelim", 573, 17.7, 23.5, 49.7, ["gergelim"]),
    ("diary-seed-sunflower", "Semente de girassol", 584, 20.8, 20.0, 51.5, ["girassol", "semente de girassol"]),
]

BEBIDAS = [
    ("diary-drink-coconut-water", "Água de coco", 22, 0.0, 5.3, 0.0, ["agua de coco", "água de coco"]),
    ("diary-drink-coffee", "Café coado sem açúcar", 4, 0.2, 0.7, 0.0, ["cafe", "café"]),
    ("diary-drink-tea", "Chá sem açúcar", 1, 0.0, 0.2, 0.0, ["cha", "chá"]),
    ("diary-drink-grape-juice", "Suco de uva integral", 60, 0.4, 14.8, 0.1, ["suco de uva"]),
    ("diary-drink-isotonic", "Isotônico", 26, 0.0, 6.4, 0.0, ["isotonico", "gatorade"]),
    ("diary-drink-energy", "Energético", 45, 0.0, 11.0, 0.0, ["energetico", "energético"]),
    ("diary-drink-soda-zero", "Refrigerante zero", 0, 0.0, 0.0, 0.0, ["refrigerante zero", "refri zero"]),
    ("diary-drink-almond-milk", "Bebida de amêndoas sem açúcar", 17, 0.6, 0.6, 1.2, ["leite de amendoas", "leite vegetal"]),
    ("diary-drink-oat-milk", "Bebida de aveia", 45, 0.8, 7.0, 1.5, ["leite de aveia"]),
    ("diary-drink-soy-milk", "Bebida de soja", 41, 3.3, 2.4, 1.8, ["leite de soja"]),
    ("diary-drink-coconut-milk", "Leite de coco", 166, 1.6, 2.8, 16.9, ["leite de coco"]),
    ("diary-drink-wine-red", "Vinho tinto", 83, 0.1, 2.6, 0.0, ["vinho", "vinho tinto"]),
    ("diary-drink-cachaca", "Cachaça", 231, 0.0, 0.0, 0.0, ["cachaca", "cachaça", "pinga"]),
]

PRATOS = [
    ("diary-dish-feijoada", "Feijoada", 116, 8.0, 8.0, 5.5, ["feijoada"]),
    ("diary-dish-stroganoff", "Strogonoff de frango", 154, 11.0, 5.0, 10.0, ["strogonoff", "estrogonofe"]),
    ("diary-dish-lasagna", "Lasanha à bolonhesa", 172, 9.0, 17.0, 7.5, ["lasanha"]),
    ("diary-dish-coxinha", "Coxinha de frango", 300, 8.0, 30.0, 16.0, ["coxinha"]),
    ("diary-dish-pastel", "Pastel de carne frito", 320, 8.5, 30.0, 19.0, ["pastel"]),
    ("diary-dish-esfiha", "Esfiha de carne", 250, 9.0, 30.0, 10.0, ["esfiha", "esfirra"]),
    ("diary-dish-tapioca-cheese", "Tapioca com queijo", 250, 6.0, 40.0, 7.0, ["tapioca recheada"]),
    ("diary-dish-misto-quente", "Misto quente", 290, 13.0, 28.0, 14.0, ["misto quente", "sanduiche de queijo"]),
    ("diary-dish-sandwich-natural", "Sanduíche natural", 200, 10.0, 25.0, 6.0, ["sanduiche natural", "sanduíche natural"]),
    ("diary-dish-escondidinho", "Escondidinho de carne", 150, 9.0, 14.0, 6.0, ["escondidinho"]),
    ("diary-dish-baiao", "Baião de dois", 140, 6.0, 20.0, 4.0, ["baiao de dois", "baião de dois"]),
    ("diary-dish-moqueca", "Moqueca de peixe", 110, 12.0, 3.0, 5.5, ["moqueca"]),
    ("diary-dish-salpicao", "Salpicão de frango", 180, 8.0, 10.0, 12.0, ["salpicao", "salpicão"]),
    ("diary-dish-yakisoba", "Yakisoba", 130, 7.0, 17.0, 4.0, ["yakisoba"]),
    ("diary-dish-parmegiana", "Frango à parmegiana", 220, 17.0, 14.0, 11.0, ["parmegiana", "frango parmegiana"]),
    ("diary-dish-omelette", "Omelete de queijo", 180, 13.0, 2.0, 14.0, ["omelete", "omelette"]),
    ("diary-dish-crepioca", "Crepioca de queijo", 160, 11.0, 14.0, 6.0, ["crepioca"]),
    ("diary-dish-soup-veg", "Sopa de legumes", 45, 2.0, 7.0, 1.0, ["sopa", "sopa de legumes"]),
    ("diary-dish-canja", "Canja de galinha", 70, 6.0, 7.0, 2.0, ["canja"]),
    ("diary-dish-steak-onion", "Bife acebolado", 230, 25.0, 3.0, 13.0, ["bife acebolado"]),
    ("diary-dish-risotto-chicken", "Risoto de frango", 150, 9.0, 18.0, 5.0, ["risoto"]),
    ("diary-dish-pancake-meat", "Panqueca de carne", 190, 10.0, 18.0, 8.0, ["panqueca"]),
    ("diary-dish-acai-bowl", "Açaí na tigela com banana e granola", 165, 2.2, 28.0, 5.5, ["acai na tigela", "tigela de acai"]),
    ("diary-dish-marmita-fit", "Marmita de frango, arroz e brócolis", 135, 12.0, 15.0, 2.5, ["marmita", "marmita fitness"]),
]

CONDIMENTOS_E_ACUCARES = [
    ("diary-cond-mayo", "Maionese", 680, 1.0, 1.0, 75.0, ["maionese"]),
    ("diary-cond-ketchup", "Ketchup", 110, 1.2, 26.0, 0.2, ["ketchup", "catchup"]),
    ("diary-cond-mustard", "Mostarda", 66, 4.0, 6.0, 3.0, ["mostarda"]),
    ("diary-cond-tomato-sauce", "Molho de tomate", 38, 1.5, 7.0, 0.4, ["molho de tomate", "molho"]),
    ("diary-cond-olive", "Azeitona", 135, 1.0, 3.8, 13.5, ["azeitona"]),
    ("diary-cond-sugar", "Açúcar refinado", 387, 0.0, 100.0, 0.0, ["acucar", "açúcar"]),
    ("diary-cond-honey", "Mel", 309, 0.3, 84.0, 0.0, ["mel"]),
    ("diary-cond-sweetener", "Adoçante", 0, 0.0, 0.0, 0.0, ["adocante", "adoçante"]),
    ("diary-cond-chocolate-70", "Chocolate 70% cacau", 540, 8.0, 34.0, 40.0, ["chocolate amargo", "chocolate 70"]),
    ("diary-cond-cocoa-powder", "Cacau em pó 100%", 355, 20.0, 35.0, 14.0, ["cacau", "cacau em po"]),
]

# ── Suplementos ──────────────────────────────────────────────────────────────────────
# Estes NAO sao por 100 g: a pessoa consome pela dose do rotulo, e registrar "100 g de
# creatina" nao existe na vida real. A coluna `grams` de cada linha diz a porcao.
# (id, nome, gramas_da_porcao, kcal, proteina, carboidrato, gordura, [apelidos], fonte)

SUPLEMENTOS = [
    ("diary-supp-albumina", "Albumina (clara de ovo desidratada)", 100, 375, 81.0, 7.0, 0.5,
     ["albumina", "clara desidratada", "clara em po", "albumina pura"],
     "Valor médio por 100 g de albumina em pó — confirme o rótulo da marca"),
    ("diary-supp-albumina-naturovos", "Albumina — Naturovos", 100, 376, 82.0, 6.5, 0.3,
     ["albumina naturovos", "naturovos"],
     "Valor típico de rótulo por 100 g — confirme a embalagem e o sabor"),
    ("diary-supp-albumina-netto", "Albumina — Netto Alimentos", 100, 373, 80.0, 7.5, 0.4,
     ["albumina netto", "netto albumina"],
     "Valor típico de rótulo por 100 g — confirme a embalagem e o sabor"),
    ("diary-supp-albumina-dux", "Albumina — DUX Nutrition", 100, 374, 81.0, 6.8, 0.4,
     ["albumina dux", "dux albumina"],
     "Valor típico de rótulo por 100 g — confirme a embalagem e o sabor"),
    ("diary-supp-albumina-growth", "Albumina — Growth Supplements", 100, 375, 81.5, 6.6, 0.3,
     ["albumina growth", "growth albumina"],
     "Valor típico de rótulo por 100 g — confirme a embalagem e o sabor"),
    ("diary-supp-whey-isolate", "Whey Protein Isolado", 30, 110, 27.0, 0.5, 0.3,
     ["whey isolado", "isolate", "wpi"],
     "Valor típico por porção de 30 g — confirme o rótulo"),
    ("diary-supp-whey-hydro", "Whey Protein Hidrolisado", 30, 112, 26.0, 1.0, 0.4,
     ["whey hidrolisado", "hidrolisado"],
     "Valor típico por porção de 30 g — confirme o rótulo"),
    ("diary-supp-casein", "Caseína micelar", 30, 110, 24.0, 3.0, 0.5,
     ["caseina", "caseína", "casein"],
     "Valor típico por porção de 30 g — confirme o rótulo"),
    ("diary-supp-creatine", "Creatina monoidratada", 3, 0, 0.0, 0.0, 0.0,
     ["creatina", "creatine", "mono"],
     "Porção de 3 g — não entra em caloria nem em macro"),
    ("diary-supp-bcaa", "BCAA em pó", 5, 20, 5.0, 0.0, 0.0,
     ["bcaa", "aminoacido"],
     "Porção de 5 g — confirme o rótulo"),
    ("diary-supp-glutamine", "Glutamina", 5, 20, 5.0, 0.0, 0.0,
     ["glutamina"],
     "Porção de 5 g — confirme o rótulo"),
    ("diary-supp-collagen", "Colágeno hidrolisado", 10, 36, 9.0, 0.0, 0.0,
     ["colageno", "colágeno"],
     "Porção de 10 g — confirme o rótulo"),
    ("diary-supp-hypercaloric", "Hipercalórico", 100, 380, 15.0, 75.0, 3.0,
     ["hipercalorico", "hipercalórico", "massa", "mass"],
     "Valor típico por 100 g — confirme o rótulo e a dose indicada"),
    ("diary-supp-maltodextrin", "Maltodextrina", 100, 380, 0.0, 95.0, 0.0,
     ["maltodextrina", "malto"],
     "Valor típico por 100 g"),
    ("diary-supp-dextrose", "Dextrose", 100, 400, 0.0, 100.0, 0.0,
     ["dextrose", "glicose"],
     "Valor típico por 100 g"),
    ("diary-supp-palatinose", "Palatinose", 100, 400, 0.0, 100.0, 0.0,
     ["palatinose", "isomaltulose"],
     "Valor típico por 100 g"),
    ("diary-supp-protein-bar", "Barra de proteína", 45, 170, 13.0, 17.0, 5.0,
     ["barra de proteina", "protein bar", "barrinha"],
     "Valor típico por barra de 45 g — confirme o rótulo"),
    ("diary-supp-egg-white-liquid", "Clara de ovo pasteurizada líquida", 100, 48, 10.5, 0.7, 0.2,
     ["clara liquida", "clara pasteurizada"],
     "Valor médio por 100 g — confirme o rótulo"),
    ("diary-supp-vegan-protein", "Proteína vegetal (ervilha e arroz)", 30, 115, 23.0, 2.5, 1.5,
     ["proteina vegana", "veg protein", "proteina de ervilha"],
     "Valor típico por porção de 30 g — confirme o rótulo"),
    ("diary-supp-pretreino", "Pré-treino em pó", 10, 20, 0.0, 4.0, 0.0,
     ["pre treino", "pré-treino", "pre workout"],
     "Porção de 10 g — confirme o rótulo"),
]

_POR_100G = [
    *FRUTAS, *VERDURAS_E_LEGUMES, *CARBOIDRATOS, *PROTEINAS,
    *LATICINIOS, *GORDURAS_E_OLEAGINOSAS, *BEBIDAS, *PRATOS, *CONDIMENTOS_E_ACUCARES,
]

_FONTE_PADRAO = "Valor médio por 100 g — confirme o rótulo quando houver"

ALIMENTOS_EXTRA = {
    fid: {"id": fid, "name": nome, "grams": 100, "kcal": kcal, "protein_g": proteina,
          "carbs_g": carbo, "fat_g": gordura, "aliases": apelidos, "source": _FONTE_PADRAO}
    for fid, nome, kcal, proteina, carbo, gordura, apelidos in _POR_100G
}

ALIMENTOS_EXTRA.update({
    fid: {"id": fid, "name": nome, "grams": gramas, "kcal": kcal, "protein_g": proteina,
          "carbs_g": carbo, "fat_g": gordura, "aliases": apelidos, "source": fonte}
    for fid, nome, gramas, kcal, proteina, carbo, gordura, apelidos, fonte in SUPLEMENTOS
})

# Apelidos que faltavam em alimentos que JA existiam no catalogo. Preenchidos aqui em vez de
# em `foods.json` porque aquele arquivo alimenta o gerador de plano, e apelido de busca nao
# tem por que atravessar o motor de nutricao.
APELIDOS_EXTRA = {
    "beans-carioca": ["feijao", "feijão"],
    "green-beans": ["feijao vagem"],
    "yogurt-greek": ["grego"],
}
