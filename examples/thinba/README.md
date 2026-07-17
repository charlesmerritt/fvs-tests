# thinba

This is the Southern (`SN`) variant `thinba` example used to qualify engine
adapters. It applies a thinning-from-below treatment in 2010 with a residual
basal-area target of 80.

The keyfile and fixed-width tree data were copied from
`~/projects/FVSjl/examples/legacy/` at FVSjl commit
`4afcf70c60d0086ecdb4383025c8a01f2eaad578`. Their latest source commit was
`faa0fccf2a3ea9aca3491ad2d3cd55fc2ffef35b`.

No expected database is declared yet. A baseline should be added only after its
engine, version, invocation, and provenance are recorded; until then this bundle
is a CLI smoke-test input rather than a numerical regression oracle.
