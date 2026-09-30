##
# Makefile template trabajos (BibLaTeX + biber)
#

MAIN=main

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex referencias.bib
	pdflatex --shell-escape $(MAIN).tex
	biber $(MAIN)
	pdflatex --shell-escape $(MAIN).tex
	pdflatex --shell-escape $(MAIN).tex

clean:
	rm -f $(MAIN).aux $(MAIN).bbl $(MAIN).bcf $(MAIN).blg \
	      $(MAIN).log $(MAIN).out $(MAIN).run.xml $(MAIN).toc \
	      $(MAIN).pdf

cleanaux:
	rm -f $(MAIN).aux $(MAIN).bbl $(MAIN).bcf $(MAIN).blg \
	      $(MAIN).log $(MAIN).out $(MAIN).run.xml $(MAIN).toc
