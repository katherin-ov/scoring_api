test:
	pytest

coverage:
    pytest tests/ --cov=scoring_api --cov-report=html --cov-fail-under=100


