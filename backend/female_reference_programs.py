"""Training tables transcribed from three user-supplied PDFs, September 2026.

No PDF images, videos, biographies or author branding are redistributed.
Unspecified/contradictory fields are identified in visible notes, not silently repaired.
"""


def build_female_reference_programs(ex, session, phase, program):
    def e(id, sets, reps, rest="90 s", technique="straight", note=""):
        return ex(id, sets, reps, "2", rest, technique, note)

    common = "RIR 2 é um valor inicial de revisão FORGE: as fichas não informam RIR. Durações são estimativas, não tempos da ficha. Revise antes de salvar; não aplique automaticamente pela seleção de feminino."
    november = [
        session("A · Quadríceps e panturrilhas", ["Quadríceps", "Panturrilhas"], [
            e("leg-press",5,"12/10/8/6/15",technique="pyramid",note="Ficha: séries XXX; 5 entradas propostas para as 5 repetições listadas. Confirmar."),
            e("smith-squat",3,"10–12",note="Agachamento fixo: interpretado como Smith. Ficha 3–4 séries; começa em 3."),
            e("hack-squat",3,"8–10"),e("leg-extension",3,"8–10",technique="rest-pause"),
            e("lunge",3,"12–15",note="Passada alternada livre; ficha 3–4 séries."),
            e("seated-calf",3,"20–25",note="Ficha 3–4 séries."),e("leg-press-calf",3,"20–25",note="Ficha 3–4 séries."),
        ],"HIGH",70),
        session("B · Posteriores, adutores e abdômen", ["Posteriores","Adutores","Core"], [
            e("seated-hamstring-curl",5,"12/10/8/6/15",technique="pyramid",note="Ficha: séries XXX; 5 entradas propostas para as 5 repetições listadas. Confirmar."),
            e("lying-leg-curl",4,"10–12",note="Ficha 4–5 séries."),e("nordic-curl",4,"8–10",note="Tração de femorais russa; ficha 4–5 séries."),
            e("cable-hip-adduction",3,"10–12",note="Nonstop unilateral; ficha 3–4 séries. Alternar lados sem pausa entre eles."),
            e("scissor-adduction",3,"10–12"),e("adductor-machine",3,"8–10",note="Ficha 3–4 séries."),
            e("cable-crunch",3,"15–20",note="Abdominal carretilha; ficha 3–4 séries."),e("alternating-crunch",3,"15–20",note="Ficha 3–4 séries."),
        ],"HIGH",75),
        session("C · Tronco e panturrilhas", ["Costas","Peitoral","Braços","Panturrilhas"], [
            e("cable-row",4,"10–12",note="Ficha 4–5 séries."),e("cable-pulldown",4,"10–12",note="Puxador delta na ficha; usar a pegada indicada na revisão. Ficha 4–5 séries."),
            e("bb-curl",4,"10–12",note="Ficha 4–5 séries."),e("bb-upright-row",4,"10–12",note="Ficha 4–5 séries."),
            e("incline-smith",4,"10–12",note="Ficha 4–5 séries."),e("cable-fly",4,"10–12",note="Ficha 4–5 séries."),
            e("reverse-pushdown",4,"10–12",note="Ficha 4–5 séries."),e("seated-calf",3,"20–25"),e("leg-press-calf",3,"20–25"),
        ],"HIGH",85),
        session("D · Glúteos, ombros e abdômen", ["Glúteos","Deltoides","Core"], [
            e("smith-lunge",4,"8–10",note="Ficha 4–5 séries."),e("four-point-kickback",4,"8–10",note="Nonstop: alternar lados sem pausa entre eles; ficha 4–5 séries."),
            e("reverse-hyper",4,"8–10",note="Ficha 4–5 séries; versão adaptada."),e("abductor-machine",3,"10+10+10",technique="drop-set"),
            e("db-ohp",3,"10–12"),e("lateral-raise",3,"10–12"),e("cable-crunch",3,"15–20"),e("alternating-crunch",3,"15–20"),
        ],"HIGH",75),
    ]
    advanced = [
        session("Dia 1 · Pernas",["Quadríceps","Glúteos","Posteriores","Panturrilhas"],[
            e("hip-thrust",10,"10","10 s"),
            e("leg-extension",5,"15/12/12/12/falha técnica","60 s","superset","Parear com mesa flexora; intervalo após o par."),
            e("lying-leg-curl",5,"15/12/12/12/falha técnica","60 s","superset","Parear com cadeira extensora."),
            e("bb-squat",5,"15/12/10/10/8","60 s","pyramid"),e("smith-lunge",4,"12","60 s"),
            e("leg-press",4,"15/15/15/falha técnica","60 s",note="Pés abduzidos."),
            e("leg-press-calf",5,"15; última 10+10+10","60 s","drop-set","Ficha declara 5 séries, mas lista só 3x15 + drop. Revisar a série faltante."),
            e("standing-calf",5,"15; última 10+10+10","60 s","drop-set","Ficha declara 5 séries, mas lista só 3x15 + drop. Revisar a série faltante."),
        ],"HIGH",100),
        session("Dia 2 · Peito, ombro, braços e abdômen",["Peitoral","Deltoides","Braços"],[
            e("db-incline-fly",3,"15","60 s"),e("bb-incline-press",4,"12/12/10/10","60 s"),e("pushup",3,"15","60 s"),
            e("db-ohp",4,"12/10/10/8","60 s","pyramid"),e("db-lateral-raise",5,"12/12/12/12/8+8+8","60 s","drop-set"),
            e("db-front-raise",5,"12/12/12/12/8+8+8","60 s","drop-set","Pegada pronada."),
            e("machine-rear-fly",3,"15; última falha técnica","60 s",note="Ficha declara 3 séries e lista 3x15 + falha. Mantidas 3; confirmar se a falha é adicional."),
            e("rope-pushdown",5,"12/12/12/12/8+8+8","60 s","superset","Linha compartilhada com rosca de corda; drop final. Confirmar execução do par."),
            e("rope-curl",5,"12/12/12/12/8+8+8","60 s","superset","Linha compartilhada com tríceps corda; drop final."),
            e("db-overhead-extension",5,"12/12/12/12/8+8+8","60 s","drop-set","Sentado, bilateral. Cabeçalho inclui abdômen, mas não há exercício abdominal nesta página."),
        ],"HIGH",100),
        session("Dia 3 · Glúteos e panturrilhas",["Glúteos","Panturrilhas"],[
            e("hip-thrust",6,"15/15/12/12/10/10","60 s"),e("cable-glute-kickback",10,"10","10 s"),e("abductor-machine",10,"10","10 s"),
            e("smith-lunge",4,"12","60 s"),e("single-leg-press",4,"15/15/15/falha técnica","60 s"),
            e("leg-press-calf",5,"15/15/15/15/10+10+10","60 s","drop-set"),e("standing-calf",5,"15/15/15/15/10+10+10","60 s","drop-set"),
        ],"HIGH",100),
        session("Dia 4 · Costas, posterior de ombro e abdômen",["Costas","Deltoide posterior","Core"],[
            e("supinated-pulldown",5,"12/12/12/12/8+8+8","60 s","drop-set"),e("cable-straight-arm-pulldown",5,"12/12/12/12/falha técnica","60 s"),
            e("db-row",4,"12/12/12/falha técnica","60 s"),e("back-extension",4,"20","60 s"),
            e("db-ohp",4,"15; última falha técnica","60 s",note="Ficha declara 4 séries e lista 4x15 + falha; confirmar se é adicional."),
            e("machine-rear-fly",4,"15/15/15/8+8+8","60 s","drop-set"),e("jackknife",4,"30","60 s"),e("front-plank",4,"60 s","60 s"),
        ],"HIGH",85),
        session("Dia 5 · Posterior de coxa e panturrilha",["Posteriores","Panturrilhas"],[
            e("lying-leg-curl",5,"12/12/12/12/8+8+8","60 s","drop-set"),
            e("db-leg-curl",4,"15","60 s","superset","Linha compartilhada com stiff; confirmar execução do par."),e("rdl",4,"15","60 s","superset","Parear com flexor com halter."),
            e("sumo-db-deadlift",4,"15/12/10/10","60 s"),e("single-leg-press",4,"12","60 s"),e("lunge",4,"40 passos","60 s","straight","Passadas livres com halteres."),
            e("leg-press-calf",5,"15/15/15/15/8+8+8","60 s","drop-set"),e("standing-calf",5,"15/15/15/15/8+8+8","30 s","drop-set"),
        ],"HIGH",90),
        session("Dia 6 · Glúteo e abdômen",["Glúteos","Core"],[
            e("abductor-machine",5,"12/12/12/12/8+8+8","60 s","drop-set"),e("cable-glute-kickback",10,"10","60 s"),e("hip-thrust",4,"15","60 s"),
            e("floor-crunch",4,"30","60 s",note="No banco reto, com peso."),e("jackknife",4,"30","60 s"),e("front-plank",4,"60 s","30 s"),
        ],"HIGH",75),
    ]
    cavala = [
        session("Segunda · Quadríceps",["Quadríceps","Glúteos","Panturrilhas"],[
            e("leg-extension",8,"10",note="Ficha: 4 séries curtas e depois 4 séries completas; 8 séries no total."),
            e("smith-squat",4,"12/10/8/6",technique="pyramid",note="Progressão de carga."),e("leg-press",4,"10+10",note="10 completas, sustentar 10 s, mais 10 completas."),
            e("hack-squat",4,"10+10",note="Hack 10: 10 repetições com pausa de 2 s, depois 10 sem pausa."),e("single-leg-extension",4,"12"),
            e("lunge",4,"ida e volta",note="Afundo com carga; a ficha não especifica quantidade de passos."),e("abductor-machine",4,"15"),e("goblet-squat",4,"12"),e("standing-calf",3,"15"),
        ],"HIGH",95),
        session("Terça · Peito, ombro e tríceps",["Peitoral","Deltoides","Tríceps"],[
            e("db-fly",3,"12"),e("bb-bench-press",3,"12"),e("bar-pushdown",3,"12",note="Ficha indica carga alta."),e("reverse-pushdown",3,"12"),
            e("db-lateral-raise",3,"10",technique="superset",note="Bi-set com elevação frontal."),e("db-front-raise",3,"10",technique="superset",note="Bi-set com elevação lateral."),
            e("db-ohp",3,"12"),e("db-rear-fly",3,"12",note="Ficha não especifica equipamento; halteres selecionados para revisão."),e("floor-crunch",4,"25",note="Ficha apenas diz abdominal; variante selecionada para revisão."),
        ],"HIGH",75),
        session("Quarta · Glúteo e posterior",["Glúteos","Posteriores"],[
            e("abductor-machine",4,"20 curtas + 15 completas"),e("sumo-deadlift",4,"12"),e("hip-thrust",4,"12"),e("bulgarian-split-squat",4,"12+12",note="12 com carga + 12 sem carga."),
            e("lunge",4,"12",note="Afundo sobre dois steps."),e("cable-glute-kickback",3,"12+10",note="12 com perna reta + 10 flexionada. Séries ausentes na ficha: 3 propostas para revisão."),
            e("lying-leg-curl",4,"12"),e("db-stiff-bilateral",4,"12"),
        ],"HIGH",85),
        session("Quinta · Dorsal e bíceps",["Costas","Bíceps","Core"],[
            e("cable-pulldown",4,"12"),e("lat-prayer",4,"12",note="Puxada fechada com triângulo; revisar equipamento no catálogo."),e("row",4,"12",note="Remada baixa na máquina na ficha; ajustar máquina disponível."),
            e("cable-curl",4,"12",note="Barra reta no cross."),e("high-cable-curl",3,"12"),e("db-curl",3,"12"),e("floor-crunch",4,"25",note="Ficha apenas diz abdômen; variante selecionada para revisão."),
        ],"HIGH",75),
        session("Sexta · Legday",["Quadríceps","Posteriores","Glúteos"],[
            e("bb-squat",4,"12"),e("hack-squat",4,"12",note="Amplitude máxima controlada."),e("leg-extension",4,"10 isométricas + 10 completas",note="A ficha usa 'repetições isométricas' sem duração; confirmar protocolo."),
            e("leg-press",4,"10+10",note="Leg 20: 10 pés abduzidos + 10 pés paralelos."),
            e("conventional-deadlift",3,"12–15",technique="superset",note="Ficha 'agachamento terra + sumô curto'; confirmar variante antes de aplicar."),
            e("sumo-db-deadlift",3,"12–15",technique="superset",note="Sumô curto em par com agachamento terra; variante para revisão."),
            e("lunge",4,"12",note="Com halteres."),e("rdl",4,"10–12",technique="superset",note="Bi-set com stiff unilateral."),e("db-rdl",4,"10–12",technique="superset",note="Bi-set com stiff com barra."),
        ],"HIGH",90),
    ]
    return [
        program("female-november-abcd","abcd","Rotina de Treinamento Novembro","Avançado",5,"Feminino",
                "Quatro sessões: quadríceps, posteriores, tronco e glúteos. Faixas de séries preservadas nas observações.","Ficha feminina enviada",[
                    phase("november","Rotina ABCD","Pirâmide, rest-pause e nonstop",november,"1–5",common+" Descansos de 90 s são editáveis e não constam na ficha. Agenda base: A/B/descanso/C/D/descanso/descanso. A ficha também traz rotações de 5 e 6 dias; não são aplicadas automaticamente.")],
                "advanced","Revise as séries marcadas XXX e as variantes antes de aplicar. Cardio da ficha não foi convertido em prescrição automática.",audience_type="female"),
        program("female-advanced-7","abcdef","Avançado 7 Feminino","Avançado",8,"Feminino",
                "Seis sessões de especialização, seguindo as oito semanas indicadas na ficha; sétimo dia de descanso.","Ficha Avançado 7 enviada",[
                    phase("weeks-1-8","Semanas 1–8","Alto volume e drops",advanced,"1–8",common+" Descanso no dia 7. Algumas linhas têm divergência entre séries e repetições; leia as notas. Cardio condicionado a BF na ficha não é aplicado automaticamente.")],
                "expert","Volume muito alto e intervalos de até 10 s. Exige revisão profissional e confirmação das divergências; não é recomendação automática para todas as atletas.",audience_type="female"),
        program("female-shape-de-cavala","abcde","Treino Shape de Cavala","Avançado",0,"Feminino",
                "Cinco sessões de segunda a sexta: quadríceps, push, glúteos/posteriores, pull e legday.","Ficha Shape de Cavala enviada",[
                    phase("base","Semana de treino","Bi-sets, isometrias e progressão",cavala,"",common+" A ficha não define duração em semanas, RIR nem descanso; 90 s é apenas valor inicial editável. Séries da extensão de quadril estão ausentes e precisam de confirmação.")],
                "expert","Alto volume. Revise os campos incompletos, os bi-sets e a recuperação antes de aplicar.",audience_type="female"),
    ]
