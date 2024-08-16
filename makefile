build:
	rm -rf ./dist
	python -m build

upload:
	python3 -m twine upload --repository testpypi dist/*

publish: build upload
