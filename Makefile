.PHONY: dev run test check clean db
.DEFAULT: help
-include .env

PYTHON=python3.11

help: ## Display this help message
	@echo "Please use \`make <target>\` where <target> is one of"
	@awk -F ':.*?## ' '/^[a-zA-Z]/ && NF==2 {printf "\033[36m  %-25s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

clean: ## Remove general artifact files
	find . -name '*.pyc' -delete
	find . -name '*.pyo' -delete
	find . -name '__pycache__' -type d | xargs rm -rf

run: ## Run the app
	uv run streamlit run src/main.py



