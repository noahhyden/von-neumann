## Only exact-by-definition constants go in constants.toml

That table is for values fixed by definition (SI, IAU). A measured value carries an uncertainty and belongs in its module's `distributions.py`, not here as a bare float; each entry needs value, unit, source, basis and verdict, enforced by a test.
