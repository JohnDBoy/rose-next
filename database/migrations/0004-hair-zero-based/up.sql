-- Hair ids are zero-based (2026-10-11).
--
-- Every hair style is a block of five LIST_HAIR rows -- the base hair, three
-- flattened "under a hat" variants and an empty "no hair" slot -- starting at
-- 0, 5, 10 ...; the client adds a cap's hair type (LIST_CAP col 33, 0..4) to the
-- character's hair id to pick the model under it. The world server refused hair 0
-- at creation, so our data had the first style shifted to rows 1-4 and creation
-- handed out hair 1. Under a type-4 cap (a wig: Dimple Bonnet and 90 others) that
-- resolved to row 5, the SECOND style's full hair, drawn through the wig.
--
-- scripts/fix-hair-block0.py moved style 1 to rows 0-3 (row 4 empty) and made
-- creation offer hair 0. Every existing hair-1 character is that same style, so
-- it becomes hair 0; 2-4 were never creatable. The column default follows.
UPDATE "character" SET "hair_id" = 0 WHERE "hair_id" = 1;

ALTER TABLE "character"
    ALTER COLUMN "hair_id" SET DEFAULT 0;
