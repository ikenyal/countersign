"""The same asymmetric gate, a different decision: may a coding agent merge this pull request alone?

Only the typed question, the options and the flags are new. The gate, the routing
and the way thresholds are measured come unchanged from countersign/gate.py.
"""

QUESTION = ("A coding agent wants to merge this pull request without a human review. "
            "May it merge alone, or must a human review it first?")
OPTIONS = {
    "merge": "Routine. Small, covered by passing tests, and touches nothing sensitive.",
    "security": "It touches authentication, permissions, secrets, encryption, or input that comes from users.",
    "public_contract": "It changes a public API, a file format, a CLI flag, or anything other teams or customers depend on.",
    "data": "It changes a database schema, migrates or deletes stored data, or changes how data is retained.",
    "unverified": "The tests do not cover the change, the tests fail, or the CI result is unknown.",
}
FLAGS = {
    "security": "Does this change touch authentication, permissions, secrets, encryption, or the handling of user input?",
    "public_contract": "Does this change alter something other teams or customers depend on, such as a public API, file format, or CLI flag?",
    "data": "Does this change alter a database schema, or migrate, delete, or change the retention of stored data?",
    "unverified": "Is the change not covered by passing tests, or is the CI result unknown or failing?",
}
REASONS = {
    "security": "it touches security-sensitive code",
    "public_contract": "it changes something others depend on",
    "data": "it changes stored data or its schema",
    "unverified": "it is not verified by passing tests",
}
