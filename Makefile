.PHONY: run

run:
	@echo "Starting Odoo"
	python odoo/odoo-bin -c config/odoo.conf --dev xml -u blinds_sale