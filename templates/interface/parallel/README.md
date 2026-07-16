# Parallel tests

Add tests that execute independent FVS cases concurrently.

Use the same cases and assertions as the synchronous suite. Configure the worker count explicitly, isolate every run's working directory and outputs, and compare each normalized result with its synchronous baseline.
