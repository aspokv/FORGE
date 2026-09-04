# Reviewed exercise photographs

Replaces the six exercise thumbnails reported in the mobile screenshots with
individually generated and visually inspected photographs. These are identification
thumbnails, not movement animations. Generated with the built-in image generation
tool; exported from 1254px source images to 512px WebP at quality 92.

## Reviewed associations and generation briefs

Shared direction: realistic adult athlete, gray shirt, black shorts, dark gym,
neutral key light and amber rim light, full exercise and equipment visible,
square composition, no text or logos.

| Exact catalog ID | Required visible content |
| --- | --- |
| `rdl` | Barbell held near shins, hips pushed back, slight knee bend, both feet on floor. |
| `lying-leg-curl` | Prone on padded machine bench, knees flexed, roller behind lower legs. |
| `hip-thrust` | Upper back on bench, feet on floor, padded bar across hips. |
| `db-step-up` | Lead foot on a box, trailing foot below, one dumbbell per hand. |
| `abductor-machine` | Seated with knees apart and resistance pads outside knees. Rejected inner-pad and non-contact variants. |
| `seated-calf` | Seated, knees flexed, resistance pads above thighs, forefeet supported and heels raised. |

Files: `frontend/public/images/exercises/<id>-v1.webp`.
Total payload for the six images: 243272 bytes. Original atlas is unchanged.

## Scope and verification

- Six reported movements have exact-ID associations before the legacy atlas.
- Exact normalized name aliases apply only when no ID is provided.
- The other 128 catalog entries do not inherit these photographs. In particular,
  seated curl, Smith hip thrust, unilateral dumbbell RDL, adductor, standing calf,
  and leg-press calf cannot receive these six images through fuzzy matching.
- Reviewing the 134 resolver outputs exposed substring collisions in the legacy
  resolver (e.g. `leg curl` matched biceps and `hip thrust barra` matched `t bar`).
  The exact reviewed lookup bypasses those rules for these six exercises. This
  change does not certify the remaining legacy artwork as individually reviewed.
- Four UI suites: 27 tests passed. Production build passed with existing App.js
  hook warnings. Actual component rendered using production CSS in Edge/Chromium
  at 375x812, 412x915, and 360x740; six images decode at 512x512 and fully fit their
  containers, with no horizontal page overflow.
