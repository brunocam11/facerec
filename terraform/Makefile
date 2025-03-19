.PHONY: init plan apply destroy fmt validate clean

init:
	terraform init

plan:
	terraform plan -out=tfplan

apply:
	terraform apply tfplan

destroy:
	terraform destroy

fmt:
	terraform fmt

validate:
	terraform validate

clean:
	rm -f tfplan
	rm -rf .terraform/

init-upgrade:
	terraform init -upgrade

all: fmt validate plan

# Create tfvars file from example if it doesn't exist
setup:
	@if [ ! -f terraform.tfvars ]; then \
		cp terraform.tfvars.example terraform.tfvars; \
		echo "Created terraform.tfvars from example. Please edit with your values."; \
	else \
		echo "terraform.tfvars already exists."; \
	fi

help:
	@echo "Available commands:"
	@echo "  make init         - Initialize Terraform"
	@echo "  make plan         - Create an execution plan"
	@echo "  make apply        - Apply the plan"
	@echo "  make destroy      - Destroy all resources"
	@echo "  make fmt          - Format Terraform files"
	@echo "  make validate     - Validate Terraform files"
	@echo "  make clean        - Clean up temporary files"
	@echo "  make init-upgrade - Initialize with plugin upgrades"
	@echo "  make all          - Format, validate, and plan"
	@echo "  make setup        - Create terraform.tfvars from example" 