# Small pixel Hello Kitty

Generated with the built-in image_gen tool, using the original idle, working,
and permission PNGs as edit references. Original assets remain available.

Generation prompt:

Edit references into a production game sprite atlas for the same Hello Kitty desktop pet, in crisp authentic low-resolution pixel art. Reference 1 is character identity and classic outfit, references 2/3 are mood reference only. Preserve white head, red bow on viewer right, black eyes and whiskers, yellow nose, no mouth, blue overalls yellow buttons. Use hard square pixels and stepped silhouettes, solid colors, very limited 12-color palette, no painterly smoothing, no shadows outside sprites. OUTPUT: exactly square PNG transparent background with a regular THREE columns by THREE rows grid, nine equal square cells, no gutters, no labels no text no borders. Each cell holds a single full-body pixel Hello Kitty centered horizontally, feet at 88% cell height, character about 66% cell height, entire silhouette and accessories inside its cell with ample transparent padding. Match character size consistently across all cells. State order row-major: row1 normal standing arms down; hover waving one paw; dragging paws raised surprised. Row2 working holding a tiny red apple; bored sitting sleepy eyes; permission holding a tiny magnifying glass with a red pixel question mark above. Row3 completed happy raised paws with two tiny yellow pixel sparkles; failed downcast with a tiny blue tear; closing side-facing walking away and waving. Render as if each character were originally hand-pixelled at 48x48 pixels then enlarged with nearest neighbor to cell size, crisp uniform square pixel grid. Asset must be actually alpha-transparent, not a checkerboard picture. Same adorable compact proportions as reference. No other characters.

Runtime uses explicit pose rectangles because the generated grid has unequal row
spacing. Each pose is rendered on a 64-pixel canvas with nearest-neighbor sampling,
gentle one-pixel motion, and a slide-away closing animation. Display size: 144.
