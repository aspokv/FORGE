# FORGE exercise media coverage

Catalog snapshot: `backend/exercises.json` at FORGE commit `bdca68d1128f7f118c601deea6c63fd4269f68c1`.

Reference snapshot: `hasaneyldrm/exercises-dataset` commit `7455efae41b330c265e7cd4b78dfa848e7ce5ebd`.

| Classification | Count | Coverage |
| --- | ---: | ---: |
| Total FORGE exercises | 134 | 100% |
| Exact | 106 | 79.10% |
| Equivalent, pending human review | 13 | 9.70% |
| Unmatched | 15 | 11.19% |
| Total potential coverage | 119 | 88.81% |

Matches were reviewed using the exercise name and synonyms together with equipment, target muscle, movement pattern, and laterality. Name similarity alone was not accepted. The FORGE exercise ID remains the primary key.

## Equivalent matches requiring human review

| FORGE ID | FORGE exercise | Dataset ID | Dataset exercise | Review reason |
| --- | --- | --- | --- | --- |
| `row` | Remada apoiada no peito | `1350` | lever seated row | Machine geometry and chest support can vary. |
| `machine-chest-press` | Chest press máquina convergente | `0577` | lever chest press | Dataset does not identify a convergent machine. |
| `lat-prayer` | Puxador articulado / Pulldown | `0579` | lever front pulldown | Articulated handle path can vary by machine. |
| `db-ohp` | Desenvolvimento com halteres | `0405` | dumbbell seated shoulder press | FORGE does not specify seated versus standing. |
| `preacher-curl` | Rosca no banco Scott | `0592` | lever preacher curl | FORGE permits machine or dumbbell; dataset is a lever machine. |
| `bulgarian-split-squat` | Agachamento búlgaro | `0410` | dumbbell single leg split squat | Rear-foot elevation must be visually confirmed. |
| `machine-crunch` | Abdominal máquina | `1452` | lever seated crunch | Machine pad and linkage geometry can vary. |
| `rope-pushdown` | Tríceps corda V na polia | `0241` | cable triceps pushdown (v-bar) | FORGE naming mixes rope and V-bar attachments. |
| `nordic-curl` | Nordic curl assistido | `3235` | cable assisted inverse leg curl | Assistance mechanism differs from some Nordic setups. |
| `cable-woodchop` | Woodchop no cabo | `0862` | cable twist (up-down) | Rotation direction and cable path need visual confirmation. |
| `bb-upright-row` | Remada alta com barra W | `0120` | barbell upright row | Dataset uses a straight bar rather than an EZ/W bar. |
| `alternating-crunch` | Abdominal alto alternado | `0262` | cross body crunch | Alternating cadence and trunk rotation need confirmation. |
| `supinated-cable-row` | Remada baixa supinada | `0208` | cable reverse-grip straight back seated high row | Dataset record is a high-row variation. |

Equivalent entries are excluded by default by `ExerciseMedia`; enabling them requires an explicit `allowEquivalent` decision after human review.

## Unmatched exercises

| FORGE ID | FORGE exercise | Reason |
| --- | --- | --- |
| `cable-face-pull` | Face pull no cabo | No reliable face-pull execution exists in the dataset. |
| `hip-thrust` | Hip thrust barra | Dataset has floor glute bridges, not a reliable barbell hip thrust on bench. |
| `smith-hip-thrust` | Hip thrust Smith | No Smith-machine hip thrust is present. |
| `db-adductor-lunge` | Lunge lateral com halter | Available lateral lunge uses a barbell. |
| `side-lying-adduction` | Adução deitado lateral com halter | Available side-lying adduction is bodyweight. |
| `db-pullover-row` | Pullover combinado com halter | Combined pullover-row execution is absent. |
| `bayesian-curl` | Rosca Bayesian na polia | Generic one-arm cable curls do not preserve the shoulder-behind-body setup. |
| `single-leg-extension` | Cadeira extensora unilateral | Dataset has only bilateral machine leg extension. |
| `sumo-db-deadlift` | Terra sumô com halter | Dumbbell sumo pull-through is a different movement. |
| `reverse-hyper` | Hiperextensão reversa adaptada | Available versions use a machine or stability ball, not the FORGE bench adaptation. |
| `front-plank` | Prancha abdominal | No unweighted standard front plank record is available. |
| `four-point-kickback` | Glúteos em quatro apoios | No reliable bodyweight quadruped glute kickback exists. |
| `scissor-adduction` | Adução tesoura | Dataset scissor jump is a different movement. |
| `spider-curl` | Rosca spider | Available records use an EZ bar or reverse dumbbell grip. |
| `wrist-flexion-extension` | Flexão e extensão de punho | Dataset separates flexion and extension into different exercises. |

All unmatched exercises keep the current reviewed FORGE artwork.

## License gate

External thumbnails and GIFs are not enabled or copied into FORGE. The upstream `NOTICE.md` says the media is owned by Gym Visual and included in that repository under separate written permission; cloning the repository grants no media license to another project. The upstream `LICENSE` explicitly excludes `images/` and `videos/` from MIT.

`EXTERNAL_EXERCISE_MEDIA_ENABLED` therefore remains `false`. Production continues to render only current FORGE assets. Before changing that gate, FORGE must obtain its own written commercial-use permission from Gym Visual, preserve 180×180 resolution, retain attribution on every use, and complete human review of equivalent matches.
