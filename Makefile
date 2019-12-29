prepare:
	pip3 install --user -r requirements.txt -r requirements-dev.txt

test:
	pylint *.py

run:
	./run_me.sh
