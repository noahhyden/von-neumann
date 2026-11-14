## Duplicate test basenames in modules/subsystems are intentional

Each submodule has its own test_distributions.py, so basenames repeat across tests/<submodule>/; pyproject sets --import-mode=importlib for that. Do not rename test files or add __init__.py to test dirs to fix the collision.
